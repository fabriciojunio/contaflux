"""O baixador da coleção de vídeos.

A rede não é tocada em nenhum destes testes. Teste que baixa de verdade falha
quando a internet cai, quando o servidor muda de endereço e quando alguém roda
a suíte no avião, e nenhuma dessas falhas diz nada sobre o código.
"""

from __future__ import annotations

import io
import sys
import urllib.error
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import baixar_videos as bv  # noqa: E402


@pytest.fixture
def pasta(tmp_path, monkeypatch):
    monkeypatch.setattr(bv, 'PASTA', tmp_path)
    return tmp_path


class RespostaFalsa:
    """Imita o objeto devolvido por urlopen, entregando o conteúdo em pedaços."""

    def __init__(self, conteudo: bytes) -> None:
        self._restante = conteudo

    def read(self, quantidade: int) -> bytes:
        pedaco, self._restante = self._restante[:quantidade], self._restante[quantidade:]
        return pedaco

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def responder(monkeypatch, conteudo: bytes):
    monkeypatch.setattr(bv.urllib.request, 'urlopen', lambda *_a, **_k: RespostaFalsa(conteudo))


def falhar(monkeypatch, erro: Exception):
    def explodir(*_a, **_k):
        raise erro

    monkeypatch.setattr(bv.urllib.request, 'urlopen', explodir)


# --------------------------------------------------------------------------
# A coleção
# --------------------------------------------------------------------------


def test_a_colecao_tem_dez_videos():
    assert len(bv.COLECAO) == 10


def test_os_nomes_sao_unicos():
    """Nome repetido faria um vídeo sobrescrever o outro em silêncio."""
    nomes = [v.nome for v in bv.COLECAO]
    assert len(nomes) == len(set(nomes))


def test_as_origens_sao_unicas():
    caminhos = [v.caminho_remoto for v in bv.COLECAO]
    assert len(caminhos) == len(set(caminhos))


@pytest.mark.parametrize('video', bv.COLECAO, ids=lambda v: v.nome)
def test_cada_video_tem_descricao(video):
    assert video.descricao.strip()


@pytest.mark.parametrize('video', bv.COLECAO, ids=lambda v: v.nome)
def test_a_url_aponta_para_o_pixabay(video):
    assert video.url.startswith('https://cdn.pixabay.com/video/')
    assert video.url.endswith('.mp4')


@pytest.mark.parametrize('video', bv.COLECAO, ids=lambda v: v.nome)
def test_o_destino_e_um_mp4_com_o_nome_do_video(video):
    assert video.destino.name == f'{video.nome}.mp4'


def test_os_nomes_comecam_com_numero_para_ordenar():
    """O menu lista em ordem alfabética, e o número é o que a mantém previsível."""
    assert all(v.nome[:2].isdigit() for v in bv.COLECAO)


# --------------------------------------------------------------------------
# Download
# --------------------------------------------------------------------------


def test_baixa_e_grava_o_arquivo(pasta, monkeypatch):
    responder(monkeypatch, b'x' * 200_000)
    ok, mensagem = bv.baixar(bv.COLECAO[0])
    assert ok
    assert 'baixado' in mensagem
    assert bv.COLECAO[0].destino.stat().st_size == 200_000


def test_nao_baixa_de_novo_o_que_ja_existe(pasta, monkeypatch):
    """Rodar o script duas vezes não pode custar centenas de megabytes."""
    bv.COLECAO[0].destino.write_bytes(b'y' * 200_000)
    falhar(monkeypatch, AssertionError('não deveria ter tentado baixar'))

    ok, mensagem = bv.baixar(bv.COLECAO[0])
    assert ok
    assert 'já existe' in mensagem


def test_forcar_baixa_por_cima(pasta, monkeypatch):
    bv.COLECAO[0].destino.write_bytes(b'antigo')
    responder(monkeypatch, b'z' * 200_000)

    ok, _ = bv.baixar(bv.COLECAO[0], forcar=True)
    assert ok
    assert bv.COLECAO[0].destino.stat().st_size == 200_000


def test_erro_de_rede_nao_deixa_arquivo_pela_metade(pasta, monkeypatch):
    """Arquivo truncado seria considerado pronto na próxima execução."""
    falhar(monkeypatch, urllib.error.URLError('sem rede'))

    ok, mensagem = bv.baixar(bv.COLECAO[0])
    assert not ok
    assert 'falhou' in mensagem
    assert not bv.COLECAO[0].destino.exists()
    assert list(pasta.glob('*.parcial')) == []


def test_resposta_pequena_demais_e_recusada(pasta, monkeypatch):
    """Página de erro do servidor chega como HTML de poucos kilobytes."""
    responder(monkeypatch, b'<html>404</html>')

    ok, mensagem = bv.baixar(bv.COLECAO[0])
    assert not ok
    assert 'pequeno demais' in mensagem
    assert not bv.COLECAO[0].destino.exists()


def test_cria_a_pasta_se_nao_existir(tmp_path, monkeypatch):
    destino = tmp_path / 'ainda' / 'nao' / 'existe'
    monkeypatch.setattr(bv, 'PASTA', destino)
    responder(monkeypatch, b'x' * 200_000)

    ok, _ = bv.baixar(bv.COLECAO[0])
    assert ok
    assert destino.is_dir()


# --------------------------------------------------------------------------
# A coleção inteira
# --------------------------------------------------------------------------


def test_baixar_colecao_sem_falhas(pasta, monkeypatch):
    responder(monkeypatch, b'x' * 200_000)
    saida = io.StringIO()

    assert bv.baixar_colecao(saida=saida) == 0
    assert len(list(pasta.glob('*.mp4'))) == len(bv.COLECAO)
    assert 'Todos prontos' in saida.getvalue()


def test_baixar_colecao_conta_as_falhas(pasta, monkeypatch):
    falhar(monkeypatch, urllib.error.URLError('sem rede'))
    saida = io.StringIO()

    assert bv.baixar_colecao(saida=saida) == len(bv.COLECAO)
    assert 'não vieram' in saida.getvalue()


def test_a_mensagem_de_falha_ensina_o_que_fazer(pasta, monkeypatch):
    falhar(monkeypatch, urllib.error.URLError('sem rede'))
    saida = io.StringIO()
    bv.baixar_colecao(saida=saida)

    texto = saida.getvalue()
    assert 'Rode de novo' in texto
    assert 'seus próprios vídeos' in texto
