"""Descobrir sozinho onde a linha de contagem deve ficar.

Sem isto, cada vídeo precisa de quatro números medidos à mão, e o programa só
serve para os vídeos que alguém já calibrou. Com isto, ele abre qualquer vídeo
de câmera fixa e se vira.

A ideia é simples e vem do próprio problema: a linha tem que ficar atravessada
no caminho dos veículos. Então basta observar por onde eles passam e para onde
vão. Rodando alguns segundos de vídeo, o rastreio já entrega as duas coisas: a
nuvem de posições diz onde é a via, e a soma dos deslocamentos diz o sentido do
tráfego. A linha é a perpendicular a esse sentido, passando pelo meio da nuvem.

Isto não substitui marcar a linha na mão, e não deveria: quem quer contar só
uma das pistas, ou só quem entra numa saída, precisa dizer onde. Serve para o
caso comum e para a primeira execução, que é quando ninguém sabe ainda quais
números digitar.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from contaflux.contagem import Linha
from contaflux.deteccao import DetectorDeMovimento
from contaflux.perfis import PADRAO, Perfil
from contaflux.rastreio import Rastreador

DESLOCAMENTO_MINIMO = 12.0
"""Quanto um alvo precisa ter andado para o rumo dele valer como amostra.

Alvo que mal se mexeu tem direção dominada por ruído da caixa, e incluir esses
casos embaralha a média justamente onde ela precisa ser firme."""


@dataclass(frozen=True, slots=True)
class Observacao:
    """O que alguns segundos de vídeo revelaram sobre o tráfego."""

    total_de_alvos: int
    posicoes: int
    centro: tuple[float, float] | None
    direcao: tuple[float, float] | None
    area_tipica: float

    @property
    def confiavel(self) -> bool:
        """Se dá para confiar na sugestão.

        Três alvos com rumo coerente é pouco, mas é o suficiente para acertar
        melhor que o palpite fixo. Abaixo disso é melhor admitir que não sabe.
        """
        return (
            self.centro is not None
            and self.direcao is not None
            and self.total_de_alvos >= 3
            and self.posicoes >= 30
        )


def observar(quadros, perfil: Perfil = PADRAO, limite_de_quadros: int = 400) -> Observacao:
    """Roda detecção e rastreio por alguns quadros, só para olhar o tráfego."""
    detector = DetectorDeMovimento(
        area_minima=perfil.area_minima,
        area_maxima=perfil.area_maxima,
        proporcao_maxima=perfil.proporcao_maxima,
        historico=perfil.historico_fundo,
        limiar_variancia=perfil.limiar_variancia,
    )
    rastreador = Rastreador(
        distancia_maxima=perfil.distancia_maxima,
        tolerancia_sumico=perfil.tolerancia_sumico,
    )

    centros: list[tuple[float, float]] = []
    areas: list[int] = []
    rumos: list[tuple[float, float]] = []
    vistos: set[int] = set()
    aquecimento = min(perfil.historico_fundo, limite_de_quadros // 3)

    for indice, quadro in enumerate(quadros):
        if indice >= limite_de_quadros:
            break

        deteccoes, _ = detector.detectar(quadro)
        if indice < aquecimento:
            continue

        alvos = rastreador.atualizar(deteccoes, indice)
        for identificador, alvo in alvos.items():
            if alvo.sumido_ha:
                continue
            vistos.add(identificador)
            centros.append(alvo.centro)
            areas.append(alvo.area)

            dx, dy = alvo.deslocamento
            if math.hypot(dx, dy) >= DESLOCAMENTO_MINIMO:
                rumos.append((dx, dy))

    centro = None
    if centros:
        pontos = np.array(centros, dtype=float)
        centro = (float(np.median(pontos[:, 0])), float(np.median(pontos[:, 1])))

    direcao = _rumo_dominante(rumos)
    area = float(np.median(areas)) if areas else 0.0
    return Observacao(len(vistos), len(centros), centro, direcao, area)


def _rumo_dominante(rumos: list[tuple[float, float]]) -> tuple[float, float] | None:
    """Direção média do tráfego, como vetor unitário.

    Os rumos são normalizados antes de somar. Sem isso, um caminhão que
    atravessou a tela inteira pesaria dez vezes mais que um carro que apareceu
    perto da borda, e a direção passaria a ser a de um veículo só.
    """
    if not rumos:
        return None

    soma_x = soma_y = 0.0
    for dx, dy in rumos:
        tamanho = math.hypot(dx, dy)
        if tamanho < 1e-9:
            continue
        soma_x += dx / tamanho
        soma_y += dy / tamanho

    tamanho = math.hypot(soma_x, soma_y)
    if tamanho < 1e-9:
        return None
    return (soma_x / tamanho, soma_y / tamanho)


def linha_a_partir_de(
    observacao: Observacao, largura: int, altura: int, cobertura: float = 0.9
) -> Linha | None:
    """Perpendicular ao tráfego, passando pelo centro da via."""
    if not observacao.confiavel:
        return None

    cx, cy = observacao.centro
    dx, dy = observacao.direcao

    # Perpendicular ao sentido do tráfego: é assim que a linha corta o caminho
    # em vez de acompanhá-lo.
    px, py = -dy, dx

    # O comprimento é o que basta para atravessar o quadro inteiro na direção
    # perpendicular, de modo que nenhuma faixa fique de fora.
    alcance = math.hypot(largura, altura) * cobertura / 2.0

    x1, y1 = cx - px * alcance, cy - py * alcance
    x2, y2 = cx + px * alcance, cy + py * alcance
    return Linha(x1, y1, x2, y2)


def sugerir_linha(
    quadros, largura: int, altura: int, perfil: Perfil = PADRAO, limite_de_quadros: int = 400
) -> tuple[Linha | None, Observacao]:
    """Observa o tráfego e devolve a linha sugerida, com o que foi observado."""
    observacao = observar(quadros, perfil, limite_de_quadros)
    return linha_a_partir_de(observacao, largura, altura), observacao
