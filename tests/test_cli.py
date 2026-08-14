"""A linha de comando."""

from __future__ import annotations

import io
import json

import pytest

from contaflux import __version__
from contaflux.cli import (
    analisar_linha,
    construir_parser,
    executar,
    main,
    pasta_ao_lado_do_executavel,
    pasta_para_menu_automatico,
    preparar_console,
    salvar_cena_de_demonstracao,
)
from contaflux.contagem import Linha
from contaflux.video import FonteDeVideo, FonteIndisponivel


def argumentos(*extras):
    """Argumentos de demonstração pequena, sem janela, para rodar rápido."""
    base = ['--sem-janela', '--demo-veiculos', '3', *extras]
    return construir_parser().parse_args(base)


# --------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------


def test_sem_argumentos_a_fonte_e_a_demonstracao():
    """Quem recebe o programa roda ele antes de ter um vídeo na mão."""
    assert construir_parser().parse_args([]).fonte == 'demo'


@pytest.mark.parametrize('fonte', ['video.mp4', '0', '1', 'C:/pasta/rodovia.avi'])
def test_a_fonte_e_lida_como_posicional(fonte):
    assert construir_parser().parse_args([fonte]).fonte == fonte


@pytest.mark.parametrize('perfil', ['rodovia', 'urbano'])
def test_perfis_validos_sao_aceitos(perfil):
    assert construir_parser().parse_args(['--perfil', perfil]).perfil == perfil


def test_perfil_invalido_e_recusado_pelo_parser():
    with pytest.raises(SystemExit):
        construir_parser().parse_args(['--perfil', 'pessoas'])


def test_o_perfil_padrao_e_rodovia():
    assert construir_parser().parse_args([]).perfil == 'rodovia'


@pytest.mark.parametrize(
    'opcao,atributo',
    [
        ('--sem-janela', 'sem_janela'),
        ('--mascara', 'mascara'),
    ],
)
def test_opcoes_de_liga_desliga(opcao, atributo):
    parser = construir_parser()
    assert getattr(parser.parse_args([]), atributo) is False
    assert getattr(parser.parse_args([opcao]), atributo) is True


@pytest.mark.parametrize('largura', [320, 640, 960, 1280])
def test_largura_de_processamento(largura):
    assert construir_parser().parse_args(['--largura', str(largura)]).largura == largura


@pytest.mark.parametrize('metros', ['10', '25.5', '40'])
def test_metros_visiveis_vira_numero(metros):
    assert construir_parser().parse_args(['--metros', metros]).metros == float(metros)


def test_versao_encerra_o_programa(capsys):
    with pytest.raises(SystemExit) as saida:
        construir_parser().parse_args(['--versao'])
    assert saida.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_a_ajuda_mostra_exemplos(capsys):
    with pytest.raises(SystemExit):
        construir_parser().parse_args(['--ajuda-inexistente'])
    parser = construir_parser()
    assert 'exemplos' in parser.format_help()


# --------------------------------------------------------------------------
# analisar_linha
# --------------------------------------------------------------------------


def test_sem_linha_o_padrao_e_uma_vertical_no_meio():
    """A maioria das câmeras de via filma o trânsito passando de lado."""
    linha = analisar_linha(None, 640, 360)
    assert linha.x1 == linha.x2 == 320
    assert linha.y1 < linha.y2


@pytest.mark.parametrize('largura,altura', [(320, 240), (640, 360), (1920, 1080)])
def test_a_linha_padrao_acompanha_o_tamanho_do_quadro(largura, altura):
    linha = analisar_linha(None, largura, altura)
    assert linha.x1 == largura / 2
    assert 0 < linha.y1 < linha.y2 < altura


@pytest.mark.parametrize(
    'texto,esperada',
    [
        ('10,20,30,40', Linha(10, 20, 30, 40)),
        ('0,0,100,0', Linha(0, 0, 100, 0)),
        ('10;20;30;40', Linha(10, 20, 30, 40)),
        (' 10 , 20 , 30 , 40 ', Linha(10, 20, 30, 40)),
        ('1.5,2.5,3.5,4.5', Linha(1.5, 2.5, 3.5, 4.5)),
        ('-10,-20,30,40', Linha(-10, -20, 30, 40)),
    ],
)
def test_linha_informada_e_interpretada(texto, esperada):
    assert analisar_linha(texto, 640, 360) == esperada


@pytest.mark.parametrize('texto', ['1,2,3', '1,2', '1', '1,2,3,4,5', ''])
def test_linha_com_numero_errado_de_valores_e_recusada(texto):
    if texto == '':
        assert analisar_linha(texto, 640, 360).x1 == 320
        return
    with pytest.raises(ValueError, match='quatro números'):
        analisar_linha(texto, 640, 360)


@pytest.mark.parametrize('texto', ['a,b,c,d', '1,2,3,x', 'dez,20,30,40'])
def test_coordenada_nao_numerica_e_recusada(texto):
    with pytest.raises(ValueError, match='inválida'):
        analisar_linha(texto, 640, 360)


@pytest.mark.parametrize('texto', ['5,5,5,5', '0,0,0,0', '-3,7,-3,7'])
def test_linha_de_comprimento_zero_e_recusada(texto):
    """Sem comprimento não há trecho, e nada seria contado, em silêncio."""
    with pytest.raises(ValueError, match='iguais'):
        analisar_linha(texto, 640, 360)


# --------------------------------------------------------------------------
# Execução da demonstração
# --------------------------------------------------------------------------


@pytest.mark.lento
def test_demonstracao_conta_o_esperado():
    saida = io.StringIO()
    relatorio = executar(argumentos(), saida=saida)
    assert relatorio.total > 0
    assert 'Conferência com o gabarito' in saida.getvalue()
    assert 'exato' in saida.getvalue()


@pytest.mark.lento
def test_demonstracao_grava_csv(tmp_path):
    destino = tmp_path / 'saida.csv'
    executar(argumentos('--csv', str(destino)), saida=io.StringIO())
    linhas = destino.read_text(encoding='utf-8').strip().splitlines()
    assert len(linhas) > 1


@pytest.mark.lento
def test_demonstracao_grava_json(tmp_path):
    destino = tmp_path / 'saida.json'
    executar(argumentos('--json', str(destino)), saida=io.StringIO())
    dados = json.loads(destino.read_text(encoding='utf-8'))
    assert dados['total'] > 0
    assert dados['fonte'] == 'demonstração'


@pytest.mark.lento
def test_demonstracao_grava_video_anotado(tmp_path):
    destino = tmp_path / 'anotado.mp4'
    executar(argumentos('--gravar', str(destino)), saida=io.StringIO())
    assert destino.exists()
    assert destino.stat().st_size > 0


@pytest.mark.lento
def test_metros_visiveis_ligam_a_velocidade():
    saida = io.StringIO()
    relatorio = executar(argumentos('--metros', '30'), saida=saida)
    assert relatorio.velocidade_media is not None
    assert 'Velocidade média' in saida.getvalue()


@pytest.mark.lento
def test_sem_metros_nao_ha_velocidade():
    relatorio = executar(argumentos(), saida=io.StringIO())
    assert relatorio.velocidade_media is None


@pytest.mark.lento
@pytest.mark.parametrize('perfil', ['rodovia', 'urbano'])
def test_a_demonstracao_roda_nos_dois_perfis(perfil):
    relatorio = executar(argumentos('--perfil', perfil), saida=io.StringIO())
    assert relatorio.total > 0


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


@pytest.mark.lento
def test_main_devolve_zero_quando_da_certo():
    assert main(['--sem-janela', '--demo-veiculos', '2']) == 0


# --------------------------------------------------------------------------
# Gravar a cena de demonstração como vídeo
# --------------------------------------------------------------------------


@pytest.mark.lento
def test_salvar_demo_grava_video_que_abre_de_volta(tmp_path):
    """É o caminho que permite exercitar o modo de arquivo sem filmar uma rodovia."""
    destino = tmp_path / 'rodovia.mp4'
    argumentos = construir_parser().parse_args(
        ['--salvar-demo', str(destino), '--demo-veiculos', '3']
    )
    salvar_cena_de_demonstracao(argumentos, saida=io.StringIO())

    assert destino.exists()
    with FonteDeVideo(str(destino)) as fonte:
        assert len(list(fonte.quadros())) > 100


@pytest.mark.lento
def test_salvar_demo_cria_a_pasta_que_faltar(tmp_path):
    destino = tmp_path / 'a' / 'b' / 'rodovia.mp4'
    argumentos = construir_parser().parse_args(
        ['--salvar-demo', str(destino), '--demo-veiculos', '2']
    )
    assert salvar_cena_de_demonstracao(argumentos, saida=io.StringIO()).exists()


@pytest.mark.lento
def test_salvar_demo_encerra_sem_contar(tmp_path, capsys):
    destino = tmp_path / 'rodovia.mp4'
    assert main(['--salvar-demo', str(destino), '--demo-veiculos', '2']) == 0
    assert 'Total de veículos' not in capsys.readouterr().out


@pytest.mark.lento
def test_o_video_gravado_e_contado_com_o_numero_certo(tmp_path):
    """Ida e volta completa: grava a cena, lê de novo do disco e conta.

    É o teste mais próximo do uso real que dá para fazer sem uma rodovia: o
    vídeo passa por compressão com perda antes de ser contado, exatamente como
    um arquivo vindo de celular.
    """
    destino = tmp_path / 'rodovia.mp4'
    gravar = construir_parser().parse_args(
        ['--salvar-demo', str(destino), '--demo-veiculos', '6']
    )
    salvar_cena_de_demonstracao(gravar, saida=io.StringIO())

    contar = construir_parser().parse_args([str(destino), '--sem-janela'])
    relatorio = executar(contar, saida=io.StringIO())
    assert relatorio.total == 6


def test_main_avisa_quando_o_arquivo_nao_existe(capsys):
    assert main(['nao_existe_mesmo.mp4', '--sem-janela']) == 1
    assert 'Erro' in capsys.readouterr().err


def test_main_avisa_quando_a_linha_e_invalida(capsys):
    assert main(['--sem-janela', '--linha', '1,2,3']) == 1
    assert 'quatro números' in capsys.readouterr().err


def test_fonte_inexistente_levanta_erro_tratado():
    with pytest.raises(FonteIndisponivel):
        executar(construir_parser().parse_args(['nao_existe.mp4', '--sem-janela']))


def test_preparar_console_nao_quebra_em_nenhum_sistema():
    """Ele mexe em detalhe de console do Windows e precisa ser inofensivo fora dele."""
    preparar_console()
    preparar_console()


# --------------------------------------------------------------------------
# Abrir o executável com dois cliques
# --------------------------------------------------------------------------


def empacotado(monkeypatch, executavel, argv=None):
    """Finge que estamos rodando pelo executável, e não pelo Python."""
    monkeypatch.setattr('sys.frozen', True, raising=False)
    monkeypatch.setattr('sys.executable', str(executavel))
    monkeypatch.setattr('sys.argv', argv or [str(executavel)])


def test_a_pasta_de_videos_e_procurada_ao_lado_do_executavel(monkeypatch, tmp_path):
    """Dois cliques não deixam o diretório atual na pasta do programa."""
    empacotado(monkeypatch, tmp_path / 'Contaflux.exe')
    assert pasta_ao_lado_do_executavel('videos') == str(tmp_path / 'videos')


def test_pasta_absoluta_e_respeitada_como_veio(monkeypatch, tmp_path):
    empacotado(monkeypatch, tmp_path / 'Contaflux.exe')
    absoluta = str(tmp_path / 'outra')
    assert pasta_ao_lado_do_executavel(absoluta) == absoluta


def test_executavel_aberto_sem_argumento_oferece_os_videos_da_pasta(monkeypatch, tmp_path):
    """Quem já copiou os vídeos quer contá-los, não ver a cena sintética."""
    empacotado(monkeypatch, tmp_path / 'Contaflux.exe')
    videos = tmp_path / 'videos'
    videos.mkdir()
    (videos / 'rodovia.mp4').write_bytes(b'')

    assert pasta_para_menu_automatico(construir_parser().parse_args([])) == str(videos)


def test_sem_video_ao_lado_do_executavel_a_demonstracao_continua(monkeypatch, tmp_path):
    empacotado(monkeypatch, tmp_path / 'Contaflux.exe')
    assert pasta_para_menu_automatico(construir_parser().parse_args([])) is None


def test_pasta_de_videos_vazia_tambem_cai_na_demonstracao(monkeypatch, tmp_path):
    empacotado(monkeypatch, tmp_path / 'Contaflux.exe')
    (tmp_path / 'videos').mkdir()
    assert pasta_para_menu_automatico(construir_parser().parse_args([])) is None


def test_executavel_com_argumento_nao_abre_o_menu(monkeypatch, tmp_path):
    """`Contaflux.exe --sem-janela --csv saida.csv` precisa continuar em lote."""
    executavel = tmp_path / 'Contaflux.exe'
    empacotado(monkeypatch, executavel, argv=[str(executavel), '--sem-janela'])
    videos = tmp_path / 'videos'
    videos.mkdir()
    (videos / 'rodovia.mp4').write_bytes(b'')

    argumentos = construir_parser().parse_args(['--sem-janela'])
    assert pasta_para_menu_automatico(argumentos) is None


def test_rodando_pelo_python_sem_argumento_continua_na_demonstracao(monkeypatch, tmp_path):
    """Pelo Python, `contaflux` sem argumento é a demonstração, como documentado."""
    monkeypatch.setattr('sys.frozen', False, raising=False)
    monkeypatch.chdir(tmp_path)
    videos = tmp_path / 'videos'
    videos.mkdir()
    (videos / 'rodovia.mp4').write_bytes(b'')

    assert pasta_para_menu_automatico(construir_parser().parse_args([])) is None
