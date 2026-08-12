"""Identidade dos objetos entre quadros."""

from __future__ import annotations

import pytest

from contaflux.deteccao import Deteccao
from contaflux.rastreio import Alvo, Rastreador


def det(x: int, y: int, largura: int = 40, altura: int = 30) -> Deteccao:
    return Deteccao(x, y, largura, altura, largura * altura)


# --------------------------------------------------------------------------
# Alvo
# --------------------------------------------------------------------------


def test_alvo_novo_nao_tem_deslocamento():
    """Um ponto só não define direção."""
    assert Alvo(1, (10, 10), (0, 0, 20, 20), trajetoria=[(10, 10)]).deslocamento == (0.0, 0.0)


def test_alvo_sem_trajetoria_nao_tem_deslocamento():
    assert Alvo(1, (10, 10), (0, 0, 20, 20)).deslocamento == (0.0, 0.0)


@pytest.mark.parametrize('dx', range(-30, 31, 5))
@pytest.mark.parametrize('dy', [-20, 0, 20])
def test_deslocamento_e_a_diferenca_entre_as_pontas(dx, dy):
    alvo = Alvo(1, (0, 0), (0, 0, 1, 1), trajetoria=[(0, 0), (5, 5), (dx, dy)])
    assert alvo.deslocamento == (dx, dy)


def test_alvos_diferentes_nao_dividem_a_trajetoria():
    um, outro = Alvo(1, (0, 0), (0, 0, 1, 1)), Alvo(2, (0, 0), (0, 0, 1, 1))
    um.trajetoria.append((1, 1))
    assert outro.trajetoria == []


# --------------------------------------------------------------------------
# Criação de alvos
# --------------------------------------------------------------------------


@pytest.mark.parametrize('quantidade', range(0, 20))
def test_primeiro_quadro_cria_um_alvo_por_deteccao(quantidade):
    rastreador = Rastreador()
    alvos = rastreador.atualizar([det(i * 50, 10) for i in range(quantidade)], 0)
    assert len(alvos) == quantidade


@pytest.mark.parametrize('quantidade', range(1, 12))
def test_identificadores_sao_sequenciais_e_unicos(quantidade):
    rastreador = Rastreador()
    alvos = rastreador.atualizar([det(i * 50, 10) for i in range(quantidade)], 0)
    assert sorted(alvos) == list(range(1, quantidade + 1))


def test_alvo_guarda_o_quadro_em_que_nasceu():
    rastreador = Rastreador()
    alvos = rastreador.atualizar([det(10, 10)], 77)
    assert alvos[1].indices == [77]


def test_alvo_guarda_a_area_da_deteccao():
    rastreador = Rastreador()
    alvos = rastreador.atualizar([Deteccao(0, 0, 50, 30, 1234)], 0)
    assert alvos[1].area == 1234


# --------------------------------------------------------------------------
# Associação entre quadros
# --------------------------------------------------------------------------


@pytest.mark.parametrize('passo', range(1, 40, 3))
def test_objeto_que_anda_pouco_mantem_a_identidade(passo):
    rastreador = Rastreador(distancia_maxima=50.0)
    rastreador.atualizar([det(100, 100)], 0)
    alvos = rastreador.atualizar([det(100 + passo, 100)], 1)
    assert list(alvos) == [1]
    assert alvos[1].quadros_visto == 2


@pytest.mark.parametrize('salto', [60, 80, 120, 200, 400])
def test_salto_maior_que_o_limite_cria_alvo_novo(salto):
    """Um objeto não teleporta. Salto grande demais é outro objeto."""
    rastreador = Rastreador(distancia_maxima=50.0)
    rastreador.atualizar([det(100, 100)], 0)
    alvos = rastreador.atualizar([det(100 + salto, 100)], 1)
    assert len(alvos) == 2


@pytest.mark.parametrize('n', range(2, 10))
def test_varios_objetos_mantem_identidades_separadas(n):
    rastreador = Rastreador(distancia_maxima=40.0)
    rastreador.atualizar([det(i * 100, 50) for i in range(n)], 0)
    alvos = rastreador.atualizar([det(i * 100 + 10, 50) for i in range(n)], 1)
    assert len(alvos) == n
    assert sorted(alvos) == list(range(1, n + 1))


def test_associacao_escolhe_o_par_mais_proximo():
    """Com dois candidatos ao alcance, vence o mais perto, não o primeiro."""
    rastreador = Rastreador(distancia_maxima=100.0)
    rastreador.atualizar([det(0, 0), det(60, 0)], 0)
    alvos = rastreador.atualizar([det(62, 0), det(2, 0)], 1)
    assert alvos[1].centro[0] == pytest.approx(det(2, 0).centro[0])
    assert alvos[2].centro[0] == pytest.approx(det(62, 0).centro[0])


def test_cada_deteccao_alimenta_no_maximo_um_alvo():
    """Dois alvos não podem se agarrar à mesma detecção."""
    rastreador = Rastreador(distancia_maxima=200.0)
    rastreador.atualizar([det(0, 0), det(20, 0)], 0)
    alvos = rastreador.atualizar([det(10, 0)], 1)
    atualizados = [a for a in alvos.values() if a.sumido_ha == 0]
    assert len(atualizados) == 1


# --------------------------------------------------------------------------
# Sumiço e envelhecimento
# --------------------------------------------------------------------------


@pytest.mark.parametrize('tolerancia', range(0, 15))
def test_alvo_sobrevive_ate_a_tolerancia(tolerancia):
    rastreador = Rastreador(tolerancia_sumico=tolerancia)
    rastreador.atualizar([det(100, 100)], 0)
    for i in range(tolerancia):
        rastreador.atualizar([], i + 1)
    assert 1 in rastreador.alvos


@pytest.mark.parametrize('tolerancia', range(0, 15))
def test_alvo_morre_depois_da_tolerancia(tolerancia):
    rastreador = Rastreador(tolerancia_sumico=tolerancia)
    rastreador.atualizar([det(100, 100)], 0)
    for i in range(tolerancia + 1):
        rastreador.atualizar([], i + 1)
    assert 1 not in rastreador.alvos


@pytest.mark.parametrize('sumico', range(1, 8))
def test_alvo_que_volta_dentro_da_tolerancia_conserva_o_id(sumico):
    """É o veículo que passa atrás de um poste. Voltar como alvo novo o contaria duas vezes."""
    rastreador = Rastreador(distancia_maxima=200.0, tolerancia_sumico=10)
    rastreador.atualizar([det(100, 100)], 0)
    for i in range(sumico):
        rastreador.atualizar([], i + 1)
    alvos = rastreador.atualizar([det(120, 100)], sumico + 1)
    assert list(alvos) == [1]


def test_sumido_ha_zera_quando_o_alvo_reaparece():
    rastreador = Rastreador(tolerancia_sumico=10)
    rastreador.atualizar([det(100, 100)], 0)
    rastreador.atualizar([], 1)
    rastreador.atualizar([], 2)
    assert rastreador.alvos[1].sumido_ha == 2
    rastreador.atualizar([det(105, 100)], 3)
    assert rastreador.alvos[1].sumido_ha == 0


# --------------------------------------------------------------------------
# Trajetória
# --------------------------------------------------------------------------


@pytest.mark.parametrize('passos', range(1, 30))
def test_trajetoria_acumula_um_ponto_por_quadro(passos):
    rastreador = Rastreador(distancia_maxima=100.0, historico_trajetoria=1000)
    for i in range(passos):
        rastreador.atualizar([det(100 + i * 10, 100)], i)
    assert len(rastreador.alvos[1].trajetoria) == passos


@pytest.mark.parametrize('limite', range(2, 20))
def test_trajetoria_nao_passa_do_limite(limite):
    """Vídeo de horas com o histórico solto acabaria com a memória da máquina."""
    rastreador = Rastreador(distancia_maxima=100.0, historico_trajetoria=limite)
    for i in range(limite + 25):
        rastreador.atualizar([det(100 + i * 5, 100)], i)
    alvo = rastreador.alvos[1]
    assert len(alvo.trajetoria) == limite
    assert len(alvo.indices) == limite


@pytest.mark.parametrize('passos', range(2, 25))
def test_indices_acompanham_a_trajetoria_ponto_a_ponto(passos):
    """A velocidade depende de cada ponto saber de que quadro veio."""
    rastreador = Rastreador(distancia_maxima=100.0, historico_trajetoria=1000)
    for i in range(passos):
        rastreador.atualizar([det(100 + i * 6, 100)], i * 3)
    alvo = rastreador.alvos[1]
    assert alvo.indices == [i * 3 for i in range(passos)]


def test_indices_registram_o_buraco_do_sumico():
    """Quando o objeto some e volta, os quadros pulados não podem virar pontos."""
    rastreador = Rastreador(distancia_maxima=200.0, tolerancia_sumico=10)
    rastreador.atualizar([det(100, 100)], 0)
    for i in range(1, 5):
        rastreador.atualizar([], i)
    rastreador.atualizar([det(150, 100)], 5)
    assert rastreador.alvos[1].indices == [0, 5]


@pytest.mark.parametrize('area_grande', [800, 1500, 4000, 9000])
def test_area_do_alvo_guarda_a_maior_ja_vista(area_grande):
    """O objeto aparece recortado ao entrar no quadro; o porte é o do meio."""
    rastreador = Rastreador(distancia_maxima=100.0)
    rastreador.atualizar([Deteccao(0, 0, 40, 30, 300)], 0)
    rastreador.atualizar([Deteccao(5, 0, 40, 30, area_grande)], 1)
    rastreador.atualizar([Deteccao(10, 0, 40, 30, 200)], 2)
    assert rastreador.alvos[1].area == area_grande


# --------------------------------------------------------------------------
# Reinício
# --------------------------------------------------------------------------


def test_reiniciar_esvazia_e_recomeça_a_numeração():
    rastreador = Rastreador()
    rastreador.atualizar([det(0, 0), det(100, 0)], 0)
    rastreador.reiniciar()
    assert rastreador.alvos == {}
    alvos = rastreador.atualizar([det(0, 0)], 0)
    assert list(alvos) == [1]


def test_atualizar_sem_deteccoes_e_sem_alvos_nao_quebra():
    assert Rastreador().atualizar([], 0) == {}
