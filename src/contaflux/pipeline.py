"""Orquestração: do vídeo até o número contado."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from contaflux.contagem import Contagem, ContadorDeLinha, Linha
from contaflux.deteccao import Deteccao, DetectorDeMovimento
from contaflux.perfis import PESSOAS, Perfil
from contaflux.rastreio import Alvo, Rastreador


@dataclass
class EstadoQuadro:
    """O que aconteceu num quadro. Alimenta a interface."""

    indice: int
    deteccoes: list[Deteccao]
    alvos: dict[int, Alvo]
    contagem: Contagem
    mascara: np.ndarray


class ContadorDeFluxo:
    """Junta detecção, rastreio e contagem."""

    def __init__(
        self,
        linha: Linha,
        perfil: Perfil = PESSOAS,
        detector: DetectorDeMovimento | None = None,
        rastreador: Rastreador | None = None,
        quadros_de_aquecimento: int = 45,
    ) -> None:
        """
        O perfil carrega a calibração de tudo que muda entre contar pessoa e
        contar carro, e por isso é um argumento e não uma constante espalhada
        pelo código.

        `quadros_de_aquecimento` são descartados no começo, enquanto o modelo de
        fundo ainda não aprendeu a cena. Sem isso, os primeiros quadros marcam a
        imagem inteira como movimento e geram contagens fantasmas.
        """
        self.perfil = perfil
        self.detector = detector or DetectorDeMovimento(
            area_minima=perfil.area_minima,
            area_maxima=perfil.area_maxima,
            proporcao_maxima=perfil.proporcao_maxima,
            historico=perfil.historico_fundo,
            limiar_variancia=perfil.limiar_variancia,
        )
        self.rastreador = rastreador or Rastreador(
            distancia_maxima=perfil.distancia_maxima,
            tolerancia_sumico=perfil.tolerancia_sumico,
        )
        self.contador = ContadorDeLinha(linha, quadros_minimos=perfil.quadros_minimos)
        self.quadros_de_aquecimento = quadros_de_aquecimento
        self._indice = 0

    @property
    def contagem(self) -> Contagem:
        return self.contador.contagem

    def processar(self, quadro: np.ndarray) -> EstadoQuadro:
        deteccoes, mascara = self.detector.detectar(quadro)
        indice = self._indice
        self._indice += 1

        if indice < self.quadros_de_aquecimento:
            return EstadoQuadro(indice, [], {}, self.contagem, mascara)

        alvos = self.rastreador.atualizar(deteccoes)
        contagem = self.contador.atualizar(alvos, indice)
        return EstadoQuadro(indice, deteccoes, alvos, contagem, mascara)

    def reiniciar(self) -> None:
        self.rastreador.reiniciar()
        self.contador.reiniciar()
        self._indice = 0


def contar_sequencia(quadros, linha: Linha, **opcoes) -> Contagem:
    """Processa uma sequência inteira de quadros e devolve os totais."""
    contador = ContadorDeFluxo(linha, **opcoes)
    for quadro in quadros:
        contador.processar(quadro)
    return contador.contagem
