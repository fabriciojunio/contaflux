"""Calibração para cada tipo de cena.

O algoritmo é o mesmo em qualquer vídeo; o que muda de uma câmera para outra é
o tamanho que um veículo ocupa na imagem e o quanto ele anda entre dois
quadros. Deixar esses números soltos pelo código foi a primeira versão deste
projeto, e cada ajuste exigia caçar constantes em três arquivos. Agrupados num
perfil, trocar de cena é trocar um argumento.

Sobre o limiar de variância, que é o número mais delicado daqui: ele decide
quanto um pixel precisa destoar do fundo para contar como movimento. A primeira
calibração usou 40, que é a ordem de grandeza sugerida na documentação do MOG2,
e a contagem acertava 8 casos em 12. O motivo apareceu medindo quadro a quadro:
um carro verde-escuro sobre asfalto cinza tem diferença de cor pequena o
bastante para ficar abaixo do limiar, e simplesmente não era detectado. Não era
o rastreador errando, era o objeto nunca chegando até ele.

O valor 3 é o maior que fecha os dez casos da varredura de calibração. Ele é
bem mais baixo que o padrão do OpenCV, e isso tem uma explicação: a textura do
asfalto é fixa e o modelo de fundo a aprende, então o que sobra de variância no
pixel é quase só ruído de sensor, e o limiar não precisa cobrir mais que isso.

A pergunta óbvia é se um limiar tão baixo não passa a contar ruído como
veículo. Dois casos da varredura existem para responder isso: uma cena vazia,
que precisa devolver zero, e uma cena com o triplo do ruído, que precisa
devolver o número certo. As duas fecham. Quem segura o ruído não é o limiar, é
o filtro de área junto com a morfologia.
"""

from __future__ import annotations

from dataclasses import dataclass

from contaflux.porte import FaixasDePorte


@dataclass(frozen=True, slots=True)
class Perfil:
    """Parâmetros calibrados para um tipo de cena."""

    nome: str
    descricao: str
    area_minima: int
    area_maxima: int | None
    proporcao_maxima: float
    """Razão largura sobre altura aceita, do maior valor. O recíproco também é
    aceito, então o filtro barra formas alongadas nos dois sentidos."""

    distancia_maxima: float
    tolerancia_sumico: int
    quadros_minimos: int
    historico_fundo: int
    limiar_variancia: float
    faixas: FaixasDePorte
    rotulo_positivo: str
    rotulo_negativo: str


RODOVIA = Perfil(
    nome='rodovia',
    descricao='pista de fluxo livre, câmera lateral ou de passarela',
    # Um carro numa câmera de passarela ocupa alguns milhares de pixels.
    # Setecentos é folgado o bastante para pegar moto e apertado o bastante
    # para descartar folha, pássaro e ruído.
    area_minima=700,
    area_maxima=None,
    # Caminhão visto de lado é bem mais comprido que alto, e seis cobre isso
    # sem deixar passar a faixa da pista, que é muito mais alongada.
    proporcao_maxima=6.0,
    # A noventa quilômetros por hora, numa câmera que enquadra trinta metros a
    # vinte e cinco quadros por segundo, o veículo anda cerca de vinte pixels
    # entre quadros. Noventa dá margem para o dobro disso sem confundir
    # veículos vizinhos.
    distancia_maxima=90.0,
    tolerancia_sumico=10,
    quadros_minimos=3,
    historico_fundo=300,
    limiar_variancia=3.0,
    faixas=FaixasDePorte(ate_moto=1400, ate_carro=4200),
    rotulo_positivo='sentido A',
    rotulo_negativo='sentido B',
)


URBANO = Perfil(
    nome='urbano',
    descricao='via de cidade, câmera mais baixa e trânsito mais lento',
    # Câmera mais perto da via: o mesmo carro ocupa mais pixels, então o piso
    # sobe junto para não promover sombra e pedestre a veículo.
    area_minima=1200,
    area_maxima=None,
    proporcao_maxima=5.0,
    # Trânsito lento anda pouco entre quadros, e apertar aqui é o que evita
    # que dois carros parados no semáforo troquem de identidade.
    distancia_maxima=55.0,
    # Em cidade o veículo some atrás de poste, placa e outro veículo com muito
    # mais frequência, e voltar como alvo novo significaria contar duas vezes.
    tolerancia_sumico=18,
    quadros_minimos=4,
    historico_fundo=400,
    limiar_variancia=3.0,
    faixas=FaixasDePorte(ate_moto=2200, ate_carro=7000),
    rotulo_positivo='sentido A',
    rotulo_negativo='sentido B',
)


PERFIS: dict[str, Perfil] = {RODOVIA.nome: RODOVIA, URBANO.nome: URBANO}

PADRAO = RODOVIA


def obter(nome: str) -> Perfil:
    """Busca um perfil pelo nome, com mensagem útil quando não existe."""
    chave = nome.strip().lower()
    if chave not in PERFIS:
        disponiveis = ', '.join(PERFIS)
        raise ValueError(f'Perfil desconhecido: {nome!r}. Disponíveis: {disponiveis}.')
    return PERFIS[chave]
