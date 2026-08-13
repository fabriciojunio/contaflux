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
from dataclasses import dataclass, replace
from pathlib import Path

import cv2

from contaflux import __version__
from contaflux.cena import GeradorDeCena, ParametrosCena, veiculos_regulares
from contaflux.contagem import Linha
from contaflux.desenho import anotar, lado_a_lado
from contaflux.menu import escolher_video
from contaflux.perfis import PERFIS, obter
from contaflux.porte import FaixasDePorte
from contaflux.pipeline import ContadorDeFluxo
from contaflux.relatorio import Relatorio
from contaflux.selecao import escolher_linha, primeiro_quadro_util
from contaflux.deteccao_yolo import DetectorYolo, UltralyticsIndisponivel
from contaflux.sugestao import sugerir_linha
from contaflux.velocidade import Escala
from contaflux.video import FonteDeVideo, FonteIndisponivel

TECLA_SAIR = {ord('q'), ord('Q'), 27}
TECLA_PAUSA = {ord(' ')}

SEGUNDOS_DE_AQUECIMENTO = 5.0
"""Quanto de vídeo real é descartado para o fundo ser aprendido.

O número saiu de medida, num vídeo de rodovia de 50 quadros por segundo. Com
menos que isso, o modelo ainda não aprendeu a pista e produz uma rajada de
contagens fantasmas no começo: com 0,9 segundo apareceram 12 travessias nos 8
segundos seguintes, contra 2 quando o aquecimento subiu para 5 segundos. O
total caiu de 37 para 26 e parou de mudar, que é o sinal de que o excesso era
artefato e não veículo.

Cinco segundos batem com a janela de histórico do modelo, de 300 quadros, e é
por aí que a explicação fecha: antes disso ele simplesmente não viu a cena
vazia tempo suficiente.
"""

QUADROS_DE_OBSERVACAO = 400
"""Quantos quadros são olhados para deduzir onde fica a linha.

Precisa cobrir o aquecimento do modelo de fundo e ainda sobrar alguns segundos
de tráfego depois dele, senão a amostra vira ruído do próprio aquecimento."""

AQUECIMENTO_DA_DEMONSTRACAO = 45
"""A cena sintética tem fundo estático e converge quase de imediato.

Usar os mesmos 5 segundos aqui descartaria boa parte de uma demonstração curta
sem ganho nenhum, porque o problema que o aquecimento resolve, que é ruído de
sensor e compressão do vídeo real, não existe numa cena gerada.
"""


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

    A entrada é ajustada junto com a saída, e isso não é simetria por capricho.
    A primeira versão mexia só na saída, e no executável o menu passou a
    imprimir a lista e encerrar sem esperar resposta: a leitura do teclado
    devolvia fim de arquivo na primeira tentativa. Deixar as duas páginas de
    código em UTF-8 mantém entrada e saída no mesmo idioma e a leitura volta a
    funcionar.
    """
    if sys.platform != 'win32':
        return

    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass

    for fluxo in (sys.stdin, sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError, OSError):
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
        '--detector',
        default='auto',
        choices=('auto', 'yolo', 'movimento'),
        help=(
            'como achar os veículos. "yolo" reconhece o veículo e ignora nuvem, '
            'sombra e pedestre; "movimento" usa subtração de fundo e não precisa '
            'baixar nada. "auto" usa yolo se estiver instalado (padrão)'
        ),
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
        '--desenhar-linha',
        action='store_true',
        help='mostra o primeiro quadro para você marcar a linha com o mouse',
    )
    parser.add_argument(
        '--menu',
        action='store_true',
        help='lista os vídeos da pasta e deixa você escolher pelo número',
    )
    parser.add_argument(
        '--linha-fixa',
        action='store_true',
        help='usa a vertical do meio em vez de deduzir a linha pelo tráfego',
    )
    parser.add_argument(
        '--pasta',
        default='videos',
        help='onde o menu procura os vídeos (padrão: videos)',
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
        help='quadros descartados enquanto o fundo é aprendido (padrão: 5 segundos)',
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
    # O programa inteiro fala português, e quem for usar vai tentar --ajuda
    # antes de --help. Custa uma linha atender.
    parser.add_argument('--ajuda', action='help', help='mostra esta ajuda')
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

FPS_DA_DEMONSTRACAO = 25.0
"""Taxa da cena sintética, usada para dimensionar a folga inicial do vídeo gravado."""


def _cena_de_demonstracao(quantidade: int, inicio: int = 20) -> GeradorDeCena:
    """Cena sintética com duração ajustada à quantidade de veículos.

    A duração é calculada, e não fixa, porque uma demonstração com três carros
    numa cena de dezoito segundos passa a maior parte do tempo mostrando pista
    vazia. Ela é a soma do que o último veículo espera para entrar com o tempo
    de atravessar o quadro, mais uma folga.
    """
    entrada_do_ultimo = inicio + max(0, quantidade - 1) * INTERVALO_DA_DEMONSTRACAO
    quadros = max(200, entrada_do_ultimo + 160)

    parametros = ParametrosCena(quadros=quadros, semente=12, oscilacao_luz=0.03)
    parametros.veiculos = veiculos_regulares(
        quantidade,
        parametros,
        intervalo=INTERVALO_DA_DEMONSTRACAO,
        semente=12,
        inicio=inicio,
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

    sintetica: bool = False
    """Cena gerada precisa de bem menos aquecimento que vídeo real."""

    def aquecimento_padrao(self) -> int:
        if self.sintetica:
            return AQUECIMENTO_DA_DEMONSTRACAO
        return max(AQUECIMENTO_DA_DEMONSTRACAO, int(self.fps * SEGUNDOS_DE_AQUECIMENTO))


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
        return Entrada(
            cena.quadros(),
            p.largura,
            p.altura,
            p.fps,
            'demonstração',
            esperado,
            sintetica=True,
        )

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

    A cena gravada começa com pista vazia, o que a mostrada na tela não faz. É
    proposital: contado como arquivo comum, o vídeo perde os primeiros segundos
    no aquecimento do modelo de fundo, e sem essa folga os primeiros veículos
    passariam sem ser contados. O problema apareceu na integração contínua, com
    o vídeo gravado devolvendo 5 de 6.
    """
    cena = _cena_de_demonstracao(
        argumentos.demo_veiculos, inicio=int(FPS_DA_DEMONSTRACAO * SEGUNDOS_DE_AQUECIMENTO) + 20
    )
    destino = Path(argumentos.salvar_demo)
    destino.parent.mkdir(parents=True, exist_ok=True)
    cena.gravar(str(destino))

    esperado = cena.travessias_esperadas(cena.parametros.largura / 2)
    print(f'Vídeo gravado: {destino.resolve()}', file=saida)
    print(f'Ele tem {esperado} veículos cruzando o meio do quadro.', file=saida)
    print(f'Para contar: contaflux "{destino}"', file=saida)
    return destino


def montar_detector(escolha: str, perfil, saida=sys.stdout):
    """Cria o detector pedido, ou explica por que caiu no outro.

    "auto" prefere o reconhecimento porque é ele que distingue carro de nuvem,
    de contêiner e de pedestre. Sem o pacote instalado, cai na subtração de
    fundo em vez de falhar: ela conta bem em pista limpa e não precisa baixar
    nada, o que mantém a demonstração funcionando em qualquer máquina.
    """
    if escolha == 'movimento':
        return None

    try:
        detector = DetectorYolo()
    except UltralyticsIndisponivel as erro:
        if escolha == 'yolo':
            raise
        print(f'Detecção por reconhecimento indisponível, usando movimento.', file=saida)
        return None

    print('Detectando por reconhecimento de veículo (YOLO).', file=saida)
    return detector


class Cancelado(Exception):
    """A pessoa desistiu na tela de escolha. Não é erro."""


def _e_arquivo(fonte: str) -> bool:
    return fonte != 'demo' and not str(fonte).isdigit()


def _linha_sugerida(argumentos, largura: int, altura: int, perfil, saida):
    """Observa alguns segundos do vídeo e deduz onde a linha deve ficar.

    Só vale para arquivo: a observação consome quadros, e num arquivo dá para
    reabrir do começo e contar tudo depois. Numa câmera ao vivo esses segundos
    passariam sem ser contados.
    """
    if not _e_arquivo(argumentos.fonte):
        return None, None

    print('Observando o tráfego para posicionar a linha...', file=saida)
    try:
        with FonteDeVideo(argumentos.fonte, redimensionar_para=argumentos.largura) as fonte:
            linha, observacao = sugerir_linha(
                fonte.quadros(), largura, altura, perfil, QUADROS_DE_OBSERVACAO
            )
    except FonteIndisponivel:
        return None, None

    if linha is None:
        print(
            '  Não deu para deduzir: pouco movimento nos primeiros segundos. '
            'Usando uma vertical no meio do quadro.',
            file=saida,
        )
        return None, observacao

    print(
        f'  {observacao.total_de_alvos} veículos observados. '
        f'Linha em {linha.x1:.0f},{linha.y1:.0f} até {linha.x2:.0f},{linha.y2:.0f}.',
        file=saida,
    )
    print('  Para escolher outra:  --desenhar-linha  ou  --linha x1,y1,x2,y2', file=saida)
    return linha, observacao


def _ajustar_porte(perfil, observacao, saida):
    """Reancora as faixas de porte no tamanho que os veículos têm neste vídeo.

    Os limites do perfil são pixels absolutos, medidos numa cena de referência.
    Em vídeo real eles erram feio: num vídeo de câmera baixa, quinze dos vinte
    e três veículos saíram como caminhão, sendo quase todos carro. A área
    mediana observada dá a âncora certa para aquela câmera.
    """
    if observacao is None or observacao.area_tipica <= 0:
        return perfil

    faixas = FaixasDePorte.relativas(observacao.area_tipica)
    print(
        f'  Porte ancorado no veículo mediano deste vídeo '
        f'({observacao.area_tipica:.0f} pixels).',
        file=saida,
    )
    return replace(perfil, faixas=faixas)


def _definir_linha(argumentos, largura: int, altura: int, perfil, saida):
    """Devolve a linha e a observação do tráfego, quando houve uma."""
    if argumentos.linha:
        return analisar_linha(argumentos.linha, largura, altura), None

    if argumentos.desenhar_linha and argumentos.fonte != 'demo':
        quadro = primeiro_quadro_util(
            argumentos.fonte, pular=30, largura=argumentos.largura
        )
        if quadro is not None:
            print('Marque a linha de contagem com o mouse na janela que abriu.', file=saida)
            escolhida = escolher_linha(quadro)
            if escolhida is None:
                raise Cancelado('Escolha da linha cancelada.')
            print(
                f'Linha: {escolhida.x1:.0f},{escolhida.y1:.0f} até '
                f'{escolhida.x2:.0f},{escolhida.y2:.0f}',
                file=saida,
            )
            return escolhida, None

    if not argumentos.linha_fixa:
        sugerida, observacao = _linha_sugerida(argumentos, largura, altura, perfil, saida)
        if sugerida is not None:
            return sugerida, observacao

    return analisar_linha(None, largura, altura), None


def executar(argumentos, saida=sys.stdout) -> Relatorio:
    """Roda o processamento inteiro e devolve o relatório."""
    entrada = _preparar_entrada(argumentos, saida)
    quadros, largura, altura = entrada.quadros, entrada.largura, entrada.altura
    fps, rotulo, esperado = entrada.fps, entrada.rotulo, entrada.esperado
    perfil = obter(argumentos.perfil)
    linha, observacao = _definir_linha(argumentos, largura, altura, perfil, saida)
    perfil = _ajustar_porte(perfil, observacao, saida)

    escala = None
    if argumentos.metros:
        escala = Escala.de_largura(largura, argumentos.metros, fps)

    aquecimento = (
        argumentos.aquecimento
        if argumentos.aquecimento is not None
        else entrada.aquecimento_padrao()
    )

    detector = montar_detector(argumentos.detector, perfil, saida)
    if detector is not None:
        # O reconhecimento não aprende a cena, então não há o que aquecer.
        aquecimento = 0

    contador = ContadorDeFluxo(
        linha,
        perfil=perfil,
        escala=escala,
        fps=fps,
        detector=detector,
        quadros_de_aquecimento=aquecimento,
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

        if argumentos.menu:
            escolhido = escolher_video(argumentos.pasta)
            if escolhido is None:
                return 0
            argumentos.fonte = str(escolhido)

        executar(argumentos)
    except Cancelado:
        print('Cancelado.', file=sys.stderr)
        return 0
    except (FonteIndisponivel, ValueError) as erro:
        print(f'Erro: {erro}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('\nInterrompido.', file=sys.stderr)
        return 130
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
