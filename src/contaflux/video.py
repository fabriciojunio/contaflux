"""Ler quadros de arquivo ou de câmera.

Separado do resto porque é a única parte que conversa com o mundo. Todo o
restante do sistema recebe imagens já prontas e não sabe de onde vieram, o que
torna possível testar a contagem inteira sem nenhum arquivo de vídeo.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


class FonteIndisponivel(RuntimeError):
    """A câmera ou o arquivo não pôde ser aberto."""


# Ordem de tentativa para abrir câmera no Windows. Não é preciosismo: o
# Media Foundation é o padrão do OpenCV e falha em boa parte das webcams com
# `MF_E_HW_MFT_FAILED_START_STREAMING`, abrindo o dispositivo, acendendo a luz
# e não entregando quadro nenhum. O DirectShow é mais velho e funciona nessas
# câmeras. Fora do Windows, o padrão do sistema resolve.
BACKENDS_DE_CAMERA = (
    ('Media Foundation', cv2.CAP_MSMF),
    ('DirectShow', cv2.CAP_DSHOW),
    ('padrão do sistema', cv2.CAP_ANY),
)


def _abrir_camera(indice: int) -> tuple[cv2.VideoCapture, str]:
    """Tenta cada backend e devolve o primeiro que entregar um quadro de verdade.

    Conferir `isOpened()` não basta, e essa é a parte que custa descobrir: a
    câmera pode abrir, reportar sucesso e nunca devolver imagem. Só a leitura de
    um quadro prova que ela está funcionando.
    """
    tentativas = BACKENDS_DE_CAMERA if sys.platform == 'win32' else (('padrão', cv2.CAP_ANY),)
    falhas: list[str] = []

    for nome, backend in tentativas:
        captura = cv2.VideoCapture(indice, backend)
        if not captura.isOpened():
            captura.release()
            falhas.append(f'{nome}: não abriu')
            continue

        ok, quadro = captura.read()
        if ok and quadro is not None and quadro.size:
            return captura, nome

        captura.release()
        falhas.append(f'{nome}: abriu mas não entregou quadro')

    detalhe = '; '.join(falhas)
    raise FonteIndisponivel(
        f'Não foi possível usar a câmera {indice}. Tentativas: {detalhe}. '
        'Verifique se outro programa está usando a câmera e se o Windows '
        'permite acesso em Privacidade e segurança.'
    )


@dataclass(frozen=True, slots=True)
class InfoVideo:
    largura: int
    altura: int
    fps: float
    total_de_quadros: int
    """Zero quando a fonte é câmera ao vivo, que não tem fim conhecido."""


class FonteDeVideo:
    """Sequência de quadros vinda de arquivo ou de câmera."""

    def __init__(self, origem: str | int, redimensionar_para: int | None = None) -> None:
        """
        `redimensionar_para` limita a largura dos quadros. Vídeo de celular chega
        em 1920 e processar nessa resolução não melhora a contagem, só deixa
        tudo quatro vezes mais lento: os objetos continuam sendo os mesmos, com
        mais pixels cada. Reduzir para algo em torno de 960 mantém o resultado e
        devolve a fluidez.
        """
        self._ao_vivo = not (isinstance(origem, str) and not origem.isdigit())
        self.backend = 'arquivo'

        if self._ao_vivo:
            self._captura, self.backend = _abrir_camera(int(origem))
        else:
            caminho = Path(origem)
            if not caminho.exists():
                raise FonteIndisponivel(f'Arquivo não encontrado: {origem}')
            self._captura = cv2.VideoCapture(str(caminho))
            if not self._captura.isOpened():
                raise FonteIndisponivel(
                    f'Não foi possível abrir o vídeo: {origem}. '
                    'O arquivo pode estar corrompido ou num formato que o OpenCV '
                    'não lê nesta máquina.'
                )

        self.redimensionar_para = redimensionar_para

    @property
    def info(self) -> InfoVideo:
        largura = int(self._captura.get(cv2.CAP_PROP_FRAME_WIDTH))
        altura = int(self._captura.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(self._captura.get(cv2.CAP_PROP_FPS)) or 25.0
        total = 0 if self._ao_vivo else int(self._captura.get(cv2.CAP_PROP_FRAME_COUNT))

        if self.redimensionar_para and largura > self.redimensionar_para:
            escala = self.redimensionar_para / largura
            largura = self.redimensionar_para
            altura = int(round(altura * escala))

        return InfoVideo(largura, altura, fps, max(0, total))

    def _ajustar(self, quadro: np.ndarray) -> np.ndarray:
        if not self.redimensionar_para:
            return quadro
        altura, largura = quadro.shape[:2]
        if largura <= self.redimensionar_para:
            return quadro
        escala = self.redimensionar_para / largura
        novo = (self.redimensionar_para, int(round(altura * escala)))
        return cv2.resize(quadro, novo, interpolation=cv2.INTER_AREA)

    def quadros(self) -> Iterator[np.ndarray]:
        while True:
            ok, quadro = self._captura.read()
            if not ok or quadro is None:
                break
            yield self._ajustar(quadro)

    def liberar(self) -> None:
        if self._captura is not None:
            self._captura.release()

    def __enter__(self) -> 'FonteDeVideo':
        return self

    def __exit__(self, *_) -> None:
        self.liberar()


def gravar(quadros, caminho: str, fps: float, tamanho: tuple[int, int]) -> int:
    """Grava uma sequência de quadros anotados e devolve quantos foram escritos."""
    escritor = cv2.VideoWriter(
        caminho, cv2.VideoWriter_fourcc(*'mp4v'), fps, tamanho
    )
    if not escritor.isOpened():
        raise FonteIndisponivel(f'Não foi possível gravar em: {caminho}')

    escritos = 0
    try:
        for quadro in quadros:
            escritor.write(quadro)
            escritos += 1
    finally:
        escritor.release()
    return escritos
