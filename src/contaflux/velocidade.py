"""Estimar a velocidade de cada veículo a partir da trajetória.

Contar quantos passaram é metade do que uma câmera de rodovia precisa
responder. A outra metade é a que velocidade passaram, e ela sai de graça:
o rastreio já guarda onde o veículo estava em cada quadro, e velocidade é a
inclinação dessa reta.

A conversão de pixel para metro precisa de uma referência medida na cena, e
não há como adivinhá-la a partir da imagem. Aqui ela é um parâmetro explícito:
o usuário informa quantos metros cabem na largura do quadro, ou o comprimento
de um trecho conhecido, e o resto é aritmética.

A inclinação é estimada por Theil-Sen, que é a mediana das inclinações entre
todos os pares de pontos, e não por mínimos quadrados. O motivo é o modo de
falhar deste rastreador: quando dois veículos se encostam, a caixa vira uma só
e o centro pula. Mínimos quadrados elevam esse pulo ao quadrado e a estimativa
vai junto. A mediana ignora o pulo enquanto ele for minoria, que é o caso.
"""

from __future__ import annotations

from dataclasses import dataclass

from contaflux.rastreio import Alvo


@dataclass(frozen=True, slots=True)
class Escala:
    """Como converter pixel em metro nesta cena."""

    metros_por_pixel: float
    fps: float

    @classmethod
    def de_largura(cls, largura_quadro: int, metros_visiveis: float, fps: float) -> 'Escala':
        """Escala a partir de quantos metros de pista cabem na largura da imagem.

        É a forma mais fácil de calibrar em campo: mede-se com trena um trecho
        que atravessa o quadro inteiro, ou usa-se a distância entre dois postes.
        """
        if largura_quadro <= 0:
            raise ValueError('A largura do quadro precisa ser positiva.')
        if metros_visiveis <= 0:
            raise ValueError('O trecho visível precisa ser positivo.')
        if fps <= 0:
            raise ValueError('A taxa de quadros precisa ser positiva.')
        return cls(metros_visiveis / largura_quadro, fps)

    @classmethod
    def de_trecho(cls, pixels: float, metros: float, fps: float) -> 'Escala':
        """Escala a partir de um trecho conhecido medido em pixels na imagem."""
        if pixels <= 0:
            raise ValueError('O trecho em pixels precisa ser positivo.')
        if metros <= 0:
            raise ValueError('O trecho em metros precisa ser positivo.')
        if fps <= 0:
            raise ValueError('A taxa de quadros precisa ser positiva.')
        return cls(metros / pixels, fps)


def inclinacao_robusta(tempos: list[int], valores: list[float]) -> float:
    """Mediana das inclinações entre todos os pares. Zero se não der para medir."""
    inclinacoes: list[float] = []
    for i in range(len(tempos)):
        for j in range(i + 1, len(tempos)):
            dt = tempos[j] - tempos[i]
            if dt == 0:
                continue
            inclinacoes.append((valores[j] - valores[i]) / dt)

    if not inclinacoes:
        return 0.0

    inclinacoes.sort()
    meio = len(inclinacoes) // 2
    if len(inclinacoes) % 2:
        return inclinacoes[meio]
    return (inclinacoes[meio - 1] + inclinacoes[meio]) / 2.0


def pixels_por_quadro(alvo: Alvo, minimo_de_pontos: int = 5) -> float | None:
    """Rapidez do alvo em pixels por quadro, ou None se a trajetória é curta.

    Devolver None em vez de zero é proposital. Um alvo recém-nascido tem dois
    ou três pontos, e qualquer número tirado dali é ruído com cara de medida.
    É melhor a interface mostrar um traço do que mostrar 3 km/h para um carro a
    80.
    """
    if len(alvo.trajetoria) < minimo_de_pontos:
        return None
    if len(alvo.indices) != len(alvo.trajetoria):
        return None

    dx = inclinacao_robusta(alvo.indices, [p[0] for p in alvo.trajetoria])
    dy = inclinacao_robusta(alvo.indices, [p[1] for p in alvo.trajetoria])
    return (dx * dx + dy * dy) ** 0.5


def em_km_por_hora(alvo: Alvo, escala: Escala, minimo_de_pontos: int = 5) -> float | None:
    """Velocidade do alvo em quilômetros por hora."""
    rapidez = pixels_por_quadro(alvo, minimo_de_pontos)
    if rapidez is None:
        return None
    metros_por_segundo = rapidez * escala.fps * escala.metros_por_pixel
    return metros_por_segundo * 3.6
