"""Manter a identidade de cada objeto entre quadros.

Detectar não basta para contar. Sem identidade, o mesmo carro seria contado
uma vez por quadro em que aparece, e um vídeo de trinta quadros por segundo
daria trinta carros para cada carro que passou.

O rastreador liga as detecções de um quadro às do quadro anterior por
proximidade do centro. É simples de propósito: numa cena de câmera fixa, entre
dois quadros consecutivos, um objeto se desloca pouco, e o candidato mais
próximo é quase sempre o mesmo objeto.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from contaflux.deteccao import Deteccao


@dataclass
class Alvo:
    """Um objeto acompanhado ao longo do tempo."""

    identificador: int
    centro: tuple[float, float]
    caixa: tuple[int, int, int, int]
    trajetoria: list[tuple[float, float]] = field(default_factory=list)
    indices: list[int] = field(default_factory=list)
    """Em que quadro cada ponto da trajetória foi visto.

    Guardado separadamente porque a trajetória tem buracos: quando o objeto
    passa atrás de outro, ele some por alguns quadros e volta. Supor que os
    pontos são consecutivos faria a estimativa de velocidade errar exatamente
    nos casos em que ela mais importa, que são os de trânsito carregado.
    """

    sumido_ha: int = 0
    contado: bool = False
    quadros_visto: int = 1
    area: int = 0

    @property
    def deslocamento(self) -> tuple[float, float]:
        """Direção do movimento, medida entre o início e o fim da trajetória."""
        if len(self.trajetoria) < 2:
            return (0.0, 0.0)
        inicio = self.trajetoria[0]
        fim = self.trajetoria[-1]
        return (fim[0] - inicio[0], fim[1] - inicio[1])


class Rastreador:
    """Associa detecções a alvos por proximidade."""

    def __init__(
        self,
        distancia_maxima: float = 80.0,
        tolerancia_sumico: int = 12,
        historico_trajetoria: int = 40,
    ) -> None:
        """
        `distancia_maxima` é o quanto um objeto pode ter andado entre dois
        quadros e ainda ser considerado o mesmo. Muito baixo e um veículo rápido
        vira dois; muito alto e dois veículos próximos trocam de identidade.

        `tolerancia_sumico` mantém o alvo vivo por alguns quadros depois de ele
        desaparecer. Objeto passando atrás de poste ou de outro veículo some por
        um instante, e sem essa memória ele voltaria como um alvo novo, sendo
        contado duas vezes.
        """
        self.distancia_maxima = distancia_maxima
        self.tolerancia_sumico = tolerancia_sumico
        self.historico_trajetoria = historico_trajetoria
        self.alvos: dict[int, Alvo] = {}
        self._proximo_id = 1

    def atualizar(self, deteccoes: list[Deteccao], indice: int = 0) -> dict[int, Alvo]:
        """Consome as detecções de um quadro e devolve os alvos vivos."""
        if not self.alvos:
            for deteccao in deteccoes:
                self._criar(deteccao, indice)
            return self.alvos

        ids = list(self.alvos)
        if not deteccoes:
            self._envelhecer(set())
            return self.alvos

        # Matriz de distâncias entre cada alvo e cada detecção.
        centros_alvos = np.array([self.alvos[i].centro for i in ids], dtype=float)
        centros_novos = np.array([d.centro for d in deteccoes], dtype=float)
        distancias = np.linalg.norm(
            centros_alvos[:, None, :] - centros_novos[None, :, :], axis=2
        )

        # Associação gulosa pelo par mais próximo. O algoritmo húngaro daria o
        # ótimo global, e não compensa aqui: com poucos objetos em cena os
        # resultados coincidem, e o guloso é bem mais simples de acompanhar.
        usados_alvos: set[int] = set()
        usadas_deteccoes: set[int] = set()

        while True:
            candidata = None
            menor = self.distancia_maxima
            for i in range(len(ids)):
                if i in usados_alvos:
                    continue
                for j in range(len(deteccoes)):
                    if j in usadas_deteccoes:
                        continue
                    if distancias[i][j] < menor:
                        menor = distancias[i][j]
                        candidata = (i, j)
            if candidata is None:
                break

            i, j = candidata
            usados_alvos.add(i)
            usadas_deteccoes.add(j)
            self._mover(self.alvos[ids[i]], deteccoes[j], indice)

        for j, deteccao in enumerate(deteccoes):
            if j not in usadas_deteccoes:
                self._criar(deteccao, indice)

        self._envelhecer({ids[i] for i in usados_alvos})
        return self.alvos

    def _criar(self, deteccao: Deteccao, indice: int = 0) -> None:
        alvo = Alvo(
            identificador=self._proximo_id,
            centro=deteccao.centro,
            caixa=deteccao.como_tupla(),
            trajetoria=[deteccao.centro],
            indices=[indice],
            area=deteccao.area,
        )
        self.alvos[self._proximo_id] = alvo
        self._proximo_id += 1

    def _mover(self, alvo: Alvo, deteccao: Deteccao, indice: int = 0) -> None:
        alvo.centro = deteccao.centro
        alvo.caixa = deteccao.como_tupla()
        alvo.trajetoria.append(deteccao.centro)
        alvo.indices.append(indice)
        if len(alvo.trajetoria) > self.historico_trajetoria:
            alvo.trajetoria.pop(0)
            alvo.indices.pop(0)
        alvo.sumido_ha = 0
        alvo.quadros_visto += 1
        # A área mediana ao longo da vida é mais estável que a de um quadro só,
        # e é o que a classificação por porte usa. Guardar a maior vista serve
        # ao mesmo fim sem precisar manter a lista inteira: o objeto aparece
        # recortado ao entrar e ao sair do quadro, e é no meio que ele tem o
        # tamanho verdadeiro.
        alvo.area = max(alvo.area, deteccao.area)

    def _envelhecer(self, atualizados: set[int]) -> None:
        for identificador in list(self.alvos):
            if identificador in atualizados:
                continue
            alvo = self.alvos[identificador]
            alvo.sumido_ha += 1
            if alvo.sumido_ha > self.tolerancia_sumico:
                del self.alvos[identificador]

    def reiniciar(self) -> None:
        self.alvos.clear()
        self._proximo_id = 1
