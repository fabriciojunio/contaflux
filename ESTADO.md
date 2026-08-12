# Onde o trabalho parou

## Funciona e está validado

Contagem de **veículos**: 5 de 5 e 12 de 12 corretos contra gabarito exato.
Um caso de 8 deu 7, provavelmente dois veículos unidos pela sombra.

O núcleo inteiro está escrito: subtração de fundo com MOG2, filtro por área e
proporção, rastreio por proximidade entre quadros com tolerância a sumiço, e
contagem por cruzamento de linha com sentido, detectada pela troca de sinal do
produto vetorial.

## Não funciona ainda

Contagem de **pessoas**. O gabarito e a contagem não batem, e o padrão não é
proporcional: 3 esperados dão 1, 5 dão 3, 8 dão 3, 10 dão 5.

## O que já foi descartado por medição

A detecção não é o problema. Medida quadro a quadro, ela entrega um blob de
cerca de 2.300 pixels com proporção 0,43, ou seja, mais alto que largo, bem
acima do mínimo de 900 do perfil. O objeto está sendo visto.

Duas hipóteses foram testadas e não resolveram:

1. Velocidade irreal na cena. A primeira versão fazia a pessoa levar onze
   segundos para atravessar, o que empilhava oito pessoas simultâneas na mesma
   faixa. Corrigido para dois a três segundos, que é a geometria real de uma
   câmera de porta. Melhorou pouco.
2. Modelo de fundo ainda aprendendo. A primeira pessoa passava antes de o MOG2
   estabilizar. A cena passou a começar vazia e o aquecimento subiu para 45
   quadros. Não resolveu.

## Próximo passo

Rastrear o ciclo de vida dos alvos no caso mais simples, com três pessoas, e
comparar quadro a quadro com as travessias esperadas. O instrumento para isso
já existe e está em ESTADO.md desta pasta como referência: registrar por alvo o
quadro de nascimento e morte, o x mínimo e máximo, e se cruzou a linha.

A suspeita mais forte é a associação gulosa do rastreador trocando identidades
quando duas pessoas ocupam a mesma faixa de altura, já que veículos, que usam
três faixas distintas, funcionam.
