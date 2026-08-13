"""Escolha do vídeo e desenho da linha com o mouse."""

from __future__ import annotations

import numpy as np
import pytest

from contaflux.contagem import Linha
from contaflux.selecao import (
    EXTENSOES,
    EstadoDoDesenho,
    desenhar_previa,
    descrever,
    listar_videos,
    primeiro_quadro_util,
)


@pytest.fixture
def quadro():
    return np.full((360, 640, 3), 90, dtype=np.uint8)


def criar(pasta, *nomes):
    for nome in nomes:
        (pasta / nome).write_bytes(b'nao e video de verdade')
    return pasta


# --------------------------------------------------------------------------
# listar_videos
# --------------------------------------------------------------------------


def test_pasta_inexistente_devolve_lista_vazia(tmp_path):
    assert listar_videos(tmp_path / 'nao_existe') == []


def test_pasta_vazia_devolve_lista_vazia(tmp_path):
    assert listar_videos(tmp_path) == []


@pytest.mark.parametrize('extensao', EXTENSOES)
def test_reconhece_cada_extensao_suportada(tmp_path, extensao):
    criar(tmp_path, f'video{extensao}')
    assert len(listar_videos(tmp_path)) == 1


@pytest.mark.parametrize('extensao', ['.txt', '.png', '.csv', '.json', '.zip'])
def test_ignora_o_que_nao_e_video(tmp_path, extensao):
    criar(tmp_path, f'arquivo{extensao}')
    assert listar_videos(tmp_path) == []


@pytest.mark.parametrize('extensao', ['.MP4', '.Avi', '.MKV'])
def test_extensao_em_maiuscula_tambem_vale(tmp_path, extensao):
    criar(tmp_path, f'video{extensao}')
    assert len(listar_videos(tmp_path)) == 1


def test_ordem_e_alfabetica():
    """O número que o tutorial manda digitar precisa ser o mesmo em qualquer máquina."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as pasta:
        criar(Path(pasta), 'c.mp4', 'a.mp4', 'B.mp4')
        assert [v.name for v in listar_videos(pasta)] == ['a.mp4', 'B.mp4', 'c.mp4']


def test_ignora_subpastas(tmp_path):
    (tmp_path / 'uma_pasta.mp4').mkdir()
    assert listar_videos(tmp_path) == []


# --------------------------------------------------------------------------
# descrever
# --------------------------------------------------------------------------


def test_descrever_arquivo_quebrado_avisa(tmp_path):
    """Vídeo corrompido não pode derrubar o menu inteiro."""
    criar(tmp_path, 'quebrado.mp4')
    texto = descrever(tmp_path / 'quebrado.mp4')
    assert 'quebrado.mp4' in texto
    assert 'não foi possível abrir' in texto


# --------------------------------------------------------------------------
# EstadoDoDesenho
# --------------------------------------------------------------------------


def test_estado_nasce_vazio():
    estado = EstadoDoDesenho()
    assert estado.pontos == []
    assert estado.completo is False
    assert estado.como_linha() is None


def test_um_clique_nao_forma_linha():
    estado = EstadoDoDesenho()
    estado.clicar(10, 20)
    assert estado.completo is False
    assert estado.como_linha() is None


def test_dois_cliques_formam_a_linha():
    estado = EstadoDoDesenho()
    estado.clicar(10, 20)
    estado.clicar(30, 40)
    assert estado.completo is True
    assert estado.como_linha() == Linha(10.0, 20.0, 30.0, 40.0)


def test_o_terceiro_clique_recomeca():
    """Sem isso, quem errasse o segundo ponto teria que fechar a janela."""
    estado = EstadoDoDesenho()
    estado.clicar(10, 20)
    estado.clicar(30, 40)
    estado.clicar(99, 99)
    assert estado.pontos == [(99, 99)]
    assert estado.completo is False


def test_limpar_apaga_os_pontos():
    estado = EstadoDoDesenho()
    estado.clicar(10, 20)
    estado.clicar(30, 40)
    estado.limpar()
    assert estado.pontos == []


def test_dois_cliques_no_mesmo_lugar_nao_viram_linha():
    """Linha de comprimento zero não conta nada, e em silêncio."""
    estado = EstadoDoDesenho()
    estado.clicar(50, 50)
    estado.clicar(50, 50)
    assert estado.como_linha() is None


@pytest.mark.parametrize('x1,y1,x2,y2', [(0, 0, 5, 5), (100, 0, 0, 100), (7, 9, 7, 300)])
def test_a_linha_guarda_os_pontos_clicados(x1, y1, x2, y2):
    estado = EstadoDoDesenho()
    estado.clicar(x1, y1)
    estado.clicar(x2, y2)
    assert estado.como_linha() == Linha(float(x1), float(y1), float(x2), float(y2))


# --------------------------------------------------------------------------
# desenhar_previa
# --------------------------------------------------------------------------


def test_previa_nao_altera_o_quadro(quadro):
    copia = quadro.copy()
    estado = EstadoDoDesenho()
    estado.clicar(10, 10)
    desenhar_previa(quadro, estado)
    assert np.array_equal(quadro, copia)


def test_previa_sem_cliques_ainda_mostra_instrucao(quadro):
    saida = desenhar_previa(quadro, EstadoDoDesenho())
    assert not np.array_equal(saida, quadro)


def test_previa_marca_o_ponto_clicado(quadro):
    estado = EstadoDoDesenho()
    estado.clicar(300, 200)
    assert not np.array_equal(desenhar_previa(quadro, estado), quadro)


def test_previa_acompanha_o_cursor(quadro):
    """A linha seguindo o mouse evita clicar, ver que ficou torta e recomeçar."""
    com_cursor = EstadoDoDesenho()
    com_cursor.clicar(100, 100)
    com_cursor.cursor = (400, 300)

    sem_cursor = EstadoDoDesenho()
    sem_cursor.clicar(100, 100)

    assert not np.array_equal(
        desenhar_previa(quadro, com_cursor), desenhar_previa(quadro, sem_cursor)
    )


def test_previa_com_linha_pronta_muda_a_instrucao(quadro):
    meio = EstadoDoDesenho()
    meio.clicar(100, 100)

    pronta = EstadoDoDesenho()
    pronta.clicar(100, 100)
    pronta.clicar(500, 300)

    assert not np.array_equal(
        desenhar_previa(quadro, meio), desenhar_previa(quadro, pronta)
    )


def test_previa_preserva_formato(quadro):
    estado = EstadoDoDesenho()
    estado.clicar(1, 1)
    estado.clicar(2, 2)
    saida = desenhar_previa(quadro, estado)
    assert saida.shape == quadro.shape
    assert saida.dtype == quadro.dtype


# --------------------------------------------------------------------------
# primeiro_quadro_util
# --------------------------------------------------------------------------


def test_arquivo_invalido_devolve_nada(tmp_path):
    criar(tmp_path, 'quebrado.mp4')
    assert primeiro_quadro_util(tmp_path / 'quebrado.mp4') is None


def test_arquivo_inexistente_devolve_nada(tmp_path):
    assert primeiro_quadro_util(tmp_path / 'nao_existe.mp4') is None
