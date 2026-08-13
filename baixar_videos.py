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


# A coleção é variada de propósito: pista de mão dupla, via expressa vista de
# cima, cruzamento urbano, câmera de frente e câmera de lado. Um contador que
# só funciona num enquadramento não serve de nada, e é justamente a variedade
# que mostra onde o método se sustenta e onde ele sofre.
COLECAO = (
    VideoDeExemplo(
        '01-rodovia-de-frente',
        '2016/01/11/1900-151662242_large.mp4',
        'pista dupla, câmera baixa, veículos vindo de frente. Conta 23 em 60 s',
    ),
    VideoDeExemplo(
        '02-rodovia-lateral',
        '2018/09/04/18083-288452975_large.mp4',
        'pista vista de longe, veículos pequenos na imagem. Conta 21',
    ),
    VideoDeExemplo(
        '03-trafego-urbano',
        '2020/10/28/53583-475000652_large.mp4',
        'ponte vista de cima, dois sentidos separados. Conta 8',
    ),
    VideoDeExemplo(
        '04-estrada-aberta',
        '2019/05/01/23232-333604632_large.mp4',
        'viaduto largo, fluxo constante. Conta 32, o mais movimentado',
    ),
    VideoDeExemplo(
        '05-rua-de-cidade',
        '2020/09/19/50299-460295794_large.mp4',
        'rua com carros parados dos dois lados, que o fundo aprende. Conta 8',
    ),
    VideoDeExemplo(
        '06-viaduto',
        '2022/03/05/109756-685086367_large.mp4',
        'vista aérea alta: os veículos ficam pequenos e poucos são vistos. Conta 2',
    ),
    VideoDeExemplo(
        '07-avenida-larga',
        '2020/08/29/48504-454713939_large.mp4',
        'avenida larga com muito movimento na calçada. Conta 89, provavelmente demais',
    ),
    VideoDeExemplo(
        '08-via-movimentada',
        '2019/05/15/23712-337108764_large.mp4',
        'trânsito denso visto de cima, veículos grandes na imagem. Conta 68',
    ),
    VideoDeExemplo(
        '09-rua-comercial',
        '2019/08/06/25816-352978422_large.mp4',
        'rua de comércio, veículos lentos e pedestres na calçada. Conta 7',
    ),
    VideoDeExemplo(
        '10-rotatoria',
        '2021/05/27/75457-556022183_large.mp4',
        'rotatória vista de cima, trajetória curva. Conta 9',
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
