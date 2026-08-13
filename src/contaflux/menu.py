"""Menu de vídeos, para usar sem decorar linha de comando.

Existe porque a plateia da demonstração não é quem escreveu o programa. Alguém
que recebe o projeto e quer ver funcionando não deveria precisar saber o que é
`--linha 200,380,960,380`. Aqui a pessoa vê a lista, digita um número, desenha
a linha com o mouse e assiste.
"""

from __future__ import annotations

import sys
from pathlib import Path

from contaflux.selecao import descrever, listar_videos

PASTA_PADRAO = 'videos'


def _linha_divisoria(largura: int = 62) -> str:
    return '-' * largura


def montar_menu(videos: list[Path]) -> str:
    """Texto do menu, com um número por vídeo."""
    if not videos:
        return ''
    linhas = ['', 'Vídeos disponíveis:', _linha_divisoria()]
    for indice, video in enumerate(videos, start=1):
        linhas.append(f'  {indice:2d}. {descrever(video)}')
    linhas.append(_linha_divisoria())
    return '\n'.join(linhas)


def interpretar_escolha(texto: str, total: int) -> int | None:
    """Número digitado, ou None para sair. Levanta ValueError se não servir."""
    limpo = texto.strip().lower()
    if limpo in ('', 'q', 'sair', 'x'):
        return None

    if not limpo.isdigit():
        raise ValueError(f'Digite um número de 1 a {total}, ou q para sair.')

    escolha = int(limpo)
    if not 1 <= escolha <= total:
        raise ValueError(f'Não existe o vídeo {escolha}. Escolha de 1 a {total}.')
    return escolha


def _texto_sem_teclado(videos: list[Path]) -> str:
    """O que dizer quando o menu não conseguiu ler o teclado."""
    exemplo = videos[0] if videos else Path('videos/rodovia.mp4')
    return (
        'Não consegui ler o teclado neste terminal.\n\n'
        'Passe o vídeo direto na linha de comando, que funciona igual:\n'
        f'  contaflux "{exemplo}"\n'
    )


def _texto_de_pasta_vazia(pasta: str) -> str:
    return (
        f'Nenhum vídeo encontrado em "{pasta}".\n\n'
        'Duas formas de resolver:\n'
        '  1. Baixe os vídeos de exemplo:  python baixar_videos.py\n'
        f'  2. Copie seus próprios vídeos para a pasta "{pasta}".\n'
    )


def escolher_video(
    pasta: str = PASTA_PADRAO, entrada=input, saida=sys.stdout
) -> Path | None:
    """Mostra o menu e devolve o vídeo escolhido, ou None para sair."""
    videos = listar_videos(pasta)
    if not videos:
        print(_texto_de_pasta_vazia(pasta), file=saida)
        return None

    print(montar_menu(videos), file=saida)

    leu_alguma_vez = False
    while True:
        try:
            digitado = entrada(f'Qual vídeo? (1 a {len(videos)}, ou q para sair): ')
            leu_alguma_vez = True
        except (EOFError, KeyboardInterrupt):
            print('', file=saida)
            # Fim de arquivo logo na primeira leitura não é alguém desistindo:
            # é o teclado não chegando ao programa. Aconteceu no executável, e o
            # menu sumia da tela sem explicar nada, com o número digitado indo
            # parar no prompt do sistema. Quem passa por isso precisa saber que
            # existe outro caminho.
            if not leu_alguma_vez:
                print(_texto_sem_teclado(videos), file=saida)
            return None

        try:
            escolha = interpretar_escolha(digitado, len(videos))
        except ValueError as erro:
            print(f'  {erro}', file=saida)
            continue

        if escolha is None:
            return None
        return videos[escolha - 1]
