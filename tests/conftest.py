"""Ajustes que valem para a suíte inteira."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

# O OpenCV abre um pool de threads por operação. Com a suíte rodando em
# paralelo, esses pools competem entre si e o resultado é lentidão e falha
# intermitente em máquina de poucos núcleos. Uma thread por processo deixa o
# paralelismo por conta do pytest, que é quem sabe quantos processos existem.
cv2.setNumThreads(1)


@pytest.fixture
def quadro_vazio() -> np.ndarray:
    """Imagem cinza uniforme, do tamanho padrão das cenas."""
    return np.full((360, 640, 3), 96, dtype=np.uint8)


@pytest.fixture
def gerador():
    """Fonte de aleatoriedade com semente fixa.

    Semente fixa em teste não é preciosismo: sem ela, uma falha que aparece uma
    vez a cada vinte execuções não pode ser reproduzida para ser corrigida.
    """
    return np.random.default_rng(20240101)
