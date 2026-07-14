"""Normalização de texto para matching por substring (regra de negócio pura, sem I/O)."""
from __future__ import annotations

import unicodedata


def normalizar(txt: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode("ascii")
    return sem_acento.lower().strip()


def contem(descricao: str, padrao: str) -> bool:
    return normalizar(padrao) in normalizar(descricao)
