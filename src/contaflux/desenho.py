"""Desenhar o que o sistema entendeu, por cima do quadro.

Serve para duas coisas ao mesmo tempo, e é por isso que vale ter um módulo só
para ela. Para quem assiste, é a demonstração. Para quem desenvolve, é o
depurador: quase todo erro deste sistema é visível na tela antes de aparecer no
número, seja a caixa que engloba dois carros de uma vez, seja o identificador
que troca no meio da travessia.
"""

from __future__ import annotations

import cv2
import numpy as np

from contaflux.contagem import Contagem, Linha
from contaflux.rastreio import Alvo

VERDE = (80, 220, 100)
AMARELO = (60, 200, 240)
BRANCO = (245, 245, 245)
PRETO = (20, 20, 20)
VERMELHO = (80, 80, 235)
FONTE = cv2.FONT_HERSHEY_SIMPLEX


def _texto_com_fundo(
    imagem: np.ndarray,
    texto: str,
    posicao: tuple[int, int],
    escala: float = 0.5,
    cor: tuple[int, int, int] = BRANCO,
) -> None:
    """Texto sobre tarja escura.

    Sem a tarja, o texto some quando passa por cima de um carro claro, que é
    justamente o momento em que alguém está olhando para ele.
    """
    (largura, altura), base = cv2.getTextSize(texto, FONTE, escala, 1)
    x, y = posicao
    cv2.rectangle(imagem, (x - 3, y - altura - 4), (x + largura + 3, y + base), PRETO, -1)
    cv2.putText(imagem, texto, (x, y), FONTE, escala, cor, 1, cv2.LINE_AA)


def desenhar_linha(imagem: np.ndarray, linha: Linha) -> None:
    """A linha de contagem, com as pontas marcadas."""
    p1 = (int(linha.x1), int(linha.y1))
    p2 = (int(linha.x2), int(linha.y2))
    cv2.line(imagem, p1, p2, AMARELO, 2, cv2.LINE_AA)
    cv2.circle(imagem, p1, 4, AMARELO, -1)
    cv2.circle(imagem, p2, 4, AMARELO, -1)


def desenhar_alvos(
    imagem: np.ndarray,
    alvos: dict[int, Alvo],
    rotulos: dict[int, str] | None = None,
    trajetoria: bool = True,
) -> None:
    """Caixa, identificador e rastro de cada objeto acompanhado."""
    rotulos = rotulos or {}
    for identificador, alvo in alvos.items():
        x, y, largura, altura = alvo.caixa
        cor = VERMELHO if alvo.contado else VERDE
        cv2.rectangle(imagem, (x, y), (x + largura, y + altura), cor, 2)

        etiqueta = rotulos.get(identificador) or f'#{identificador}'
        _texto_com_fundo(imagem, etiqueta, (x, max(14, y - 6)), 0.45, cor)

        if trajetoria and len(alvo.trajetoria) > 1:
            pontos = np.array(alvo.trajetoria, dtype=np.int32).reshape(-1, 1, 2)
            cv2.polylines(imagem, [pontos], False, cor, 1, cv2.LINE_AA)


def desenhar_painel(
    imagem: np.ndarray,
    contagem: Contagem,
    rotulo_positivo: str = 'sentido A',
    rotulo_negativo: str = 'sentido B',
    extras: list[str] | None = None,
) -> None:
    """Placar no canto superior esquerdo."""
    linhas = [
        f'total: {contagem.total}',
        f'{rotulo_positivo}: {contagem.entradas}',
        f'{rotulo_negativo}: {contagem.saidas}',
    ]
    linhas.extend(extras or [])

    for i, texto in enumerate(linhas):
        _texto_com_fundo(imagem, texto, (12, 26 + i * 22), 0.58)


def anotar(
    quadro: np.ndarray,
    linha: Linha,
    alvos: dict[int, Alvo],
    contagem: Contagem,
    rotulos: dict[int, str] | None = None,
    rotulo_positivo: str = 'sentido A',
    rotulo_negativo: str = 'sentido B',
    extras: list[str] | None = None,
) -> np.ndarray:
    """Quadro anotado. Não altera o original."""
    imagem = quadro.copy()
    desenhar_linha(imagem, linha)
    desenhar_alvos(imagem, alvos, rotulos)
    desenhar_painel(imagem, contagem, rotulo_positivo, rotulo_negativo, extras)
    return imagem


def lado_a_lado(quadro: np.ndarray, mascara: np.ndarray) -> np.ndarray:
    """Junta o quadro anotado e a máscara de movimento numa imagem só.

    É a visão que mais ajuda a entender por que a contagem errou: quase sempre
    a resposta está na máscara, seja porque o objeto não apareceu nela, seja
    porque apareceu grudado no vizinho.
    """
    if mascara.ndim == 2:
        mascara = cv2.cvtColor(mascara, cv2.COLOR_GRAY2BGR)
    if mascara.shape[:2] != quadro.shape[:2]:
        mascara = cv2.resize(mascara, (quadro.shape[1], quadro.shape[0]))
    return np.hstack([quadro, mascara])
