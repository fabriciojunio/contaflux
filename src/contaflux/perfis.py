"""Calibração para cada tipo de objeto contado.

Pessoa e veículo são o mesmo problema geométrico e exigem números bem
diferentes, e usar os mesmos parâmetros para os dois é o jeito mais rápido de
errar a contagem.

Pessoa é mais alta que larga, e carro é o contrário. Pessoa anda de três a cinco
vezes mais devagar, então cabe menos deslocamento entre quadros e o rastreio
pode ser mais exigente na distância. E pessoa some atrás de outra pessoa com
muito mais frequência, o que pede mais tolerância a desaparecimento: numa porta
de loja, duas pessoas entrando lado a lado se cobrem por vários quadros.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Perfil:
    """Parâmetros calibrados para um tipo de objeto."""

    nome: str
    area_minima: int
    area_maxima: int | None
    proporcao_maxima: float
    """Razão largura sobre altura aceita, do maior valor. O recíproco também
    é aceito, então o filtro barra formas alongadas nos dois sentidos."""

    distancia_maxima: float
    tolerancia_sumico: int
    quadros_minimos: int
    historico_fundo: int
    limiar_variancia: float
    rotulo_positivo: str
    rotulo_negativo: str
    conta_saldo: bool
    """Se faz sentido perguntar quantos estão dentro neste momento."""


PESSOAS = Perfil(
    nome='pessoas',
    # Pessoa ocupa menos pixels que carro numa cena típica de porta de loja,
    # onde a câmera está a poucos metros.
    area_minima=900,
    area_maxima=60_000,
    # Pessoa em pé raramente passa de uma vez e meia mais larga que alta, mesmo
    # de braços abertos ou carregando sacola.
    proporcao_maxima=2.2,
    # Andando devagar, o deslocamento entre quadros é pequeno. Apertar aqui
    # evita que duas pessoas próximas troquem de identidade.
    distancia_maxima=55.0,
    # Na porta, uma pessoa esconde a outra com frequência. Tolerar mais quadros
    # de sumiço evita que a mesma pessoa volte como alvo novo e seja contada
    # duas vezes.
    tolerancia_sumico=20,
    quadros_minimos=4,
    historico_fundo=400,
    limiar_variancia=32.0,
    rotulo_positivo='entradas',
    rotulo_negativo='saídas',
    conta_saldo=True,
)


VEICULOS = Perfil(
    nome='veiculos',
    area_minima=700,
    area_maxima=None,
    proporcao_maxima=6.0,
    distancia_maxima=90.0,
    tolerancia_sumico=10,
    quadros_minimos=3,
    historico_fundo=300,
    limiar_variancia=40.0,
    rotulo_positivo='sentido A',
    rotulo_negativo='sentido B',
    conta_saldo=False,
)


PERFIS: dict[str, Perfil] = {PESSOAS.nome: PESSOAS, VEICULOS.nome: VEICULOS}


def obter(nome: str) -> Perfil:
    """Busca um perfil pelo nome, com mensagem útil quando não existe."""
    chave = nome.strip().lower()
    if chave not in PERFIS:
        disponiveis = ', '.join(PERFIS)
        raise ValueError(f'Perfil desconhecido: {nome!r}. Disponíveis: {disponiveis}.')
    return PERFIS[chave]
