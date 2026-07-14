from datetime import date
from decimal import Decimal

from dominio.modelos import Natureza
from infra.normalizador import extrair_cnpj, normalizar_cnpj, parse_periodo, to_decimal, to_saldo


def test_to_decimal_milhar_e_decimal():
    assert to_decimal("102.551,92") == Decimal("102551.92")


def test_to_decimal_zero():
    assert to_decimal("0,00") == Decimal("0.00")


def test_to_saldo_com_natureza_devedora():
    saldo = to_saldo("102.551,92D")
    assert saldo.valor == Decimal("102551.92")
    assert saldo.natureza is Natureza.DEVEDOR


def test_to_saldo_com_natureza_credora():
    saldo = to_saldo("13.972,35C")
    assert saldo.valor == Decimal("13972.35")
    assert saldo.natureza is Natureza.CREDOR


def test_to_saldo_zerado_sem_sufixo():
    saldo = to_saldo("0,00")
    assert saldo.valor == Decimal("0.00")
    assert saldo.natureza is None


def test_normalizar_cnpj():
    assert normalizar_cnpj("12.509.263/0001-00") == "12509263000100"


def test_extrair_cnpj_de_texto_livre():
    assert extrair_cnpj("Empresa: X CNPJ: 12.509.263/0001-00 Período...") == "12509263000100"


def test_parse_periodo():
    periodo = parse_periodo("Período: 01/11/2025 a 31/12/2025")
    assert periodo.inicio == date(2025, 11, 1)
    assert periodo.fim == date(2025, 12, 31)
