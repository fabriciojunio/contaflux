"""Linha de comando do Contaflux.

Três usos, na ordem em que costumam ser necessários:

    contaflux                          demonstração, sem precisar de arquivo
    contaflux rodovia.mp4              conta um vídeo e mostra a janela
    contaflux 0                        conta ao vivo pela câmera

A demonstração existe porque a primeira coisa que alguém faz ao receber um
programa destes é rodá-lo, e exigir um vídeo de rodovia na mão antes de ver
qualquer coisa acontecer é um jeito ruim de começar.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2

from contaflux import __version__
from contaflux.cena import GeradorDeCena, ParametrosCena, veiculos_regulares
from contaflux.contagem import Linha
from contaflux.desenho import anotar, lado_a_lado
from contaflux.perfis import PERFIS, obter
from contaflux.pipeline import ContadorDeFluxo
from contaflux.relatorio import Relatorio
from contaflux.velocidade import Escala
from contaflux.video import FonteDeVideo, FonteIndisponivel

TECLA_SAIR = {ord('q'), ord('Q'), 27}
TECLA_PAUSA = {ord(' ')}


def preparar_console() -> None:
    """Faz o console do Windows aceitar acentos.

    O terminal do Windows abre numa página de código antiga, em que "ó" e "ã"
    saem como caracteres soltos. O programa inteiro escreve em português, então
    isso não é detalhe: o resumo final fica ilegível justo na hora em que
    alguém está lendo o resultado.

    São duas coisas: pedir ao console a página de código UTF-8 e pedir ao Python
    para escrever nela. Fora do Windows nada disso é necessário e a função não
    faz nada. Se qualquer das duas falhar, o programa segue com o texto
    estranho, que é bem melhor do que não rodar.
    """
    if sys.platform != 'win32':
        return

    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass

    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='contaflux',
        description='Conta veículos que cruzam uma linha em vídeo de câmera fixa.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'exemplos:\n'
            '  contaflux                              roda a demonstração\n'
            '  contaflux rodovia.mp4                  conta um arquivo\n'
            '  contaflux 0 --perfil urbano            conta pela câmera 0\n'
            '  contaflux via.mp4 --sem-janela --csv saida.csv\n'
            '  contaflux via.mp4 --metros 30          estima velocidade\n'
        ),
    )
    parser.add_argument(
        'fonte',
        nargs='?',
        default='demo',
        help='caminho do vídeo, índice da câmera ou "demo" (padrão: demo)',
    )
    parser.add_argument(
        '--perfil',
        default='rodovia',
        choices=sorted(PERFIS),
        help='calibração da cena (padrão: rodovia)',
    )
    parser.add_argument(
        '--linha',
        help='linha de contagem como x1,y1,x2,y2. Sem isso, uma vertical no meio.',
    )
    parser.add_argument(
        '--metros',
        type=float,
        help='quantos metros de via cabem na largura do quadro; liga a velocidade',
    )
    parser.add_argument('--csv', help='grava as passagens em CSV')
    parser.add_argument('--json', dest='json_saida', help='grava o relatório em JSON')
    parser.add_argument('--gravar', help='grava o vídeo anotado neste caminho')
    parser.add_argument(
        '--largura',
        type=int,
        default=960,
        help='reduz o vídeo para esta largura antes de processar (padrão: 960)',
    )
    parser.add_argument(
        '--aquecimento',
        type=int,
        default=45,
        help='quadros descartados enquanto o fundo é aprendido (padrão: 45)',
    )
    parser.add_argument(
        '--mascara', action='store_true', help='mostra a máscara de movimento ao lado'
    )
    parser.add_argument(
        '--sem-janela',
        action='store_true',
        help='processa sem abrir janela, para servidor ou lote',
    )
    parser.add_argument(
        '--demo-veiculos',
        type=int,
        default=12,
        help='quantos veículos a demonstração gera (padrão: 12)',
    )
    parser.add_argument(
        '--salvar-demo',
        help='grava a cena da demonstração como vídeo e encerra, sem contar nada',
    )
    parser.add_argument('--versao', action='version', version=f'contaflux {__version__}')
    return parser


def analisar_linha(texto: str | None, largura: int, altura: int) -> Linha:
    """Interpreta o argumento de linha, ou devolve uma vertical no meio da cena.

    O padrão é uma vertical, e não uma horizontal, porque a maioria das câmeras
    de via filma o trânsito passando de lado. Quem tiver uma câmera de cima
    passa a linha na mão.
    """
    if not texto:
        return Linha(largura / 2, altura * 0.15, largura / 2, altura * 0.95)

    partes = texto.replace(';', ',').split(',')
    if len(partes) != 4:
        raise ValueError(
            f'A linha precisa de quatro números no formato x1,y1,x2,y2. Recebido: {texto!r}'
        )
    try:
        x1, y1, x2, y2 = (float(p.strip()) for p in partes)
    except ValueError as erro:
        raise ValueError(f'Coordenada inválida em {texto!r}.') from erro

    if (x1, y1) == (x2, y2):
        raise ValueError('Os dois pontos da linha não podem ser iguais.')
    return Linha(x1, y1, x2, y2)


INTERVALO_DA_DEMONSTRACAO = 26
"""Quadros entre a entrada de um veículo e a do seguinte."""


def _cena_de_demonstracao(quantidade: int) -> GeradorDeCena:
    """Cena sintética com duração ajustada à quantidade de veículos.

    A duração é calculada, e não fixa, porque uma demonstração com três carros
    numa cena de dezoito segundos passa a maior parte do tempo mostrando pista
    vazia. Ela é a soma do que o último veículo espera para entrar com o tempo
    de atravessar o quadro, mais uma folga.
    """
    entrada_do_ultimo = 20 + max(0, quantidade - 1) * INTERVALO_DA_DEMONSTRACAO
    quadros = max(200, entrada_do_ultimo + 160)

    parametros = ParametrosCena(quadros=quadros, semente=12, oscilacao_luz=0.03)
    parametros.veiculos = veiculos_regulares(
        quantidade, parametros, intervalo=INTERVALO_DA_DEMONSTRACAO, semente=12
    )
    return GeradorDeCena(parametros)


@dataclass
class Entrada:
    """De onde vêm os quadros e o que se sabe sobre eles."""

    quadros: object
    largura: int
    altura: int
    fps: float
    rotulo: str
    esperado: int | None = None
    """Gabarito, que só existe na demonstração. Permite conferir na hora."""

    fonte: FonteDeVideo | None = None
    """Guardado para poder ser liberado no fim. Câmera que não é liberada fica
    ocupada até o processo morrer, e o próximo programa não consegue abri-la."""


def _preparar_entrada(argumentos, saida) -> Entrada:
    if argumentos.fonte == 'demo':
        cena = _cena_de_demonstracao(argumentos.demo_veiculos)
        p = cena.parametros
        esperado = cena.travessias_esperadas(p.largura / 2)
        print(
            f'Demonstração: cena sintética com {len(p.veiculos)} veículos, '
            f'{esperado} deles cruzando a linha.',
            file=saida,
        )
        return Entrada(cena.quadros(), p.largura, p.altura, p.fps, 'demonstração', esperado)

    fonte = FonteDeVideo(argumentos.fonte, redimensionar_para=argumentos.largura)
    info = fonte.info

    if fonte.backend != 'arquivo':
        print(f'Câmera {argumentos.fonte} aberta via {fonte.backend}.', file=saida)
        print('Deixe a cena vazia por alguns segundos, para o fundo ser aprendido.', file=saida)
    else:
        duracao = info.total_de_quadros / info.fps if info.fps else 0
        print(
            f'{argumentos.fonte}: {info.largura}x{info.altura}, '
            f'{info.fps:.0f} quadros por segundo, {duracao:.0f} segundos.',
            file=saida,
        )

    return Entrada(
        fonte.quadros(),
        info.largura,
        info.altura,
        info.fps,
        str(argumentos.fonte),
        None,
        fonte,
    )


def salvar_cena_de_demonstracao(argumentos, saida=sys.stdout) -> Path:
    """Grava a cena sintética como arquivo de vídeo.

    Serve para exercitar o caminho de arquivo sem precisar filmar uma rodovia:
    grava, e em seguida `contaflux o_arquivo.mp4` conta em cima dele.
    """
    cena = _cena_de_demonstracao(argumentos.demo_veiculos)
    destino = Path(argumentos.salvar_demo)
    destino.parent.mkdir(parents=True, exist_ok=True)
    cena.gravar(str(destino))

    esperado = cena.travessias_esperadas(cena.parametros.largura / 2)
    print(f'Vídeo gravado: {destino.resolve()}', file=saida)
    print(f'Ele tem {esperado} veículos cruzando o meio do quadro.', file=saida)
    print(f'Para contar: contaflux "{destino}"', file=saida)
    return destino


def executar(argumentos, saida=sys.stdout) -> Relatorio:
    """Roda o processamento inteiro e devolve o relatório."""
    entrada = _preparar_entrada(argumentos, saida)
    quadros, largura, altura = entrada.quadros, entrada.largura, entrada.altura
    fps, rotulo, esperado = entrada.fps, entrada.rotulo, entrada.esperado
    linha = analisar_linha(argumentos.linha, largura, altura)
    perfil = obter(argumentos.perfil)

    escala = None
    if argumentos.metros:
        escala = Escala.de_largura(largura, argumentos.metros, fps)

    contador = ContadorDeFluxo(
        linha,
        perfil=perfil,
        escala=escala,
        quadros_de_aquecimento=argumentos.aquecimento,
    )

    mostrar = not argumentos.sem_janela
    escritor = None
    janela = 'Contaflux'
    pausado = False

    try:
        for quadro in quadros:
            estado = contador.processar(quadro)

            precisa_desenhar = mostrar or argumentos.gravar
            if precisa_desenhar:
                extras = []
                if estado.aquecendo:
                    extras.append('aprendendo o fundo...')
                elif escala is not None and contador.velocidade_media is not None:
                    extras.append(f'média: {contador.velocidade_media:.0f} km/h')

                imagem = anotar(
                    quadro,
                    linha,
                    estado.alvos,
                    estado.contagem,
                    rotulos=contador.rotulos(estado.alvos),
                    rotulo_positivo=perfil.rotulo_positivo,
                    rotulo_negativo=perfil.rotulo_negativo,
                    extras=extras,
                )
                if argumentos.mascara:
                    imagem = lado_a_lado(imagem, estado.mascara)

                if argumentos.gravar:
                    if escritor is None:
                        escritor = cv2.VideoWriter(
                            argumentos.gravar,
                            cv2.VideoWriter_fourcc(*'mp4v'),
                            fps,
                            (imagem.shape[1], imagem.shape[0]),
                        )
                        if not escritor.isOpened():
                            raise FonteIndisponivel(
                                f'Não foi possível gravar em: {argumentos.gravar}'
                            )
                    escritor.write(imagem)

                if mostrar:
                    cv2.imshow(janela, imagem)
                    espera = 0 if pausado else max(1, int(1000 / fps))
                    tecla = cv2.waitKey(espera) & 0xFF
                    if tecla in TECLA_SAIR:
                        break
                    if tecla in TECLA_PAUSA:
                        pausado = not pausado
    finally:
        if escritor is not None:
            escritor.release()
        if entrada.fonte is not None:
            entrada.fonte.liberar()
        if mostrar:
            cv2.destroyAllWindows()

    relatorio = contador.relatorio(rotulo)

    print('', file=saida)
    print(relatorio.resumo(), file=saida)
    if esperado is not None:
        acerto = 'exato' if relatorio.total == esperado else f'esperado {esperado}'
        print(f'Conferência com o gabarito da cena: {acerto}', file=saida)

    if argumentos.csv:
        print(f'CSV: {relatorio.salvar_csv(argumentos.csv)}', file=saida)
    if argumentos.json_saida:
        print(f'JSON: {relatorio.salvar_json(argumentos.json_saida)}', file=saida)
    if argumentos.gravar:
        print(f'Vídeo anotado: {Path(argumentos.gravar).resolve()}', file=saida)

    return relatorio


def main(argv: list[str] | None = None) -> int:
    preparar_console()
    parser = construir_parser()
    argumentos = parser.parse_args(argv)

    try:
        if argumentos.salvar_demo:
            salvar_cena_de_demonstracao(argumentos)
            return 0
        executar(argumentos)
    except (FonteIndisponivel, ValueError) as erro:
        print(f'Erro: {erro}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('\nInterrompido.', file=sys.stderr)
        return 130
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
