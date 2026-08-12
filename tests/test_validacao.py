"""Validação de ponta a ponta contra gabarito exato.

É o teste que responde à pergunta que importa: o número que sai está certo?
Cada caso monta uma cena em que sabemos exatamente quantos veículos cruzam a
linha, roda o sistema inteiro por cima dela e compara.

São lentos porque processam centenas de quadros cada, e por isso ficam sob a
marca `lento`. Para rodar só o resto da suíte: pytest -m "not lento".
"""

from __future__ import annotations

import pytest

from contaflux.cena import (
    CAMINHAO,
    CARRO,
    MOTO,
    GeradorDeCena,
    ParametrosCena,
    veiculos_regulares,
    veiculos_variados,
)
from contaflux.contagem import Linha
from contaflux.perfis import RODOVIA, URBANO
from contaflux.pipeline import ContadorDeFluxo, contar_sequencia
from contaflux.velocidade import Escala

pytestmark = pytest.mark.lento

LINHA = Linha(320, 60, 320, 340)


def montar(quantidade, semente, **extras):
    intervalo = extras.pop('intervalo', 26)
    sentido = extras.pop('sentido', 1)
    parametros = ParametrosCena(quadros=extras.pop('quadros', 460), semente=semente, **extras)
    parametros.veiculos = veiculos_regulares(
        quantidade, parametros, intervalo=intervalo, sentido=sentido, semente=semente
    )
    return GeradorDeCena(parametros)


def contar(cena, **opcoes):
    return contar_sequencia(cena.quadros(), LINHA, **opcoes)


# --------------------------------------------------------------------------
# Contagem exata em condições normais
# --------------------------------------------------------------------------


@pytest.mark.parametrize('quantidade', [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15])
def test_conta_o_numero_exato_de_veiculos(quantidade):
    cena = montar(quantidade, semente=quantidade)
    esperado = cena.travessias_esperadas(320.0)
    assert contar(cena).total == esperado


@pytest.mark.parametrize('semente', range(20, 32))
def test_conta_certo_em_cenas_sorteadas_diferentes(semente):
    """Sementes diferentes trocam cor, tamanho e velocidade de todo mundo."""
    cena = montar(8, semente=semente)
    esperado = cena.travessias_esperadas(320.0)
    assert contar(cena).total == esperado


# --------------------------------------------------------------------------
# Condições adversas
# --------------------------------------------------------------------------


@pytest.mark.parametrize('ruido', [0.0, 2.0, 4.0, 8.0, 12.0])
def test_conta_certo_sob_ruido_de_sensor(ruido):
    cena = montar(8, semente=40, ruido=ruido)
    esperado = cena.travessias_esperadas(320.0)
    assert contar(cena).total == esperado


@pytest.mark.parametrize('oscilacao', [0.0, 0.02, 0.04, 0.06])
def test_conta_certo_com_iluminacao_oscilando(oscilacao):
    """Nuvem passando na frente do sol muda o brilho da cena inteira."""
    cena = montar(8, semente=50, oscilacao_luz=oscilacao)
    esperado = cena.travessias_esperadas(320.0)
    assert contar(cena).total == esperado


@pytest.mark.parametrize('sombra', [True, False])
def test_conta_certo_com_e_sem_sombra(sombra):
    cena = montar(8, semente=60, sombra=sombra)
    esperado = cena.travessias_esperadas(320.0)
    assert contar(cena).total == esperado


@pytest.mark.parametrize('intervalo', [16, 20, 26, 34, 44])
def test_conta_certo_em_transito_denso_e_esparso(intervalo):
    """Intervalo curto empilha veículos na tela e é onde o rastreio sofre."""
    cena = montar(10, semente=70, intervalo=intervalo)
    esperado = cena.travessias_esperadas(320.0)
    assert contar(cena).total == esperado


def test_cena_vazia_nao_inventa_veiculo():
    """O teste que mais importa para o limiar baixo: nada precisa dar zero."""
    cena = montar(0, semente=7)
    assert contar(cena).total == 0


def test_cena_vazia_com_ruido_alto_nao_inventa_veiculo():
    cena = montar(0, semente=8, ruido=12.0)
    assert contar(cena).total == 0


# --------------------------------------------------------------------------
# Sentido
# --------------------------------------------------------------------------


@pytest.mark.parametrize('quantidade', [1, 3, 5, 8])
def test_sentido_da_esquerda_para_a_direita(quantidade):
    cena = montar(quantidade, semente=quantidade + 80, sentido=1)
    contagem = contar(cena)
    assert contagem.total == cena.travessias_esperadas(320.0)
    assert contagem.entradas == 0
    assert contagem.saidas == contagem.total


@pytest.mark.parametrize('quantidade', [1, 3, 5, 8])
def test_sentido_da_direita_para_a_esquerda(quantidade):
    cena = montar(quantidade, semente=quantidade + 90, sentido=-1)
    contagem = contar(cena)
    assert contagem.total == cena.travessias_esperadas(320.0)
    assert contagem.saidas == 0
    assert contagem.entradas == contagem.total


# --------------------------------------------------------------------------
# Posição da linha
# --------------------------------------------------------------------------


@pytest.mark.parametrize('x', [160, 240, 320, 400, 480])
def test_a_posicao_da_linha_nao_muda_o_total(x):
    """Todo mundo atravessa a cena inteira, então qualquer x dá o mesmo número."""
    cena = montar(8, semente=100)
    esperado = cena.travessias_esperadas(float(x))
    contagem = contar_sequencia(cena.quadros(), Linha(x, 60, x, 340))
    assert contagem.total == esperado


# --------------------------------------------------------------------------
# Perfis
# --------------------------------------------------------------------------


@pytest.mark.parametrize('perfil', [RODOVIA, URBANO])
def test_os_dois_perfis_contam_a_mesma_cena(perfil):
    """A cena tem veículos grandes o bastante para passar nos dois pisos de área."""
    cena = montar(6, semente=110)
    esperado = cena.travessias_esperadas(320.0)
    assert contar(cena, perfil=perfil).total == esperado


# --------------------------------------------------------------------------
# Classificação de porte
# --------------------------------------------------------------------------


def test_classifica_o_porte_de_cada_veiculo():
    # A duração é a menor que ainda deixa o último veículo atravessar. Cada
    # quadro a mais custa tempo em toda a suíte e não acrescenta nada ao que o
    # teste mede.
    parametros = ParametrosCena(quadros=420, semente=200)
    portes = [MOTO, CARRO, CAMINHAO, CARRO, MOTO, CAMINHAO]
    parametros.veiculos = veiculos_variados(portes, parametros, semente=200)
    cena = GeradorDeCena(parametros)

    contador = ContadorDeFluxo(LINHA, perfil=RODOVIA)
    for quadro in cena.quadros():
        contador.processar(quadro)

    esperados = [v.porte for v in cena.quem_cruza(320.0)]
    obtidos = [p.classe for p in contador.passagens]
    assert obtidos == esperados


@pytest.mark.parametrize('porte', [MOTO, CARRO, CAMINHAO])
def test_classifica_uma_fila_de_um_porte_so(porte):
    parametros = ParametrosCena(quadros=360, semente=210)
    parametros.veiculos = veiculos_variados([porte] * 4, parametros, semente=210)
    cena = GeradorDeCena(parametros)

    contador = ContadorDeFluxo(LINHA, perfil=RODOVIA)
    for quadro in cena.quadros():
        contador.processar(quadro)

    assert contador.contagem.total == cena.travessias_esperadas(320.0)
    assert {p.classe for p in contador.passagens} == {porte}


# --------------------------------------------------------------------------
# Velocidade
# --------------------------------------------------------------------------


@pytest.mark.parametrize('metros_visiveis', [20.0, 30.0, 45.0])
def test_velocidade_estimada_bate_com_a_da_cena(metros_visiveis):
    """A cena sabe a velocidade real em pixels por quadro; o resto é conversão."""
    cena = montar(5, semente=300)
    escala = Escala.de_largura(640, metros_visiveis, 25.0)

    contador = ContadorDeFluxo(LINHA, perfil=RODOVIA, escala=escala)
    for quadro in cena.quadros():
        contador.processar(quadro)

    reais = {
        v.velocidade * 25.0 * escala.metros_por_pixel * 3.6 for v in cena.quem_cruza(320.0)
    }
    minimo, maximo = min(reais), max(reais)

    medidas = [p.velocidade_kmh for p in contador.passagens if p.velocidade_kmh is not None]
    assert medidas, 'nenhuma velocidade foi medida'
    for medida in medidas:
        assert minimo - 5 <= medida <= maximo + 5


def test_sem_escala_a_velocidade_fica_em_branco():
    """Sem calibração medida, inventar quilômetros por hora seria mentir."""
    cena = montar(4, semente=310)
    contador = ContadorDeFluxo(LINHA, perfil=RODOVIA)
    for quadro in cena.quadros():
        contador.processar(quadro)

    assert contador.passagens
    assert all(p.velocidade_kmh is None for p in contador.passagens)


# --------------------------------------------------------------------------
# Relatório
# --------------------------------------------------------------------------


def test_relatorio_bate_com_a_contagem():
    cena = montar(7, semente=400)
    contador = ContadorDeFluxo(LINHA, perfil=RODOVIA, escala=Escala(0.05, 25.0))
    for quadro in cena.quadros():
        contador.processar(quadro)

    relatorio = contador.relatorio('cena de teste')
    assert relatorio.total == contador.contagem.total
    assert relatorio.quadros_processados == 460
    assert sum(relatorio.por_classe.values()) == relatorio.total
    assert relatorio.veiculos_por_minuto > 0


def test_cada_veiculo_gera_exatamente_uma_passagem():
    cena = montar(9, semente=410)
    contador = ContadorDeFluxo(LINHA, perfil=RODOVIA)
    for quadro in cena.quadros():
        contador.processar(quadro)

    identificadores = [p.identificador for p in contador.passagens]
    assert len(identificadores) == len(set(identificadores))
    assert len(identificadores) == cena.travessias_esperadas(320.0)


def test_passagens_saem_em_ordem_de_quadro():
    cena = montar(9, semente=420)
    contador = ContadorDeFluxo(LINHA, perfil=RODOVIA)
    for quadro in cena.quadros():
        contador.processar(quadro)

    quadros = [p.quadro for p in contador.passagens]
    assert quadros == sorted(quadros)


# --------------------------------------------------------------------------
# Determinismo
# --------------------------------------------------------------------------


@pytest.mark.parametrize('semente', [500, 501, 502])
def test_a_mesma_cena_da_sempre_o_mesmo_numero(semente):
    """Sem isso, nenhuma calibração pode ser comparada com a anterior."""
    primeira = contar(montar(6, semente=semente)).total
    segunda = contar(montar(6, semente=semente)).total
    assert primeira == segunda
