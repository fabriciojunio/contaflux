"""Baixa os vídeos de rodovia usados na demonstração.

    python baixar_videos.py

Os vídeos não ficam no repositório de propósito. São dezenas de megabytes cada,
e versionar arquivo binário grande incha o histórico para sempre: quem clonar
depois baixa tudo de novo mesmo que os vídeos já tenham sido trocados. Com o
baixador, o repositório continua leve e cada pessoa pega os arquivos uma vez.

Todos vêm do Pixabay, sob a licença de conteúdo deles, que permite uso livre
inclusive comercial e sem exigir atribuição. A origem de cada um está na lista
abaixo, para poder ser conferida.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

PASTA = Path(__file__).parent / 'videos'
BASE = 'https://cdn.pixabay.com/video/'

TEMPO_LIMITE = 120
BLOCO = 1 << 16


@dataclass(frozen=True)
class VideoDeExemplo:
    """Um vídeo da coleção de demonstração."""

    nome: str
    caminho_remoto: str
    descricao: str

    @property
    def url(self) -> str:
        return BASE + self.caminho_remoto

    @property
    def destino(self) -> Path:
        return PASTA / f'{self.nome}.mp4'


# Cinco vídeos, escolhidos olhando a tela e não os números: as caixas de
# detecção têm que cair em cima dos veículos, e em mais nada.
#
# Dois deles, o 04 e o 05, entraram de propósito com prédio, árvore e cidade no
# quadro. Eles não passariam na versão anterior do detector, que marcava
# qualquer coisa em movimento e enchia a tela de caixa em nuvem e em vegetação.
# Com o reconhecimento de veículo eles funcionam, e é justamente isso que
# mostram.
#
# O que continua reprovando um vídeo é o veículo ficar pequeno demais na
# imagem: filmagem aérea alta e tomada muito distante rendem carro com poucos
# pixels, e o modelo não reconhece o que mal dá para ver. Filmagem de drone e
# dashcam também estão fora, porque a contagem por linha pressupõe câmera fixa.
COLECAO = (
    VideoDeExemplo(
        '01-rodovia-de-frente',
        '2016/01/11/1900-151662242_large.mp4',
        'pista dupla, veículos vindo de frente e bem próximos. O melhor da coleção',
    ),
    VideoDeExemplo(
        '02-rua-de-cidade',
        '2020/09/19/50299-460295794_large.mp4',
        'rua com carros parados dos dois lados e trânsito passando no meio',
    ),
    VideoDeExemplo(
        '03-via-movimentada',
        '2019/05/15/23712-337108764_large.mp4',
        'trânsito denso visto de passarela, muitos veículos ao mesmo tempo',
    ),
    VideoDeExemplo(
        '04-rua-com-arvores',
        '2019/10/25/28293-369325244_large.mp4',
        'rua arborizada com prédios, para mostrar que o entorno não atrapalha',
    ),
    VideoDeExemplo(
        '05-rodovia-urbana',
        '2020/07/04/43849-437611813_large.mp4',
        'rodovia larga com a cidade ao fundo, várias faixas no mesmo sentido',
    ),
)


def _formatar(bytes_baixados: int) -> str:
    return f'{bytes_baixados / 1_000_000:.1f} MB'


def baixar(video: VideoDeExemplo, forcar: bool = False) -> tuple[bool, str]:
    """Baixa um vídeo. Devolve (deu certo, mensagem)."""
    if video.destino.exists() and not forcar:
        return True, f'já existe ({_formatar(video.destino.stat().st_size)})'

    PASTA.mkdir(parents=True, exist_ok=True)
    # O arquivo é escrito com outro nome e só renomeado no fim. Assim, um
    # download interrompido no meio não deixa para trás um vídeo truncado que
    # a próxima execução consideraria pronto.
    parcial = video.destino.with_suffix('.parcial')

    try:
        pedido = urllib.request.Request(video.url, headers={'User-Agent': 'contaflux'})
        with urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE) as resposta:
            with parcial.open('wb') as arquivo:
                total = 0
                while True:
                    pedaco = resposta.read(BLOCO)
                    if not pedaco:
                        break
                    arquivo.write(pedaco)
                    total += len(pedaco)
    except (urllib.error.URLError, OSError, TimeoutError) as erro:
        parcial.unlink(missing_ok=True)
        return False, f'falhou: {erro}'

    if total < 100_000:
        parcial.unlink(missing_ok=True)
        return False, 'falhou: o arquivo veio pequeno demais para ser um vídeo'

    parcial.replace(video.destino)
    return True, f'baixado ({_formatar(total)})'


def baixar_colecao(forcar: bool = False, saida=sys.stdout) -> int:
    """Baixa a coleção inteira. Devolve quantos falharam."""
    print(f'Baixando {len(COLECAO)} vídeos para {PASTA}\n', file=saida)

    falhas = 0
    for indice, video in enumerate(COLECAO, start=1):
        print(f'[{indice:2d}/{len(COLECAO)}] {video.nome} ... ', end='', flush=True, file=saida)
        ok, mensagem = baixar(video, forcar)
        print(mensagem, file=saida)
        if not ok:
            falhas += 1

    print('', file=saida)
    if falhas:
        print(
            f'{falhas} de {len(COLECAO)} não vieram. Rode de novo para tentar só '
            'os que faltam, ou use seus próprios vídeos na pasta.',
            file=saida,
        )
    else:
        print('Todos prontos. Agora rode:  python -m contaflux --menu', file=saida)

    return falhas


if __name__ == '__main__':
    raise SystemExit(1 if baixar_colecao('--forcar' in sys.argv) else 0)
