"""Separação entre o que se move e o que fica parado."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from contaflux.deteccao import Deteccao, DetectorDeMovimento


def cena_com_retangulo(x, y, largura, altura, fundo=96, cor=(230, 230, 230)):
    imagem = np.full((360, 640, 3), fundo, dtype=np.uint8)
    cv2.rectangle(imagem, (x, y), (x + largura, y + altura), cor, -1)
    return imagem


def quadros_ruidosos(quantidade, brilho=96, semente=7, ruido=7.0):
    """Sequência de quadros com granulado que muda a cada quadro.

    Existe para os testes de iluminação, e a diferença para um fundo chapado é
    o que eles medem. Sobre fundo chapado, o modelo aprende variância perto de
    zero, e aí qualquer mudança de tom marca a imagem inteira como movimento:
    o objeto se funde com o resto num borrão só e some. Isso é artefato de cena
    lisa, não do detector, e um teste escrito assim mede a coisa errada.
    """
    gerador = np.random.default_rng(semente)
    base = np.full((360, 640, 3), float(brilho))
    for _ in range(quantidade):
        yield np.clip(base + gerador.normal(0, ruido, base.shape), 0, 255).astype(np.uint8)


def detector(**opcoes) -> DetectorDeMovimento:
    padrao = dict(area_minima=700, limiar_variancia=3.0, historico=100)
    padrao.update(opcoes)
    return DetectorDeMovimento(**padrao)


def aprender_fundo(det, quadros=60, fundo=96):
    vazio = np.full((360, 640, 3), fundo, dtype=np.uint8)
    det.aquecer([vazio] * quadros)


# --------------------------------------------------------------------------
# Deteccao
# --------------------------------------------------------------------------


@pytest.mark.parametrize('x', range(0, 300, 40))
@pytest.mark.parametrize('y', [0, 50, 120])
def test_centro_fica_no_meio_da_caixa(x, y):
    d = Deteccao(x, y, 40, 20, 800)
    assert d.centro == (x + 20.0, y + 10.0)


@pytest.mark.parametrize('largura', range(10, 100, 10))
@pytest.mark.parametrize('altura', [10, 20, 40])
def test_proporcao_e_largura_sobre_altura(largura, altura):
    assert Deteccao(0, 0, largura, altura, 1).proporcao == pytest.approx(largura / altura)


def test_proporcao_de_altura_zero_e_zero():
    """Divisão por zero aqui derrubaria o processamento no meio do vídeo."""
    assert Deteccao(0, 0, 40, 0, 1).proporcao == 0.0


@pytest.mark.parametrize('caixa', [(0, 0, 10, 20), (5, 7, 30, 40), (100, 200, 1, 1)])
def test_como_tupla_devolve_a_caixa(caixa):
    assert Deteccao(*caixa, 1).como_tupla() == caixa


def test_deteccao_e_imutavel():
    with pytest.raises(AttributeError):
        Deteccao(0, 0, 10, 10, 100).x = 5


# --------------------------------------------------------------------------
# Máscara
# --------------------------------------------------------------------------


def test_mascara_e_binaria():
    det = detector()
    aprender_fundo(det)
    mascara = det.mascara(cena_com_retangulo(100, 100, 60, 40))
    assert set(np.unique(mascara)) <= {0, 255}


def test_mascara_tem_o_tamanho_do_quadro():
    det = detector()
    aprender_fundo(det)
    assert det.mascara(cena_com_retangulo(100, 100, 60, 40)).shape == (360, 640)


def test_fundo_parado_nao_gera_movimento():
    det = detector()
    aprender_fundo(det, quadros=120)
    vazio = np.full((360, 640, 3), 96, dtype=np.uint8)
    assert det.mascara(vazio).sum() == 0


# --------------------------------------------------------------------------
# Detecção
# --------------------------------------------------------------------------


def test_objeto_novo_e_detectado():
    det = detector()
    aprender_fundo(det)
    encontrados, _ = det.detectar(cena_com_retangulo(200, 150, 70, 40))
    assert len(encontrados) == 1


@pytest.mark.parametrize('x', range(60, 500, 60))
def test_a_caixa_cai_em_cima_do_objeto(x):
    det = detector()
    aprender_fundo(det)
    encontrados, _ = det.detectar(cena_com_retangulo(x, 150, 70, 40))
    caixa = encontrados[0]
    assert abs(caixa.centro[0] - (x + 35)) < 15
    assert abs(caixa.centro[1] - 170) < 15


@pytest.mark.parametrize('lado', [10, 15, 20])
def test_objeto_pequeno_demais_e_descartado(lado):
    """Folha, pingo de chuva e ruído do sensor entram todos nesta faixa."""
    det = detector(area_minima=2000)
    aprender_fundo(det)
    encontrados, _ = det.detectar(cena_com_retangulo(200, 150, lado, lado))
    assert encontrados == []


@pytest.mark.parametrize('area_maxima', [1000, 2000, 4000])
def test_objeto_grande_demais_e_descartado(area_maxima):
    det = detector(area_maxima=area_maxima)
    aprender_fundo(det)
    encontrados, _ = det.detectar(cena_com_retangulo(100, 100, 200, 120))
    assert all(d.area <= area_maxima for d in encontrados)


@pytest.mark.parametrize('largura', [300, 400, 500])
def test_forma_muito_alongada_e_descartada(largura):
    """É a faixa da pista, o guard rail e a sombra comprida."""
    det = detector(proporcao_maxima=3.0)
    aprender_fundo(det)
    encontrados, _ = det.detectar(cena_com_retangulo(50, 150, largura, 12))
    assert encontrados == []


def test_forma_alongada_na_vertical_tambem_e_descartada():
    """O filtro precisa valer nos dois sentidos, não só na horizontal."""
    det = detector(proporcao_maxima=3.0)
    aprender_fundo(det)
    encontrados, _ = det.detectar(cena_com_retangulo(300, 20, 12, 300))
    assert encontrados == []


@pytest.mark.parametrize('quantidade', range(1, 6))
def test_varios_objetos_separados_geram_varias_deteccoes(quantidade):
    det = detector()
    aprender_fundo(det)
    imagem = np.full((360, 640, 3), 96, dtype=np.uint8)
    for i in range(quantidade):
        cv2.rectangle(imagem, (i * 120 + 10, 150), (i * 120 + 80, 195), (230, 230, 230), -1)
    encontrados, _ = det.detectar(imagem)
    assert len(encontrados) == quantidade


def test_detectar_devolve_a_mascara_usada():
    """A máscara na mão é o que permite mostrar na tela por que a contagem errou."""
    det = detector()
    aprender_fundo(det)
    encontrados, mascara = det.detectar(cena_com_retangulo(200, 150, 70, 40))
    assert mascara.shape == (360, 640)
    assert mascara.sum() > 0


def test_veiculo_escuro_de_baixo_contraste_e_detectado():
    """O caso que quebrava a versão anterior: cinza-chumbo sobre asfalto cinza.

    Com o limiar de variância em 40, este veículo não aparecia na máscara e a
    contagem simplesmente pulava ele. É a razão de o limiar dos perfis ser 3.
    """
    det = detector(limiar_variancia=3.0)
    aprender_fundo(det, quadros=120)
    encontrados, _ = det.detectar(
        cena_com_retangulo(200, 150, 76, 33, fundo=96, cor=(84, 101, 110))
    )
    assert len(encontrados) == 1


def test_aquecer_decide_o_que_e_fundo():
    """O que estiver na cena durante o aquecimento vira fundo, e some.

    É o risco concreto de apontar a câmera para uma via já com carro parado
    dentro do enquadramento: ele é aprendido como parte do cenário e deixa de
    existir para a contagem. Por isso a orientação de deixar a cena vazia nos
    primeiros segundos.
    """
    imagem = cena_com_retangulo(200, 150, 70, 40)

    aprendeu_vazio = detector()
    aprender_fundo(aprendeu_vazio, quadros=120)
    assert len(aprendeu_vazio.detectar(imagem)[0]) == 1

    aprendeu_com_o_objeto = detector()
    aprendeu_com_o_objeto.aquecer([imagem] * 120)
    assert aprendeu_com_o_objeto.detectar(imagem)[0] == []


def test_fundo_aprendido_deixa_so_o_objeto_na_mascara():
    """O que sobra na máscara tem que ser o tamanho do objeto, não da cena."""
    det = detector()
    det.aquecer(list(quadros_ruidosos(120)))

    quadro = next(quadros_ruidosos(1, semente=99))
    cv2.rectangle(quadro, (200, 150), (270, 190), (230, 230, 230), -1)

    marcados = int(np.count_nonzero(det.mascara(quadro)))
    assert 2000 < marcados < 20_000


def test_aquecer_com_lista_vazia_nao_quebra():
    det = detector()
    det.aquecer([])
    assert det.detectar(cena_com_retangulo(200, 150, 70, 40))[0] is not None


# --------------------------------------------------------------------------
# Compensação de luz
# --------------------------------------------------------------------------


@pytest.mark.parametrize('fator', [0.90, 0.94, 1.06, 1.12])
def test_mudanca_de_brilho_na_cena_inteira_nao_vira_movimento(fator):
    """É o preço do limiar baixo, e sem esta correção uma nuvem zera a contagem.

    Com o limiar em 3, uma variação de poucos tons na cena inteira já basta para
    todo pixel destoar do modelo de fundo, e o quadro vira um borrão de
    movimento em que nada pode ser rastreado.
    """
    det = detector()
    aprender_fundo(det, quadros=120)

    escurecido = np.full((360, 640, 3), int(96 * fator), dtype=np.uint8)
    encontrados, _ = det.detectar(escurecido)
    assert encontrados == []


def test_compensacao_pode_ser_desligada():
    """Desligada, a mesma mudança de brilho tem que aparecer como movimento.

    O teste clareia a cena em vez de escurecer, e o motivo é instrutivo:
    escurecer a cena inteira mantendo a cor é literalmente a definição de sombra
    para o MOG2, então o quadro escurecido sai marcado como sombra e some da
    máscara de objeto por outro caminho. Clareando, não há essa saída, e o teste
    mede o que se propõe a medir.
    """
    det = detector(compensar_luz=False)
    aprender_fundo(det, quadros=120)

    clareado = np.full((360, 640, 3), 112, dtype=np.uint8)
    _, mascara = det.detectar(clareado)
    assert mascara.sum() > 0


def test_mudanca_grande_de_brilho_nao_vira_veiculo_gigante():
    """Sem esta barreira, escurecer a cena vira um veículo do tamanho da tela.

    A regra que recupera veículo escuro procura região sem contraste alto, e uma
    cena inteira escurecida é exatamente isso. O limite de fração do quadro é o
    que separa "carro cinza" de "a luz mudou".
    """
    det = detector(compensar_luz=False)
    aprender_fundo(det, quadros=120)

    for tom in (78, 84, 90, 112, 120):
        encontrados, _ = det.detectar(np.full((360, 640, 3), tom, dtype=np.uint8))
        assert encontrados == [], f'tom {tom} virou detecção'


@pytest.mark.parametrize('fracao', [0.1, 0.25, 0.5])
def test_o_limite_de_fracao_do_quadro_e_configuravel(fracao):
    pixels = 360 * 640
    det = detector(fracao_maxima_do_quadro=fracao)
    assert det._grande_demais(int(pixels * fracao) + 100, pixels) is True
    assert det._grande_demais(int(pixels * fracao) - 100, pixels) is False


def test_sem_saber_o_tamanho_do_quadro_nada_e_grande_demais():
    """O filtro precisa ser inofensivo quando não recebe a referência."""
    assert detector()._grande_demais(999_999, 0) is False


def test_a_compensacao_nao_estraga_a_deteccao_normal():
    det = detector()
    aprender_fundo(det, quadros=120)
    encontrados, _ = det.detectar(cena_com_retangulo(200, 150, 70, 40))
    assert len(encontrados) == 1


def test_veiculo_continua_visivel_com_a_luz_oscilando():
    """A correção não pode apagar o objeto junto com a variação de luz."""
    det = detector()
    gerador = np.random.default_rng(3)
    for i in range(150):
        tom = 96 * (1 + 0.06 * np.sin(2 * np.pi * i / 60))
        base = np.full((360, 640, 3), tom)
        quadro = np.clip(base + gerador.normal(0, 7, base.shape), 0, 255).astype(np.uint8)
        det.detectar(quadro)

    # O quadro de teste vem no pico da oscilação, que é o pior momento: é onde a
    # cena mais destoa do fundo aprendido e onde o objeto correria o risco de
    # sumir junto com a correção.
    base = np.full((360, 640, 3), 96 * 1.06)
    quadro = np.clip(base + gerador.normal(0, 7, base.shape), 0, 255).astype(np.uint8)
    cv2.rectangle(quadro, (200, 150), (270, 190), (230, 230, 230), -1)

    encontrados, _ = det.detectar(quadro)
    assert len(encontrados) == 1


def test_um_objeto_grande_nao_desloca_a_referencia_de_brilho():
    """A mediana é usada justamente porque um caminhão branco puxaria a média."""
    det = detector()
    aprender_fundo(det, quadros=120)
    referencia = det._brilho_de_referencia

    det.detectar(cena_com_retangulo(100, 100, 200, 120, cor=(255, 255, 255)))
    assert det._brilho_de_referencia == referencia


@pytest.mark.parametrize('ruido', [2.0, 5.0, 10.0])
def test_ruido_sozinho_nao_vira_deteccao(ruido):
    """O que segura o limiar baixo é o filtro de área, e é isto que prova."""
    gerador = np.random.default_rng(7)
    det = detector()
    for _ in range(80):
        base = np.full((360, 640, 3), 96, dtype=np.float64)
        quadro = np.clip(base + gerador.normal(0, ruido, base.shape), 0, 255).astype(np.uint8)
        encontrados, _ = det.detectar(quadro)
    assert encontrados == []
