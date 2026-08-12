"""Ponto de entrada para `python -m contaflux` e para o executável.

O executável é aberto com dois cliques na maioria das vezes, sem nenhum
argumento, e por isso a linha de comando cai na demonstração quando não recebe
fonte nenhuma. Abrir e não acontecer nada seria o pior primeiro contato
possível.
"""

from __future__ import annotations

import sys

from contaflux.cli import main

if __name__ == '__main__':
    sys.exit(main())
