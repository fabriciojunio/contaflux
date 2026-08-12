"""Leitura de vídeo de arquivo.

Os testes usam um vídeo escrito na hora, e não um arquivo guardado no
repositório. Vídeo versionado envelhece: muda de codec, incha o clone e um dia
para de abrir na máquina de outra pessoa.
"""

from __future__ import annotations

import numpy as np
import pytest

from contaflux.cena import GeradorDeCena, ParametrosCena, veiculos_regulares
from contaflux.video import (
    BACKENDS_DE_CAMERA,
    FonteDeVideo,
    FonteIndisponivel,
    gravar,
)


@pytest.fixture(scope='module')
def video(tmp_path_factory):
    destino = tmp_path_factory.mktemp('video') / 'cena.mp4'
    parametros = ParametrosCena(quadros=40, largura=320, altura=240)
    parametros.veiculos = veiculos_regulares(2, parametros, semente=1)
    GeradorDeCena(parametros).gravar(str(destino))
    return destino


# --------------------------------------------------------------------------
# Abertura
# --------------------------------------------------------------------------


def test_abre_arquivo_existente(video):
    with FonteDeVideo(str(video)) as fonte:
        assert fonte.info.largura == 320


def test_arquivo_inexistente_diz_o_caminho(tmp_path):
    """Erro de caminho é o mais comum de todos, e a mensagem precisa ajudar."""
    faltando = tmp_path / 'nao_existe.mp4'
    with pytest.raises(FonteIndisponivel, match='não encontrado'):
        FonteDeVideo(str(faltando))


def test_arquivo_que_nao_e_video_e_recusado(tmp_path):
    texto = tmp_path / 'nao_e_video.mp4'
    texto.write_text('isto não é um vídeo', encoding='utf-8')
    with pytest.raises(FonteIndisponivel):
        FonteDeVideo(str(texto))


# --------------------------------------------------------------------------
# Informações
# --------------------------------------------------------------------------


def test_info_traz_tamanho_e_taxa(video):
    with FonteDeVideo(str(video)) as fonte:
        info = fonte.info
        assert (info.largura, info.altura) == (320, 240)
        assert info.fps > 0
        assert info.total_de_quadros > 0


@pytest.mark.parametrize('largura_alvo', [80, 160, 240])
def test_info_reflete_o_redimensionamento(video, largura_alvo):
    with FonteDeVideo(str(video), redimensionar_para=largura_alvo) as fonte:
        assert fonte.info.largura == largura_alvo


def test_redimensionar_preserva_a_proporcao(video):
    with FonteDeVideo(str(video), redimensionar_para=160) as fonte:
        info = fonte.info
        assert info.altura == pytest.approx(120, abs=1)


def test_nao_amplia_video_menor_que_o_alvo(video):
    """Ampliar não inventa detalhe, só gasta processamento."""
    with FonteDeVideo(str(video), redimensionar_para=1920) as fonte:
        assert fonte.info.largura == 320


# --------------------------------------------------------------------------
# Leitura de quadros
# --------------------------------------------------------------------------


def test_le_todos_os_quadros(video):
    with FonteDeVideo(str(video)) as fonte:
        assert len(list(fonte.quadros())) >= 35


def test_quadros_tem_o_formato_esperado(video):
    with FonteDeVideo(str(video)) as fonte:
        quadro = next(iter(fonte.quadros()))
    assert quadro.shape == (240, 320, 3)
    assert quadro.dtype == np.uint8


@pytest.mark.parametrize('largura_alvo', [80, 160])
def test_quadros_saem_redimensionados(video, largura_alvo):
    with FonteDeVideo(str(video), redimensionar_para=largura_alvo) as fonte:
        quadro = next(iter(fonte.quadros()))
    assert quadro.shape[1] == largura_alvo


def test_a_sequencia_termina_sozinha(video):
    with FonteDeVideo(str(video)) as fonte:
        primeira = len(list(fonte.quadros()))
        segunda = len(list(fonte.quadros()))
    assert primeira > 0
    assert segunda == 0


def test_liberar_pode_ser_chamado_duas_vezes(video):
    fonte = FonteDeVideo(str(video))
    fonte.liberar()
    fonte.liberar()


def test_arquivo_e_marcado_como_tal(video):
    """A interface avisa por qual backend a câmera abriu, e arquivo não tem backend."""
    with FonteDeVideo(str(video)) as fonte:
        assert fonte.backend == 'arquivo'


# --------------------------------------------------------------------------
# Câmera
# --------------------------------------------------------------------------


def test_a_ordem_dos_backends_tenta_o_directshow_antes_do_padrao():
    """A ordem importa: muitas webcams abrem no Media Foundation e não dão quadro."""
    nomes = [nome for nome, _ in BACKENDS_DE_CAMERA]
    assert nomes.index('DirectShow') < nomes.index('padrão do sistema')


def test_cada_backend_tem_nome_legivel():
    """O nome vai para a tela quando a câmera falha, e precisa dizer algo a quem lê."""
    assert all(isinstance(nome, str) and nome for nome, _ in BACKENDS_DE_CAMERA)


class CapturaFalsa:
    """Substitui a captura do OpenCV para testar a cascata sem hardware.

    A primeira versão destes testes abria a câmera de verdade num índice alto,
    esperando falhar. Foi um erro caro: sondar dispositivo inexistente no
    Windows chega a travar por vários minutos, e uma execução da suíte inteira
    ficou meia hora parada num único teste. Além disso o resultado dependeria de
    quantas câmeras a máquina tem, o que é o oposto de teste.
    """

    def __init__(self, abre: bool, entrega_quadro: bool) -> None:
        self._abre = abre
        self._entrega = entrega_quadro
        self.liberada = False

    def isOpened(self):  # noqa: N802 - o nome é o da API do OpenCV
        return self._abre

    def read(self):
        if not self._entrega:
            return False, None
        return True, np.zeros((240, 320, 3), dtype=np.uint8)

    def release(self):
        self.liberada = True

    def get(self, _propriedade):
        return 0.0


def instalar_capturas(monkeypatch, comportamentos):
    """Faz cada abertura de captura devolver o próximo comportamento da lista."""
    criadas = []

    def fabricar(_origem, _backend=None):
        abre, entrega = comportamentos[len(criadas)]
        captura = CapturaFalsa(abre, entrega)
        criadas.append(captura)
        return captura

    monkeypatch.setattr('contaflux.video.cv2.VideoCapture', fabricar)
    monkeypatch.setattr('contaflux.video.sys.platform', 'win32')
    return criadas


def test_camera_que_nao_abre_em_nenhum_backend_explica_o_que_tentou(monkeypatch):
    """Mensagem genérica deixa a pessoa sem saber se é permissão ou hardware."""
    instalar_capturas(monkeypatch, [(False, False)] * 3)

    with pytest.raises(FonteIndisponivel) as erro:
        FonteDeVideo('0')

    mensagem = str(erro.value)
    assert 'câmera 0' in mensagem
    assert 'Tentativas' in mensagem
    for nome, _ in BACKENDS_DE_CAMERA:
        assert nome in mensagem


def test_backend_que_abre_mas_nao_entrega_quadro_e_recusado(monkeypatch):
    """É o caso real: a webcam abre, a luz acende e a imagem nunca vem."""
    instalar_capturas(monkeypatch, [(True, False), (True, True)])

    fonte = FonteDeVideo('0')
    assert fonte.backend == 'DirectShow'


def test_o_primeiro_backend_que_funciona_e_o_escolhido(monkeypatch):
    instalar_capturas(monkeypatch, [(True, True)])
    assert FonteDeVideo('0').backend == 'Media Foundation'


def test_backend_recusado_e_liberado(monkeypatch):
    """Captura aberta e abandonada deixa a câmera ocupada para o resto do sistema."""
    criadas = instalar_capturas(monkeypatch, [(True, False), (True, True)])
    FonteDeVideo('0')
    assert criadas[0].liberada is True
    assert criadas[1].liberada is False


def test_todos_os_backends_sao_tentados_antes_de_desistir(monkeypatch):
    criadas = instalar_capturas(monkeypatch, [(False, False)] * 3)
    with pytest.raises(FonteIndisponivel):
        FonteDeVideo('0')
    assert len(criadas) == len(BACKENDS_DE_CAMERA)


# --------------------------------------------------------------------------
# Gravação
# --------------------------------------------------------------------------


@pytest.mark.parametrize('quantidade', [1, 5, 20])
def test_gravar_escreve_a_quantidade_pedida(tmp_path, quantidade):
    quadros = [np.full((120, 160, 3), 100, dtype=np.uint8) for _ in range(quantidade)]
    escritos = gravar(quadros, str(tmp_path / 'saida.mp4'), 25.0, (160, 120))
    assert escritos == quantidade


def test_gravar_produz_arquivo_que_abre_de_volta(tmp_path):
    destino = tmp_path / 'ida_e_volta.mp4'
    quadros = [np.full((120, 160, 3), 100, dtype=np.uint8) for _ in range(12)]
    gravar(quadros, str(destino), 25.0, (160, 120))

    with FonteDeVideo(str(destino)) as fonte:
        assert len(list(fonte.quadros())) >= 10


def test_gravar_em_caminho_invalido_avisa(tmp_path):
    with pytest.raises(FonteIndisponivel):
        gravar([], str(tmp_path / 'sem' / 'pasta' / 'x.mp4'), 25.0, (160, 120))
