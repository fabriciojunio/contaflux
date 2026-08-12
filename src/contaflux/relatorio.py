"""Guardar o resultado num formato que outra pessoa consiga usar.

Número na tela some quando a janela fecha. Para o resultado servir de alguma
coisa, ele precisa virar arquivo: CSV para abrir na planilha e olhar evento por
evento, JSON para outro programa consumir.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Passagem:
    """Um veículo que cruzou a linha."""

    identificador: int
    quadro: int
    sentido: str
    segundo: float
    classe: str = 'desconhecido'
    velocidade_kmh: float | None = None

    def como_linha(self) -> dict[str, object]:
        return {
            'id': self.identificador,
            'quadro': self.quadro,
            'segundo': round(self.segundo, 2),
            'sentido': self.sentido,
            'classe': self.classe,
            'velocidade_kmh': (
                '' if self.velocidade_kmh is None else round(self.velocidade_kmh, 1)
            ),
        }


@dataclass
class Relatorio:
    """Tudo que um processamento produziu."""

    fonte: str
    quadros_processados: int = 0
    fps: float = 25.0
    passagens: list[Passagem] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.passagens)

    @property
    def por_sentido(self) -> dict[str, int]:
        totais: dict[str, int] = {}
        for passagem in self.passagens:
            totais[passagem.sentido] = totais.get(passagem.sentido, 0) + 1
        return totais

    @property
    def por_classe(self) -> dict[str, int]:
        totais: dict[str, int] = {}
        for passagem in self.passagens:
            totais[passagem.classe] = totais.get(passagem.classe, 0) + 1
        return totais

    @property
    def velocidade_media(self) -> float | None:
        """Média das velocidades medidas, ignorando as que não deram para medir."""
        medidas = [p.velocidade_kmh for p in self.passagens if p.velocidade_kmh is not None]
        if not medidas:
            return None
        return sum(medidas) / len(medidas)

    @property
    def veiculos_por_minuto(self) -> float:
        """Fluxo médio. É o número que interessa para dimensionar via."""
        if self.fps <= 0 or self.quadros_processados <= 0:
            return 0.0
        minutos = self.quadros_processados / self.fps / 60.0
        if minutos <= 0:
            return 0.0
        return self.total / minutos

    def salvar_csv(self, caminho: str | Path) -> Path:
        destino = Path(caminho)
        destino.parent.mkdir(parents=True, exist_ok=True)
        colunas = ['id', 'quadro', 'segundo', 'sentido', 'classe', 'velocidade_kmh']
        # newline='' é obrigatório no Windows: sem isso o módulo csv escreve
        # \r\r\n e a planilha abre com uma linha em branco entre cada registro.
        with destino.open('w', newline='', encoding='utf-8') as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=colunas)
            escritor.writeheader()
            for passagem in self.passagens:
                escritor.writerow(passagem.como_linha())
        return destino

    def salvar_json(self, caminho: str | Path) -> Path:
        destino = Path(caminho)
        destino.parent.mkdir(parents=True, exist_ok=True)
        conteudo = {
            'fonte': self.fonte,
            'quadros_processados': self.quadros_processados,
            'fps': self.fps,
            'total': self.total,
            'por_sentido': self.por_sentido,
            'por_classe': self.por_classe,
            'veiculos_por_minuto': round(self.veiculos_por_minuto, 2),
            'velocidade_media_kmh': (
                None if self.velocidade_media is None else round(self.velocidade_media, 1)
            ),
            'passagens': [p.como_linha() for p in self.passagens],
        }
        destino.write_text(
            json.dumps(conteudo, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        return destino

    def resumo(self) -> str:
        """Texto curto para imprimir no terminal ao fim do processamento."""
        linhas = [
            f'Fonte: {self.fonte}',
            f'Quadros processados: {self.quadros_processados}',
            f'Total de veículos: {self.total}',
        ]
        for sentido, quantidade in sorted(self.por_sentido.items()):
            linhas.append(f'  {sentido}: {quantidade}')
        if self.por_classe:
            linhas.append('Por porte:')
            for classe, quantidade in sorted(self.por_classe.items()):
                linhas.append(f'  {classe}: {quantidade}')
        linhas.append(f'Fluxo: {self.veiculos_por_minuto:.1f} veículos por minuto')
        if self.velocidade_media is not None:
            linhas.append(f'Velocidade média: {self.velocidade_media:.1f} km/h')
        return '\n'.join(linhas)
