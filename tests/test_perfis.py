"""Os perfis de calibração."""

from __future__ import annotations

import pytest

from contaflux.perfis import PADRAO, PERFIS, RODOVIA, URBANO, Perfil, obter


@pytest.mark.parametrize('nome', sorted(PERFIS))
def test_obter_devolve_o_perfil_pelo_nome(nome):
    assert obter(nome).nome == nome


@pytest.mark.parametrize('nome', ['RODOVIA', 'Rodovia', '  rodovia  ', 'URBANO'])
def test_obter_ignora_caixa_e_espacos(nome):
    """Quem digita na linha de comando erra a caixa o tempo todo."""
    assert obter(nome).nome == nome.strip().lower()


@pytest.mark.parametrize('nome', ['pessoas', 'moto', '', 'rodovías', 'urbanos'])
def test_perfil_desconhecido_lista_os_disponiveis(nome):
    """A mensagem de erro precisa dizer o que fazer, não só que deu errado."""
    with pytest.raises(ValueError) as erro:
        obter(nome)
    assert 'rodovia' in str(erro.value)
    assert 'urbano' in str(erro.value)


def test_o_perfil_padrao_e_o_de_rodovia():
    assert PADRAO is RODOVIA


@pytest.mark.parametrize('perfil', list(PERFIS.values()))
def test_area_minima_e_positiva(perfil: Perfil):
    assert perfil.area_minima > 0


@pytest.mark.parametrize('perfil', list(PERFIS.values()))
def test_proporcao_maxima_permite_objeto_quadrado(perfil: Perfil):
    """Proporção abaixo de um barraria tudo, inclusive o objeto quadrado."""
    assert perfil.proporcao_maxima > 1.0


@pytest.mark.parametrize('perfil', list(PERFIS.values()))
def test_distancia_maxima_e_positiva(perfil: Perfil):
    assert perfil.distancia_maxima > 0


@pytest.mark.parametrize('perfil', list(PERFIS.values()))
def test_quadros_minimos_permite_ao_menos_uma_travessia(perfil: Perfil):
    assert perfil.quadros_minimos >= 1


@pytest.mark.parametrize('perfil', list(PERFIS.values()))
def test_tolerancia_de_sumico_nao_e_negativa(perfil: Perfil):
    assert perfil.tolerancia_sumico >= 0


@pytest.mark.parametrize('perfil', list(PERFIS.values()))
def test_historico_de_fundo_e_suficiente_para_aprender(perfil: Perfil):
    assert perfil.historico_fundo >= 100


@pytest.mark.parametrize('perfil', list(PERFIS.values()))
def test_limiar_de_variancia_e_positivo(perfil: Perfil):
    assert perfil.limiar_variancia > 0


@pytest.mark.parametrize('perfil', list(PERFIS.values()))
def test_faixas_de_porte_sao_crescentes(perfil: Perfil):
    assert perfil.faixas.ate_moto < perfil.faixas.ate_carro


@pytest.mark.parametrize('perfil', list(PERFIS.values()))
def test_rotulos_de_sentido_sao_distintos(perfil: Perfil):
    """Rótulos iguais fariam o placar mostrar a mesma coisa duas vezes."""
    assert perfil.rotulo_positivo != perfil.rotulo_negativo


@pytest.mark.parametrize('perfil', list(PERFIS.values()))
def test_perfil_tem_descricao(perfil: Perfil):
    assert perfil.descricao.strip()


@pytest.mark.parametrize('perfil', list(PERFIS.values()))
def test_perfil_e_imutavel(perfil: Perfil):
    """Perfil compartilhado e mutável viraria calibração mudando sozinha."""
    with pytest.raises(AttributeError):
        perfil.area_minima = 1


def test_urbano_e_mais_exigente_que_rodovia():
    """Câmera mais perto, objeto maior, e menos deslocamento entre quadros."""
    assert URBANO.area_minima > RODOVIA.area_minima
    assert URBANO.distancia_maxima < RODOVIA.distancia_maxima


def test_urbano_tolera_mais_oclusao():
    """Poste, placa e outro carro escondem o veículo o tempo todo na cidade."""
    assert URBANO.tolerancia_sumico > RODOVIA.tolerancia_sumico


def test_faixas_do_urbano_sao_maiores():
    """O mesmo carro ocupa mais pixels numa câmera mais baixa."""
    assert URBANO.faixas.ate_moto > RODOVIA.faixas.ate_moto
    assert URBANO.faixas.ate_carro > RODOVIA.faixas.ate_carro


def test_os_nomes_do_dicionario_batem_com_os_dos_perfis():
    assert all(chave == perfil.nome for chave, perfil in PERFIS.items())
