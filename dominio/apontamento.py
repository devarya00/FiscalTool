from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from dominio.modelos import Referencia


class Severidade(Enum):
    IMPEDITIVO = "impeditivo"  # aborta a execução (Passos 1 e 2)
    CRITICO = "critico"        # divergência de valor / coluna errada
    ALERTA = "alerta"          # conta esperada zerada / não mapeado
    OK = "ok"                  # conferido, sem divergência


@dataclass
class Apontamento:
    regra: str
    severidade: Severidade
    descricao: str
    valor_fiscal: Decimal | None = None
    valor_contabil: Decimal | None = None
    diferenca: Decimal | None = None
    coluna_esperada: str | None = None
    coluna_encontrada: str | None = None
    origem_fiscal: Referencia | None = None
    origem_balancete: Referencia | None = None
