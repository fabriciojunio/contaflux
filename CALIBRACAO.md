# Calibração

Registro das medidas que definiram os números do arquivo `perfis.py`. Está aqui
porque constante escolhida sem medida é chute, e chute não se defende nem se
corrige depois.

Todas as varreduras usam cenas sintéticas com gabarito exato: nós decidimos
quantos veículos passam, e o número esperado sai das trajetórias, não da
quantidade criada. Quem entra tarde demais e não chega à linha antes de o vídeo
acabar não entra na conta.

Os acertos abaixo são resultados históricos de ajuste. Os parâmetros foram
escolhidos usando esse gerador, também presente na suíte de regressão. Eles
comprovam os casos sintéticos declarados, mas não estimam desempenho em vídeos
reais independentes. Para essa avaliação, siga o [protocolo](VALIDACAO.md).

## O ponto de partida

A primeira versão usou `varThreshold = 40`, na ordem de grandeza sugerida pela
documentação do MOG2, com o corte de sombra em 200. Resultado sobre doze cenas:

| veículos | esperado | contado |
|---|---|---|
| 1 a 3 | igual | igual |
| 4 | 4 | 3 |
| 5 a 7 | igual | igual |
| 8 | 8 | 7 |
| 9 | 9 | 9 |
| 10 | 10 | 9 |
| 12 | 12 | 12 |
| 15 | 14 | 10 |

**8 acertos em 12**, e todos os erros para baixo.

## Primeira suspeita, e por que estava errada

A hipótese inicial foi troca de identidade no rastreador. Ela caiu na medida:
instrumentando a cena de quatro veículos, apareceu que só três alvos chegaram a
nascer. O quarto veículo não estava sendo perdido pelo rastreio; ele nunca
aparecia na máscara.

O veículo em questão tinha cor `(79, 137, 100)` sobre asfalto `96`. A soma dos
quadrados das diferenças por canal dá 1.986, contra um limiar efetivo em torno
de 2.600. Ele estava abaixo do corte por muito pouco, e sumia inteiro.

Isto vale registrar como método: **antes de mexer no rastreio, confirme que o
objeto chegou até ele.**

## Varredura do limiar de variância

Vinte cenas, incluindo cena vazia e cena com o triplo do ruído.

| limiar | acertos |
|---|---|
| 40 | 7/10 |
| 32 | 7/10 |
| 25 | 7/10 |
| 20 | 7/10 |
| 16 | 7/10 |
| 8 | 8/10 |
| 6 | 7/10 |
| 5 | 7/10 |
| 4 | 8/10 |
| 3 | **10/10** |
| 2 | 10/10 |

Escolhido **3**, o maior valor que fecha tudo nessa varredura. Esse critério de
ajuste não demonstra que haja margem suficiente para vídeo real.

A cena vazia e a cena de ruído triplicado estão na varredura exatamente para
responder à objeção óbvia, que é o limiar baixo passar a contar ruído. As duas
fecham. Quem segura o ruído não é o limiar, é o filtro de área.

## O veículo que o MOG2 chama de sombra

Com o limiar em 3, uma cena nova ainda falhava: oito veículos, sete contados. O
faltante tinha cor `(90, 92, 107)` sobre asfalto `96`. A diferença por canal é
`(-6, -4, 11)`, soma dos quadrados 173. É um carro literalmente da cor do
asfalto.

O para-brisa dele, porém, tem soma dos quadrados 5.769, bem acima de qualquer
limiar razoável. Ele *era* detectado, e mesmo assim sumia. O motivo é o corte de
sombra: o para-brisa é mais escuro que o fundo mantendo a cor, que é a definição
de sombra para o MOG2. Ele marcava o veículo com 127, e o corte em 200 o
apagava.

Não dá para resolver baixando o limiar, porque o problema não é sensibilidade.
E não dá para resolver tirando o corte de sombra, porque aí a sombra volta a
unir veículos de faixas vizinhas.

### Medida das duas alternativas simples

| configuração | acertos |
|---|---|
| corte 200, sombra descartada | 4/8 |
| corte 100, sombra mantida | 5/8 |

Nenhuma das duas resolve: descartando sombra, veículo escuro some; mantendo
sombra, veículos vizinhos se fundem e ainda aparece contagem a mais. O que
resolveu foi usar as duas máscaras, cada uma para o que ela sabe, como está
descrito no cabeçalho de `deteccao.py`.

## O preço do limiar baixo apareceu na oscilação de luz

Com a suíte inteira rodando, dois casos de iluminação oscilando falharam: 4% e
6% de variação no brilho da cena. É consequência direta do limiar 3. Uma
variação de seis por cento em 96 tons dá cerca de seis níveis de cinza, mais que
suficiente para todo pixel destoar do modelo ao mesmo tempo. O quadro inteiro
vira movimento e não há o que rastrear.

Não é artefato de cena sintética: é o que uma nuvem passando na frente do sol faz
num vídeo de rodovia.

A correção nivela o brilho antes da subtração, multiplicando o quadro pela razão
entre o brilho de referência e o atual. A medida usa mediana, e não média, por um
motivo concreto: um caminhão branco entrando no quadro puxa a média e faria a
correção escurecer a cena inteira por causa de um veículo. A mediana só se move
quando a mudança pega a maior parte da imagem.

### A correção quebrou um teste que passava

Com a compensação ligada, a cena da semente 25 voltou a errar, de 8 para 7. Era a
compensação disparando por causa de ruído, e o motivo é a quantização: a mediana
de pixels inteiros é um número inteiro, e quando o valor verdadeiro fica perto da
fronteira entre dois níveis, a medida alterna entre eles. Um pulo de 88 para 89 é
mais de um por cento, acima da zona morta de então. A cena inteira era
multiplicada por 1,011, e o carro cinza que estava por um fio acima do limiar
caía para baixo dele.

Três coisas juntas resolveram, e cada uma trata uma parte do problema:

| medida | o que corrige |
|---|---|
| média móvel do brilho, peso 0,25 | o pulo de nível de um quadro isolado |
| referência tirada de 30 quadros, não de 1 | erro fixo herdado de um quadro ruidoso |
| zona morta de 2,5% | o que sobra da quantização |

Medido depois: a correção passou a disparar em zero dos 460 quadros de uma cena
de iluminação estável, e continua corrigindo as cenas de 4% e 6%.

Vale registrar o padrão, porque ele se repetiu no projeto inteiro: **a correção
de um problema criou outro, e só apareceu porque havia teste cobrindo o caso
antigo.** Sem o caso da semente 25 na suíte, essa regressão teria ido para o
repositório sem ninguém notar.

## A moto era pequena demais para o próprio detector

Dois testes de classificação falhavam sem motivo aparente. Medindo a área
detectada por classe:

| porte | área desenhada | área detectada |
|---|---|---|
| moto | 416 a 551 | 632 a 781 |
| carro | 1.716 a 2.368 | 2.294 a 2.863 |
| caminhão | 5.808 a 7.200 | 5.500 a 7.965 |

O piso de área do detector é 700. A moto do gerador de cenas caía **abaixo do
piso** e era descartada antes de chegar ao classificador. O erro não estava na
classificação; estava no tamanho escolhido para a moto na cena de teste.

Com os tamanhos corrigidos, as três classes ficam separadas com folga:

| porte | área detectada |
|---|---|
| moto | 1.050 a 1.308 |
| carro | 2.437 a 3.315 |
| caminhão | 3.999 a 17.372 |

Os limites do perfil, 1.400 e 4.200, caem nos vãos entre as distribuições, e não
precisaram mudar.

## O gerador de cenas era o gargalo

Medindo uma cena de 460 quadros:

```
gerar 15,0s    contar 3,8s
```

O sistema em teste custava um quarto do tempo do teste. As contas de imagem
passaram de `float64` para `float32` e a conversão do fundo passou a ser feita
uma vez em vez de por quadro:

```
gerar  6,1s    contar 4,1s
```

Meio tom de precisão não muda nada numa imagem de oito bits, e a suíte inteira
ficou praticável.

## O que o vídeo real mostrou que a cena sintética escondia

A cena sintética validou o algoritmo, e não a operação. Rodar em dez vídeos de
rodovia de verdade expôs três coisas que nenhum teste sintético pegaria.

**A taxa de quadros não chegava ao relatório.** Ela só existia dentro da escala
de velocidade, que é opcional. Num vídeo de 50 quadros por segundo sem
`--metros`, todos os horários saíam dobrados: o relatório marcava 63 segundos
num vídeo de 60. O gerador de cenas usa 25 quadros por segundo, que era
justamente o valor assumido por omissão, então o erro nunca apareceu.

**O aquecimento era contado em quadros, não em tempo.** Quarenta e cinco
quadros a 50 por segundo dão menos de um segundo de cena vazia:

| aquecimento | total contado | travessias nos 8 s seguintes |
|---|---|---|
| 0,9 s | 37 | 12 |
| 2,0 s | 34 | 10 |
| 3,0 s | 30 | 6 |
| 5,0 s | 26 | 2 |
| 7,0 s | 26 | 3 |
| 10,0 s | 24 | 3 |

O total para de cair em torno de 5 segundos, que é a janela de histórico do
modelo de fundo. O excedente era artefato: contagens fantasma geradas enquanto o
modelo ainda não tinha aprendido a pista.

**A linha padrão estava errada na maioria dos vídeos.** A vertical no meio do
quadro só serve para câmera lateral. Em câmera baixa, os veículos vêm em direção
à lente e a linha precisa ser horizontal; em pista curva, diagonal. Isso motivou
a dedução automática descrita no README.

## Por que oito dos dezoito vídeos foram descartados

A coleção começou com dezoito e ficou em dez. Os descartes delimitam onde o
método funciona, e por isso valem registro:

| motivo | quantos | por que não tem conserto |
|---|---|---|
| dashcam ou drone | 3 | a câmera se move, e todo o método parte de fundo fixo |
| timelapse noturno | 1 | cada veículo vira um rastro contínuo, não um objeto |
| tomada aérea distante | 3 | o veículo fica com poucos pixels, abaixo do piso de área |
| sem via no enquadramento | 1 | não há o que contar |

Vale notar uma tentativa que falhou: medir movimento de câmera por correlação de
fase entre quadros. Ela acusa translação, e dashcam apontada para a frente
produz expansão radial, não translação. O vídeo de dashcam passou no teste com
0,264 pixel por quadro, dentro da faixa dos vídeos de câmera fixa. A triagem
acabou sendo feita a olho, olhando um quadro de cada vídeo.

## A linha automática usava o sentido do tráfego, e devia usar o eixo

Achado em 29/09/2026, no vídeo `05-rodovia-urbana`, que contava **1 veículo em
12 segundos** de rodovia cheia.

A dedução da linha somava os rumos dos alvos e tirava a média. Numa via de mão
dupla os dois fluxos apontam para lados opostos e essa soma se anula: sobra o
resíduo do ruído, e a perpendicular do ruído é uma linha qualquer. Nesse vídeo
ela saiu subindo pelo céu, por cima dos prédios.

A linha não precisa saber quem vai para que lado, só em que reta a via corre.
A média passou a ser no ângulo dobrado, que é como se promedia orientação sem
sentido: 0° e 180° caem no mesmo ponto e os dois fluxos se reforçam.

Medido nos cinco vídeos, com o detector de movimento e 400 quadros:

| vídeo | rumos | eixo | coerência do eixo | coerência da média antiga |
|---|---|---|---|---|
| 01 rodovia de frente | 1.033 | 38,0° | 0,317 | 0,577 |
| 02 rua de cidade | 361 | 153,4° | 0,206 | 0,400 |
| 03 via movimentada | 3.110 | 172,4° | 0,099 | 0,059 |
| 04 rua com árvores | 788 | 8,2° | 0,255 | 0,178 |
| 05 rodovia urbana | 304 | 165,7° | **0,593** | **0,224** |

O vídeo 05 é a assinatura do problema: é o de **maior** coerência de eixo e o de
menor coerência de sentido. O eixo está lá, firme; o que não existe é sentido
dominante. Conferido também com o reconhecimento em vez do detector de
movimento, que devolveu 165,3° e coerência 0,406 — os dois concordam.

### O piso de coerência que não entrou

A ideia seguinte era recusar a sugestão quando a coerência fosse baixa, em vez
de chutar um eixo. A tabela acima matou a ideia: vídeo que funciona fica entre
0,10 e 0,32, porque a caixa do detector de movimento treme e cada alvo
contribui com rumo ruidoso. Um piso de 0,45 foi testado e recusou quatro dos
cinco, derrubando a via movimentada de 106 para 30 e a rua de cidade de 10
para 8. Não há piso.

### A causa mais funda: a linha era posta olhando o detector errado

Trocar a média pelo eixo consertou o vídeo 05 e **quebrou** o 03, que caiu de
106 para 29. O quadro anotado mostrou por quê sem deixar dúvida: a linha saiu
deitada ao longo da via, paralela aos carros, enquanto os rastros dos veículos
corriam na vertical.

O eixo medido não batia com o trânsito porque quem media era o detector de
movimento, e nesse vídeo ele não está olhando veículo: a cena tem passarela,
escada rolante, pedestre na calçada e a sombra do viaduto, e tudo isso entrou na
conta do rumo. A coerência de 0,099 era o aviso, e o valor de 172,4° era ruído.

A linha passou a ser posicionada **com o mesmo detector que vai contar**. No
vídeo 03, observando por reconhecimento, a linha sai em `991,295 até 0,305`,
horizontal, perpendicular ao trânsito:

| vídeo 03 | linha | contados |
|---|---|---|
| média de sentido, observando por movimento | 77,45 a 918,570 | 106 |
| eixo, observando por movimento | 432,-184 a 563,799 | 29 |
| eixo, observando por reconhecimento | 991,295 a 0,305 | **154** |

O reconhecimento observa 150 quadros em vez de 400: ele não precisa aquecer
fundo, e cada quadro custa ~0,16 s na CPU contra ~0,01 s do outro.

### O que continua sem conserto no vídeo 05

Mesmo com o eixo certo a contagem fica baixa, e o motivo não é a linha: a
tomada é alta e distante, e só a faixa de baixo do quadro tem veículo com pixels
suficientes para o reconhecimento. É o mesmo motivo que descartou três vídeos na
triagem, e este ficou na coleção. Para contar nele é preciso marcar a linha à
mão sobre uma pista só, onde os veículos já estão grandes.

## O que não foi testado

Vídeo real com gabarito contado à mão. A validação é exata, o que vídeo real não
permite sem alguém sentar e contar, mas cena sintética não tem chuva, farol à
noite, reflexo em piso molhado nem moto passando entre dois carros. As
limitações estão listadas no README.
