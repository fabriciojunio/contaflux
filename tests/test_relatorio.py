"""Agregação e exportação dos resultados."""

from __future__ import annotations

import csv
import json

import pytest

from contaflux.relatorio import Passagem, Relatorio


def passagem(identificador=1, quadro=100, sentido='sentido A', classe='carro', kmh=60.0):
    return Passagem(identificador, quadro, sentido, quadro / 25.0, classe, kmh)


# --------------------------------------------------------------------------
# Passagem
# --------------------------------------------------------------------------


@pytest.mark.parametrize('identificador', range(1, 15))
def test_linha_traz_o_identificador(identificador):
    assert passagem(identificador=identificador).como_linha()['id'] == identificador


@pytest.mark.parametrize('segundo', [0.0, 1.234, 12.567, 99.999])
def test_segundo_e_arredondado_para_duas_casas(segundo):
    p = Passagem(1, 0, 'sentido A', segundo)
    assert p.como_linha()['segundo'] == round(segundo, 2)


@pytest.mark.parametrize('kmh', [0.0, 33.33, 61.55, 128.9])
def test_velocidade_e_arredondada_para_uma_casa(kmh):
    assert passagem(kmh=kmh).como_linha()['velocidade_kmh'] == round(kmh, 1)


def test_velocidade_ausente_vira_celula_vazia():
    """Célula vazia é o que a planilha entende. Zero seria lido como parado."""
    assert passagem(kmh=None).como_linha()['velocidade_kmh'] == ''


def test_classe_padrao_e_desconhecida():
    assert Passagem(1, 0, 'sentido A', 0.0).classe == 'desconhecido'


def test_linha_tem_sempre_as_mesmas_colunas():
    esperadas = {'id', 'quadro', 'segundo', 'sentido', 'classe', 'velocidade_kmh'}
    assert set(passagem().como_linha()) == esperadas


# --------------------------------------------------------------------------
# Agregações
# --------------------------------------------------------------------------


@pytest.mark.parametrize('n', range(0, 20))
def test_total_e_o_numero_de_passagens(n):
    r = Relatorio('teste', passagens=[passagem(i) for i in range(n)])
    assert r.total == n


@pytest.mark.parametrize('a', range(0, 8))
@pytest.mark.parametrize('b', range(0, 8))
def test_totais_por_sentido(a, b):
    passagens = [passagem(sentido='sentido A') for _ in range(a)]
    passagens += [passagem(sentido='sentido B') for _ in range(b)]
    r = Relatorio('teste', passagens=passagens)
    assert r.por_sentido.get('sentido A', 0) == a
    assert r.por_sentido.get('sentido B', 0) == b


@pytest.mark.parametrize('motos', range(0, 6))
@pytest.mark.parametrize('caminhoes', range(0, 6))
def test_totais_por_classe(motos, caminhoes):
    passagens = [passagem(classe='moto') for _ in range(motos)]
    passagens += [passagem(classe='caminhão') for _ in range(caminhoes)]
    r = Relatorio('teste', passagens=passagens)
    assert r.por_classe.get('moto', 0) == motos
    assert r.por_classe.get('caminhão', 0) == caminhoes


def test_relatorio_vazio_nao_tem_agregados():
    r = Relatorio('teste')
    assert r.total == 0
    assert r.por_sentido == {}
    assert r.por_classe == {}
    assert r.velocidade_media is None


@pytest.mark.parametrize(
    'velocidades,esperada',
    [
        ([60.0], 60.0),
        ([50.0, 70.0], 60.0),
        ([40.0, 50.0, 60.0], 50.0),
        ([10.0, 20.0, 30.0, 40.0], 25.0),
    ],
)
def test_velocidade_media(velocidades, esperada):
    r = Relatorio('teste', passagens=[passagem(kmh=v) for v in velocidades])
    assert r.velocidade_media == pytest.approx(esperada)


def test_velocidade_media_ignora_as_nao_medidas():
    """Tratar não medido como zero puxaria a média para baixo em silêncio."""
    r = Relatorio('teste', passagens=[passagem(kmh=80.0), passagem(kmh=None)])
    assert r.velocidade_media == pytest.approx(80.0)


def test_velocidade_media_de_nenhuma_medida_e_nada():
    r = Relatorio('teste', passagens=[passagem(kmh=None), passagem(kmh=None)])
    assert r.velocidade_media is None


@pytest.mark.parametrize('quadros', [1500, 3000, 7500])
@pytest.mark.parametrize('total', [1, 5, 20])
def test_fluxo_por_minuto(quadros, total):
    r = Relatorio(
        'teste', quadros_processados=quadros, fps=25.0, passagens=[passagem()] * total
    )
    minutos = quadros / 25.0 / 60.0
    assert r.veiculos_por_minuto == pytest.approx(total / minutos)


@pytest.mark.parametrize('fps', [0.0, -1.0])
def test_fluxo_com_fps_invalido_e_zero(fps):
    r = Relatorio('teste', quadros_processados=1000, fps=fps, passagens=[passagem()])
    assert r.veiculos_por_minuto == 0.0


def test_fluxo_sem_quadros_e_zero():
    assert Relatorio('teste', quadros_processados=0).veiculos_por_minuto == 0.0


# --------------------------------------------------------------------------
# CSV
# --------------------------------------------------------------------------


def test_csv_tem_cabecalho_e_uma_linha_por_passagem(tmp_path):
    r = Relatorio('teste', passagens=[passagem(i, quadro=i * 30) for i in range(1, 6)])
    destino = r.salvar_csv(tmp_path / 'saida.csv')

    with destino.open(encoding='utf-8') as arquivo:
        linhas = list(csv.DictReader(arquivo))
    assert len(linhas) == 5
    assert linhas[0]['id'] == '1'


def test_csv_nao_deixa_linha_em_branco_entre_registros(tmp_path):
    """No Windows, sem newline='' o módulo csv escreve \\r\\r\\n e a planilha estraga."""
    r = Relatorio('teste', passagens=[passagem(1), passagem(2)])
    destino = r.salvar_csv(tmp_path / 'saida.csv')
    conteudo = destino.read_text(encoding='utf-8')
    assert '\r\r' not in conteudo


def test_csv_vazio_ainda_tem_cabecalho(tmp_path):
    destino = Relatorio('teste').salvar_csv(tmp_path / 'vazio.csv')
    linhas = destino.read_text(encoding='utf-8').strip().splitlines()
    assert len(linhas) == 1
    assert 'velocidade_kmh' in linhas[0]


def test_csv_cria_a_pasta_que_faltar(tmp_path):
    destino = Relatorio('teste').salvar_csv(tmp_path / 'a' / 'b' / 'saida.csv')
    assert destino.exists()


def test_csv_aceita_acentos(tmp_path):
    r = Relatorio('teste', passagens=[passagem(classe='caminhão')])
    destino = r.salvar_csv(tmp_path / 'acentos.csv')
    assert 'caminhão' in destino.read_text(encoding='utf-8')


# --------------------------------------------------------------------------
# JSON
# --------------------------------------------------------------------------


def test_json_traz_o_resumo_e_as_passagens(tmp_path):
    r = Relatorio(
        'video.mp4',
        quadros_processados=1500,
        fps=25.0,
        passagens=[passagem(1), passagem(2, classe='moto')],
    )
    destino = r.salvar_json(tmp_path / 'saida.json')
    dados = json.loads(destino.read_text(encoding='utf-8'))

    assert dados['fonte'] == 'video.mp4'
    assert dados['total'] == 2
    assert dados['por_classe'] == {'carro': 1, 'moto': 1}
    assert len(dados['passagens']) == 2


def test_json_sem_velocidade_guarda_nulo(tmp_path):
    r = Relatorio('teste', passagens=[passagem(kmh=None)])
    dados = json.loads(r.salvar_json(tmp_path / 's.json').read_text(encoding='utf-8'))
    assert dados['velocidade_media_kmh'] is None


def test_json_nao_escapa_acentos(tmp_path):
    """Escapar viraria \\u00e3 e deixaria o arquivo ilegível para quem for conferir."""
    r = Relatorio('teste', passagens=[passagem(classe='caminhão')])
    destino = r.salvar_json(tmp_path / 's.json')
    assert 'caminhão' in destino.read_text(encoding='utf-8')


def test_json_de_relatorio_vazio_e_valido(tmp_path):
    dados = json.loads(
        Relatorio('teste').salvar_json(tmp_path / 'v.json').read_text(encoding='utf-8')
    )
    assert dados['total'] == 0
    assert dados['passagens'] == []


# --------------------------------------------------------------------------
# Resumo
# --------------------------------------------------------------------------


def test_resumo_traz_os_numeros_principais():
    r = Relatorio(
        'video.mp4', quadros_processados=1500, fps=25.0, passagens=[passagem(), passagem(2)]
    )
    texto = r.resumo()
    assert 'video.mp4' in texto
    assert 'Total de veículos: 2' in texto
    assert 'veículos por minuto' in texto


def test_resumo_omite_velocidade_quando_nao_ha_medida():
    r = Relatorio('teste', passagens=[passagem(kmh=None)])
    assert 'Velocidade média' not in r.resumo()


def test_resumo_mostra_velocidade_quando_ha_medida():
    r = Relatorio('teste', passagens=[passagem(kmh=72.0)])
    assert 'Velocidade média: 72.0 km/h' in r.resumo()


def test_resumo_de_relatorio_vazio_nao_quebra():
    assert 'Total de veículos: 0' in Relatorio('teste').resumo()
