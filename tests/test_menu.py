"""O menu de vídeos."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from contaflux.menu import escolher_video, interpretar_escolha, montar_menu


def criar(pasta: Path, *nomes: str) -> Path:
    for nome in nomes:
        (pasta / nome).write_bytes(b'x')
    return pasta


def respostas(*textos):
    """Simula alguém digitando, um texto por chamada."""
    fila = list(textos)

    def perguntar(_pergunta=''):
        if not fila:
            raise EOFError
        return fila.pop(0)

    return perguntar


# --------------------------------------------------------------------------
# interpretar_escolha
# --------------------------------------------------------------------------


@pytest.mark.parametrize('digitado', ['1', '2', '5', '10'])
def test_numero_valido_e_aceito(digitado):
    assert interpretar_escolha(digitado, 10) == int(digitado)


@pytest.mark.parametrize('digitado', ['  3  ', '3\n', '\t3'])
def test_espacos_em_volta_sao_ignorados(digitado):
    assert interpretar_escolha(digitado, 10) == 3


@pytest.mark.parametrize('digitado', ['', 'q', 'Q', 'sair', 'x', '  '])
def test_pedidos_de_sair(digitado):
    assert interpretar_escolha(digitado, 10) is None


@pytest.mark.parametrize('digitado', ['abc', '1.5', '2a', '-'])
def test_texto_que_nao_e_numero_e_recusado(digitado):
    with pytest.raises(ValueError, match='número'):
        interpretar_escolha(digitado, 10)


@pytest.mark.parametrize('digitado', ['0', '11', '99'])
def test_numero_fora_da_lista_e_recusado(digitado):
    with pytest.raises(ValueError, match='Escolha de 1 a 10'):
        interpretar_escolha(digitado, 10)


def test_a_mensagem_de_erro_diz_o_intervalo():
    with pytest.raises(ValueError) as erro:
        interpretar_escolha('7', 3)
    assert '1 a 3' in str(erro.value)


# --------------------------------------------------------------------------
# montar_menu
# --------------------------------------------------------------------------


def test_menu_vazio_e_texto_vazio():
    assert montar_menu([]) == ''


def test_menu_numera_a_partir_de_um(tmp_path):
    criar(tmp_path, 'a.mp4', 'b.mp4')
    texto = montar_menu(sorted(tmp_path.glob('*.mp4')))
    assert '1.' in texto
    assert '2.' in texto
    assert '0.' not in texto


@pytest.mark.parametrize('quantidade', range(1, 8))
def test_menu_lista_todos(tmp_path, quantidade):
    criar(tmp_path, *[f'video_{i}.mp4' for i in range(quantidade)])
    texto = montar_menu(sorted(tmp_path.glob('*.mp4')))
    assert texto.count('.mp4') == quantidade


# --------------------------------------------------------------------------
# escolher_video
# --------------------------------------------------------------------------


def test_pasta_sem_video_ensina_o_que_fazer(tmp_path):
    """Mensagem só dizendo "vazio" deixa a pessoa travada."""
    saida = io.StringIO()
    assert escolher_video(str(tmp_path), entrada=respostas(), saida=saida) is None
    texto = saida.getvalue()
    assert 'baixar_videos.py' in texto
    assert 'Nenhum vídeo' in texto


def test_escolha_valida_devolve_o_arquivo(tmp_path):
    criar(tmp_path, 'a.mp4', 'b.mp4')
    escolhido = escolher_video(str(tmp_path), entrada=respostas('2'), saida=io.StringIO())
    assert escolhido.name == 'b.mp4'


def test_escolha_invalida_pergunta_de_novo(tmp_path):
    criar(tmp_path, 'a.mp4')
    saida = io.StringIO()
    escolhido = escolher_video(
        str(tmp_path), entrada=respostas('abc', '9', '1'), saida=saida
    )
    assert escolhido.name == 'a.mp4'
    assert saida.getvalue().count('número') >= 1


def test_sair_devolve_nada(tmp_path):
    criar(tmp_path, 'a.mp4')
    assert escolher_video(str(tmp_path), entrada=respostas('q'), saida=io.StringIO()) is None


def test_encerrar_a_entrada_devolve_nada(tmp_path):
    """Ctrl+C ou fim de entrada não pode virar exceção na cara do usuário."""
    criar(tmp_path, 'a.mp4')
    assert escolher_video(str(tmp_path), entrada=respostas(), saida=io.StringIO()) is None
