"""Descobrir sozinho onde a linha de contagem deve ficar.

Sem isto, cada vídeo precisa de quatro números medidos à mão, e o programa só
serve para os vídeos que alguém já calibrou. Com isto, ele abre qualquer vídeo
de câmera fixa e se vira.

A ideia é simples e vem do próprio problema: a linha tem que ficar atravessada
no caminho dos veículos. Então basta observar por onde eles passam e para onde
vão. Rodando alguns segundos de vídeo, o rastreio já entrega as duas coisas: a
nuvem de posições diz onde é a via, e os deslocamentos dizem em que reta ela
corre. A linha é a perpendicular a essa reta, passando pelo meio da nuvem.

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
    eixo: tuple[float, float] | None
    """Reta em que a via corre. O sinal não quer dizer nada."""
    area_tipica: float

    @property
    def confiavel(self) -> bool:
        """Se dá para confiar na sugestão.

        Três alvos com rumo coerente é pouco, mas é o suficiente para acertar
        melhor que o palpite fixo. Abaixo disso é melhor admitir que não sabe.
        """
        return (
            self.centro is not None
            and self.eixo is not None
            and self.total_de_alvos >= 3
            and self.posicoes >= 30
        )


def observar(
    quadros,
    perfil: Perfil = PADRAO,
    limite_de_quadros: int = 400,
    detector=None,
) -> Observacao:
    """Roda detecção e rastreio por alguns quadros, só para olhar o tráfego.

    `detector` deve ser o mesmo que vai contar, e isso não é detalhe. Observando
    por movimento uma cena onde quem conta é o reconhecimento, a linha é posta
    para os objetos errados: numa rua movimentada de Bangkok, o pedestre na
    calçada, a escada rolante e a sombra do viaduto entraram na conta do rumo e
    o eixo saiu a 172°, quase perpendicular ao trânsito de verdade. A linha ficou
    deitada ao longo da via, paralela aos carros, e a contagem caiu de 106 para
    29. Sem `detector`, cai no de movimento, que é o que existia antes.
    """
    proprio = detector is None
    if proprio:
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
    # O reconhecimento não aprende a cena, então não há fundo para aquecer.
    aquecimento = min(perfil.historico_fundo, limite_de_quadros // 3) if proprio else 0

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

    eixo = _eixo_dominante(rumos)
    area = float(np.median(areas)) if areas else 0.0
    return Observacao(len(vistos), len(centros), centro, eixo, area)


# Chegou a existir aqui um piso de coerência, para recusar cena sem eixo em vez
# de chutar um. A medida nos cinco vídeos derrubou a ideia: a resultante do
# ângulo dobrado ficou entre 0,10 e 0,59 mesmo onde a linha sai certa, porque a
# caixa do detector de movimento treme e cada alvo contribui com rumo ruidoso.
# Um piso que aceitasse a via movimentada (0,10) aceitaria qualquer coisa, e um
# que recusasse ruído recusaria quatro dos cinco vídeos. Ver CALIBRACAO.md.


def _eixo_dominante(rumos: list[tuple[float, float]]) -> tuple[float, float] | None:
    """Eixo do tráfego, como vetor unitário de sinal arbitrário.

    Eixo, e não sentido, e a diferença custou um vídeo inteiro. Numa via de mão
    dupla os dois fluxos apontam para lados opostos, e somar os vetores fazia
    eles se anularem: sobrava o ruído, e a perpendicular do ruído virou uma
    linha de contagem subindo para o céu sobre os prédios, que contou 1 veículo
    onde passaram 28.

    A linha não precisa saber quem vai para que lado, só em que reta a via
    corre. Então a média é feita no ângulo dobrado, que é como se promedia
    orientação sem sentido: dobrar o ângulo faz 0° e 180° caírem no mesmo
    ponto, os dois fluxos passam a se reforçar, e a metade do ângulo médio
    volta para o eixo.

    Os rumos são normalizados antes de somar. Sem isso, um caminhão que
    atravessou a tela inteira pesaria dez vezes mais que um carro que apareceu
    perto da borda, e o eixo passaria a ser o de um veículo só.

    Não há piso de coerência, e isso foi medido e não esquecido: ver o comentário
    acima e a tabela em CALIBRACAO.md.
    """
    unitarios = []
    for dx, dy in rumos:
        tamanho = math.hypot(dx, dy)
        if tamanho < 1e-9:
            continue
        unitarios.append((dx / tamanho, dy / tamanho))
    if not unitarios:
        return None

    # cos(2a) e sen(2a) a partir do unitario, sem precisar do arco.
    soma_x = sum(ux * ux - uy * uy for ux, uy in unitarios)
    soma_y = sum(2.0 * ux * uy for ux, uy in unitarios)

    if math.hypot(soma_x, soma_y) < 1e-9:
        return None

    angulo = math.atan2(soma_y, soma_x) / 2.0
    return (math.cos(angulo), math.sin(angulo))


def linha_a_partir_de(
    observacao: Observacao, largura: int, altura: int, cobertura: float = 0.9
) -> Linha | None:
    """Perpendicular ao tráfego, passando pelo centro da via."""
    if not observacao.confiavel:
        return None

    cx, cy = observacao.centro
    dx, dy = observacao.eixo

    # Perpendicular ao eixo da via: é assim que a linha corta o caminho em vez
    # de acompanhá-lo.
    px, py = -dy, dx

    # O comprimento é o que basta para atravessar o quadro inteiro na direção
    # perpendicular, de modo que nenhuma faixa fique de fora.
    alcance = math.hypot(largura, altura) * cobertura / 2.0

    x1, y1 = cx - px * alcance, cy - py * alcance
    x2, y2 = cx + px * alcance, cy + py * alcance
    return Linha(x1, y1, x2, y2)


def sugerir_linha(
    quadros,
    largura: int,
    altura: int,
    perfil: Perfil = PADRAO,
    limite_de_quadros: int = 400,
    detector=None,
) -> tuple[Linha | None, Observacao]:
    """Observa o tráfego e devolve a linha sugerida, com o que foi observado."""
    observacao = observar(quadros, perfil, limite_de_quadros, detector)
    return linha_a_partir_de(observacao, largura, altura), observacao
