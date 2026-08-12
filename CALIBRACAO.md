# Calibração

Registro das medidas que definiram os números do arquivo `perfis.py`. Está aqui
porque constante escolhida sem medida é chute, e chute não se defende nem se
corrige depois.

Todas as varreduras usam cenas sintéticas com gabarito exato: nós decidimos
quantos veículos passam, e o número esperado sai das trajetórias, não da
quantidade criada. Quem entra tarde demais e não chega à linha antes de o vídeo
acabar não entra na conta.

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

Escolhido **3**, o maior valor que fecha tudo. Maior é melhor aqui: sobra
margem para vídeo real, que tem mais variação que cena sintética.

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

## O que não foi testado

Vídeo real com gabarito contado à mão. A validação é exata, o que vídeo real não
permite sem alguém sentar e contar, mas cena sintética não tem chuva, farol à
noite, reflexo em piso molhado nem moto passando entre dois carros. As
limitações estão listadas no README.
