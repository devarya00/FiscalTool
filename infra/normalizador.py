"""Normalização de valores extraídos do PDF em tipos de domínio."""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from dominio.modelos import Natureza, Periodo, Saldo

_PERIODO_RE = re.compile(r"(\d{2}/\d{2}/\d{4}).{0,12}?(\d{2}/\d{2}/\d{4})")
_CNPJ_RE = re.compile(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}")


def to_decimal(txt: str) -> Decimal:
    """'102.551,92' -> Decimal('102551.92'). Aceita sufixo D/C, que é descartado."""
    limpo = txt.strip().rstrip("DCdc").strip()
    limpo = limpo.replace(".", "").replace(",", ".")
    if not limpo:
        return Decimal("0")
    try:
        return Decimal(limpo)
    except InvalidOperation as exc:
        raise ValueError(f"Valor numérico inválido: {txt!r}") from exc


def to_saldo(txt: str) -> Saldo:
    """'102.551,92D' -> Saldo(Decimal('102551.92'), Natureza.D). '0,00' -> Saldo(0, None)."""
    txt = txt.strip()
    natureza = None
    if txt and txt[-1] in ("D", "C", "d", "c"):
        natureza = Natureza(txt[-1].upper())
        txt = txt[:-1]
    valor = to_decimal(txt)
    if valor == 0:
        natureza = None
    return Saldo(valor, natureza)


def normalizar_cnpj(txt: str) -> str:
    return re.sub(r"\D", "", txt)


def extrair_cnpj(texto: str) -> str | None:
    m = _CNPJ_RE.search(texto)
    return normalizar_cnpj(m.group(0)) if m else None


def parse_periodo(txt: str) -> Periodo:
    m = _PERIODO_RE.search(txt)
    if not m:
        raise ValueError(f"Período não encontrado em: {txt!r}")
    return Periodo(_parse_data(m.group(1)), _parse_data(m.group(2)))


def _parse_data(txt: str) -> date:
    dia, mes, ano = txt.split("/")
    return date(int(ano), int(mes), int(dia))
