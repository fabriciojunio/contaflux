"""Dedução automática de onde a linha de contagem deve ficar."""

from __future__ import annotations

import math

import pytest

from contaflux.cena import GeradorDeCena, ParametrosCena, veiculos_regulares
from contaflux.perfis import RODOVIA
from contaflux.sugestao import (
    Observacao,
    _eixo_dominante,
    linha_a_partir_de,
    observar,
    sugerir_linha,
)


def observacao(centro=(320.0, 180.0), eixo=(1.0, 0.0), alvos=8, posicoes=200, area=2500.0):
    return Observacao(alvos, posicoes, centro, eixo, area)


# --------------------------------------------------------------------------
# Rumo dominante
# --------------------------------------------------------------------------


def mesmo_eixo(obtido, esperado, tolerancia=1e-6):
    """Compara eixos, e não vetores: (1,0) e (-1,0) são a mesma reta.

    O sinal do eixo é arbitrário por construção, então exigir um sinal
    específico seria fixar em teste uma coisa que o código não promete.
    """
    if obtido is None or esperado is None:
        return obtido is esperado
    ax, ay = obtido
    bx, by = esperado
    return abs(abs(ax * bx + ay * by) - 1.0) < tolerancia


def test_sem_rumos_nao_ha_eixo():
    assert _eixo_dominante([]) is None


@pytest.mark.parametrize(
    'rumo,esperado',
    [
        ((10.0, 0.0), (1.0, 0.0)),
        ((-10.0, 0.0), (1.0, 0.0)),
        ((0.0, 7.0), (0.0, 1.0)),
        ((3.0, 4.0), (0.6, 0.8)),
    ],
)
def test_um_rumo_vira_eixo_unitario(rumo, esperado):
    assert mesmo_eixo(_eixo_dominante([rumo]), esperado)


def test_rumos_iguais_mantem_o_eixo():
    assert mesmo_eixo(_eixo_dominante([(5.0, 0.0)] * 20), (1.0, 0.0))


def test_rumos_opostos_reforcam_o_mesmo_eixo():
    """Via de mão dupla é o caso comum, e não um caso sem resposta.

    A versão anterior somava os vetores e devolvia None aqui, por entender que
    não havia sentido dominante. Não havia mesmo, e não importa: a linha de
    contagem é perpendicular à via, e dois fluxos opostos descrevem a mesma
    via com o dobro de amostras.
    """
    assert mesmo_eixo(_eixo_dominante([(5.0, 0.0), (-5.0, 0.0)]), (1.0, 0.0))
    assert mesmo_eixo(_eixo_dominante([(0.0, 6.0)] * 9 + [(0.0, -6.0)] * 8), (0.0, 1.0))


def test_rumos_espalhados_ainda_devolvem_um_eixo():
    """Não há piso de coerência, e a medição é que decidiu isso.

    A resultante do ângulo dobrado ficou entre 0,10 e 0,59 nos cinco vídeos de
    exemplo, inclusive onde a linha sai certa, porque a caixa do detector de
    movimento treme. Nesse cenário nenhum piso separa "sem eixo" de "eixo com
    ruído", e um piso de 0,45 chegou a recusar quatro dos cinco. Ver
    CALIBRACAO.md.
    """
    espalhados = [(1.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, -1.0), (-1.0, 1.0)]
    assert _eixo_dominante(espalhados) is not None


def test_um_veiculo_longo_nao_domina_a_media():
    """Os rumos são normalizados antes de somar, senão um carro decide sozinho."""
    muitos_curtos = [(0.0, 10.0)] * 5
    um_enorme = [(900.0, 0.0)]
    eixo = _eixo_dominante(muitos_curtos + um_enorme)
    assert abs(eixo[1]) > abs(eixo[0])


def test_rumo_de_tamanho_zero_e_ignorado():
    assert mesmo_eixo(_eixo_dominante([(0.0, 0.0), (4.0, 0.0)]), (1.0, 0.0))


# --------------------------------------------------------------------------
# Confiabilidade da observação
# --------------------------------------------------------------------------


def test_observacao_completa_e_confiavel():
    assert observacao().confiavel is True


@pytest.mark.parametrize('alvos', [0, 1, 2])
def test_poucos_alvos_nao_sao_confiaveis(alvos):
    assert observacao(alvos=alvos).confiavel is False


@pytest.mark.parametrize('posicoes', [0, 10, 29])
def test_poucas_posicoes_nao_sao_confiaveis(posicoes):
    assert observacao(posicoes=posicoes).confiavel is False


def test_sem_centro_nao_e_confiavel():
    assert observacao(centro=None).confiavel is False


def test_sem_eixo_nao_e_confiavel():
    assert observacao(eixo=None).confiavel is False


# --------------------------------------------------------------------------
# Construção da linha
# --------------------------------------------------------------------------


def test_observacao_fraca_nao_gera_linha():
    """Melhor cair no padrão do que apontar a linha para o lugar errado."""
    assert linha_a_partir_de(observacao(alvos=1), 640, 360) is None


def test_trafego_horizontal_gera_linha_vertical():
    linha = linha_a_partir_de(observacao(eixo=(1.0, 0.0)), 640, 360)
    assert linha.x1 == pytest.approx(linha.x2)
    assert linha.y1 != pytest.approx(linha.y2)


def test_trafego_vertical_gera_linha_horizontal():
    """É o caso da câmera de frente, com os carros vindo em direção a ela."""
    linha = linha_a_partir_de(observacao(eixo=(0.0, 1.0)), 640, 360)
    assert linha.y1 == pytest.approx(linha.y2)
    assert linha.x1 != pytest.approx(linha.x2)


@pytest.mark.parametrize('angulo', range(0, 360, 15))
def test_a_linha_e_sempre_perpendicular_ao_trafego(angulo):
    radianos = math.radians(angulo)
    eixo = (math.cos(radianos), math.sin(radianos))
    linha = linha_a_partir_de(observacao(eixo=eixo), 640, 360)

    da_linha = (linha.x2 - linha.x1, linha.y2 - linha.y1)
    produto = da_linha[0] * eixo[0] + da_linha[1] * eixo[1]
    assert produto == pytest.approx(0.0, abs=1e-6)


@pytest.mark.parametrize('centro', [(100.0, 100.0), (320.0, 180.0), (500.0, 250.0)])
def test_a_linha_passa_pelo_centro_do_trafego(centro):
    linha = linha_a_partir_de(observacao(centro=centro), 640, 360)
    meio = ((linha.x1 + linha.x2) / 2, (linha.y1 + linha.y2) / 2)
    assert meio == pytest.approx(centro)


@pytest.mark.parametrize('largura,altura', [(320, 240), (640, 360), (1920, 1080)])
def test_a_linha_e_longa_o_bastante_para_cruzar_o_quadro(largura, altura):
    """Linha curta demais deixa faixas de fora e some com veículos da conta."""
    linha = linha_a_partir_de(observacao(), largura, altura)
    assert linha.comprimento >= min(largura, altura)


# --------------------------------------------------------------------------
# Observação de uma cena inteira
# --------------------------------------------------------------------------


@pytest.mark.lento
def test_observa_cena_sintetica_e_acha_o_eixo():
    """Na cena de rodovia os veículos correm na horizontal."""
    parametros = ParametrosCena(quadros=460, semente=3)
    parametros.veiculos = veiculos_regulares(10, parametros, semente=3)
    cena = GeradorDeCena(parametros)

    obtida = observar(cena.quadros(), RODOVIA, limite_de_quadros=460)
    assert obtida.confiavel
    assert abs(obtida.eixo[0]) > 0.8


@pytest.mark.lento
def test_o_eixo_e_o_mesmo_no_sentido_contrario():
    """Inverter o sentido não muda a via, e a linha tem que sair igual."""
    parametros = ParametrosCena(quadros=460, semente=4)
    parametros.veiculos = veiculos_regulares(10, parametros, sentido=-1, semente=4)
    cena = GeradorDeCena(parametros)

    obtida = observar(cena.quadros(), RODOVIA, limite_de_quadros=460)
    assert obtida.confiavel
    assert abs(obtida.eixo[0]) > 0.8


@pytest.mark.lento
def test_cena_vazia_nao_gera_sugestao():
    """Sem tráfego não há o que deduzir, e inventar seria pior."""
    cena = GeradorDeCena(ParametrosCena(quadros=400, semente=5))
    linha, obtida = sugerir_linha(cena.quadros(), 640, 360, RODOVIA, 400)
    assert linha is None
    assert obtida.confiavel is False


@pytest.mark.lento
def test_a_linha_sugerida_conta_a_cena_sintetica():
    """O teste que importa: a linha deduzida sozinha dá o número certo."""
    from contaflux.pipeline import contar_sequencia

    parametros = ParametrosCena(quadros=460, semente=6)
    parametros.veiculos = veiculos_regulares(8, parametros, semente=6)

    cena = GeradorDeCena(parametros)
    linha, _ = sugerir_linha(cena.quadros(), 640, 360, RODOVIA, 460)
    assert linha is not None

    de_novo = GeradorDeCena(parametros)
    esperado = de_novo.travessias_esperadas((linha.x1 + linha.x2) / 2)
    contagem = contar_sequencia(de_novo.quadros(), linha, perfil=RODOVIA)
    assert contagem.total == esperado
