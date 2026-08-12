"""Separar o que se move do que fica parado.

A ideia é a mais direta possível para uma câmera fixa: se a câmera não se
mexe, tudo que muda entre um quadro e outro é objeto em movimento. O modelo de
fundo aprende como é a cena vazia e marca como primeiro plano o que destoa.

Usamos o MOG2, que modela cada pixel como uma mistura de gaussianas em vez de
guardar um único valor de referência. A diferença aparece em cena real: um
pixel de asfalto sob a sombra de uma árvore que balança alterna entre dois tons
o tempo todo, e um modelo de valor único acusaria movimento a cada oscilação.
Com mistura, os dois tons são aprendidos como fundo e só um carro passando gera
detecção.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True, slots=True)
class Deteccao:
    """Um objeto encontrado num quadro."""

    x: int
    y: int
    largura: int
    altura: int
    area: int

    @property
    def centro(self) -> tuple[float, float]:
        return (self.x + self.largura / 2.0, self.y + self.altura / 2.0)

    @property
    def proporcao(self) -> float:
        return self.largura / self.altura if self.altura else 0.0

    def como_tupla(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.largura, self.altura)


class DetectorDeMovimento:
    """Encontra objetos em movimento numa cena de câmera fixa."""

    def __init__(
        self,
        area_minima: int = 700,
        area_maxima: int | None = None,
        historico: int = 300,
        limiar_variancia: float = 40.0,
        detectar_sombras: bool = True,
        proporcao_maxima: float = 6.0,
    ) -> None:
        """
        `area_minima` descarta o que é pequeno demais para ser o objeto de
        interesse: folha voando, chuva, ruído do sensor.

        `detectar_sombras` liga a marcação separada de sombra pelo MOG2. Sombra
        é o erro mais comum neste tipo de contagem: ela acompanha o veículo,
        gruda nele e faz dois carros vizinhos virarem um só borrão. Marcada, ela
        pode ser removida antes da contagem.
        """
        self._fundo = cv2.createBackgroundSubtractorMOG2(
            history=historico,
            varThreshold=limiar_variancia,
            detectShadows=detectar_sombras,
        )
        self.area_minima = area_minima
        self.area_maxima = area_maxima
        self.proporcao_maxima = proporcao_maxima
        self._nucleo = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

    def mascara(self, quadro: np.ndarray) -> np.ndarray:
        """Máscara binária do que está em movimento."""
        bruta = self._fundo.apply(quadro)

        # O MOG2 marca sombra com 127 e objeto com 255. Cortar em 200 descarta a
        # sombra e mantém o objeto, que é o que evita dois veículos próximos
        # serem unidos pela sombra de um sobre o outro.
        _, binaria = cv2.threshold(bruta, 200, 255, cv2.THRESH_BINARY)

        # Abertura tira pontos isolados; fechamento costura o objeto que saiu
        # partido em pedaços por causa de reflexo ou de cor parecida com a pista.
        binaria = cv2.morphologyEx(binaria, cv2.MORPH_OPEN, self._nucleo)
        binaria = cv2.morphologyEx(binaria, cv2.MORPH_CLOSE, self._nucleo, iterations=2)
        return cv2.dilate(binaria, self._nucleo, iterations=1)

    def detectar(self, quadro: np.ndarray) -> tuple[list[Deteccao], np.ndarray]:
        """Objetos em movimento e a máscara usada, para poder ser exibida."""
        binaria = self.mascara(quadro)
        contornos, _ = cv2.findContours(
            binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        encontrados: list[Deteccao] = []
        for contorno in contornos:
            area = int(cv2.contourArea(contorno))
            if area < self.area_minima:
                continue
            if self.area_maxima is not None and area > self.area_maxima:
                continue

            x, y, largura, altura = cv2.boundingRect(contorno)
            if altura == 0:
                continue
            proporcao = largura / altura
            # Formas muito alongadas costumam ser faixa da pista, guard rail ou
            # sombra comprida, e não veículo.
            if proporcao > self.proporcao_maxima or proporcao < 1 / self.proporcao_maxima:
                continue

            encontrados.append(Deteccao(x, y, largura, altura, area))

        return encontrados, binaria

    def aquecer(self, quadros: list[np.ndarray]) -> None:
        """Aprende o fundo antes de começar a contar.

        Sem isso, os primeiros quadros produzem detecção em cena inteira, porque
        o modelo ainda não sabe como é o fundo e considera tudo novidade.
        """
        for quadro in quadros:
            self._fundo.apply(quadro)
