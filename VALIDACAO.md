# Validação de contagem e velocidade

## Evidência disponível

A suíte verifica geometria, rastreio, relatórios e cenas geradas com gabarito
conhecido. Os parâmetros do detector de movimento foram ajustados nesse mesmo
gerador. Essas cenas exercitam o comportamento implementado; o número de testes
e a cobertura de código não são acurácia em trânsito real.

As contagens dos vídeos de exemplo e as inspeções descritas no README são
registros exploratórios. Sem anotações individuais independentes, elas não
fornecem precisão, recall ou erro de velocidade de campo.

## Avaliação em vídeo real

1. Fixar vídeos, detector, pesos, limiares, linha, resolução e região antes de
   avaliar o conjunto final. Guardar versões, origem, licença/autorização e
   configuração de cada execução.
2. Separar sessões por câmera e dia. Ajustar parâmetros no conjunto de treino;
   escolher configurações na validação; usar o teste somente na avaliação final.
   Trechos vizinhos do mesmo vídeo permanecem na mesma partição.
3. Anotar cada travessia com quadro/instante, sentido e classe, incluindo os
   casos ocultos, ambíguos e não detectados. Conferir as anotações com uma segunda
   pessoa quando possível e declarar regras de exclusão antes de ver resultados.
4. Associar previsões a travessias de referência com tolerância temporal fixada
   antes da avaliação e correspondência um a um. Relatar falsos positivos,
   falsos negativos, precisão e recall por sentido e condição, além do erro
   absoluto do total. Um total correto pode esconder erros que se cancelam.
5. Relatar chuva, noite, reflexos, sombras, tráfego denso, oclusão e veículos
   pequenos. Não somar quadros correlacionados como vídeos independentes.

## Regra geométrica e tempo

A contagem exige lados opostos do segmento, maturidade do alvo e interseção da
trajetória entre os centros observados. Há tolerância de 5% nas pontas.
Um alvo que nasce sobre a linha não tem lado de origem; encostar e voltar não
conta. A travessia com um quadro exatamente sobre a linha só é confirmada na
saída para o outro lado. O evento registra o quadro de confirmação, não um
instante de cruzamento interpolado.

O rastreador pode perder ou trocar identidades em oclusões. A trava de uma
contagem por identificador não demonstra que cada veículo real será contado
uma única vez. A taxa de quadros nominal fornece o tempo das passagens;
vídeos com intervalos variáveis exigem validação específica.

## Velocidade

`Escala` converte o deslocamento de centros na imagem usando uma única razão
metros/pixel e FPS nominal. Não há homografia nem correção de perspectiva.
Uma calibração local não autoriza aplicar a mesma escala a pontos com fatores
de projeção diferentes. Antes de reportar velocidade real, comparar com uma
referência independente, registrar a geometria e sincronização e relatar erro
por posição e trajetória. A suíte atual só comprova conversão e estimativa
em trajetórias sintéticas com escala constante. A saída fica vazia até haver
ao menos cinco observações cobrindo 0,2 s; essa regra reduz medidas em
travessias curtas, mas não substitui validação de campo.
