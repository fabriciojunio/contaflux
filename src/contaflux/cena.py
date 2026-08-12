"""Gerador de cenas sintéticas com contagem conhecida.

É o que torna a validação exata. Num vídeo de rodovia de verdade só dá para
dizer que o número "parece certo", a menos que alguém sente e conte à mão. Aqui
somos nós que decidimos quantos veículos passam, de que tamanho e em que
sentido, então o erro vira um número em vez de uma impressão.

A cena reproduz de propósito o que atrapalha a contagem em vídeo real: fundo com
textura, ruído de sensor, oscilação de iluminação, sombra acompanhando cada
veículo, e veículos de portes, cores e velocidades diferentes. Uma cena limpa
demais faria os testes passarem sem dizer nada sobre vídeo de verdade.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np

MOTO = 'moto'
CARRO = 'carro'
CAMINHAO = 'caminhão'


@dataclass(frozen=True, slots=True)
class Veiculo:
    """Um veículo que atravessa a cena."""

    entrada_quadro: int
    y: int
    largura: int
    altura: int
    velocidade: float
    cor: tuple[int, int, int]
    sentido: int = 1
    """1 vai da esquerda para a direita, -1 da direita para a esquerda."""

    porte: str = CARRO
    """Só para o gabarito da classificação. Não muda o desenho."""

    def posicao(self, quadro: int, largura_cena: int) -> float | None:
        """Posição x no quadro dado, ou None se ainda não entrou ou já saiu."""
        decorridos = quadro - self.entrada_quadro
        if decorridos < 0:
            return None
        percorrido = decorridos * self.velocidade
        x = -self.largura + percorrido if self.sentido > 0 else largura_cena - percorrido
        if self.sentido > 0 and x > largura_cena:
            return None
        if self.sentido < 0 and x + self.largura < 0:
            return None
        return x


@dataclass
class ParametrosCena:
    largura: int = 640
    altura: int = 360
    fps: float = 25.0
    quadros: int = 460
    ruido: float = 4.0
    sombra: bool = True
    oscilacao_luz: float = 0.0
    semente: int = 1
    veiculos: list[Veiculo] = field(default_factory=list)


# Faixas de tamanho por porte, em pixels na cena de 640 por 360.
#
# A primeira versão fez a moto pequena demais, com 20 por 16 pixels, e o teste
# de classificação falhava sem dizer por quê: a área detectada ficava em torno
# de 630, abaixo do piso de área do detector, e a moto era descartada antes de
# chegar ao classificador. Medindo a área detectada por classe é que apareceu.
#
# Os tamanhos de agora foram escolhidos a partir dessa medida, para que as três
# classes fiquem separadas com folga e o teste meça o classificador em vez do
# arredondamento.
TAMANHOS = {
    MOTO: ((30, 38), (22, 28)),
    CARRO: ((52, 78), (28, 40)),
    CAMINHAO: ((104, 150), (44, 58)),
}


def veiculos_regulares(
    quantidade: int,
    parametros: ParametrosCena,
    intervalo: int = 26,
    sentido: int = 1,
    semente: int | None = None,
) -> list[Veiculo]:
    """Fila de carros espaçados, com tamanho, cor e velocidade variados.

    As três faixas de altura não são enfeite: veículos em faixas diferentes se
    cruzam na imagem e é aí que a sombra de um encosta no outro, que é o modo
    de falhar mais comum deste tipo de contador.
    """
    gerador = np.random.default_rng(semente if semente is not None else parametros.semente)
    faixas = [int(parametros.altura * f) for f in (0.42, 0.58, 0.72)]
    veiculos: list[Veiculo] = []

    for i in range(quantidade):
        largura = int(gerador.integers(46, 78))
        altura = int(gerador.integers(26, 40))
        veiculos.append(
            Veiculo(
                entrada_quadro=20 + i * intervalo,
                y=faixas[i % len(faixas)] - altura // 2,
                largura=largura,
                altura=altura,
                velocidade=float(gerador.uniform(4.5, 7.5)),
                cor=tuple(int(v) for v in gerador.integers(40, 220, 3)),
                sentido=sentido,
                porte=CARRO,
            )
        )
    return veiculos


def veiculos_variados(
    portes: list[str],
    parametros: ParametrosCena,
    intervalo: int = 34,
    sentido: int = 1,
    semente: int | None = None,
) -> list[Veiculo]:
    """Fila com os portes pedidos, na ordem, para testar a classificação.

    O intervalo é maior que o dos carros porque caminhão é comprido: com o
    espaçamento de carro, um caminhão entraria na cena antes de o anterior
    sair, e o gabarito passaria a medir oclusão em vez de classificação.
    """
    gerador = np.random.default_rng(semente if semente is not None else parametros.semente)
    faixas = [int(parametros.altura * f) for f in (0.42, 0.58, 0.72)]
    veiculos: list[Veiculo] = []

    for i, porte in enumerate(portes):
        if porte not in TAMANHOS:
            raise ValueError(f'Porte desconhecido: {porte!r}. Use moto, carro ou caminhão.')
        (l_min, l_max), (a_min, a_max) = TAMANHOS[porte]
        largura = int(gerador.integers(l_min, l_max + 1))
        altura = int(gerador.integers(a_min, a_max + 1))
        veiculos.append(
            Veiculo(
                entrada_quadro=20 + i * intervalo,
                y=faixas[i % len(faixas)] - altura // 2,
                largura=largura,
                altura=altura,
                velocidade=float(gerador.uniform(5.0, 7.0)),
                # Cores claras, longe do cinza do asfalto: este gerador serve
                # para medir classificação por tamanho, e um veículo de baixo
                # contraste que some antes de ser classificado só embaralharia
                # o que o teste mede.
                cor=tuple(int(v) for v in gerador.integers(150, 240, 3)),
                sentido=sentido,
                porte=porte,
            )
        )
    return veiculos


class GeradorDeCena:
    """Desenha os quadros de uma cena sintética."""

    def __init__(self, parametros: ParametrosCena) -> None:
        self.parametros = parametros
        self._gerador = np.random.default_rng(parametros.semente)
        self._fundo = self._montar_fundo()
        # Só é usado quando há oscilação de luz, e converter uma vez evita
        # refazer a conversão em cada um dos milhares de quadros.
        self._fundo_claro = self._fundo.astype(np.float32)

    def _montar_fundo(self) -> np.ndarray:
        p = self.parametros
        fundo = np.full((p.altura, p.largura, 3), 96, dtype=np.uint8)
        cv2.rectangle(fundo, (0, 0), (p.largura, int(p.altura * 0.3)), (58, 92, 60), -1)
        cv2.rectangle(
            fundo, (0, int(p.altura * 0.85)), (p.largura, p.altura), (58, 92, 60), -1
        )
        for x in range(0, p.largura, 60):
            cv2.rectangle(
                fundo,
                (x, int(p.altura * 0.5) - 2),
                (x + 30, int(p.altura * 0.5) + 2),
                (210, 210, 210),
                -1,
            )

        # Textura no fundo de propósito. Fundo de cor chapada tornaria a
        # subtração trivial, e o teste deixaria de dizer qualquer coisa sobre
        # vídeo real, onde asfalto e grama sempre têm granulado.
        textura = self._gerador.normal(0, 7, fundo.shape)
        return np.clip(fundo.astype(float) + textura, 0, 255).astype(np.uint8)

    def quadro(self, indice: int) -> np.ndarray:
        p = self.parametros

        # As contas em float32, e não no float64 padrão do NumPy, cortam pela
        # metade o tempo de gerar a cena. Isso importa porque a suíte gera
        # dezenas de milhares de quadros, e medindo deu para ver que gerar
        # custava quatro vezes mais que contar. Meio tom de precisão não muda
        # nada numa imagem de oito bits.
        if p.oscilacao_luz:
            fator = 1 + p.oscilacao_luz * math.sin(2 * math.pi * indice / 60.0)
            imagem = np.clip(self._fundo_claro * fator, 0, 255).astype(np.uint8)
        else:
            imagem = self._fundo.copy()

        for veiculo in p.veiculos:
            x = veiculo.posicao(indice, p.largura)
            if x is None:
                continue
            xi = int(round(x))

            if p.sombra:
                self._desenhar_sombra(imagem, xi, veiculo)

            cv2.rectangle(
                imagem,
                (xi, veiculo.y),
                (xi + veiculo.largura, veiculo.y + veiculo.altura),
                veiculo.cor,
                -1,
            )
            # Para-brisa, para o objeto não ser um retângulo chapado. Ele muda
            # a estatística interna do blob, que é o que a subtração de fundo
            # enxerga.
            cv2.rectangle(
                imagem,
                (xi + 6, veiculo.y + 5),
                (xi + veiculo.largura - 6, veiculo.y + veiculo.altura // 2),
                tuple(int(c * 0.55) for c in veiculo.cor),
                -1,
            )

        if p.ruido:
            ruido = self._gerador.standard_normal(imagem.shape, dtype=np.float32)
            ruido *= p.ruido
            imagem = np.clip(imagem + ruido, 0, 255).astype(np.uint8)

        return imagem

    def _desenhar_sombra(self, imagem: np.ndarray, x: int, veiculo: Veiculo) -> None:
        """Sombra deslocada, escurecendo o fundo sem cobri-lo.

        É o principal artefato deste tipo de cena. Ela gruda no veículo, pode
        unir dois vizinhos num borrão só, e é escura o bastante para o modelo de
        fundo marcá-la como movimento se ninguém tratar disso.
        """
        p = self.parametros
        x0, y0 = x + 8, veiculo.y + veiculo.altura - 6
        x1, y1 = x + veiculo.largura + 8, veiculo.y + veiculo.altura + 10
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(p.largura, x1), min(p.altura, y1)
        if x1 <= x0 or y1 <= y0:
            return
        recorte = imagem[y0:y1, x0:x1].astype(float) * 0.62
        imagem[y0:y1, x0:x1] = recorte.astype(np.uint8)

    def quadros(self):
        for indice in range(self.parametros.quadros):
            yield self.quadro(indice)

    def gravar(self, caminho: str) -> None:
        """Grava a cena em arquivo, para poder ser aberta como vídeo real."""
        p = self.parametros
        escritor = cv2.VideoWriter(
            caminho, cv2.VideoWriter_fourcc(*'mp4v'), p.fps, (p.largura, p.altura)
        )
        try:
            for quadro in self.quadros():
                escritor.write(quadro)
        finally:
            escritor.release()

    def travessias_esperadas(self, x_linha: float) -> int:
        """Quantos veículos realmente cruzam a linha vertical dada.

        Calculado a partir das trajetórias, e não do número de veículos criados:
        um veículo que entre tarde demais pode não chegar à linha antes de o
        vídeo acabar, e contá-lo como esperado tornaria o gabarito errado.
        """
        return len(self.quem_cruza(x_linha))

    def quem_cruza(self, x_linha: float) -> list[Veiculo]:
        """Os veículos que cruzam a linha, na ordem em que a cruzam."""
        p = self.parametros
        cruzam: list[tuple[int, Veiculo]] = []

        for veiculo in p.veiculos:
            anterior = None
            for indice in range(p.quadros):
                x = veiculo.posicao(indice, p.largura)
                if x is None:
                    continue
                atual = (x + veiculo.largura / 2) - x_linha
                if anterior is not None and (anterior > 0) != (atual > 0):
                    cruzam.append((indice, veiculo))
                    break
                anterior = atual

        cruzam.sort(key=lambda par: par[0])
        return [veiculo for _, veiculo in cruzam]
