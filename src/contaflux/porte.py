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
