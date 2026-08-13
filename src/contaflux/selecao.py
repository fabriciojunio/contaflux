"""Escolher o vídeo e desenhar a linha de contagem com o mouse.

É a parte que faz o programa servir para qualquer vídeo em vez de só para os
que alguém já calibrou. Cada câmera enquadra a via de um jeito: numa a linha
precisa ser vertical, na outra horizontal, e numa terceira diagonal
acompanhando a curva. Pedir quatro números em pixels para quem vai só assistir
à demonstração não funciona, e chutar por padrão erra na maioria dos vídeos.

Aqui a pessoa vê o primeiro quadro, clica em dois pontos e pronto.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from contaflux.contagem import Linha
from contaflux.desenho import AMARELO, BRANCO, FONTE, PRETO

EXTENSOES = ('.mp4', '.avi', '.mkv', '.mov', '.webm', '.m4v')

TECLA_CONFIRMAR = {13, 32}
TECLA_CANCELAR = {27, ord('q'), ord('Q')}
TECLA_LIMPAR = {ord('r'), ord('R')}


def listar_videos(pasta: str | Path) -> list[Path]:
    """Vídeos da pasta, em ordem alfabética.

    Ordem alfabética, e não a do sistema de arquivos, porque o número que a
    pessoa digita no menu precisa corresponder ao mesmo vídeo em qualquer
    máquina. A ordem do sistema de arquivos varia entre Windows e Linux, e um
    tutorial que diz "digite 3" quebraria.
    """
    caminho = Path(pasta)
    if not caminho.is_dir():
        return []
    encontrados = [
        arquivo
        for arquivo in caminho.iterdir()
        if arquivo.is_file() and arquivo.suffix.lower() in EXTENSOES
    ]
    return sorted(encontrados, key=lambda a: a.name.lower())


def descrever(video: Path) -> str:
    """Nome, resolução e duração, para o menu dizer algo além do arquivo."""
    captura = cv2.VideoCapture(str(video))
    if not captura.isOpened():
        captura.release()
        return f'{video.name}  (não foi possível abrir)'

    largura = int(captura.get(cv2.CAP_PROP_FRAME_WIDTH))
    altura = int(captura.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = captura.get(cv2.CAP_PROP_FPS) or 0
    total = int(captura.get(cv2.CAP_PROP_FRAME_COUNT))
    captura.release()

    duracao = total / fps if fps else 0
    return f'{video.name}  ({largura}x{altura}, {duracao:.0f}s)'


@dataclass
class EstadoDoDesenho:
    """Pontos clicados até agora, e o ponto sob o cursor."""

    pontos: list[tuple[int, int]] = field(default_factory=list)
    cursor: tuple[int, int] | None = None

    def clicar(self, x: int, y: int) -> None:
        if len(self.pontos) >= 2:
            self.pontos.clear()
        self.pontos.append((x, y))

    def limpar(self) -> None:
        self.pontos.clear()

    @property
    def completo(self) -> bool:
        return len(self.pontos) == 2

    def como_linha(self) -> Linha | None:
        if not self.completo:
            return None
        (x1, y1), (x2, y2) = self.pontos
        if (x1, y1) == (x2, y2):
            return None
        return Linha(float(x1), float(y1), float(x2), float(y2))


def _instrucoes(imagem: np.ndarray, estado: EstadoDoDesenho) -> None:
    if estado.completo:
        texto = 'ENTER conta  |  R refaz  |  ESC cancela'
    elif estado.pontos:
        texto = 'clique no outro lado da via'
    else:
        texto = 'clique de um lado da via, atravessando as faixas'

    (largura, altura), base = cv2.getTextSize(texto, FONTE, 0.6, 1)
    cv2.rectangle(imagem, (8, 8), (16 + largura, 20 + altura + base), PRETO, -1)
    cv2.putText(imagem, texto, (12, 16 + altura), FONTE, 0.6, BRANCO, 1, cv2.LINE_AA)


def desenhar_previa(quadro: np.ndarray, estado: EstadoDoDesenho) -> np.ndarray:
    """Quadro com a linha em construção por cima. Não altera o original."""
    imagem = quadro.copy()

    for ponto in estado.pontos:
        cv2.circle(imagem, ponto, 5, AMARELO, -1)

    if estado.completo:
        cv2.line(imagem, estado.pontos[0], estado.pontos[1], AMARELO, 2, cv2.LINE_AA)
    elif estado.pontos and estado.cursor:
        # A linha acompanhando o cursor evita o vaivém de clicar, ver que
        # ficou torta e ter que recomeçar.
        cv2.line(imagem, estado.pontos[0], estado.cursor, AMARELO, 1, cv2.LINE_AA)

    _instrucoes(imagem, estado)
    return imagem


def escolher_linha(quadro: np.ndarray, titulo: str = 'Contaflux') -> Linha | None:
    """Abre o quadro e devolve a linha desenhada, ou None se cancelada."""
    estado = EstadoDoDesenho()
    janela = f'{titulo} - onde fica a linha de contagem'

    def ao_mexer_o_mouse(evento, x, y, _flags, _param):
        if evento == cv2.EVENT_LBUTTONDOWN:
            estado.clicar(x, y)
        elif evento == cv2.EVENT_MOUSEMOVE:
            estado.cursor = (x, y)

    cv2.namedWindow(janela, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(janela, ao_mexer_o_mouse)

    try:
        while True:
            cv2.imshow(janela, desenhar_previa(quadro, estado))
            tecla = cv2.waitKey(20) & 0xFF

            if tecla in TECLA_CANCELAR:
                return None
            if tecla in TECLA_LIMPAR:
                estado.limpar()
            if tecla in TECLA_CONFIRMAR and estado.completo:
                return estado.como_linha()
    finally:
        cv2.destroyWindow(janela)


def primeiro_quadro_util(caminho: str | Path, pular: int = 0, largura: int | None = 960):
    """Um quadro do vídeo para servir de fundo ao desenho da linha.

    Pular alguns quadros ajuda: muitos vídeos começam com fade ou com a cena
    ainda vazia, e é mais fácil posicionar a linha vendo carro na pista.
    """
    captura = cv2.VideoCapture(str(caminho))
    if not captura.isOpened():
        captura.release()
        return None

    quadro = None
    for indice in range(pular + 1):
        ok, lido = captura.read()
        if not ok:
            break
        quadro = lido
    captura.release()

    if quadro is None:
        return None

    if largura and quadro.shape[1] > largura:
        escala = largura / quadro.shape[1]
        novo = (largura, int(round(quadro.shape[0] * escala)))
        quadro = cv2.resize(quadro, novo, interpolation=cv2.INTER_AREA)

    return quadro
