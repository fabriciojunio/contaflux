"""Separar moto, carro e caminhão pelo tamanho na imagem.

Uma contagem de rodovia que devolve só um número serve para pouco. Saber que
passaram trezentos veículos e que quarenta deles eram caminhões muda o que se
conclui sobre desgaste de pavimento e sobre horário de pico.

A separação aqui é por área da caixa, e é honesta sobre o próprio limite: ela
funciona porque a câmera é fixa e enquadra sempre a mesma faixa de pista, então
um carro sempre ocupa mais ou menos os mesmos pixels. Num enquadramento com
muita perspectiva, em que o fundo da cena fica bem menor que a frente, a área
sozinha deixa de bastar e seria preciso corrigir pela posição vertical antes de
classificar. Está registrado no README como limitação conhecida.
"""

from __future__ import annotations

from dataclasses import dataclass

MOTO = 'moto'
CARRO = 'carro'
CAMINHAO = 'caminhão'
DESCONHECIDO = 'desconhecido'

FRACAO_DE_MOTO = 0.55
"""Abaixo desta fração do veículo mediano, é moto.

Uma moto vista de trás ocupa perto de um terço da área de um carro; de lado,
perto de metade. Cinquenta e cinco por cento fica acima dos dois casos sem
chegar perto do carro pequeno, que raramente desce de setenta por cento da
mediana."""

FRACAO_DE_CAMINHAO = 1.9
"""Acima desta fração do veículo mediano, é caminhão.

Um caminhão ou ônibus tem o dobro do comprimento de um carro e um pouco mais
de altura, o que dá bem mais que o dobro de área. Um e nove deixa de fora a
picape e a van grande, que são carros para efeito de contagem de tráfego."""


@dataclass(frozen=True, slots=True)
class FaixasDePorte:
    """Limites de área, em pixels, que separam as classes."""

    ate_moto: int
    ate_carro: int

    def __post_init__(self) -> None:
        if self.ate_moto <= 0:
            raise ValueError('O limite de moto precisa ser positivo.')
        if self.ate_carro <= self.ate_moto:
            raise ValueError('O limite de carro precisa ser maior que o de moto.')

    @classmethod
    def relativas(cls, area_tipica: float) -> 'FaixasDePorte':
        """Faixas ancoradas no tamanho que os veículos têm neste vídeo.

        Limites em pixels absolutos só valem para a câmera em que foram
        medidos. Numa câmera baixa, o carro que passa perto ocupa quinze mil
        pixels e é classificado como caminhão; numa vista aérea, o caminhão
        ocupa mil e vira moto. Foi exatamente o que apareceu ao rodar num vídeo
        real: quinze dos vinte e três veículos saíram como caminhão, num vídeo
        em que quase tudo era carro.

        A âncora é a área mediana observada. Ela funciona porque carro é o
        veículo mais comum em qualquer via: a mediana cai em cima dele, e as
        outras duas classes se definem por proporção a partir dali.

        O preço é conhecido e vale dizer: numa via só de caminhões, a mediana
        vira caminhão e a classificação inteira escorrega. Para esse caso, e
        para comparar vídeos entre si, as faixas fixas do perfil continuam
        disponíveis.
        """
        if area_tipica <= 0:
            raise ValueError('A área típica precisa ser positiva.')
        return cls(
            ate_moto=max(1, int(area_tipica * FRACAO_DE_MOTO)),
            ate_carro=max(2, int(area_tipica * FRACAO_DE_CAMINHAO)),
        )

    def classificar(self, area: int) -> str:
        """Nome da classe para uma área. Área não positiva vira desconhecido."""
        if area <= 0:
            return DESCONHECIDO
        if area <= self.ate_moto:
            return MOTO
        if area <= self.ate_carro:
            return CARRO
        return CAMINHAO


def contar_por_classe(classes: list[str]) -> dict[str, int]:
    """Totais por classe, com todas as chaves presentes mesmo quando zeradas.

    Manter as chaves fixas evita o relatório mudar de formato conforme o vídeo,
    que é o tipo de coisa que quebra a planilha de quem consome o CSV.
    """
    totais = {MOTO: 0, CARRO: 0, CAMINHAO: 0, DESCONHECIDO: 0}
    for classe in classes:
        totais[classe] = totais.get(classe, 0) + 1
    return totais
