# Contaflux

Conta veículos que passam por uma via, a partir de um vídeo de câmera fixa.
Cada carro é acompanhado quadro a quadro e contado uma única vez, no instante em
que atravessa uma linha desenhada na cena. Além do total, o programa separa por
sentido, classifica por porte e estima velocidade.

Trabalho de Processamento de Imagens e Sinais, feito por Fabrício Júnio Almeida
Dias, Camila Pereira Raimundo, Luan Miranda Padilha e Kauã Limão Nunes.

**Para instalar e usar passo a passo, veja o [TUTORIAL.md](TUTORIAL.md).** Quem
só quer ver rodando pode baixar o `Contaflux.exe` em
[releases](https://github.com/fabriciojunio/contaflux/releases/latest) e dar dois
cliques, sem instalar nada.

```
python -m contaflux --menu      # escolhe o vídeo pela lista e marca a linha no mouse
python -m contaflux rodovia.mp4 # conta um vídeo de rodovia
python -m contaflux 0           # conta ao vivo pela câmera
python -m contaflux             # demonstração, sem precisar de vídeo
```

Os cinco vídeos de exemplo não vêm no repositório, para não deixá-lo pesado. Um
comando os baixa:

```
python baixar_videos.py
```

Uma janela abre mostrando a linha de contagem, uma caixa em volta de cada
veículo acompanhado, o rastro do movimento e o placar no canto. A caixa muda de
cor no instante em que o veículo é contado. Espaço pausa, `q` encerra.

## Os três modos, na prática

### Vídeo de rodovia

Qualquer arquivo que o OpenCV abra serve: mp4, avi, mkv. Filme de uma passarela,
de uma janela alta ou de um viaduto, com o celular apoiado em algo firme.

```
contaflux rodovia.mp4
contaflux rodovia.mp4 --csv passagens.csv --gravar anotado.mp4
```

O importante é a câmera não se mexer. Todo o método parte de que o fundo é
fixo, e vídeo na mão invalida isso.

### Câmera ao vivo

```
contaflux 0            # câmera padrão
contaflux 1            # segunda câmera, se houver
```

Deixe a cena vazia nos primeiros segundos: é o tempo de o modelo aprender como é
o fundo sem carro nenhum. Enquanto isso o placar mostra "aprendendo o fundo".

No Windows, o programa tenta o Media Foundation, depois o DirectShow e por fim o
padrão do sistema, e só aceita o backend que realmente entregar um quadro.
Muitas webcams abrem no Media Foundation, acendem a luz e não devolvem imagem
nenhuma; conferir só se a câmera "abriu" faria o programa travar numa tela
preta sem explicar por quê.

### Sem vídeo nenhum

```
contaflux                              # demonstração na tela
contaflux --salvar-demo rodovia.mp4    # grava a cena como arquivo
contaflux rodovia.mp4                  # e conta em cima dele
```

A demonstração usa uma cena sintética com gabarito conhecido, então ela imprime
no fim se a contagem bateu com o número certo. É a forma mais rápida de
verificar que a instalação está funcionando.

## Por que linha de contagem, e não presença na tela

Contar quantos objetos aparecem na imagem parece o caminho óbvio e não funciona.
O número sobe e desce conforme os veículos entram e saem do quadro, e um carro
parado dentro da cena fica sendo contado para sempre.

Cruzamento de linha resolve isso: o veículo é contado no instante em que
atravessa, uma única vez, e o lado de onde ele veio dá o sentido. É o mesmo
princípio do laço indutivo enterrado no asfalto.

A travessia é detectada pelo sinal do produto vetorial entre a linha e o centro
do objeto. O sinal diz de que lado o ponto está; a troca de sinal entre dois
quadros consecutivos significa que a linha foi cruzada no intervalo.

## Dois jeitos de achar o veículo

O sistema tem dois detectores, e a diferença entre eles é a pergunta que cada um
faz.

**Subtração de fundo** pergunta *"isso se moveu?"*. Não precisa baixar nada,
roda em qualquer máquina e é rápido. Em pista limpa a resposta serve, porque a
única coisa que se move é veículo. Fora dela, não: num vídeo de porto ele marcou
contêiner, guindaste e reflexo na água; num vídeo com céu aberto, marcou nuvem.
Todos são movimento de verdade, e nenhum é carro.

**Reconhecimento** pergunta *"isso é um carro?"*. Usa um modelo YOLO treinado, e
com ele prédio, árvore, céu e pedestre deixam de aparecer na conta. Foi testado
numa rodovia com a cidade inteira ao fundo e numa rua arborizada: zero caixa
fora dos veículos. Ele também informa o tipo do veículo, o que resolve de vez a
classificação de porte, que antes era deduzida do tamanho em pixels e errava sob
perspectiva.

```
contaflux via.mp4                      # usa reconhecimento se estiver instalado
contaflux via.mp4 --detector movimento # força subtração de fundo
pip install ultralytics                # é o que liga o reconhecimento
```

O preço do reconhecimento é real: o pacote e o modelo somam centenas de
megabytes, e sem placa de vídeo é lento. Medido neste projeto, o modelo nano
leva 0,16 segundo por quadro e o grande 1,32, o que num vídeo de três mil
quadros é a diferença entre nove e setenta e um minutos. Por isso ele é
opcional, e por isso o executável não o inclui: sem o pacote, o programa avisa e
usa a subtração de fundo.

## Como funciona, em quatro etapas

**1. Subtração de fundo.** A câmera é fixa, então tudo que muda entre quadros é
movimento. O modelo usado é o MOG2, que representa cada pixel como uma mistura
de gaussianas em vez de um valor único. Isso importa em cena real: um pixel de
asfalto sob a sombra de uma árvore que balança alterna entre dois tons o tempo
todo, e um modelo de valor único acusaria movimento a cada oscilação.

**2. Filtro de forma.** Do que sobrou, valem apenas as regiões com área e
proporção compatíveis com veículo. É o que descarta folha voando, chuva, ruído
de sensor e a faixa da pista.

**3. Rastreio.** Cada objeto recebe um identificador que sobrevive entre
quadros, por proximidade do centro. Sem isso, o mesmo carro seria contado uma
vez por quadro, e um vídeo de trinta quadros por segundo daria trinta carros
para cada carro que passou. O rastreio tolera o veículo sumir por alguns quadros
atrás de um poste ou de outro veículo, o que evita ele voltar como objeto novo e
ser contado duas vezes.

**4. Contagem.** A troca de sinal do produto vetorial, com a exigência de que o
alvo já tenha sido visto por alguns quadros e de que o cruzamento aconteça
dentro do trecho desenhado, e não no prolongamento infinito da reta.

## O problema da sombra, e por que ele custou caro

Vale contar esta parte porque foi o erro mais difícil do projeto, e o tipo de
erro que não se parece com erro.

O MOG2 marca com 255 o que ele acha que é objeto e com 127 o que ele acha que é
sombra. Sombra é o pior artefato desta contagem: ela gruda no veículo e faz dois
carros de faixas vizinhas virarem um borrão só, o que derruba a contagem em
trânsito denso. A solução óbvia é cortar tudo abaixo de 200 e jogar a sombra
fora. Foi o que a primeira versão fez, e funcionava.

Até aparecer o caso que quebra: um carro cinza-chumbo sobre asfalto cinza. Para
o MOG2, uma região mais escura que o fundo e com a mesma cor **é** a definição
de sombra, então ele marcava o carro inteiro com 127 e o corte apagava o
veículo. Ele não existia para o resto do sistema. A contagem simplesmente pulava
ele, sem aviso, sem exceção, sem nada estranho na tela.

A primeira suspeita foi o rastreador trocando identidades. Medindo quadro a
quadro, o objeto nunca chegava ao rastreador: ele já não estava na máscara.

A solução usa as duas máscaras, cada uma para o que ela sabe:

- A máscara só de 255 dá os objetos de contraste normal. Como a sombra ficou de
  fora, veículos vizinhos continuam separados.
- A máscara de 127 e 255 dá as regiões candidatas. Uma região dessa máscara com
  quase nenhum pixel forte dentro não é sombra de ninguém: é veículo escuro, e
  entra na conta. Sombra de verdade nasce colada ao veículo que a projeta, então
  cai na mesma região que já tem pixel forte e é descartada.

## Calibração, e por que o limiar é tão baixo

O limiar de variância decide o quanto um pixel precisa destoar do fundo para
contar como movimento. O padrão do OpenCV é 16, e a documentação sugere valores
dessa ordem. Aqui ele é 3.

O motivo é que a textura do asfalto é fixa e o modelo de fundo a aprende, então
o que sobra de variância no pixel é quase só ruído de sensor, e o limiar não
precisa cobrir mais que isso. Com 40, a contagem acertava 8 casos em 12; o valor
3 é o maior que fecha a varredura inteira.

A pergunta óbvia é se um limiar tão baixo não passa a contar ruído como veículo.
Dois casos existem na suíte exatamente para responder isso: uma cena vazia, que
precisa devolver zero, e uma cena com o triplo do ruído, que precisa devolver o
número certo. Quem segura o ruído não é o limiar, é o filtro de área junto com a
morfologia.

O limiar baixo tem um custo real, e ele apareceu na suíte: uma variação de seis
por cento no brilho da cena, que é o que uma nuvem passando na frente do sol
faz, já basta para todo pixel destoar do modelo ao mesmo tempo. O quadro inteiro
vira movimento e não há o que rastrear. Por isso o brilho é nivelado antes da
subtração, pela razão entre o brilho de referência e o do quadro atual. A medida
usa mediana, e não média, porque um caminhão branco entrando no quadro puxaria a
média e faria a correção escurecer a cena inteira por causa de um veículo só.

## Validação

Um vídeo de rodovia de verdade só permite dizer que o número "parece certo", a
menos que alguém sente e conte à mão. Por isso a validação usa cenas sintéticas
em que o gabarito é conhecido: nós decidimos quantos veículos passam, de que
tamanho, em que sentido e a que velocidade.

As cenas reproduzem de propósito o que atrapalha em vídeo real: fundo com
textura, ruído de sensor, oscilação de iluminação, sombra acompanhando cada
veículo, e veículos de portes, cores e velocidades diferentes. Uma cena limpa
demais faria os testes passarem sem dizer nada.

O gabarito é calculado a partir das trajetórias, e não do número de veículos
criados: quem entra tarde demais e não chega à linha antes de o vídeo acabar não
entra na conta esperada.

```
pytest                    # a suíte inteira
pytest -m "not lento"     # sem as validações de vídeo, para uso durante o trabalho
```

## Instalação

```
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

Requer Python 3.10 ou mais novo. As únicas dependências são NumPy e OpenCV.

## Uso

| Opção | O que faz |
|---|---|
| `--perfil rodovia\|urbano` | calibração da cena |
| `--linha x1,y1,x2,y2` | onde fica a linha de contagem |
| `--metros N` | quantos metros de via cabem na largura do quadro; liga a velocidade |
| `--csv arquivo` | grava as passagens em planilha |
| `--json arquivo` | grava o relatório completo |
| `--gravar arquivo.mp4` | grava o vídeo anotado |
| `--mascara` | mostra a máscara de movimento ao lado |
| `--sem-janela` | processa em lote, sem interface |
| `--largura N` | reduz o vídeo antes de processar |
| `--salvar-demo arquivo.mp4` | grava a cena sintética como vídeo |
| `--menu` | escolhe o vídeo pela lista da pasta |
| `--desenhar-linha` | marca a linha com dois cliques do mouse |
| `--linha-fixa` | não deduz a linha; usa a vertical do meio |

Na janela, espaço pausa e `q` encerra.

### Onde colocar a linha

Há três formas, e a ordem de preferência é esta:

**1. Deixar o programa deduzir.** É o que acontece quando você não diz nada. Ele
observa alguns segundos, vê por onde os veículos passam e para onde vão, e
coloca a linha perpendicular ao sentido do tráfego. É o que faz o sistema
funcionar num vídeo que ninguém calibrou antes.

**2. Desenhar com o mouse.** `--desenhar-linha` abre o primeiro quadro e você
marca dois cliques. É o caminho quando você quer contar só uma pista, ou quando
a dedução automática não acertou.

**3. Informar em números.** Quatro coordenadas em pixels, para repetir
exatamente a mesma medição depois:

```
contaflux rodovia.mp4 --linha 400,100,400,600
contaflux rodovia.mp4 --linha 0,350,1280,350     # horizontal, câmera de cima
```

A linha é um segmento, e não uma reta infinita: veículo que passa fora do trecho
desenhado não é contado. Isso é o que permite ignorar a pista de sentido
contrário, colocando a linha só sobre a faixa que interessa.

### Vídeo grande

Vídeo de celular chega em 1920 pixels de largura, e processar nessa resolução
não melhora a contagem: os objetos são os mesmos, só com mais pixels cada. Por
padrão o programa reduz para 960, o que mantém o resultado e devolve a fluidez.
Para desligar, `--largura 99999`.

### Velocidade

A conversão de pixel para metro precisa de uma referência medida na cena, e não
há como adivinhá-la a partir da imagem. Por isso ela é explícita: `--metros 30`
significa que a largura do quadro cobre trinta metros de via. Sem essa opção o
programa conta normalmente e deixa a velocidade em branco, que é melhor do que
inventar uma escala que ninguém mediu.

A inclinação da trajetória é estimada por Theil-Sen, a mediana das inclinações
entre todos os pares de pontos, e não por mínimos quadrados. O motivo é o modo
de falhar do rastreador: quando dois veículos se encostam, a caixa vira uma só e
o centro pula. Mínimos quadrados elevam esse pulo ao quadrado e a estimativa vai
junto; a mediana ignora enquanto o pulo for minoria.

## Limitações conhecidas

São reais e estão aqui porque medir sem dizer onde falha não vale muito.

**Câmera precisa ser fixa.** Todo o método parte de que o fundo não se mexe.
Câmera na mão, tremor de poste em dia de vento ou qualquer movimento de
enquadramento invalidam o modelo de fundo.

**A cena precisa começar vazia.** O que estiver parado no enquadramento durante
os primeiros segundos é aprendido como cenário e deixa de existir para a
contagem. Um carro estacionado dentro do quadro na hora em que o programa
começa não será contado quando sair.

**Sem reconhecimento, a classificação por porte é a parte mais fraca, e não
confie nela sob perspectiva forte.** No modo de subtração de fundo, a separação
entre moto, carro e caminhão é por área na imagem. Os limites são ancorados no
veículo mediano de cada vídeo, o que corrige a diferença entre câmeras, mas não
corrige a diferença *dentro* de um mesmo vídeo: numa câmera baixa, o mesmo carro
ocupa três vezes mais pixels ao chegar perto do que ao aparecer no fundo do
quadro. Num vídeo de rodovia em que quase tudo era carro, dez dos vinte e três
saíram como caminhão.

Resolver isso por área exigiria calibrar a perspectiva da cena, corrigindo a
área pela posição vertical antes de classificar. Não está feito, e não precisou
ser: com `pip install ultralytics` o tipo passa a vir do reconhecimento, que sabe
distinguir carro de caminhão sem depender do tamanho na imagem. **A contagem não
depende disso** nos dois modos: o porte é informação extra, e sob perspectiva
forte, deduzido só por área, é informação ruim.

**Veículo pequeno demais no quadro escapa do reconhecimento.** Em vista aérea ou
com a câmera muito longe da via, o carro tem poucas dezenas de pixels e o modelo
não o reconhece. É o motivo de a linha ficar onde os veículos já estão grandes.

**Sombra sem dono pode virar veículo.** A regra que recupera veículos escuros
trata como objeto qualquer região de movimento sem pixel de contraste alto.
Sombra de veículo nasce colada nele e é descartada por isso, mas uma sombra
projetada por algo fora do quadro, como uma nuvem grande ou um prédio, cairia na
regra. Não apareceu nos testes, mas é o ponto fraco do método.

**Oclusão prolongada quebra a identidade.** Se um veículo fica escondido por
mais quadros do que a tolerância do perfil, ele volta como objeto novo. Em
trânsito parado, isso vira contagem dobrada.

**Validação é sintética.** Ela é exata, o que vídeo real não permite sem
contagem manual, mas cena sintética não tem tudo que vídeo real tem: chuva,
faróis à noite, reflexo em piso molhado, moto entrando entre dois carros.

## Estrutura

```
src/contaflux/
  deteccao.py       subtração de fundo e filtros de forma
  deteccao_yolo.py  reconhecimento de veículo, quando o pacote está instalado
  rastreio.py       identidade dos objetos entre quadros
  contagem.py       geometria da linha e regra de contagem
  pipeline.py       costura das etapas e registro das passagens
  perfis.py         calibração por tipo de cena
  porte.py          classificação moto, carro e caminhão
  velocidade.py     estimativa por trajetória
  sugestao.py       deduz sozinho onde a linha deve ficar
  selecao.py        desenho da linha com o mouse
  menu.py           escolha do vídeo pela lista
  cena.py           gerador de cenas sintéticas com gabarito
  video.py          leitura de arquivo e de câmera
  desenho.py        anotação visual
  relatorio.py      CSV, JSON e resumo
  cli.py            linha de comando

baixar_videos.py    baixa a coleção de vídeos de exemplo
empacotar.py        gera o executável
```

## Licença

MIT.
