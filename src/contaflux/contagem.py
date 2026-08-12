"""Contar quem cruza uma linha, e em que sentido.

Contar por presença na tela seria frágil: o número subiria e desceria conforme
os objetos entram e saem do quadro, e um objeto parado dentro da cena ficaria
sendo contado para sempre.

Contar cruzamento de linha resolve isso. Um objeto só é contado no instante em
que atravessa uma linha imaginária, uma única vez, e o lado de onde ele veio dá
o sentido. É o mesmo princípio de um laço indutivo no asfalto ou de um sensor de
porta de loja.

A detecção do cruzamento usa o sinal do produto vetorial entre a linha e o
centro do objeto: o sinal diz de que lado o ponto está, e a troca de sinal entre
dois quadros consecutivos significa que a linha foi atravessada no intervalo.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from contaflux.rastreio import Alvo


@dataclass(frozen=True, slots=True)
class Linha:
    """Linha de contagem, definida por dois pontos."""

    x1: float
    y1: float
    x2: float
    y2: float

    def lado(self, ponto: tuple[float, float]) -> float:
        """Sinal indica o lado; magnitude, a distância proporcional."""
        return (self.x2 - self.x1) * (ponto[1] - self.y1) - (self.y2 - self.y1) * (
            ponto[0] - self.x1
        )

    @property
    def comprimento(self) -> float:
        return ((self.x2 - self.x1) ** 2 + (self.y2 - self.y1) ** 2) ** 0.5

    def dentro_do_segmento(self, ponto: tuple[float, float]) -> bool:
        """Confere se o cruzamento aconteceu dentro do trecho desenhado.

        A reta que passa pelos dois pontos é infinita, mas a linha de contagem
        não é. Sem esta verificação, um objeto passando muito acima ou abaixo do
        trecho marcado seria contado, porque cruzaria o prolongamento da reta.
        """
        comprimento = self.comprimento
        if comprimento < 1e-9:
            return False
        t = (
            (ponto[0] - self.x1) * (self.x2 - self.x1)
            + (ponto[1] - self.y1) * (self.y2 - self.y1)
        ) / (comprimento**2)
        return -0.05 <= t <= 1.05


@dataclass
class Contagem:
    """Totais acumulados."""

    entradas: int = 0
    saidas: int = 0
    eventos: list[tuple[int, str, int]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.entradas + self.saidas

    @property
    def saldo(self) -> int:
        """Quantos estão dentro, no caso de porta de loja."""
        return self.entradas - self.saidas


class ContadorDeLinha:
    """Conta alvos que cruzam a linha, separando por sentido."""

    def __init__(self, linha: Linha, quadros_minimos: int = 3) -> None:
        """
        `quadros_minimos` exige que o alvo tenha sido visto por alguns quadros
        antes de valer como contagem. É o filtro contra detecção passageira: um
        reflexo ou um pedaço de sombra que aparece por um instante em cima da
        linha não vira um carro.
        """
        self.linha = linha
        self.quadros_minimos = quadros_minimos
        self.contagem = Contagem()
        self._lado_anterior: dict[int, float] = {}

    def atualizar(self, alvos: dict[int, Alvo], quadro: int = 0) -> Contagem:
        """Processa os alvos de um quadro e atualiza os totais."""
        vivos = set(alvos)

        for identificador, alvo in alvos.items():
            lado_atual = self.linha.lado(alvo.centro)
            anterior = self._lado_anterior.get(identificador)
            self._lado_anterior[identificador] = lado_atual

            if anterior is None or alvo.contado:
                continue
            if alvo.quadros_visto < self.quadros_minimos:
                continue
            # Sinais iguais significam que o objeto continua do mesmo lado.
            if (anterior > 0) == (lado_atual > 0):
                continue
            if not self.linha.dentro_do_segmento(alvo.centro):
                continue

            alvo.contado = True
            if lado_atual > 0:
                self.contagem.entradas += 1
                self.contagem.eventos.append((identificador, 'entrada', quadro))
            else:
                self.contagem.saidas += 1
                self.contagem.eventos.append((identificador, 'saida', quadro))

        # Limpa o histórico de quem já saiu de cena, para a memória não crescer
        # indefinidamente num vídeo longo.
        for identificador in list(self._lado_anterior):
            if identificador not in vivos:
                del self._lado_anterior[identificador]

        return self.contagem

    def reiniciar(self) -> None:
        self.contagem = Contagem()
        self._lado_anterior.clear()
