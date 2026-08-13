"""Detectar veículo por reconhecimento, e não por movimento.

Este módulo existe por causa de um fracasso concreto. A subtração de fundo, que
é o outro detector do projeto, pergunta "isso se moveu?". Em pista limpa a
resposta serve, porque a única coisa que se move é veículo. Num vídeo de porto
ela marcou contêiner, guindaste e reflexo na água; num vídeo com céu aberto,
marcou nuvem. Todos são movimento de verdade, e nenhum é carro.

Um detector treinado pergunta outra coisa: "isso é um carro?". A diferença
aparece na tela na hora. Nuvem não é carro, contêiner não é carro, e por isso
não entram na conta.

O que este módulo troca, e o que ele mantém
-------------------------------------------

Troca só a etapa de detecção. O rastreio por proximidade, a contagem por
cruzamento de linha, o relatório e a suíte de testes continuam os mesmos, e é
por isso que a troca cabe num arquivo: `detectar` devolve a mesma coisa que a
subtração de fundo devolve, e o resto do sistema não percebe a diferença.

Ele também traz de graça algo que o outro detector nunca teve: o tipo do
veículo. O porte deixa de ser deduzido do tamanho em pixels, que erra feio
quando há perspectiva, e passa a ser o que o modelo reconheceu.

O preço, que é real
-------------------

Depende do pacote `ultralytics` e de um modelo baixado na primeira execução, o
que soma centenas de megabytes. E é lento sem placa de vídeo: medido nesta
máquina, o modelo nano leva 0,16 segundo por quadro e o grande 1,32. Por isso
ele é opcional, e não obrigatório: quem só quer rodar a demonstração continua
sem precisar de nada disso.
"""

from __future__ import annotations

import numpy as np

from contaflux.deteccao import Deteccao

MODELO_PADRAO = 'yolo11n.pt'
"""O menor da família, e a escolha certa para máquina sem placa de vídeo.

Medido num vídeo de 1280 por 720: o nano leva 0,16 segundo por quadro e o
grande 1,32. Num vídeo de três mil quadros, é a diferença entre nove minutos e
setenta e um. O nano perde os veículos bem distantes, e isso não atrapalha a
contagem: a linha fica onde os veículos já estão grandes."""

# Índices das classes de veículo no conjunto COCO, que é o que os modelos YOLO
# reconhecem por padrão. Pessoa, animal e mobiliário urbano ficam de fora de
# propósito: numa contagem de tráfego, pedestre atravessando é o falso positivo
# mais comum, e foi o que inflou a contagem de uma avenida para 89.
CLASSES_DE_VEICULO = (1, 2, 3, 5, 7)

NOMES = {
    1: 'bicicleta',
    2: 'carro',
    3: 'moto',
    5: 'ônibus',
    7: 'caminhão',
}


class UltralyticsIndisponivel(RuntimeError):
    """O pacote de detecção não está instalado."""


class DetectorYolo:
    """Encontra veículos por reconhecimento, na mesma interface do outro detector."""

    def __init__(
        self,
        modelo: str = MODELO_PADRAO,
        confianca_minima: float = 0.35,
        area_minima: int = 0,
        classes: tuple[int, ...] = CLASSES_DE_VEICULO,
    ) -> None:
        """
        `confianca_minima` é o quanto o modelo precisa estar seguro para a
        detecção valer. Abaixo de um terço aparecem caixas em sombra e em
        arbusto; acima de dois terços somem os veículos distantes, que são
        justamente os que aparecem primeiro na cena.

        `area_minima` fica em zero por padrão, ao contrário da subtração de
        fundo. Ali o piso de área era a defesa contra ruído; aqui a defesa é o
        próprio reconhecimento, e um piso alto só serviria para descartar carro
        pequeno de propósito.
        """
        try:
            from ultralytics import YOLO
        except ImportError as erro:  # pragma: sem cobertura
            raise UltralyticsIndisponivel(
                'A detecção por reconhecimento precisa do pacote ultralytics.\n'
                'Instale com:  pip install ultralytics\n'
                'Ou use a detecção por movimento, que não precisa de nada:  '
                '--detector movimento'
            ) from erro

        self._modelo = YOLO(modelo)
        self.confianca_minima = confianca_minima
        self.area_minima = area_minima
        self.classes = list(classes)

    def detectar(self, quadro: np.ndarray) -> tuple[list[Deteccao], np.ndarray]:
        """Veículos do quadro, e uma máscara com as caixas preenchidas.

        A máscara não é usada pela contagem; ela existe porque a interface a
        mostra ao lado com `--mascara`, e ver o que o detector enxergou é o que
        mais ajuda a entender um número estranho.
        """
        resultado = self._modelo.predict(
            quadro,
            classes=self.classes,
            conf=self.confianca_minima,
            verbose=False,
        )[0]

        altura, largura = quadro.shape[:2]
        mascara = np.zeros((altura, largura), dtype=np.uint8)
        encontrados: list[Deteccao] = []

        caixas = resultado.boxes
        if caixas is None or len(caixas) == 0:
            return encontrados, mascara

        coordenadas = caixas.xyxy.cpu().numpy()
        indices = caixas.cls.int().cpu().numpy()

        for (x1, y1, x2, y2), indice in zip(coordenadas, indices):
            x, y = int(x1), int(y1)
            w, h = int(x2 - x1), int(y2 - y1)
            if w <= 0 or h <= 0:
                continue

            area = w * h
            if area < self.area_minima:
                continue

            mascara[max(0, y) : y + h, max(0, x) : x + w] = 255
            encontrados.append(
                Deteccao(x, y, w, h, area, classe=NOMES.get(int(indice), ''))
            )

        return encontrados, mascara

    def aquecer(self, quadros: list[np.ndarray]) -> None:
        """Não faz nada, e é de propósito.

        A subtração de fundo precisa de segundos de cena vazia para aprender o
        fundo. O reconhecimento não aprende nada da cena: ele já sabe o que é um
        carro antes de o vídeo começar. O método existe só para as duas
        implementações terem a mesma interface.
        """
        return
