"""Gerador de cenas sintéticas com contagem conhecida.

É o que torna a validação exata. Um vídeo de rodovia de verdade só permite
dizer que o número "parece certo", a menos que alguém conte à mão. Aqui somos
nós que decidimos quantos veículos passam e em que sentido, então o erro é um
número e não uma impressão.

A cena reproduz o que atrapalha a contagem em vídeo real: fundo com textura,
ruído de sensor, oscilação de iluminação, sombra acompanhando cada objeto e
veículos de tamanhos e velocidades diferentes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass(frozen=True, slots=True)
class Veiculo:
    """Um objeto que atravessa a cena."""

    entrada_quadro: int
    y: int
    largura: int
    altura: int
    velocidade: float
    cor: tuple[int, int, int]
    sentido: int = 1
    """1 vai da esquerda para a direita, -1 da direita para a esquerda."""

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


def pessoas_regulares(
    quantidade: int,
    parametros: 'ParametrosCena',
    intervalo: int = 70,
    sentido: int = 1,
    semente: int | None = None,
) -> list[Veiculo]:
    """Pessoas atravessando a porta de uma loja.

    A diferença para veículos não é cosmética. Pessoa é mais alta que larga e
    passa por uma faixa estreita, que é a porta. Gerar pessoas com a geometria
    de carros faria os testes validarem uma calibração que não serve na loja.

    A velocidade merece explicação, porque uma primeira versão errou aqui e o
    erro custou caro. Foram usados 2,4 pixels por quadro, achando que "pessoa
    anda devagar" bastava como critério. Numa cena de 640 pixels isso dá onze
    segundos para atravessar, e com uma pessoa entrando a cada segundo e meio
    havia oito pessoas simultâneas na imagem, todas na mesma faixa, fundidas
    num borrão só. A contagem caía pela metade, e a culpa parecia do
    rastreador.

    O número certo vem da geometria real: a câmera de porta enquadra cerca de
    três metros, e alguém andando a 1,2 metro por segundo cruza isso em dois a
    três segundos. A vinte e cinco quadros por segundo, são seis a nove pixels
    por quadro.
    """
    gerador = np.random.default_rng(semente if semente is not None else parametros.semente)
    # Todos passam pela mesma região, como numa porta, variando pouco a altura
    # em que aparecem por causa da perspectiva.
    base_y = int(parametros.altura * 0.38)
    pessoas: list[Veiculo] = []

    for i in range(quantidade):
        largura = int(gerador.integers(26, 38))
        altura = int(gerador.integers(62, 88))
        pessoas.append(
            Veiculo(
                # A primeira só entra depois de um tempo de cena vazia. O modelo
                # de fundo precisa desses quadros para aprender como é a loja
                # sem ninguém; quem passa antes disso não é detectado, porque o
                # modelo ainda considera tudo novidade.
                entrada_quadro=60 + i * intervalo,
                y=base_y + int(gerador.integers(-14, 15)),
                largura=largura,
                altura=altura,
                velocidade=float(gerador.uniform(6.0, 9.0)),
                cor=tuple(int(v) for v in gerador.integers(35, 200, 3)),
                sentido=sentido,
            )
        )
    return pessoas


@dataclass
class ParametrosCena:
    largura: int = 640
    altura: int = 360
    fps: float = 25.0
    quadros: int = 400
    ruido: float = 4.0
    sombra: bool = True
    oscilacao_luz: float = 0.0
    semente: int = 1
    veiculos: list[Veiculo] = field(default_factory=list)
    cenario: str = 'rodovia'
    """`rodovia` desenha pista com faixas, `loja` desenha piso e vitrine."""


def veiculos_regulares(
    quantidade: int,
    parametros: ParametrosCena,
    intervalo: int = 26,
    sentido: int = 1,
    semente: int | None = None,
) -> list[Veiculo]:
    """Fila de veículos espaçados, com tamanho e velocidade variados."""
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
            )
        )
    return veiculos


class GeradorDeCena:
    """Desenha os quadros de uma cena sintética."""

    def __init__(self, parametros: ParametrosCena) -> None:
        self.parametros = parametros
        self._gerador = np.random.default_rng(parametros.semente)
        self._fundo = self._montar_fundo()

    def _montar_fundo(self) -> np.ndarray:
        p = self.parametros
        if p.cenario == 'loja':
            fundo = self._fundo_de_loja()
        else:
            fundo = self._fundo_de_rodovia()

        # Textura no fundo de propósito. Fundo de cor chapada tornaria a
        # subtração trivial, e o teste deixaria de dizer qualquer coisa sobre
        # vídeo real, onde piso e parede sempre têm granulado.
        textura = self._gerador.normal(0, 7, fundo.shape)
        return np.clip(fundo.astype(float) + textura, 0, 255).astype(np.uint8)

    def _fundo_de_rodovia(self) -> np.ndarray:
        p = self.parametros
        fundo = np.full((p.altura, p.largura, 3), 96, dtype=np.uint8)
        cv2.rectangle(fundo, (0, 0), (p.largura, int(p.altura * 0.3)), (58, 92, 60), -1)
        cv2.rectangle(fundo, (0, int(p.altura * 0.85)), (p.largura, p.altura), (58, 92, 60), -1)
        for x in range(0, p.largura, 60):
            cv2.rectangle(
                fundo, (x, int(p.altura * 0.5) - 2), (x + 30, int(p.altura * 0.5) + 2),
                (210, 210, 210), -1,
            )
        return fundo

    def _fundo_de_loja(self) -> np.ndarray:
        """Piso, parede e vitrine, vistos de dentro da loja."""
        p = self.parametros
        fundo = np.full((p.altura, p.largura, 3), 158, dtype=np.uint8)

        # Parede ao fundo e piso mais claro, separados na altura do rodapé.
        horizonte = int(p.altura * 0.30)
        cv2.rectangle(fundo, (0, 0), (p.largura, horizonte), (176, 172, 168), -1)
        cv2.rectangle(fundo, (0, horizonte), (p.largura, p.altura), (146, 148, 152), -1)

        # Vitrine, mais clara que a parede porque entra luz da rua por ela.
        cv2.rectangle(
            fundo, (int(p.largura * 0.18), int(p.altura * 0.05)),
            (int(p.largura * 0.82), horizonte - 6), (206, 208, 205), -1,
        )
        cv2.rectangle(
            fundo, (int(p.largura * 0.18), int(p.altura * 0.05)),
            (int(p.largura * 0.82), horizonte - 6), (120, 120, 118), 3,
        )

        # Rejunte do piso, que dá textura estruturada e não só ruído.
        for x in range(0, p.largura, 70):
            cv2.line(fundo, (x, horizonte), (x, p.altura), (132, 134, 138), 1)
        for y in range(horizonte, p.altura, 46):
            cv2.line(fundo, (0, y), (p.largura, y), (132, 134, 138), 1)

        return fundo

    def quadro(self, indice: int) -> np.ndarray:
        p = self.parametros
        imagem = self._fundo.copy().astype(float)

        if p.oscilacao_luz:
            imagem *= 1 + p.oscilacao_luz * np.sin(2 * np.pi * indice / 60.0)

        imagem = np.clip(imagem, 0, 255).astype(np.uint8)

        for veiculo in p.veiculos:
            x = veiculo.posicao(indice, p.largura)
            if x is None:
                continue
            xi = int(round(x))

            if p.sombra:
                # Sombra deslocada e escurecendo o fundo, como no vídeo real.
                # É o principal artefato deste tipo de cena: ela gruda no
                # veículo e pode unir dois vizinhos num borrão só.
                sx0, sy0 = xi + 8, veiculo.y + veiculo.altura - 6
                sx1, sy1 = xi + veiculo.largura + 8, veiculo.y + veiculo.altura + 10
                sx0c, sy0c = max(0, sx0), max(0, sy0)
                sx1c, sy1c = min(p.largura, sx1), min(p.altura, sy1)
                if sx1c > sx0c and sy1c > sy0c:
                    escurecida = imagem[sy0c:sy1c, sx0c:sx1c].astype(float) * 0.62
                    imagem[sy0c:sy1c, sx0c:sx1c] = escurecida.astype(np.uint8)

            if p.cenario == 'loja':
                self._desenhar_pessoa(imagem, xi, veiculo)
            else:
                cv2.rectangle(
                    imagem, (xi, veiculo.y),
                    (xi + veiculo.largura, veiculo.y + veiculo.altura),
                    veiculo.cor, -1,
                )
                # Para-brisa, só para o objeto não ser um retângulo chapado.
                cv2.rectangle(
                    imagem, (xi + 6, veiculo.y + 5),
                    (xi + veiculo.largura - 6, veiculo.y + veiculo.altura // 2),
                    tuple(int(c * 0.55) for c in veiculo.cor), -1,
                )

        if p.ruido:
            imagem = np.clip(
                imagem.astype(float) + self._gerador.normal(0, p.ruido, imagem.shape),
                0, 255,
            ).astype(np.uint8)

        return imagem

    @staticmethod
    def _desenhar_pessoa(imagem: np.ndarray, x: int, pessoa: Veiculo) -> None:
        """Silhueta com cabeça, tronco e pernas.

        Não é enfeite: o detector filtra por proporção entre largura e altura, e
        uma pessoa desenhada como retângulo cheio teria proporção diferente da
        silhueta real, que é estreita na cabeça e vazada entre as pernas. Testar
        contra a forma errada validaria uma calibração que não serve na loja.
        """
        cabeca_r = max(4, pessoa.largura // 3)
        centro_x = x + pessoa.largura // 2
        topo = pessoa.y

        cv2.circle(imagem, (centro_x, topo + cabeca_r), cabeca_r,
                   tuple(int(c * 0.8) for c in pessoa.cor), -1)

        tronco_topo = topo + cabeca_r * 2
        tronco_base = topo + int(pessoa.altura * 0.62)
        cv2.rectangle(imagem, (x, tronco_topo),
                      (x + pessoa.largura, tronco_base), pessoa.cor, -1)

        # Duas pernas com uma folga entre elas.
        largura_perna = max(3, pessoa.largura // 3)
        cor_perna = tuple(int(c * 0.7) for c in pessoa.cor)
        cv2.rectangle(imagem, (x + 2, tronco_base),
                      (x + 2 + largura_perna, topo + pessoa.altura), cor_perna, -1)
        cv2.rectangle(imagem, (x + pessoa.largura - 2 - largura_perna, tronco_base),
                      (x + pessoa.largura - 2, topo + pessoa.altura), cor_perna, -1)

    def quadros(self):
        for indice in range(self.parametros.quadros):
            yield self.quadro(indice)

    def gravar(self, caminho: str) -> None:
        """Grava a cena em arquivo, para poder ser aberta como vídeo real."""
        p = self.parametros
        escritor = cv2.VideoWriter(
            caminho, cv2.VideoWriter_fourcc(*'mp4v'), p.fps, (p.largura, p.altura)
        )
        for quadro in self.quadros():
            escritor.write(quadro)
        escritor.release()

    def travessias_esperadas(self, x_linha: float) -> int:
        """Quantos veículos realmente cruzam a linha vertical dada.

        Calculado a partir das trajetórias, e não do número de veículos criados:
        um veículo que entre tarde demais pode não chegar à linha antes de o
        vídeo acabar, e contá-lo como esperado tornaria o gabarito errado.
        """
        p = self.parametros
        total = 0
        for veiculo in p.veiculos:
            lados = []
            for indice in range(p.quadros):
                x = veiculo.posicao(indice, p.largura)
                if x is None:
                    continue
                lados.append((x + veiculo.largura / 2) - x_linha)
            if len(lados) < 2:
                continue
            if any((a > 0) != (b > 0) for a, b in zip(lados, lados[1:])):
                total += 1
        return total
