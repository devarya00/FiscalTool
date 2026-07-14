from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from dominio.modelos import (
    Acumulador, Balancete, ContaBalancete, Contexto, Grupo, Natureza,
    Periodo, RelatorioFiscal, Saldo, Secao,
)

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "regras.yaml"


@pytest.fixture
def config() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def periodo() -> Periodo:
    return Periodo(date(2025, 11, 1), date(2025, 12, 31))


def d(txt: str) -> Decimal:
    return Decimal(txt)


def acumulador(codigo: str, descricao: str, valor: str, secao: Secao, linha: int = 1) -> Acumulador:
    return Acumulador(
        codigo=codigo, descricao=descricao, valor_contabil=d(valor),
        secao=secao, pagina=1, linha=linha,
    )


def conta(
    codigo: int, descricao: str, grupo: Grupo,
    saldo_anterior: str = "0", debito: str = "0", credito: str = "0",
    saldo_atual: str = "0", natureza_atual: Natureza | None = Natureza.DEVEDOR,
    natureza_anterior: Natureza | None = None, linha: int = 1,
) -> ContaBalancete:
    return ContaBalancete(
        codigo=codigo, descricao=descricao, grupo=grupo,
        saldo_anterior=Saldo(d(saldo_anterior), natureza_anterior),
        debito=d(debito), credito=d(credito),
        saldo_atual=Saldo(d(saldo_atual), natureza_atual),
        pagina=1, linha=linha,
    )


def fiscal(
    cnpj: str = "12509263000100", periodo_: Periodo | None = None,
    entradas: list[Acumulador] | None = None, saidas: list[Acumulador] | None = None,
    servicos: list[Acumulador] | None = None, total_servicos: str | None = None,
) -> RelatorioFiscal:
    return RelatorioFiscal(
        cnpj=cnpj, periodo=periodo_ or Periodo(date(2025, 11, 1), date(2025, 12, 31)),
        entradas=entradas or [], saidas=saidas or [], servicos=servicos or [],
        total_servicos=d(total_servicos) if total_servicos is not None else None,
    )


def balancete(
    cnpj: str = "12509263000100", periodo_: Periodo | None = None,
    contas: list[ContaBalancete] | None = None,
) -> Balancete:
    return Balancete(
        cnpj=cnpj, periodo=periodo_ or Periodo(date(2025, 11, 1), date(2025, 12, 31)),
        contas=contas or [],
    )


def contexto(fiscal_: RelatorioFiscal, balancete_: Balancete, config_: dict, **kwargs) -> Contexto:
    return Contexto(fiscal=fiscal_, balancete=balancete_, config=config_, **kwargs)
