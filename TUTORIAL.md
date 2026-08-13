# Tutorial

Como colocar o Contaflux para rodar em qualquer computador e contar veículos
nos vídeos. São dez minutos, a maior parte esperando download.

---

## Caminho rápido: só quero ver funcionando

Se o executável já estiver na mão (`Contaflux.exe`), dê dois cliques nele. Ele
abre uma janela com uma rodovia simulada, conta os veículos e no fim diz se a
contagem bateu com o número certo. Não precisa instalar nada.

Esse caminho serve para verificar que está tudo bem. Para contar vídeos de
verdade, siga abaixo.

---

## 1. Instalar

Precisa de **Python 3.10 ou mais novo**. Para conferir se já tem:

```
python --version
```

Se aparecer erro ou uma versão menor que 3.10, instale de
[python.org/downloads](https://www.python.org/downloads/). **No Windows, marque
a caixa "Add Python to PATH"** na primeira tela do instalador. Sem ela, o
comando `python` não é reconhecido depois.

Baixe o projeto:

```
git clone https://github.com/fabriciojunio/contaflux.git
cd contaflux
```

Sem git, dá para usar o botão verde **Code → Download ZIP** no GitHub e
descompactar.

Crie o ambiente e instale:

```
python -m venv .venv
```

Ative. No **Windows**:

```
.venv\Scripts\activate
```

No **Linux ou macOS**:

```
source .venv/bin/activate
```

Você sabe que deu certo quando aparecer `(.venv)` no começo da linha. Agora:

```
pip install -e .
```

---

## 2. Baixar os vídeos

Os vídeos não vêm no repositório porque são centenas de megabytes e deixariam
o download do projeto pesado para sempre. Eles são baixados na hora:

```
python baixar_videos.py
```

São dez vídeos de rodovia, todos do Pixabay, sob licença que permite uso livre.
Se a internet cair no meio, rode o comando de novo: ele pula os que já vieram e
baixa só o que falta.

Você também pode usar **seus próprios vídeos**: é só copiar os arquivos para a
pasta `videos`. Funciona com `.mp4`, `.avi`, `.mkv`, `.mov` e `.webm`.

---

## 3. Rodar

```
python -m contaflux --menu
```

Aparece a lista:

```
Vídeos disponíveis:
--------------------------------------------------------------
   1. 01-rodovia-de-frente.mp4  (1920x1080, 60s)
   2. 03-rodovia-lateral.mp4    (1920x1080, 32s)
   ...
--------------------------------------------------------------
Qual vídeo? (1 a 10, ou q para sair):
```

Digite o número e aperte Enter. Abre uma janela mostrando o primeiro quadro do
vídeo, e você **marca a linha de contagem com dois cliques do mouse**:

1. Clique de um lado da via
2. Clique do outro lado, atravessando as faixas
3. Aperte **Enter**

A linha aparece em amarelo enquanto você move o mouse, então dá para ver como
vai ficar antes de confirmar. Se errar, aperte **R** e refaça.

O vídeo começa a rodar com:

- uma **caixa verde** em volta de cada veículo acompanhado
- o **rastro** do caminho que ele fez
- a caixa mudando para **vermelho** no instante em que é contado
- o **placar** no canto superior esquerdo

Na janela: **espaço** pausa, **q** encerra.

---

## 4. Onde colocar a linha

Ela precisa ficar **atravessada no caminho dos carros**, não junto com ele.

| A via aparece assim | Desenhe a linha assim |
|---|---|
| carros vindo de frente, em direção à câmera | horizontal, cruzando a pista |
| carros passando de um lado para o outro | vertical, cruzando a pista |
| via em diagonal | diagonal, perpendicular à pista |

Duas dicas que fazem diferença:

- **Coloque a linha onde os carros já estão grandes na imagem.** Lá no fundo do
  quadro eles têm poucos pixels e o sistema pode não enxergá-los.
- **Para contar só uma pista**, desenhe a linha cobrindo apenas ela. O que passa
  fora do trecho marcado não entra na conta. É assim que se ignora o sentido
  contrário.

Se você não marcar nada, o programa **observa alguns segundos do vídeo e deduz a
linha sozinho**, colocando-a perpendicular ao sentido do tráfego. Funciona na
maioria dos casos e é o que acontece quando você roda sem o menu:

```
python -m contaflux videos/01-rodovia-de-frente.mp4
```

---

## 5. Guardar o resultado

```
python -m contaflux videos/01-rodovia-de-frente.mp4 --csv resultado.csv
```

O CSV abre no Excel e tem uma linha por veículo: identificador, quadro,
segundo, sentido e porte.

Para gravar o vídeo já anotado, com as caixas e o placar desenhados:

```
python -m contaflux videos/01-rodovia-de-frente.mp4 --gravar contado.mp4
```

Para processar sem abrir janela, útil para rodar vários de uma vez:

```
python -m contaflux videos/01-rodovia-de-frente.mp4 --sem-janela --csv resultado.csv
```

---

## 6. Câmera ao vivo

```
python -m contaflux 0
```

O `0` é a câmera padrão. Se tiver mais de uma, tente `1`, `2` e assim por
diante.

**Deixe a cena vazia nos primeiros cinco segundos.** O sistema usa esse tempo
para aprender como é o fundo sem nenhum veículo. O que estiver parado ali nesse
momento passa a ser considerado cenário e não será contado depois.

---

## 7. Velocidade

Para o programa dizer a velocidade em km/h, ele precisa saber quantos metros de
via cabem na largura da imagem. Meça ou estime, e informe:

```
python -m contaflux videos/01-rodovia-de-frente.mp4 --metros 30
```

Sem essa informação não há como converter pixel em metro, e o programa deixa a
velocidade em branco em vez de inventar um número.

---

## Problemas comuns

**"python não é reconhecido"** — o Python não foi adicionado ao PATH. Reinstale
marcando a caixa "Add Python to PATH", ou use `py` no lugar de `python`.

**A janela abre preta ou não abre** — acontece em máquina sem interface gráfica
(servidor, WSL sem X). Use `--sem-janela --csv resultado.csv`.

**A contagem parece alta demais** — quase sempre é a linha atravessando algo que
se mexe e não é veículo: galho de árvore, sombra de nuvem, bandeira. Redesenhe
a linha cobrindo só o asfalto.

**A contagem parece baixa demais** — a linha provavelmente está numa parte do
quadro onde os carros ainda são pequenos. Traga-a para mais perto da câmera.

**"Não foi possível usar a câmera"** — outro programa pode estar usando (Teams,
Meet, Zoom). Feche e tente de novo. No Windows, confira também em
Configurações → Privacidade e segurança → Câmera.

**O vídeo está tremido** — o método parte do princípio de que a câmera não se
mexe. Filmagem na mão, dashcam ou drone não funcionam, e não é questão de
ajuste: sem fundo fixo não há como separar o que se move.

---

## Comandos, resumidos

| Comando | O que faz |
|---|---|
| `python -m contaflux --menu` | escolhe o vídeo pela lista e marca a linha no mouse |
| `python -m contaflux arquivo.mp4` | conta um vídeo, deduzindo a linha sozinho |
| `python -m contaflux 0` | conta pela câmera ao vivo |
| `python -m contaflux` | roda a demonstração, sem precisar de vídeo |
| `--desenhar-linha` | marca a linha com o mouse |
| `--linha x1,y1,x2,y2` | informa a linha em números |
| `--csv arquivo.csv` | grava a planilha de passagens |
| `--gravar saida.mp4` | grava o vídeo anotado |
| `--metros 30` | liga a estimativa de velocidade |
| `--sem-janela` | processa sem abrir janela |
| `--mascara` | mostra ao lado o que o sistema enxerga como movimento |

Para ver tudo:

```
python -m contaflux --ajuda
```
