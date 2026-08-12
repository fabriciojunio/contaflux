"""Classificação de porte pelo tamanho na imagem."""

from __future__ import annotations

import pytest

from contaflux.porte import (
    CAMINHAO,
    CARRO,
    DESCONHECIDO,
    MOTO,
    FaixasDePorte,
    contar_por_classe,
)

FAIXAS = FaixasDePorte(ate_moto=1400, ate_carro=4200)


# --------------------------------------------------------------------------
# Construção
# --------------------------------------------------------------------------


@pytest.mark.parametrize('ate_moto', [0, -1, -500])
def test_limite_de_moto_precisa_ser_positivo(ate_moto):
    with pytest.raises(ValueError, match='moto'):
        FaixasDePorte(ate_moto=ate_moto, ate_carro=4200)


@pytest.mark.parametrize('ate_carro', [1400, 1399, 500, 1])
def test_limite_de_carro_precisa_superar_o_de_moto(ate_carro):
    """Faixas invertidas tornariam a classe do meio inalcançável, em silêncio."""
    with pytest.raises(ValueError, match='carro'):
        FaixasDePorte(ate_moto=1400, ate_carro=ate_carro)


@pytest.mark.parametrize('ate_moto,ate_carro', [(1, 2), (100, 200), (1400, 4200), (5, 90_000)])
def test_faixas_validas_sao_aceitas(ate_moto, ate_carro):
    faixas = FaixasDePorte(ate_moto=ate_moto, ate_carro=ate_carro)
    assert faixas.ate_moto < faixas.ate_carro


# --------------------------------------------------------------------------
# Classificação
# --------------------------------------------------------------------------


@pytest.mark.parametrize('area', range(1, 1401, 40))
def test_area_pequena_e_moto(area):
    assert FAIXAS.classificar(area) == MOTO


@pytest.mark.parametrize('area', range(1401, 4201, 70))
def test_area_media_e_carro(area):
    assert FAIXAS.classificar(area) == CARRO


@pytest.mark.parametrize('area', range(4201, 30_000, 700))
def test_area_grande_e_caminhao(area):
    assert FAIXAS.classificar(area) == CAMINHAO


@pytest.mark.parametrize('area', [0, -1, -50, -100_000])
def test_area_invalida_vira_desconhecido(area):
    """Melhor admitir que não sabe do que chutar uma classe."""
    assert FAIXAS.classificar(area) == DESCONHECIDO


def test_limites_pertencem_a_classe_de_baixo():
    """A borda precisa cair de um lado só, e o contrato é o de baixo."""
    assert FAIXAS.classificar(FAIXAS.ate_moto) == MOTO
    assert FAIXAS.classificar(FAIXAS.ate_moto + 1) == CARRO
    assert FAIXAS.classificar(FAIXAS.ate_carro) == CARRO
    assert FAIXAS.classificar(FAIXAS.ate_carro + 1) == CAMINHAO


@pytest.mark.parametrize('area', range(1, 20_000, 250))
def test_classificacao_e_sempre_uma_das_classes_conhecidas(area):
    assert FAIXAS.classificar(area) in {MOTO, CARRO, CAMINHAO, DESCONHECIDO}


@pytest.mark.parametrize('area', range(1, 20_000, 313))
def test_classificacao_e_monotona(area):
    """Área maior nunca pode descer de classe."""
    ordem = {MOTO: 0, CARRO: 1, CAMINHAO: 2}
    assert ordem[FAIXAS.classificar(area)] <= ordem[FAIXAS.classificar(area + 1000)]


@pytest.mark.parametrize('area', range(1, 12_000, 401))
def test_faixas_mais_largas_nunca_classificam_para_cima(area):
    """Subir os limites só pode empurrar objetos para classes menores."""
    largas = FaixasDePorte(ate_moto=2800, ate_carro=8400)
    ordem = {MOTO: 0, CARRO: 1, CAMINHAO: 2}
    assert ordem[largas.classificar(area)] <= ordem[FAIXAS.classificar(area)]


# --------------------------------------------------------------------------
# Totais
# --------------------------------------------------------------------------


def test_totais_trazem_todas_as_chaves_mesmo_zeradas():
    """Formato fixo evita quebrar a planilha de quem consome o relatório."""
    totais = contar_por_classe([])
    assert set(totais) == {MOTO, CARRO, CAMINHAO, DESCONHECIDO}
    assert set(totais.values()) == {0}


@pytest.mark.parametrize('motos', range(0, 8))
@pytest.mark.parametrize('carros', range(0, 8))
def test_totais_somam_por_classe(motos, carros):
    totais = contar_por_classe([MOTO] * motos + [CARRO] * carros)
    assert totais[MOTO] == motos
    assert totais[CARRO] == carros
    assert totais[CAMINHAO] == 0


@pytest.mark.parametrize('n', range(1, 25))
def test_soma_dos_totais_e_o_tamanho_da_lista(n):
    classes = [FAIXAS.classificar(i * 400 + 1) for i in range(n)]
    assert sum(contar_por_classe(classes).values()) == n


def test_classe_inesperada_e_contada_em_vez_de_derrubar():
    """Relatório de vídeo de duas horas não pode morrer por causa de um rótulo novo."""
    totais = contar_por_classe(['ônibus', 'ônibus', CARRO])
    assert totais['ônibus'] == 2
    assert totais[CARRO] == 1
