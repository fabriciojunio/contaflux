"""Anotação visual do que o sistema entendeu."""

from __future__ import annotations

import numpy as np
import pytest

from contaflux.contagem import Contagem, Linha
from contaflux.desenho import (
    anotar,
    desenhar_alvos,
    desenhar_linha,
    desenhar_painel,
    lado_a_lado,
)
from contaflux.rastreio import Alvo

LINHA = Linha(320, 60, 320, 300)


@pytest.fixture
def quadro():
    return np.full((360, 640, 3), 96, dtype=np.uint8)


def alvo(identificador=1, x=200, y=150, contado=False, pontos=6):
    trajetoria = [(x - i * 5.0, float(y)) for i in range(pontos)]
    return Alvo(
        identificador,
        (float(x), float(y)),
        (x - 30, y - 20, 60, 40),
        trajetoria,
        list(range(pontos)),
        contado=contado,
    )


# --------------------------------------------------------------------------
# Linha
# --------------------------------------------------------------------------


def test_desenhar_linha_marca_a_imagem(quadro):
    original = quadro.copy()
    desenhar_linha(quadro, LINHA)
    assert not np.array_equal(quadro, original)


@pytest.mark.parametrize(
    'linha',
    [
        Linha(320, 60, 320, 300),
        Linha(0, 180, 640, 180),
        Linha(10, 10, 630, 350),
        Linha(630, 10, 10, 350),
    ],
)
def test_qualquer_orientacao_e_desenhada(quadro, linha):
    desenhar_linha(quadro, linha)
    assert quadro.sum() != np.full((360, 640, 3), 96, dtype=np.uint8).sum()


def test_linha_fora_do_quadro_nao_quebra(quadro):
    """Coordenada fora da imagem é entrada de usuário válida e não pode derrubar."""
    desenhar_linha(quadro, Linha(-500, -500, 5000, 5000))


# --------------------------------------------------------------------------
# Alvos
# --------------------------------------------------------------------------


def test_alvo_e_desenhado(quadro):
    original = quadro.copy()
    desenhar_alvos(quadro, {1: alvo()})
    assert not np.array_equal(quadro, original)


@pytest.mark.parametrize('quantidade', range(1, 8))
def test_varios_alvos_sao_desenhados(quantidade, quadro):
    alvos = {i: alvo(i, x=60 + i * 70) for i in range(1, quantidade + 1)}
    desenhar_alvos(quadro, alvos)
    assert quadro.std() > 0


def test_alvo_contado_muda_de_cor(quadro):
    """Ver a caixa mudar de cor é como se confere a contagem sem olhar o número."""
    normal = quadro.copy()
    desenhar_alvos(normal, {1: alvo(contado=False)})
    contado = quadro.copy()
    desenhar_alvos(contado, {1: alvo(contado=True)})
    assert not np.array_equal(normal, contado)


def test_rotulo_personalizado_e_usado(quadro):
    com_rotulo = quadro.copy()
    desenhar_alvos(com_rotulo, {1: alvo()}, rotulos={1: 'caminhão 82 km/h'})
    sem_rotulo = quadro.copy()
    desenhar_alvos(sem_rotulo, {1: alvo()})
    assert not np.array_equal(com_rotulo, sem_rotulo)


def test_trajetoria_pode_ser_desligada(quadro):
    com = quadro.copy()
    desenhar_alvos(com, {1: alvo(pontos=20)}, trajetoria=True)
    sem = quadro.copy()
    desenhar_alvos(sem, {1: alvo(pontos=20)}, trajetoria=False)
    assert not np.array_equal(com, sem)


def test_alvo_com_um_ponto_so_nao_quebra(quadro):
    desenhar_alvos(quadro, {1: alvo(pontos=1)})


def test_alvo_colado_no_topo_nao_quebra(quadro):
    """A etiqueta vai acima da caixa e precisa caber mesmo com y igual a zero."""
    desenhar_alvos(quadro, {1: alvo(y=2)})


def test_sem_alvos_a_imagem_fica_intacta(quadro):
    original = quadro.copy()
    desenhar_alvos(quadro, {})
    assert np.array_equal(quadro, original)


# --------------------------------------------------------------------------
# Painel
# --------------------------------------------------------------------------


def test_painel_e_desenhado(quadro):
    original = quadro.copy()
    desenhar_painel(quadro, Contagem(entradas=3, saidas=2))
    assert not np.array_equal(quadro, original)


@pytest.mark.parametrize('entradas', range(0, 6))
@pytest.mark.parametrize('saidas', range(0, 6))
def test_painel_aceita_qualquer_contagem(entradas, saidas, quadro):
    desenhar_painel(quadro, Contagem(entradas=entradas, saidas=saidas))


def test_painel_aceita_linhas_extras(quadro):
    com = quadro.copy()
    desenhar_painel(com, Contagem(), extras=['média: 74 km/h', 'aprendendo o fundo...'])
    sem = quadro.copy()
    desenhar_painel(sem, Contagem())
    assert not np.array_equal(com, sem)


def test_painel_com_rotulos_acentuados(quadro):
    desenhar_painel(quadro, Contagem(), rotulo_positivo='saídas', rotulo_negativo='entradas')


# --------------------------------------------------------------------------
# anotar
# --------------------------------------------------------------------------


def test_anotar_nao_altera_o_original(quadro):
    """A gravação e a janela usam a mesma imagem; alterar no lugar acumularia rastro."""
    copia = quadro.copy()
    anotar(quadro, LINHA, {1: alvo()}, Contagem(entradas=1))
    assert np.array_equal(quadro, copia)


def test_anotar_preserva_o_formato(quadro):
    saida = anotar(quadro, LINHA, {1: alvo()}, Contagem())
    assert saida.shape == quadro.shape
    assert saida.dtype == quadro.dtype


def test_anotar_desenha_alguma_coisa(quadro):
    saida = anotar(quadro, LINHA, {1: alvo()}, Contagem(entradas=1))
    assert not np.array_equal(saida, quadro)


def test_anotar_sem_alvos_ainda_desenha_linha_e_painel(quadro):
    saida = anotar(quadro, LINHA, {}, Contagem())
    assert not np.array_equal(saida, quadro)


# --------------------------------------------------------------------------
# lado_a_lado
# --------------------------------------------------------------------------


def test_lado_a_lado_dobra_a_largura(quadro):
    mascara = np.zeros((360, 640), dtype=np.uint8)
    assert lado_a_lado(quadro, mascara).shape == (360, 1280, 3)


def test_lado_a_lado_converte_mascara_para_cor(quadro):
    mascara = np.full((360, 640), 255, dtype=np.uint8)
    assert lado_a_lado(quadro, mascara).ndim == 3


def test_lado_a_lado_redimensiona_mascara_de_outro_tamanho(quadro):
    """A máscara pode vir de um quadro reduzido; empilhar sem ajustar quebraria."""
    mascara = np.zeros((180, 320), dtype=np.uint8)
    assert lado_a_lado(quadro, mascara).shape == (360, 1280, 3)


def test_lado_a_lado_aceita_mascara_ja_colorida(quadro):
    mascara = np.zeros((360, 640, 3), dtype=np.uint8)
    assert lado_a_lado(quadro, mascara).shape == (360, 1280, 3)


# --------------------------------------------------------------------------
# Acentos na tela
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    'com_acento,esperado',
    [
        ('caminhão', 'caminhao'),
        ('ônibus', 'onibus'),
        ('veículos', 'veiculos'),
        ('saídas', 'saidas'),
        ('média: 74 km/h', 'media: 74 km/h'),
        ('carro', 'carro'),
    ],
)
def test_acento_e_removido_para_desenhar(com_acento, esperado):
    """A escrita do OpenCV só desenha ASCII, e "caminhão" saía como "caminh??o".

    O acento cai só na hora de desenhar. Relatório, CSV e JSON continuam com a
    grafia certa, e há testes desses formatos exigindo o acento.
    """
    from contaflux.desenho import sem_acento

    assert sem_acento(com_acento) == esperado


def test_etiqueta_acentuada_nao_quebra_o_desenho(quadro):
    from contaflux.desenho import desenhar_alvos

    desenhar_alvos(quadro, {1: alvo()}, rotulos={1: '#1 caminhão 82 km/h'})


def test_painel_com_rotulo_acentuado_nao_quebra(quadro):
    from contaflux.desenho import desenhar_painel

    desenhar_painel(quadro, Contagem(entradas=2), rotulo_positivo='saídas')
