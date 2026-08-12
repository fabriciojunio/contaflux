"""Separar o que se move do que fica parado.

A ideia é a mais direta possível para uma câmera fixa: se a câmera não se mexe,
tudo que muda entre um quadro e outro é objeto em movimento. O modelo de fundo
aprende como é a cena vazia e marca como primeiro plano o que destoa.

Usamos o MOG2, que modela cada pixel como uma mistura de gaussianas em vez de
guardar um único valor de referência. A diferença aparece em cena real: um
pixel de asfalto sob a sombra de uma árvore que balança alterna entre dois tons
o tempo todo, e um modelo de valor único acusaria movimento a cada oscilação.
Com mistura, os dois tons são aprendidos como fundo e só um carro passando gera
detecção.

Sobre a sombra, que é o assunto mais espinhoso deste arquivo
-----------------------------------------------------------

O MOG2 separa o que ele acha que é objeto, marcado com 255, do que ele acha que
é sombra, marcado com 127. Sombra é o artefato mais atrapalhado desta contagem:
ela acompanha o veículo, gruda nele, e faz dois carros de faixas vizinhas
virarem um borrão só.

A primeira versão resolvia isso do jeito óbvio, cortando tudo abaixo de 200 e
jogando a sombra fora. Funcionava, até aparecer o caso que quebra: um carro
cinza-chumbo sobre asfalto cinza. Para o MOG2, uma região mais escura que o
fundo e com a mesma cor é a definição de sombra, então ele marcava o carro
inteiro com 127 e o corte o apagava. O veículo simplesmente não existia para o
resto do sistema, e a contagem pulava ele sem nenhum sinal de que algo tinha
dado errado.

Jogar fora o corte também não serve: sem ele, a sombra volta a unir veículos
vizinhos e a contagem passa a errar para baixo em trânsito denso.

O que este módulo faz é usar as duas máscaras, cada uma para o que ela sabe:

1. A máscara forte, só com 255, dá os objetos de contraste normal. Como a
   sombra ficou de fora, dois veículos vizinhos continuam separados.
2. A máscara completa, com 127 e 255, dá as regiões candidatas. Uma região
   dessa máscara que quase não tem pixel forte dentro não é sombra de ninguém:
   é objeto escuro, e entra na conta.

O caso que sobra em aberto é o da sombra sem dono, projetada por algo fora do
quadro, como uma nuvem ou um prédio. Ela cairia na regra 2 e viraria um objeto.
Na prática não apareceu, porque sombra de veículo nasce colada nele e cai junto
na mesma região da regra 1, mas está registrado no README como limitação.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

LIMIAR_OBJETO = 200
"""Acima disso o MOG2 tem certeza de que é objeto."""

LIMIAR_SOMBRA = 100
"""Acima disso é objeto ou sombra; abaixo é fundo."""

SUAVIZACAO_DO_BRILHO = 0.25
"""Peso do quadro atual na média móvel do brilho.

Um quarto é o meio-termo medido: alto o bastante para acompanhar uma nuvem
passando, que leva um ou dois segundos, e baixo o bastante para o pulo de um
nível inteiro na mediana não virar correção."""

ZONA_MORTA_DO_BRILHO = 0.025
"""Variação de brilho abaixo da qual não se corrige nada.

Ela existe porque a mediana de pixels inteiros é quantizada: quando o valor
verdadeiro cai perto da fronteira entre dois níveis, a medida fica alternando
entre eles, e um pulo de um nível em 89 já é mais de um por cento. Medido, o
fator espúrio nessas condições chega a 1,011.

Dois e meio por cento fica acima desse ruído e bem abaixo do que uma nuvem
passando causa, que é da ordem de quatro a seis por cento. O que sobra sem
correção nunca passa de dois e meio por cento, e isso o modelo de fundo
absorve."""

QUADROS_PARA_REFERENCIA = 30
"""Quadros usados para fixar o brilho de referência da cena.

Um quadro só não serve, e isso custou um teste para descobrir. A mediana de um
quadro ruidoso pode estar um nível inteiro fora do valor verdadeiro, e como a
referência é fixa, esse erro vira um desvio permanente de um por cento que a
correção passa a aplicar em todo quadro, para sempre. Com trinta quadros, o
erro da média cai para algo em torno de dois décimos de nível."""


@dataclass(frozen=True, slots=True)
class Deteccao:
    """Um objeto encontrado num quadro."""

    x: int
    y: int
    largura: int
    altura: int
    area: int

    @property
    def centro(self) -> tuple[float, float]:
        return (self.x + self.largura / 2.0, self.y + self.altura / 2.0)

    @property
    def proporcao(self) -> float:
        return self.largura / self.altura if self.altura else 0.0

    def como_tupla(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.largura, self.altura)


class DetectorDeMovimento:
    """Encontra objetos em movimento numa cena de câmera fixa."""

    def __init__(
        self,
        area_minima: int = 700,
        area_maxima: int | None = None,
        historico: int = 300,
        limiar_variancia: float = 3.0,
        proporcao_maxima: float = 6.0,
        fracao_forte_minima: float = 0.15,
        fracao_maxima_do_quadro: float = 0.25,
        compensar_luz: bool = True,
    ) -> None:
        """
        `area_minima` descarta o que é pequeno demais para ser o objeto de
        interesse: folha voando, chuva, ruído do sensor. É este filtro, e não o
        limiar de variância, que segura o ruído.

        `fracao_forte_minima` é o corte que separa sombra de veículo escuro.
        Uma região marcada como movimento em que menos que esta fração dos
        pixels tem contraste alto é tratada como objeto escuro, e não como
        sombra de algum objeto vizinho.

        `fracao_maxima_do_quadro` barra região que ocupa boa parte da imagem.
        Nenhum veículo ocupa um quarto do quadro numa câmera de via; o que
        ocupa é mudança de iluminação, câmera que se mexeu ou corte de cena.
        Sem essa barreira, escurecer a cena inteira vira um "veículo escuro"
        do tamanho da tela, porque escurecer mantendo a cor é exatamente o que
        a regra do veículo escuro procura.

        `compensar_luz` corrige mudança de brilho na cena inteira antes da
        subtração. É o preço do limiar baixo: com o limiar em 3, uma nuvem
        passando na frente do sol muda o brilho o bastante para o quadro inteiro
        virar movimento, e a contagem se perde. A correção é uma multiplicação
        que traz o brilho de volta à referência do primeiro quadro.
        """
        self._fundo = cv2.createBackgroundSubtractorMOG2(
            history=historico,
            varThreshold=limiar_variancia,
            detectShadows=True,
        )
        self.area_minima = area_minima
        self.area_maxima = area_maxima
        self.proporcao_maxima = proporcao_maxima
        self.fracao_forte_minima = fracao_forte_minima
        self.fracao_maxima_do_quadro = fracao_maxima_do_quadro
        self.compensar_luz = compensar_luz
        self._nucleo = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        self._brilho_de_referencia: float | None = None
        self._brilho_suavizado: float = 0.0
        self._quadros_medidos: int = 0

    def _nivelar_luz(self, quadro: np.ndarray) -> np.ndarray:
        """Traz o brilho da cena de volta ao do primeiro quadro.

        A medida é a mediana, e não a média, porque um caminhão branco entrando
        no quadro puxa a média e faria a correção escurecer a cena inteira por
        causa dele. A mediana só se move quando a mudança pega a maior parte da
        imagem, que é exatamente o caso que se quer corrigir.

        A amostragem de um pixel a cada quatro corta o custo em dezesseis vezes
        e não muda a mediana de forma perceptível numa imagem deste tamanho.

        A mediana medida passa por uma média móvel antes de virar correção, e
        isso não é refinamento: sem ela a compensação faz estrago. A mediana de
        pixels inteiros é um número inteiro, então o ruído do sensor a faz pular
        de 96 para 97, que já é uma variação de um por cento. A correção
        disparava por causa desse pulo, multiplicava a cena inteira por 1,01, e
        um carro de baixo contraste que estava por um fio acima do limiar caía
        para baixo dele e sumia. Custou um teste de contagem que só falhava
        depois de a compensação existir.
        """
        if not self.compensar_luz:
            return quadro

        brilho = float(np.median(quadro[::4, ::4]))

        if self._quadros_medidos < QUADROS_PARA_REFERENCIA:
            anteriores = self._quadros_medidos
            atual = self._brilho_de_referencia or 0.0
            self._brilho_de_referencia = (atual * anteriores + brilho) / (anteriores + 1)
            self._brilho_suavizado = self._brilho_de_referencia
            self._quadros_medidos += 1
            return quadro

        self._brilho_suavizado += SUAVIZACAO_DO_BRILHO * (brilho - self._brilho_suavizado)
        if self._brilho_suavizado <= 1.0:
            return quadro

        fator = self._brilho_de_referencia / self._brilho_suavizado
        if abs(fator - 1.0) < ZONA_MORTA_DO_BRILHO:
            return quadro

        # A trava existe para o corte de cena, quando a imagem muda por
        # completo: sem ela, a correção tentaria compensar um fator absurdo e
        # estouraria o contraste do quadro inteiro.
        fator = min(max(fator, 0.5), 2.0)
        return cv2.convertScaleAbs(quadro, alpha=fator)

    def _limpar(self, binaria: np.ndarray) -> np.ndarray:
        """Abertura tira ponto isolado; fechamento costura o objeto partido.

        Objeto sai partido em pedaços com frequência, por reflexo no capô ou
        por um trecho de cor parecida com a da pista. Sem o fechamento, um carro
        vira dois e a contagem dobra.
        """
        limpa = cv2.morphologyEx(binaria, cv2.MORPH_OPEN, self._nucleo)
        limpa = cv2.morphologyEx(limpa, cv2.MORPH_CLOSE, self._nucleo, iterations=2)
        return cv2.dilate(limpa, self._nucleo, iterations=1)

    def _mascaras(self, quadro: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Máscara só de objeto e máscara de objeto mais sombra."""
        bruta = self._fundo.apply(self._nivelar_luz(quadro))
        _, forte = cv2.threshold(bruta, LIMIAR_OBJETO, 255, cv2.THRESH_BINARY)
        _, completa = cv2.threshold(bruta, LIMIAR_SOMBRA, 255, cv2.THRESH_BINARY)
        return self._limpar(forte), self._limpar(completa)

    def mascara(self, quadro: np.ndarray) -> np.ndarray:
        """Máscara binária do que está em movimento, sem a sombra."""
        return self._mascaras(quadro)[0]

    def _grande_demais(self, area: int, pixels_do_quadro: int) -> bool:
        """Região que ocupa boa parte da imagem não é veículo."""
        if pixels_do_quadro <= 0:
            return False
        return area / pixels_do_quadro > self.fracao_maxima_do_quadro

    def _aceita(self, contorno, pixels_do_quadro: int = 0) -> Deteccao | None:
        """Aplica os filtros de tamanho e forma a um contorno."""
        area = int(cv2.contourArea(contorno))
        if area < self.area_minima:
            return None
        if self.area_maxima is not None and area > self.area_maxima:
            return None
        if self._grande_demais(area, pixels_do_quadro):
            return None

        x, y, largura, altura = cv2.boundingRect(contorno)
        if altura == 0:
            return None

        proporcao = largura / altura
        # Formas muito alongadas costumam ser faixa da pista, guard rail ou
        # sombra comprida, e não veículo. O recíproco também é barrado, para o
        # filtro valer nos dois sentidos.
        if proporcao > self.proporcao_maxima or proporcao < 1 / self.proporcao_maxima:
            return None

        return Deteccao(x, y, largura, altura, area)

    def detectar(self, quadro: np.ndarray) -> tuple[list[Deteccao], np.ndarray]:
        """Objetos em movimento e a máscara usada, para poder ser exibida."""
        forte, completa = self._mascaras(quadro)

        pixels = int(forte.shape[0] * forte.shape[1])
        contornos_fortes, _ = cv2.findContours(
            forte, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        encontrados = [
            d for c in contornos_fortes if (d := self._aceita(c, pixels)) is not None
        ]

        encontrados.extend(self._objetos_escuros(forte, completa, pixels))
        return encontrados, forte

    def _objetos_escuros(
        self, forte: np.ndarray, completa: np.ndarray, pixels_do_quadro: int = 0
    ) -> list[Deteccao]:
        """Regiões de movimento que quase não têm pixel forte dentro.

        São veículos de cor próxima à da pista, que o MOG2 confunde com sombra
        porque escurecem o fundo mantendo a cor. Uma sombra de verdade nasce
        colada ao objeto que a projeta, e por isso cai na mesma região que já
        tem pixel forte, sendo descartada aqui.

        A conta usa componentes conexos, e não contornos, por causa do custo: a
        primeira versão recortava a máscara forte com um desenho do contorno,
        alocando um quadro inteiro por região, e ficou lenta o suficiente para
        atrapalhar a própria calibração. Com rótulos, os pixels fortes de todas
        as regiões saem numa passada só.
        """
        total, rotulos, estatisticas, _ = cv2.connectedComponentsWithStats(completa, 8)
        if total <= 1:
            return []

        fortes_por_regiao = np.bincount(rotulos[forte > 0], minlength=total)

        escuros: list[Deteccao] = []
        for indice in range(1, total):
            x, y, largura, altura, area = (int(v) for v in estatisticas[indice])
            if area < self.area_minima:
                continue
            if self.area_maxima is not None and area > self.area_maxima:
                continue
            if self._grande_demais(area, pixels_do_quadro):
                continue
            if altura == 0:
                continue

            proporcao = largura / altura
            if proporcao > self.proporcao_maxima or proporcao < 1 / self.proporcao_maxima:
                continue

            if fortes_por_regiao[indice] / area >= self.fracao_forte_minima:
                continue

            escuros.append(Deteccao(x, y, largura, altura, area))

        return escuros

    def aquecer(self, quadros: list[np.ndarray]) -> None:
        """Aprende o fundo antes de começar a contar.

        Sem isso, os primeiros quadros produzem detecção em cena inteira, porque
        o modelo ainda não sabe como é o fundo e considera tudo novidade.
        """
        for quadro in quadros:
            self._fundo.apply(self._nivelar_luz(quadro))
