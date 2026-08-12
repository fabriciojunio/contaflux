"""Estimativa de velocidade a partir da trajetória."""

from __future__ import annotations

import pytest

from contaflux.rastreio import Alvo
from contaflux.velocidade import (
    Escala,
    em_km_por_hora,
    inclinacao_robusta,
    pixels_por_quadro,
)


def alvo_reto(passo_x: float, passo_y: float = 0.0, pontos: int = 12, inicio: int = 0) -> Alvo:
    """Alvo andando em linha reta, um ponto por quadro."""
    trajetoria = [(i * passo_x, i * passo_y) for i in range(pontos)]
    indices = [inicio + i for i in range(pontos)]
    return Alvo(1, trajetoria[-1], (0, 0, 10, 10), trajetoria, indices, quadros_visto=pontos)


# --------------------------------------------------------------------------
# Escala
# --------------------------------------------------------------------------


@pytest.mark.parametrize('largura', [320, 640, 960, 1280, 1920])
@pytest.mark.parametrize('metros', [10.0, 25.0, 40.0])
def test_escala_por_largura(largura, metros):
    escala = Escala.de_largura(largura, metros, 25.0)
    assert escala.metros_por_pixel == pytest.approx(metros / largura)
    assert escala.fps == 25.0


@pytest.mark.parametrize('largura', [0, -1, -640])
def test_escala_recusa_largura_invalida(largura):
    with pytest.raises(ValueError, match='largura'):
        Escala.de_largura(largura, 30.0, 25.0)


@pytest.mark.parametrize('metros', [0.0, -1.0])
def test_escala_recusa_trecho_invalido(metros):
    with pytest.raises(ValueError, match='trecho'):
        Escala.de_largura(640, metros, 25.0)


@pytest.mark.parametrize('fps', [0.0, -1.0, -30.0])
def test_escala_recusa_fps_invalido(fps):
    """Sem taxa de quadros não há tempo, e sem tempo não há velocidade."""
    with pytest.raises(ValueError, match='quadros'):
        Escala.de_largura(640, 30.0, fps)


@pytest.mark.parametrize('pixels', [50.0, 100.0, 250.0, 640.0])
@pytest.mark.parametrize('metros', [5.0, 12.0, 30.0])
def test_escala_por_trecho_medido(pixels, metros):
    escala = Escala.de_trecho(pixels, metros, 30.0)
    assert escala.metros_por_pixel == pytest.approx(metros / pixels)


@pytest.mark.parametrize('valor', [0.0, -1.0])
def test_escala_por_trecho_recusa_valores_invalidos(valor):
    with pytest.raises(ValueError):
        Escala.de_trecho(valor, 10.0, 25.0)
    with pytest.raises(ValueError):
        Escala.de_trecho(100.0, valor, 25.0)
    with pytest.raises(ValueError):
        Escala.de_trecho(100.0, 10.0, valor)


def test_as_duas_formas_de_calibrar_coincidem():
    """Medir a largura inteira ou um pedaço tem que dar na mesma escala."""
    por_largura = Escala.de_largura(640, 32.0, 25.0)
    por_trecho = Escala.de_trecho(320.0, 16.0, 25.0)
    assert por_largura.metros_por_pixel == pytest.approx(por_trecho.metros_por_pixel)


# --------------------------------------------------------------------------
# inclinacao_robusta
# --------------------------------------------------------------------------


@pytest.mark.parametrize('coeficiente', [-8.0, -3.5, -1.0, 0.0, 1.0, 2.5, 7.0, 20.0])
def test_inclinacao_de_reta_perfeita(coeficiente):
    tempos = list(range(10))
    valores = [coeficiente * t + 17.0 for t in tempos]
    assert inclinacao_robusta(tempos, valores) == pytest.approx(coeficiente)


@pytest.mark.parametrize('posicao', range(1, 9))
def test_um_ponto_fora_da_curva_nao_derruba_a_estimativa(posicao):
    """É o pulo do centro quando duas caixas se juntam. A mediana ignora."""
    tempos = list(range(10))
    valores = [5.0 * t for t in tempos]
    valores[posicao] += 400.0
    assert inclinacao_robusta(tempos, valores) == pytest.approx(5.0, abs=0.6)


def test_inclinacao_de_lista_vazia_e_zero():
    assert inclinacao_robusta([], []) == 0.0


def test_inclinacao_de_ponto_unico_e_zero():
    assert inclinacao_robusta([3], [10.0]) == 0.0


def test_tempos_repetidos_sao_ignorados_sem_dividir_por_zero():
    assert inclinacao_robusta([2, 2, 2], [1.0, 5.0, 9.0]) == 0.0


@pytest.mark.parametrize('salto', [2, 3, 5, 10])
def test_inclinacao_com_quadros_espacados(salto):
    """Trajetória com buraco: a inclinação é por quadro, não por ponto."""
    tempos = [0, salto, salto * 2, salto * 3]
    valores = [t * 4.0 for t in tempos]
    assert inclinacao_robusta(tempos, valores) == pytest.approx(4.0)


def test_inclinacao_com_numero_par_de_pares_usa_a_media_do_meio():
    """Quatro pontos dão seis pares, e a mediana de seis é a média dos dois centrais."""
    assert inclinacao_robusta([0, 1, 2, 3], [0.0, 1.0, 3.0, 4.0]) == pytest.approx(
        (4 / 3 + 1.5) / 2
    )


def test_inclinacao_com_numero_impar_de_pares_usa_o_do_meio():
    """Três pontos dão três pares, e a mediana é o valor central."""
    assert inclinacao_robusta([0, 1, 2], [0.0, 2.0, 8.0]) == pytest.approx(4.0)


# --------------------------------------------------------------------------
# pixels_por_quadro
# --------------------------------------------------------------------------


@pytest.mark.parametrize('passo', [1.0, 2.5, 5.0, 8.0, 12.0, 20.0])
def test_rapidez_horizontal(passo):
    assert pixels_por_quadro(alvo_reto(passo)) == pytest.approx(passo)


@pytest.mark.parametrize('passo', [1.0, 3.0, 6.0, 15.0])
def test_rapidez_vertical(passo):
    assert pixels_por_quadro(alvo_reto(0.0, passo)) == pytest.approx(passo)


def test_rapidez_diagonal_e_a_hipotenusa():
    assert pixels_por_quadro(alvo_reto(3.0, 4.0)) == pytest.approx(5.0)


@pytest.mark.parametrize('passo', [-2.0, -7.0, -15.0])
def test_rapidez_nao_depende_do_sentido(passo):
    """Rapidez é módulo; quem guarda o sentido é a contagem."""
    assert pixels_por_quadro(alvo_reto(passo)) == pytest.approx(abs(passo))


@pytest.mark.parametrize('pontos', range(1, 5))
def test_trajetoria_curta_devolve_nada(pontos):
    """Melhor um traço na tela do que um número inventado com três pontos."""
    assert pixels_por_quadro(alvo_reto(5.0, pontos=pontos)) is None


@pytest.mark.parametrize('pontos', range(5, 20))
def test_trajetoria_suficiente_devolve_numero(pontos):
    assert pixels_por_quadro(alvo_reto(5.0, pontos=pontos)) == pytest.approx(5.0)


@pytest.mark.parametrize('minimo', range(2, 15))
def test_minimo_de_pontos_configuravel(minimo):
    curto = alvo_reto(5.0, pontos=minimo - 1)
    exato = alvo_reto(5.0, pontos=minimo)
    assert pixels_por_quadro(curto, minimo_de_pontos=minimo) is None
    assert pixels_por_quadro(exato, minimo_de_pontos=minimo) == pytest.approx(5.0)


def test_alvo_com_indices_desalinhados_devolve_nada():
    """Sem saber de que quadro veio cada ponto, não há como medir tempo."""
    alvo = alvo_reto(5.0)
    alvo.indices = alvo.indices[:-2]
    assert pixels_por_quadro(alvo) is None


def test_alvo_parado_tem_rapidez_zero():
    assert pixels_por_quadro(alvo_reto(0.0)) == pytest.approx(0.0)


# --------------------------------------------------------------------------
# em_km_por_hora
# --------------------------------------------------------------------------


@pytest.mark.parametrize('passo', [2.0, 4.0, 6.0, 10.0, 18.0])
@pytest.mark.parametrize('fps', [15.0, 25.0, 30.0, 60.0])
def test_conversao_para_quilometros_por_hora(passo, fps):
    escala = Escala(metros_por_pixel=0.05, fps=fps)
    esperado = passo * fps * 0.05 * 3.6
    assert em_km_por_hora(alvo_reto(passo), escala) == pytest.approx(esperado)


def test_caso_de_referencia_com_numeros_redondos():
    """Vinte pixels por quadro, cinco centímetros por pixel, vinte e cinco
    quadros por segundo: vinte e cinco metros por segundo, ou noventa por hora."""
    escala = Escala(metros_por_pixel=0.05, fps=25.0)
    assert em_km_por_hora(alvo_reto(20.0), escala) == pytest.approx(90.0)


def test_sem_pontos_suficientes_nao_ha_velocidade():
    assert em_km_por_hora(alvo_reto(10.0, pontos=3), Escala(0.05, 25.0)) is None


@pytest.mark.parametrize('metros_por_pixel', [0.01, 0.05, 0.1, 0.3])
def test_velocidade_e_proporcional_a_escala(metros_por_pixel):
    base = em_km_por_hora(alvo_reto(10.0), Escala(0.01, 25.0))
    atual = em_km_por_hora(alvo_reto(10.0), Escala(metros_por_pixel, 25.0))
    assert atual == pytest.approx(base * metros_por_pixel / 0.01)


def test_velocidade_ignora_o_pulo_de_uma_caixa_fundida():
    """O caso real: por dois quadros a caixa engloba dois carros e o centro salta."""
    trajetoria = [(i * 8.0, 0.0) for i in range(14)]
    trajetoria[6] = (trajetoria[6][0] + 90.0, 0.0)
    trajetoria[7] = (trajetoria[7][0] + 90.0, 0.0)
    alvo = Alvo(1, trajetoria[-1], (0, 0, 10, 10), trajetoria, list(range(14)), quadros_visto=14)

    escala = Escala(metros_por_pixel=0.05, fps=25.0)
    esperado = 8.0 * 25.0 * 0.05 * 3.6
    assert em_km_por_hora(alvo, escala) == pytest.approx(esperado, abs=6.0)
