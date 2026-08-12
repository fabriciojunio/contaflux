"""A costura entre detecção, rastreio e contagem.

Aqui os componentes reais são trocados por dublês sempre que possível. Não é
para o teste ficar mais rápido: é para separar o que é erro de costura do que é
erro de visão computacional. Quando um teste destes falha, o problema está
neste arquivo, e não no MOG2.
"""

from __future__ import annotations

import numpy as np
import pytest

from contaflux.contagem import Linha
from contaflux.deteccao import Deteccao
from contaflux.perfis import RODOVIA, URBANO
from contaflux.pipeline import ContadorDeFluxo
from contaflux.porte import CARRO, DESCONHECIDO, MOTO
from contaflux.velocidade import Escala

LINHA = Linha(320, 60, 320, 340)


class DetectorFalso:
    """Devolve detecções combinadas de antemão, uma lista por quadro."""

    def __init__(self, roteiro: list[list[Deteccao]]) -> None:
        self.roteiro = roteiro
        self.chamadas = 0

    def detectar(self, quadro):
        indice = self.chamadas
        self.chamadas += 1
        deteccoes = self.roteiro[indice] if indice < len(self.roteiro) else []
        return deteccoes, np.zeros((360, 640), dtype=np.uint8)


def travessia(largura=60, altura=36, area=2400, y=150, passo=30, quadros=12):
    """Roteiro de um veículo atravessando a linha da esquerda para a direita."""
    return [
        [Deteccao(int(200 + i * passo), y, largura, altura, area)] for i in range(quadros)
    ]


def contador(roteiro, aquecimento=0, **opcoes):
    return ContadorDeFluxo(
        LINHA,
        detector=DetectorFalso(roteiro),
        quadros_de_aquecimento=aquecimento,
        **opcoes,
    )


def rodar(cf, quadros):
    quadro = np.zeros((360, 640, 3), dtype=np.uint8)
    for _ in range(quadros):
        cf.processar(quadro)
    return cf


# --------------------------------------------------------------------------
# Aquecimento
# --------------------------------------------------------------------------


@pytest.mark.parametrize('aquecimento', range(0, 12))
def test_quadros_de_aquecimento_nao_produzem_alvos(aquecimento):
    """Antes de o fundo ser aprendido, a cena inteira vira movimento."""
    cf = contador(travessia(quadros=40), aquecimento=aquecimento)
    quadro = np.zeros((360, 640, 3), dtype=np.uint8)
    for i in range(aquecimento):
        estado = cf.processar(quadro)
        assert estado.aquecendo is True
        assert estado.alvos == {}


def test_depois_do_aquecimento_os_alvos_aparecem():
    cf = contador(travessia(quadros=20), aquecimento=3)
    rodar(cf, 4)
    assert cf.rastreador.alvos


def test_aquecimento_nao_conta_nada():
    cf = contador(travessia(quadros=40), aquecimento=40)
    rodar(cf, 40)
    assert cf.contagem.total == 0


def test_o_indice_avanca_durante_o_aquecimento():
    """Os quadros descartados continuam contando para a duração do vídeo."""
    cf = contador([], aquecimento=10)
    rodar(cf, 10)
    assert cf.quadros_processados == 10


# --------------------------------------------------------------------------
# Contagem e passagens
# --------------------------------------------------------------------------


def test_um_veiculo_gera_uma_passagem():
    cf = rodar(contador(travessia()), 12)
    assert cf.contagem.total == 1
    assert len(cf.passagens) == 1


def test_a_passagem_guarda_o_quadro_e_o_sentido():
    cf = rodar(contador(travessia()), 12)
    passagem = cf.passagens[0]
    assert passagem.sentido == RODOVIA.rotulo_negativo
    assert 0 < passagem.quadro < 12


def test_o_sentido_usa_o_rotulo_do_perfil():
    """A contagem fala em entrada e saída; o relatório precisa falar em sentido."""
    indo = rodar(contador(travessia()), 12)
    voltando = rodar(contador(list(reversed(travessia()))), 12)
    assert indo.passagens[0].sentido == RODOVIA.rotulo_negativo
    assert voltando.passagens[0].sentido == RODOVIA.rotulo_positivo


@pytest.mark.parametrize('fps', [15.0, 25.0, 30.0, 60.0])
def test_o_segundo_da_passagem_vem_da_taxa_de_quadros(fps):
    cf = rodar(contador(travessia(), escala=Escala(0.05, fps)), 12)
    passagem = cf.passagens[0]
    assert passagem.segundo == pytest.approx(passagem.quadro / fps)


def test_sem_escala_o_segundo_usa_vinte_e_cinco_quadros():
    cf = rodar(contador(travessia()), 12)
    passagem = cf.passagens[0]
    assert passagem.segundo == pytest.approx(passagem.quadro / 25.0)


def test_nenhuma_passagem_e_registrada_duas_vezes():
    cf = rodar(contador(travessia(quadros=30)), 30)
    assert len(cf.passagens) == 1


def test_estado_traz_so_as_passagens_novas_do_quadro():
    """A interface precisa saber o que aconteceu agora, não o histórico todo."""
    cf = contador(travessia())
    quadro = np.zeros((360, 640, 3), dtype=np.uint8)
    novas_por_quadro = [len(cf.processar(quadro).novas_passagens) for _ in range(12)]
    assert sum(novas_por_quadro) == 1
    assert max(novas_por_quadro) == 1


def test_sem_deteccao_nao_ha_contagem():
    cf = rodar(contador([[] for _ in range(20)]), 20)
    assert cf.contagem.total == 0
    assert cf.passagens == []


# --------------------------------------------------------------------------
# Classificação
# --------------------------------------------------------------------------


@pytest.mark.parametrize('area,esperada', [(900, MOTO), (2400, CARRO), (9000, 'caminhão')])
def test_a_passagem_recebe_a_classe_pelo_tamanho(area, esperada):
    cf = rodar(contador(travessia(area=area)), 12)
    assert cf.passagens[0].classe == esperada


def test_perfis_diferentes_classificam_a_mesma_area_de_forma_diferente():
    """Câmera mais baixa faz o mesmo carro ocupar mais pixels."""
    area = 2000
    rodovia = rodar(contador(travessia(area=area), perfil=RODOVIA), 12)
    urbano = rodar(contador(travessia(area=area), perfil=URBANO), 12)
    assert rodovia.passagens[0].classe == CARRO
    assert urbano.passagens[0].classe == MOTO


def test_a_classe_usa_a_maior_area_vista_ate_a_travessia():
    """O veículo entra recortado pela borda, e o porte é o do meio da travessia.

    A área grande é colocada antes do cruzamento de propósito: a classe é
    decidida no instante em que a linha é atravessada, então o que aparece
    depois não pode mais mudar o que já foi registrado.
    """
    roteiro = travessia(area=500, quadros=12)
    roteiro[2] = [Deteccao(260, 150, 60, 36, 9000)]
    cf = rodar(contador(roteiro), 12)
    assert cf.passagens[0].classe == 'caminhão'


def test_a_classe_nao_muda_depois_da_travessia():
    roteiro = travessia(area=500, quadros=12)
    roteiro[9] = [Deteccao(470, 150, 60, 36, 9000)]
    cf = rodar(contador(roteiro), 12)
    assert cf.passagens[0].classe == MOTO


# --------------------------------------------------------------------------
# Velocidade
# --------------------------------------------------------------------------


def travessia_longa(passo, quadros=20, avanco=10):
    """Travessia com muitos quadros antes da linha.

    A velocidade exige uma trajetória mínima, e no roteiro curto o veículo
    cruza no quarto quadro, antes de haver pontos suficientes. Aqui ele chega à
    linha depois de `avanco` quadros.
    """
    inicio = 320 - 30 - passo * avanco
    return [
        [Deteccao(int(inicio + i * passo), 150, 60, 36, 2400)] for i in range(quadros)
    ]


@pytest.mark.parametrize('passo', [10, 20, 30])
def test_a_velocidade_e_calculada_quando_ha_escala(passo):
    escala = Escala(metros_por_pixel=0.05, fps=25.0)
    cf = rodar(contador(travessia_longa(passo), escala=escala), 20)
    esperada = passo * 25.0 * 0.05 * 3.6
    assert cf.passagens[0].velocidade_kmh == pytest.approx(esperada, rel=0.05)


def test_sem_escala_a_velocidade_fica_vazia():
    cf = rodar(contador(travessia_longa(20), escala=None), 20)
    assert cf.passagens[0].velocidade_kmh is None


def test_travessia_curta_demais_nao_ganha_velocidade():
    """Quatro pontos não bastam, e inventar um número seria pior que deixar vazio."""
    cf = rodar(contador(travessia(passo=30), escala=Escala(0.05, 25.0)), 12)
    assert cf.passagens[0].velocidade_kmh is None


# --------------------------------------------------------------------------
# Rótulos da interface
# --------------------------------------------------------------------------


def test_rotulo_traz_ao_menos_o_identificador():
    cf = rodar(contador(travessia()), 3)
    rotulos = cf.rotulos(cf.rastreador.alvos)
    assert rotulos[1].startswith('#1')


def test_rotulo_ganha_a_classe_depois_de_contado():
    cf = rodar(contador(travessia()), 12)
    assert 'carro' in cf.rotulos(cf.rastreador.alvos)[1]


def test_rotulo_ganha_a_velocidade_quando_ha_escala():
    cf = rodar(contador(travessia(), escala=Escala(0.05, 25.0)), 12)
    assert 'km/h' in cf.rotulos(cf.rastreador.alvos)[1]


def test_rotulo_sem_alvos_e_vazio():
    assert contador([]).rotulos({}) == {}


def test_rotulo_omite_classe_desconhecida():
    cf = rodar(contador(travessia(quadros=3)), 3)
    assert DESCONHECIDO not in cf.rotulos(cf.rastreador.alvos)[1]


# --------------------------------------------------------------------------
# Relatório
# --------------------------------------------------------------------------


def test_relatorio_traz_a_fonte_e_o_total():
    cf = rodar(contador(travessia()), 12)
    relatorio = cf.relatorio('rodovia.mp4')
    assert relatorio.fonte == 'rodovia.mp4'
    assert relatorio.total == 1
    assert relatorio.quadros_processados == 12


def test_relatorio_usa_a_taxa_de_quadros_da_escala():
    cf = rodar(contador(travessia(), escala=Escala(0.05, 30.0)), 12)
    assert cf.relatorio('x').fps == 30.0


def test_velocidade_media_bate_com_a_do_relatorio():
    """A janela usa o atalho e o arquivo usa o relatório; os dois têm que concordar."""
    cf = rodar(contador(travessia_longa(20), escala=Escala(0.05, 25.0)), 20)
    assert cf.velocidade_media == pytest.approx(cf.relatorio('x').velocidade_media)


def test_sem_passagens_nao_ha_velocidade_media():
    assert contador([]).velocidade_media is None


def test_relatorio_e_uma_copia_das_passagens():
    """Alterar o relatório não pode mexer no estado do contador."""
    cf = rodar(contador(travessia()), 12)
    relatorio = cf.relatorio('x')
    relatorio.passagens.clear()
    assert len(cf.passagens) == 1


# --------------------------------------------------------------------------
# Estado do quadro
# --------------------------------------------------------------------------


def test_estado_traz_indice_crescente():
    cf = contador([])
    quadro = np.zeros((360, 640, 3), dtype=np.uint8)
    indices = [cf.processar(quadro).indice for _ in range(8)]
    assert indices == list(range(8))


def test_estado_traz_a_mascara():
    cf = contador(travessia())
    estado = cf.processar(np.zeros((360, 640, 3), dtype=np.uint8))
    assert estado.mascara.shape == (360, 640)


def test_estado_traz_as_deteccoes_do_quadro():
    cf = contador(travessia())
    estado = cf.processar(np.zeros((360, 640, 3), dtype=np.uint8))
    assert len(estado.deteccoes) == 1


# --------------------------------------------------------------------------
# Reinício
# --------------------------------------------------------------------------


def test_reiniciar_zera_tudo():
    cf = rodar(contador(travessia()), 12)
    assert cf.contagem.total == 1

    cf.reiniciar()
    assert cf.contagem.total == 0
    assert cf.passagens == []
    assert cf.classes == {}
    assert cf.quadros_processados == 0
    assert cf.rastreador.alvos == {}


def test_depois_de_reiniciar_da_para_contar_de_novo():
    cf = contador(travessia() * 2)
    rodar(cf, 12)
    cf.reiniciar()
    cf.detector.chamadas = 0
    rodar(cf, 12)
    assert cf.contagem.total == 1


# --------------------------------------------------------------------------
# Construção
# --------------------------------------------------------------------------


def test_o_perfil_calibra_o_detector_e_o_rastreador():
    cf = ContadorDeFluxo(LINHA, perfil=URBANO)
    assert cf.detector.area_minima == URBANO.area_minima
    assert cf.rastreador.distancia_maxima == URBANO.distancia_maxima
    assert cf.contador.quadros_minimos == URBANO.quadros_minimos


def test_o_perfil_padrao_e_o_de_rodovia():
    assert ContadorDeFluxo(LINHA).perfil is RODOVIA


def test_a_linha_fica_acessivel_para_a_interface():
    assert ContadorDeFluxo(LINHA).linha is LINHA
