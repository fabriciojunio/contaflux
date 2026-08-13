"""Orquestração: do quadro até o número contado.

Este módulo é só a costura. A subtração de fundo, o rastreio e a contagem por
linha moram cada um no seu arquivo, e aqui eles são ligados na ordem certa e
com a calibração do perfil escolhido.

O que ele acrescenta por conta própria é o registro: no instante em que um
veículo cruza a linha, é aqui que se decide o porte dele e se calcula a
velocidade, porque é o único ponto do sistema que enxerga o alvo e a escala da
cena ao mesmo tempo.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from contaflux.contagem import Contagem, ContadorDeLinha, Linha
from contaflux.deteccao import Deteccao, DetectorDeMovimento
from contaflux.perfis import PADRAO, Perfil
from contaflux.porte import DESCONHECIDO
from contaflux.rastreio import Alvo, Rastreador
from contaflux.relatorio import Passagem, Relatorio
from contaflux.velocidade import Escala, em_km_por_hora


@dataclass
class EstadoQuadro:
    """O que aconteceu num quadro. É o que a interface desenha."""

    indice: int
    deteccoes: list[Deteccao]
    alvos: dict[int, Alvo]
    contagem: Contagem
    mascara: np.ndarray
    aquecendo: bool = False
    novas_passagens: list[Passagem] = field(default_factory=list)


class ContadorDeFluxo:
    """Junta detecção, rastreio e contagem numa coisa só."""

    def __init__(
        self,
        linha: Linha,
        perfil: Perfil = PADRAO,
        escala: Escala | None = None,
        fps: float = 25.0,
        detector: DetectorDeMovimento | None = None,
        rastreador: Rastreador | None = None,
        quadros_de_aquecimento: int = 45,
    ) -> None:
        """
        `quadros_de_aquecimento` são descartados no começo, enquanto o modelo de
        fundo ainda não aprendeu a cena. Sem isso, os primeiros quadros marcam a
        imagem inteira como movimento e geram contagens fantasmas.

        `escala` só é necessária para estimar velocidade. Sem ela o sistema
        conta normalmente e deixa a velocidade em branco, que é melhor do que
        inventar uma conversão de pixel para metro que ninguém mediu.

        `fps` é a taxa do vídeo, usada para converter quadro em segundo no
        relatório. Ela é separada da escala porque saber a hora de cada
        passagem não depende de calibrar distância: a primeira versão só tinha
        a taxa dentro da escala, e um vídeo de 50 quadros por segundo sem
        `--metros` saía com todos os horários dobrados, marcando 63 segundos
        num vídeo de 60.
        """
        self.perfil = perfil
        self.escala = escala
        self.fps = escala.fps if escala is not None else fps
        self.detector = detector or DetectorDeMovimento(
            area_minima=perfil.area_minima,
            area_maxima=perfil.area_maxima,
            proporcao_maxima=perfil.proporcao_maxima,
            historico=perfil.historico_fundo,
            limiar_variancia=perfil.limiar_variancia,
        )
        self.rastreador = rastreador or Rastreador(
            distancia_maxima=perfil.distancia_maxima,
            tolerancia_sumico=perfil.tolerancia_sumico,
        )
        self.contador = ContadorDeLinha(linha, quadros_minimos=perfil.quadros_minimos)
        self.linha = linha
        self.quadros_de_aquecimento = quadros_de_aquecimento
        self.passagens: list[Passagem] = []
        self.classes: dict[int, str] = {}
        self._indice = 0
        self._eventos_vistos = 0

    @property
    def contagem(self) -> Contagem:
        return self.contador.contagem

    @property
    def quadros_processados(self) -> int:
        return self._indice

    @property
    def velocidade_media(self) -> float | None:
        """Média das velocidades já medidas, ou None se nenhuma foi.

        Existe separado do relatório porque a janela precisa deste número a cada
        quadro, e montar um relatório inteiro trinta vezes por segundo só para
        ler uma média copiaria a lista de passagens à toa num vídeo longo.
        """
        medidas = [p.velocidade_kmh for p in self.passagens if p.velocidade_kmh is not None]
        if not medidas:
            return None
        return sum(medidas) / len(medidas)

    def processar(self, quadro: np.ndarray) -> EstadoQuadro:
        deteccoes, mascara = self.detector.detectar(quadro)
        indice = self._indice
        self._indice += 1

        if indice < self.quadros_de_aquecimento:
            return EstadoQuadro(indice, [], {}, self.contagem, mascara, aquecendo=True)

        alvos = self.rastreador.atualizar(deteccoes, indice)
        contagem = self.contador.atualizar(alvos, indice)

        novas = self._registrar_novas(alvos)
        return EstadoQuadro(indice, deteccoes, alvos, contagem, mascara, False, novas)

    def _registrar_novas(self, alvos: dict[int, Alvo]) -> list[Passagem]:
        """Transforma em passagem cada evento novo desde o quadro anterior.

        A contagem já garante que um alvo só gera evento uma vez. Aqui só
        pegamos o que ainda não foi visto, para não recalcular velocidade de
        veículo que já passou.
        """
        eventos = self.contagem.eventos
        if len(eventos) == self._eventos_vistos:
            return []

        fps = self.fps
        novas: list[Passagem] = []

        for identificador, sentido, quadro in eventos[self._eventos_vistos :]:
            alvo = alvos.get(identificador)
            classe = DESCONHECIDO
            velocidade = None
            if alvo is not None:
                # Quando o detector reconheceu o veículo, o tipo vem dele. A
                # dedução por área só entra quando não há reconhecimento, e ela
                # erra feio sob perspectiva: o mesmo carro triplica de área ao
                # se aproximar da câmera.
                classe = alvo.classe or self.perfil.faixas.classificar(alvo.area)
                if self.escala is not None:
                    velocidade = em_km_por_hora(alvo, self.escala)
                self.classes[identificador] = classe

            novas.append(
                Passagem(
                    identificador=identificador,
                    quadro=quadro,
                    # A contagem fala em entrada e saída, que é a linguagem da
                    # geometria: de que lado da linha o objeto veio. Quem lê o
                    # relatório quer o nome do sentido na via, e é o perfil que
                    # sabe disso.
                    sentido=self._nome_do_sentido(sentido),
                    segundo=quadro / fps if fps else 0.0,
                    classe=classe,
                    velocidade_kmh=velocidade,
                )
            )

        self._eventos_vistos = len(eventos)
        self.passagens.extend(novas)
        return novas

    def _nome_do_sentido(self, sentido: str) -> str:
        if sentido == 'entrada':
            return self.perfil.rotulo_positivo
        return self.perfil.rotulo_negativo

    def rotulos(self, alvos: dict[int, Alvo]) -> dict[int, str]:
        """Texto de cada caixa na tela: identificador, porte e velocidade."""
        saida: dict[int, str] = {}
        for identificador, alvo in alvos.items():
            partes = [f'#{identificador}']
            classe = self.classes.get(identificador)
            if classe and classe != DESCONHECIDO:
                partes.append(classe)
            if self.escala is not None:
                kmh = em_km_por_hora(alvo, self.escala)
                if kmh is not None:
                    partes.append(f'{kmh:.0f} km/h')
            saida[identificador] = ' '.join(partes)
        return saida

    def relatorio(self, fonte: str) -> Relatorio:
        return Relatorio(
            fonte=fonte,
            quadros_processados=self._indice,
            fps=self.fps,
            passagens=list(self.passagens),
        )

    def reiniciar(self) -> None:
        self.rastreador.reiniciar()
        self.contador.reiniciar()
        self.passagens.clear()
        self.classes.clear()
        self._indice = 0
        self._eventos_vistos = 0


def contar_sequencia(quadros, linha: Linha, **opcoes) -> Contagem:
    """Processa uma sequência inteira de quadros e devolve os totais."""
    contador = ContadorDeFluxo(linha, **opcoes)
    for quadro in quadros:
        contador.processar(quadro)
    return contador.contagem
