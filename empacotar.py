"""Gera o executável de janela única com o PyInstaller.

    python empacotar.py

O resultado fica em `dist/Contaflux.exe` no Windows e em `dist/Contaflux` no
Linux e no macOS. Ele não precisa de Python instalado na máquina de destino, que
é o ponto: o professor abre o arquivo e o programa roda.

O empacotamento não entra na suíte de testes de propósito. Ele leva minutos,
depende do sistema operacional e produz um arquivo de mais de cem megabytes, o
que não tem lugar numa suíte que precisa rodar a cada alteração.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).parent
ENTRADA = RAIZ / 'src' / 'contaflux' / '__main__.py'


def construir() -> int:
    # A chamada é pelo próprio interpretador, e não pelo comando `pyinstaller`
    # do PATH. Num ambiente virtual do Windows, a pasta Scripts costuma não
    # estar no PATH do shell, e procurar o comando falharia mesmo com o
    # PyInstaller instalado ali do lado.
    if importlib.util.find_spec('PyInstaller') is None:
        print(
            'PyInstaller não encontrado. Instale com:\n'
            f'    {sys.executable} -m pip install pyinstaller',
            file=sys.stderr,
        )
        return 1

    comando = [
        sys.executable,
        '-m',
        'PyInstaller',
        '--onefile',
        '--name',
        'Contaflux',
        '--paths',
        str(RAIZ / 'src'),
        # O OpenCV carrega parte dos seus módulos em tempo de execução, e o
        # PyInstaller não consegue enxergar isso analisando os imports. Sem a
        # inclusão explícita, o executável monta e falha ao abrir.
        '--hidden-import',
        'cv2',
        '--collect-submodules',
        'contaflux',
        # A detecção por reconhecimento fica de fora do executável de propósito.
        # O torch e os modelos somam quase um gigabyte, e o executável existe
        # justamente para quem quer rodar sem instalar nada. Quem precisa do
        # reconhecimento instala o projeto pelo pip, onde ele é uma linha.
        '--exclude-module',
        'ultralytics',
        '--exclude-module',
        'torch',
        '--exclude-module',
        'torchvision',
        '--noconfirm',
        str(ENTRADA),
    ]

    print('Empacotando. Isso leva alguns minutos.\n')
    resultado = subprocess.run(comando, cwd=RAIZ)
    if resultado.returncode != 0:
        return resultado.returncode

    destino = RAIZ / 'dist'
    gerados = list(destino.glob('Contaflux*'))
    print('\nPronto:')
    for arquivo in gerados:
        tamanho = arquivo.stat().st_size / 1_000_000
        print(f'  {arquivo}  ({tamanho:.0f} MB)')
    return 0


if __name__ == '__main__':
    raise SystemExit(construir())
