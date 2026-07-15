"""Normalização de texto para matching por substring (regra de negócio pura, sem I/O)."""
from __future__ import annotations

import unicodedata
from decimal import Decimal

from dominio.modelos import Acumulador, Contexto

# Contas retificadoras: natureza esperada é a INVERSA do grupo, e são o par
# esperado de contas de bens em auditoria de depreciação/amortização.
# Compartilhado entre P2.NATUREZA (estrutural.py) e P8.DEPRECIACAO
# (depreciacao.py) — uma lista só, editável via regras.yaml (natureza.retificadoras).
RETIFICADORAS_PADRAO = [
    "(-)", "depreciacao acumulada", "amortizacao acumulada", "exaustao acumulada",
    "provisao para devedores duvidosos", "provisao para creditos de liquidacao duvidosa",
    "provisao para perdas",
]


def normalizar(txt: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode("ascii")
    return sem_acento.lower().strip()


def contem(descricao: str, padrao: str) -> bool:
    return normalizar(padrao) in normalizar(descricao)


def tolerancia(ctx: Contexto) -> Decimal:
    centavos = ctx.config.get("tolerancia_centavos", 0)
    return Decimal(centavos) / Decimal(100)


def ignorado(ac: Acumulador, ctx: Contexto) -> bool:
    padroes = ctx.config.get("amarracao", {}).get("filtro_ignorar", ["outras"])
    return any(contem(ac.descricao, p) for p in padroes)
