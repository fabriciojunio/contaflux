"""Geometria da linha e regra de contagem.

É o módulo com mais testes da suíte, e de propósito: é aqui que mora a decisão
de contar ou não contar, e todo erro daqui aparece direto no número final.
"""

from __future__ import annotations

import math

import pytest

from contaflux.contagem import Contagem, ContadorDeLinha, Linha
from contaflux.rastreio import Alvo


def alvo(identificador: int, centro, quadros_visto: int = 10, contado: bool = False) -> Alvo:
    return Alvo(
        identificador=identificador,
        centro=centro,
        caixa=(int(centro[0]) - 10, int(centro[1]) - 10, 20, 20),
        trajetoria=[centro],
        indices=[0],
        quadros_visto=quadros_visto,
        contado=contado,
    )


# --------------------------------------------------------------------------
# Linha.lado
# --------------------------------------------------------------------------

VERTICAL = Linha(100, 0, 100, 200)
HORIZONTAL = Linha(0, 100, 200, 100)
DIAGONAL = Linha(0, 0, 100, 100)


@pytest.mark.parametrize('x', range(0, 200, 5))
@pytest.mark.parametrize('y', [10, 50, 100, 150, 190])
def test_lado_de_vertical_tem_o_sinal_do_deslocamento_em_x(x, y):
    """Numa linha vertical, o lado depende só de x, nunca de y."""
    valor = VERTICAL.lado((x, y))
    if x < 100:
        assert valor > 0
    elif x > 100:
        assert valor < 0
    else:
        assert valor == 0


@pytest.mark.parametrize('y', range(0, 200, 5))
@pytest.mark.parametrize('x', [10, 50, 100, 150, 190])
def test_lado_de_horizontal_tem_o_sinal_do_deslocamento_em_y(x, y):
    valor = HORIZONTAL.lado((x, y))
    if y < 100:
        assert valor < 0
    elif y > 100:
        assert valor > 0
    else:
        assert valor == 0


@pytest.mark.parametrize('d', range(1, 60, 2))
def test_lado_de_diagonal_separa_os_dois_semiplanos(d):
    acima = DIAGONAL.lado((50 - d, 50))
    abaixo = DIAGONAL.lado((50 + d, 50))
    assert acima > 0 > abaixo


@pytest.mark.parametrize('t', [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0])
def test_ponto_sobre_a_linha_tem_lado_zero(t):
    ponto = (DIAGONAL.x1 + t * 100, DIAGONAL.y1 + t * 100)
    assert DIAGONAL.lado(ponto) == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize('escala', [0.5, 1.0, 2.0, 10.0])
def test_lado_cresce_proporcional_a_distancia(escala):
    """A magnitude é proporcional à distância, o que permite usá-la como medida."""
    perto = abs(VERTICAL.lado((100 + 1, 50)))
    longe = abs(VERTICAL.lado((100 + escala, 50)))
    assert longe == pytest.approx(perto * escala)


def test_lado_inverte_o_sinal_quando_a_linha_e_invertida():
    """Trocar os pontos da linha troca qual sentido é entrada e qual é saída."""
    direta = Linha(100, 0, 100, 200)
    invertida = Linha(100, 200, 100, 0)
    ponto = (40, 80)
    assert direta.lado(ponto) == -invertida.lado(ponto)


# --------------------------------------------------------------------------
# Linha.comprimento
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    'linha,esperado',
    [
        (Linha(0, 0, 3, 4), 5.0),
        (Linha(0, 0, 0, 7), 7.0),
        (Linha(0, 0, 7, 0), 7.0),
        (Linha(1, 1, 1, 1), 0.0),
        (Linha(-3, -4, 0, 0), 5.0),
        (Linha(10, 10, 13, 14), 5.0),
    ],
)
def test_comprimento(linha, esperado):
    assert linha.comprimento == pytest.approx(esperado)


@pytest.mark.parametrize('n', range(1, 40))
def test_comprimento_de_diagonal_unitaria(n):
    assert Linha(0, 0, n, n).comprimento == pytest.approx(n * math.sqrt(2))


# --------------------------------------------------------------------------
# Linha.dentro_do_segmento
# --------------------------------------------------------------------------


@pytest.mark.parametrize('y', range(0, 201, 10))
def test_dentro_do_segmento_aceita_o_trecho_desenhado(y):
    assert VERTICAL.dentro_do_segmento((100, y)) is True


@pytest.mark.parametrize('y', [-100, -60, -30, 230, 260, 320])
def test_dentro_do_segmento_recusa_o_prolongamento_da_reta(y):
    """O ponto está sobre a reta infinita, mas fora do trecho marcado."""
    assert VERTICAL.dentro_do_segmento((100, y)) is False


@pytest.mark.parametrize('folga', [0.0, 0.02, 0.04])
def test_dentro_do_segmento_tolera_folga_pequena_nas_pontas(folga):
    """A folga de cinco por cento evita perder quem cruza rente à ponta."""
    assert VERTICAL.dentro_do_segmento((100, -folga * 200)) is True
    assert VERTICAL.dentro_do_segmento((100, 200 + folga * 200)) is True


@pytest.mark.parametrize('folga', [0.08, 0.2, 0.5])
def test_dentro_do_segmento_recusa_alem_da_folga(folga):
    assert VERTICAL.dentro_do_segmento((100, 200 + folga * 200)) is False


def test_dentro_do_segmento_de_linha_degenerada_e_falso():
    """Linha de comprimento zero não tem trecho, e nada pode estar dentro dela."""
    assert Linha(5, 5, 5, 5).dentro_do_segmento((5, 5)) is False


@pytest.mark.parametrize('x', range(-40, 241, 10))
def test_dentro_do_segmento_projeta_pontos_fora_da_reta(x):
    """A verificação é sobre a projeção, então o ponto não precisa estar na reta."""
    esperado = -10 <= x <= 210
    assert HORIZONTAL.dentro_do_segmento((x, 55)) is esperado


# --------------------------------------------------------------------------
# Contagem
# --------------------------------------------------------------------------


@pytest.mark.parametrize('entradas', range(0, 20, 3))
@pytest.mark.parametrize('saidas', range(0, 20, 4))
def test_total_e_saldo(entradas, saidas):
    contagem = Contagem(entradas=entradas, saidas=saidas)
    assert contagem.total == entradas + saidas
    assert contagem.saldo == entradas - saidas


def test_contagem_nasce_zerada():
    contagem = Contagem()
    assert (contagem.total, contagem.entradas, contagem.saidas) == (0, 0, 0)
    assert contagem.eventos == []


def test_eventos_de_contagens_diferentes_nao_sao_compartilhados():
    """Lista mutável como padrão de dataclass é um erro clássico; aqui não há."""
    uma, outra = Contagem(), Contagem()
    uma.eventos.append((1, 'entrada', 0))
    assert outra.eventos == []


# --------------------------------------------------------------------------
# ContadorDeLinha
# --------------------------------------------------------------------------


def test_primeiro_quadro_nunca_conta():
    """Sem um lado anterior não há travessia, só uma posição."""
    contador = ContadorDeLinha(VERTICAL, quadros_minimos=1)
    contagem = contador.atualizar({1: alvo(1, (50, 100))}, 0)
    assert contagem.total == 0


def test_travessia_da_esquerda_para_a_direita_conta_como_saida():
    contador = ContadorDeLinha(VERTICAL, quadros_minimos=1)
    contador.atualizar({1: alvo(1, (90, 100))}, 0)
    contagem = contador.atualizar({1: alvo(1, (110, 100))}, 1)
    assert (contagem.entradas, contagem.saidas) == (0, 1)


def test_travessia_da_direita_para_a_esquerda_conta_como_entrada():
    contador = ContadorDeLinha(VERTICAL, quadros_minimos=1)
    contador.atualizar({1: alvo(1, (110, 100))}, 0)
    contagem = contador.atualizar({1: alvo(1, (90, 100))}, 1)
    assert (contagem.entradas, contagem.saidas) == (1, 0)


@pytest.mark.parametrize('passos', range(2, 30))
def test_alvo_que_nunca_cruza_nao_conta(passos):
    """Andar muito de um lado só não vira contagem."""
    contador = ContadorDeLinha(VERTICAL, quadros_minimos=1)
    for i in range(passos):
        contador.atualizar({1: alvo(1, (10 + i * 2, 100))}, i)
    assert contador.contagem.total == 0


@pytest.mark.parametrize('idas_e_voltas', range(1, 12))
def test_cada_alvo_conta_no_maximo_uma_vez(idas_e_voltas):
    """Alvo que fica indo e voltando sobre a linha só pode contar uma vez.

    É o caso do veículo que para em cima da faixa e o centro da caixa oscila
    com o ruído da detecção. Sem a trava, um carro parado no semáforo somaria
    dezenas de passagens.
    """
    contador = ContadorDeLinha(VERTICAL, quadros_minimos=1)
    alvo_unico = alvo(1, (90, 100))
    contador.atualizar({1: alvo_unico}, 0)
    for i in range(idas_e_voltas):
        alvo_unico.centro = (110, 100)
        contador.atualizar({1: alvo_unico}, i * 2 + 1)
        alvo_unico.centro = (90, 100)
        contador.atualizar({1: alvo_unico}, i * 2 + 2)
    assert contador.contagem.total == 1


@pytest.mark.parametrize('minimos', range(1, 12))
def test_quadros_minimos_segura_alvo_novo_demais(minimos):
    """Detecção passageira em cima da linha não pode virar veículo."""
    contador = ContadorDeLinha(VERTICAL, quadros_minimos=minimos)
    contador.atualizar({1: alvo(1, (90, 100), quadros_visto=minimos - 1)}, 0)
    contagem = contador.atualizar({1: alvo(1, (110, 100), quadros_visto=minimos - 1)}, 1)
    assert contagem.total == 0


@pytest.mark.parametrize('minimos', range(1, 12))
def test_quadros_minimos_libera_quando_atingido(minimos):
    contador = ContadorDeLinha(VERTICAL, quadros_minimos=minimos)
    contador.atualizar({1: alvo(1, (90, 100), quadros_visto=minimos)}, 0)
    contagem = contador.atualizar({1: alvo(1, (110, 100), quadros_visto=minimos)}, 1)
    assert contagem.total == 1


@pytest.mark.parametrize('y', [-80, -40, 250, 300])
def test_travessia_fora_do_trecho_nao_conta(y):
    """Cruzar o prolongamento da reta, longe da linha desenhada, não vale."""
    contador = ContadorDeLinha(VERTICAL, quadros_minimos=1)
    contador.atualizar({1: alvo(1, (90, y))}, 0)
    contagem = contador.atualizar({1: alvo(1, (110, y))}, 1)
    assert contagem.total == 0


@pytest.mark.parametrize('quantidade', range(1, 25))
def test_varios_alvos_cruzando_juntos(quantidade):
    contador = ContadorDeLinha(VERTICAL, quadros_minimos=1)
    antes = {i: alvo(i, (90, 20 + i * 5)) for i in range(1, quantidade + 1)}
    depois = {i: alvo(i, (110, 20 + i * 5)) for i in range(1, quantidade + 1)}
    contador.atualizar(antes, 0)
    contagem = contador.atualizar(depois, 1)
    assert contagem.total == quantidade


def test_evento_guarda_identificador_sentido_e_quadro():
    contador = ContadorDeLinha(VERTICAL, quadros_minimos=1)
    contador.atualizar({7: alvo(7, (90, 100))}, 40)
    contador.atualizar({7: alvo(7, (110, 100))}, 41)
    assert contador.contagem.eventos == [(7, 'saida', 41)]


def test_historico_de_alvo_morto_e_descartado():
    """A memória não pode crescer sem limite num vídeo de horas."""
    contador = ContadorDeLinha(VERTICAL, quadros_minimos=1)
    contador.atualizar({i: alvo(i, (50, 100)) for i in range(1, 30)}, 0)
    assert len(contador._lado_anterior) == 29
    contador.atualizar({1: alvo(1, (50, 100))}, 1)
    assert list(contador._lado_anterior) == [1]


def test_alvo_que_reaparece_com_o_mesmo_id_recomeca_a_comparacao():
    """Sem histórico anterior, o reaparecimento não vira travessia sozinho."""
    contador = ContadorDeLinha(VERTICAL, quadros_minimos=1)
    contador.atualizar({1: alvo(1, (90, 100))}, 0)
    contador.atualizar({}, 1)
    contagem = contador.atualizar({1: alvo(1, (110, 100))}, 2)
    assert contagem.total == 0


def test_reiniciar_zera_tudo():
    contador = ContadorDeLinha(VERTICAL, quadros_minimos=1)
    contador.atualizar({1: alvo(1, (90, 100))}, 0)
    contador.atualizar({1: alvo(1, (110, 100))}, 1)
    assert contador.contagem.total == 1

    contador.reiniciar()
    assert contador.contagem.total == 0
    assert contador.contagem.eventos == []
    assert contador._lado_anterior == {}


@pytest.mark.parametrize('quadro', [0, 1, 7, 99, 1000, 250_000])
def test_quadro_do_evento_e_o_informado(quadro):
    contador = ContadorDeLinha(VERTICAL, quadros_minimos=1)
    contador.atualizar({1: alvo(1, (90, 100))}, quadro - 1)
    contador.atualizar({1: alvo(1, (110, 100))}, quadro)
    assert contador.contagem.eventos[0][2] == quadro


@pytest.mark.parametrize(
    'linha',
    [
        Linha(100, 0, 100, 200),
        Linha(0, 100, 200, 100),
        Linha(0, 0, 200, 200),
        Linha(200, 0, 0, 200),
        Linha(30, 10, 170, 190),
    ],
)
def test_qualquer_orientacao_de_linha_conta_uma_travessia(linha):
    """A regra é geométrica e não depende de a linha ser vertical."""
    contador = ContadorDeLinha(linha, quadros_minimos=1)
    meio = ((linha.x1 + linha.x2) / 2, (linha.y1 + linha.y2) / 2)
    normal = (-(linha.y2 - linha.y1), linha.x2 - linha.x1)
    tamanho = math.hypot(*normal) or 1.0
    unidade = (normal[0] / tamanho, normal[1] / tamanho)

    antes = (meio[0] - unidade[0] * 8, meio[1] - unidade[1] * 8)
    depois = (meio[0] + unidade[0] * 8, meio[1] + unidade[1] * 8)

    contador.atualizar({1: alvo(1, antes)}, 0)
    contagem = contador.atualizar({1: alvo(1, depois)}, 1)
    assert contagem.total == 1


def test_atualizar_sem_alvos_nao_quebra():
    contador = ContadorDeLinha(VERTICAL)
    assert contador.atualizar({}, 0).total == 0


@pytest.mark.parametrize('n', range(2, 15))
def test_sentidos_opostos_somam_em_lados_diferentes(n):
    """Metade indo para cada lado tem que aparecer separada no placar."""
    contador = ContadorDeLinha(VERTICAL, quadros_minimos=1)
    antes = {}
    depois = {}
    for i in range(n):
        y = 20 + i * 4
        if i % 2 == 0:
            antes[i + 1] = alvo(i + 1, (90, y))
            depois[i + 1] = alvo(i + 1, (110, y))
        else:
            antes[i + 1] = alvo(i + 1, (110, y))
            depois[i + 1] = alvo(i + 1, (90, y))
    contador.atualizar(antes, 0)
    contagem = contador.atualizar(depois, 1)
    assert contagem.saidas == (n + 1) // 2
    assert contagem.entradas == n // 2
