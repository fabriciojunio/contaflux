"""O gerador de cenas.

Testar o gerador parece rodeio, mas não é: ele é o gabarito de todo o resto.
Se `travessias_esperadas` errar, os testes de contagem passam a comparar dois
números errados e param de valer alguma coisa.
"""

from __future__ import annotations

import numpy as np
import pytest

from contaflux.cena import (
    CAMINHAO,
    CARRO,
    MOTO,
    GeradorDeCena,
    ParametrosCena,
    Veiculo,
    veiculos_regulares,
    veiculos_variados,
)


def veiculo(entrada=0, y=100, largura=50, altura=30, velocidade=5.0, sentido=1) -> Veiculo:
    return Veiculo(entrada, y, largura, altura, velocidade, (200, 100, 50), sentido)


# --------------------------------------------------------------------------
# Veiculo.posicao
# --------------------------------------------------------------------------


@pytest.mark.parametrize('quadro', range(-10, 0))
def test_antes_de_entrar_nao_ha_posicao(quadro):
    assert veiculo(entrada=0).posicao(quadro, 640) is None


def test_no_quadro_de_entrada_o_veiculo_esta_encostado_na_borda():
    """Ele começa fora da tela, para entrar aparecendo aos poucos."""
    assert veiculo(entrada=5, largura=50).posicao(5, 640) == -50


@pytest.mark.parametrize('passos', range(0, 40))
def test_posicao_avanca_a_velocidade_constante(passos):
    v = veiculo(entrada=0, largura=50, velocidade=6.0)
    assert v.posicao(passos, 640) == pytest.approx(-50 + passos * 6.0)


@pytest.mark.parametrize('velocidade', [1.0, 2.5, 5.0, 9.0, 15.0])
def test_velocidade_maior_chega_antes(velocidade):
    lento = veiculo(velocidade=1.0).posicao(20, 640)
    rapido = veiculo(velocidade=velocidade).posicao(20, 640)
    assert rapido >= lento


def test_depois_de_sair_pela_direita_nao_ha_posicao():
    v = veiculo(entrada=0, largura=50, velocidade=10.0)
    assert v.posicao(200, 640) is None


def test_sentido_negativo_comeca_na_direita():
    assert veiculo(entrada=0, sentido=-1).posicao(0, 640) == 640


@pytest.mark.parametrize('passos', range(0, 40))
def test_sentido_negativo_recua(passos):
    v = veiculo(entrada=0, velocidade=6.0, sentido=-1)
    assert v.posicao(passos, 640) == pytest.approx(640 - passos * 6.0)


def test_depois_de_sair_pela_esquerda_nao_ha_posicao():
    v = veiculo(entrada=0, largura=50, velocidade=10.0, sentido=-1)
    assert v.posicao(200, 640) is None


@pytest.mark.parametrize('sentido', [1, -1])
@pytest.mark.parametrize('largura_cena', [320, 640, 1280])
def test_o_veiculo_atravessa_a_cena_inteira(sentido, largura_cena):
    v = veiculo(entrada=0, largura=40, velocidade=5.0, sentido=sentido)
    posicoes = [
        p for i in range(400) if (p := v.posicao(i, largura_cena)) is not None
    ]
    assert min(posicoes) <= 0
    assert max(posicoes) + 40 >= largura_cena


# --------------------------------------------------------------------------
# Geradores de veículos
# --------------------------------------------------------------------------


@pytest.mark.parametrize('quantidade', range(0, 20))
def test_gerador_regular_produz_a_quantidade_pedida(quantidade):
    p = ParametrosCena()
    assert len(veiculos_regulares(quantidade, p, semente=1)) == quantidade


@pytest.mark.parametrize('intervalo', [10, 20, 26, 40])
def test_entradas_sao_espacadas_pelo_intervalo(intervalo):
    p = ParametrosCena()
    veiculos = veiculos_regulares(6, p, intervalo=intervalo, semente=1)
    entradas = [v.entrada_quadro for v in veiculos]
    assert all(b - a == intervalo for a, b in zip(entradas, entradas[1:]))


@pytest.mark.parametrize('semente', range(1, 12))
def test_a_mesma_semente_gera_os_mesmos_veiculos(semente):
    p = ParametrosCena()
    assert veiculos_regulares(5, p, semente=semente) == veiculos_regulares(
        5, p, semente=semente
    )


def test_sementes_diferentes_geram_veiculos_diferentes():
    p = ParametrosCena()
    assert veiculos_regulares(5, p, semente=1) != veiculos_regulares(5, p, semente=2)


def test_veiculos_regulares_usam_tres_faixas():
    """Faixas distintas são o que faz a sombra de um encostar no outro."""
    p = ParametrosCena()
    veiculos = veiculos_regulares(9, p, semente=1)
    assert len({v.y + v.altura // 2 for v in veiculos}) == 3


@pytest.mark.parametrize('porte', [MOTO, CARRO, CAMINHAO])
def test_gerador_variado_respeita_o_porte_pedido(porte):
    p = ParametrosCena()
    veiculos = veiculos_variados([porte] * 5, p, semente=1)
    assert all(v.porte == porte for v in veiculos)


def test_portes_tem_tamanhos_crescentes():
    p = ParametrosCena()
    areas = {}
    for porte in (MOTO, CARRO, CAMINHAO):
        veiculos = veiculos_variados([porte] * 6, p, semente=3)
        areas[porte] = sum(v.largura * v.altura for v in veiculos) / 6
    assert areas[MOTO] < areas[CARRO] < areas[CAMINHAO]


def test_porte_desconhecido_e_recusado():
    with pytest.raises(ValueError, match='Porte desconhecido'):
        veiculos_variados(['trator'], ParametrosCena(), semente=1)


def test_gerador_variado_aceita_lista_vazia():
    assert veiculos_variados([], ParametrosCena(), semente=1) == []


# --------------------------------------------------------------------------
# Desenho dos quadros
# --------------------------------------------------------------------------


def test_quadro_tem_o_tamanho_pedido():
    cena = GeradorDeCena(ParametrosCena(largura=320, altura=240))
    assert cena.quadro(0).shape == (240, 320, 3)


def test_quadro_e_de_bytes():
    """Vídeo é uint8; float vazaria para o OpenCV e quebraria lá na frente."""
    assert GeradorDeCena(ParametrosCena()).quadro(0).dtype == np.uint8


@pytest.mark.parametrize('indice', range(0, 60, 6))
def test_o_mesmo_indice_gera_sempre_o_mesmo_quadro(indice):
    """Sem isso, nenhuma falha de contagem poderia ser reproduzida."""
    uma = GeradorDeCena(ParametrosCena(semente=9)).quadro(indice)
    outra = GeradorDeCena(ParametrosCena(semente=9)).quadro(indice)
    assert np.array_equal(uma, outra)


def test_o_veiculo_muda_a_imagem():
    p = ParametrosCena(ruido=0.0)
    vazia = GeradorDeCena(p).quadro(60)
    p.veiculos = [veiculo(entrada=0, velocidade=5.0)]
    com_veiculo = GeradorDeCena(p).quadro(60)
    assert not np.array_equal(vazia, com_veiculo)


def test_ruido_zero_deixa_o_fundo_estavel():
    cena = GeradorDeCena(ParametrosCena(ruido=0.0))
    assert np.array_equal(cena.quadro(0), cena.quadro(30))


def test_ruido_faz_os_quadros_diferirem():
    cena = GeradorDeCena(ParametrosCena(ruido=6.0))
    assert not np.array_equal(cena.quadro(0), cena.quadro(1))


@pytest.mark.parametrize('oscilacao', [0.05, 0.1, 0.2])
def test_oscilacao_de_luz_muda_o_brilho_medio(oscilacao):
    cena = GeradorDeCena(ParametrosCena(ruido=0.0, oscilacao_luz=oscilacao))
    brilhos = [float(cena.quadro(i).mean()) for i in range(0, 60, 5)]
    assert max(brilhos) - min(brilhos) > 3.0


def test_sombra_escurece_a_regiao_abaixo_do_veiculo():
    p = ParametrosCena(ruido=0.0, sombra=True)
    p.veiculos = [veiculo(entrada=0, y=150, largura=60, altura=30, velocidade=5.0)]
    com = GeradorDeCena(p).quadro(40)

    p_sem = ParametrosCena(ruido=0.0, sombra=False)
    p_sem.veiculos = p.veiculos
    sem = GeradorDeCena(p_sem).quadro(40)

    faixa = slice(182, 190)
    assert com[faixa].mean() < sem[faixa].mean()


@pytest.mark.parametrize('quantidade', range(1, 8))
def test_quadros_produz_a_sequencia_completa(quantidade):
    cena = GeradorDeCena(ParametrosCena(quadros=quantidade))
    assert len(list(cena.quadros())) == quantidade


# --------------------------------------------------------------------------
# Gabarito
# --------------------------------------------------------------------------


@pytest.mark.parametrize('quantidade', range(0, 13))
def test_todos_cruzam_quando_ha_tempo_de_sobra(quantidade):
    p = ParametrosCena(quadros=900)
    p.veiculos = veiculos_regulares(quantidade, p, semente=quantidade + 1)
    assert GeradorDeCena(p).travessias_esperadas(320.0) == quantidade


def test_quem_entra_tarde_demais_nao_entra_no_gabarito():
    """Contar como esperado quem não chegou à linha tornaria o gabarito errado."""
    p = ParametrosCena(quadros=120)
    p.veiculos = [veiculo(entrada=0, velocidade=6.0), veiculo(entrada=110, velocidade=6.0)]
    assert GeradorDeCena(p).travessias_esperadas(320.0) == 1


@pytest.mark.parametrize('x', [100, 200, 320, 450, 600])
def test_o_gabarito_nao_depende_de_onde_a_linha_esta(x):
    """Todos atravessam a cena inteira, então cruzam qualquer vertical."""
    p = ParametrosCena(quadros=900)
    p.veiculos = veiculos_regulares(6, p, semente=5)
    assert GeradorDeCena(p).travessias_esperadas(float(x)) == 6


def test_linha_fora_da_cena_nao_e_cruzada():
    p = ParametrosCena(quadros=900)
    p.veiculos = veiculos_regulares(6, p, semente=5)
    assert GeradorDeCena(p).travessias_esperadas(5000.0) == 0


def test_quem_cruza_vem_na_ordem_da_travessia():
    p = ParametrosCena(quadros=900)
    p.veiculos = veiculos_regulares(6, p, semente=5)
    cena = GeradorDeCena(p)
    ordem = cena.quem_cruza(320.0)
    assert [v.entrada_quadro for v in ordem] == sorted(v.entrada_quadro for v in ordem)


def test_quem_cruza_e_consistente_com_a_contagem_esperada():
    p = ParametrosCena(quadros=460)
    p.veiculos = veiculos_regulares(9, p, semente=6)
    cena = GeradorDeCena(p)
    assert len(cena.quem_cruza(320.0)) == cena.travessias_esperadas(320.0)


@pytest.mark.parametrize('sentido', [1, -1])
def test_o_gabarito_vale_nos_dois_sentidos(sentido):
    p = ParametrosCena(quadros=900)
    p.veiculos = veiculos_regulares(5, p, sentido=sentido, semente=4)
    assert GeradorDeCena(p).travessias_esperadas(320.0) == 5


def test_cena_sem_veiculos_tem_gabarito_zero():
    assert GeradorDeCena(ParametrosCena()).travessias_esperadas(320.0) == 0


def test_gravar_cria_arquivo_de_video(tmp_path):
    destino = tmp_path / 'cena.mp4'
    p = ParametrosCena(quadros=20)
    p.veiculos = veiculos_regulares(2, p, semente=1)
    GeradorDeCena(p).gravar(str(destino))
    assert destino.exists()
    assert destino.stat().st_size > 0
