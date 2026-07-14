"""Smoke tests dos parsers contra PDFs sintéticos gerados com reportlab.

Não substitui a suíte de fixtures reais recomendada no Roadmap (Fase 0: 15-20
pares de PDFs de clientes) — valida que o caminho de código (extract_words +
faixas de coluna / extract_text linear) funciona de ponta a ponta.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from reportlab.pdfgen import canvas

from dominio.modelos import Grupo, Natureza, Secao
from infra.balancete_parser import BalanceteParser
from infra.fiscal_parser import FiscalParser


def _gerar_pdf_fiscal(caminho: Path) -> None:
    c = canvas.Canvas(str(caminho), pagesize=(600, 800))
    c.setFont("Courier", 10)
    linhas = [
        "CNPJ: 12.509.263/0001-00",
        "Periodo: 01/11/2025 a 31/12/2025",
        "ENTRADAS",
        "107 COMPRA DE USO E CONSUMO A PRAZO 10.782,39",
        "SAIDAS",
        "401 VENDA DE MERCADORIAS 5.000,00",
        "SERVICOS",
        "900 PRESTACAO DE SERVICOS 500,00",
        "TOTAL SERVICOS 500,00",
    ]
    y = 760
    for linha in linhas:
        c.drawString(50, y, linha)
        y -= 20
    c.save()


def test_fiscal_parser_extrai_secoes_e_total(tmp_path):
    caminho = tmp_path / "fiscal.pdf"
    _gerar_pdf_fiscal(caminho)

    relatorio = FiscalParser().parse(str(caminho))

    assert relatorio.cnpj == "12509263000100"
    assert relatorio.periodo.inicio.isoformat() == "2025-11-01"
    assert relatorio.periodo.fim.isoformat() == "2025-12-31"

    assert len(relatorio.entradas) == 1
    assert relatorio.entradas[0].codigo == "107"
    assert relatorio.entradas[0].valor_contabil == Decimal("10782.39")
    assert relatorio.entradas[0].secao is Secao.ENTRADAS

    assert len(relatorio.saidas) == 1
    assert relatorio.saidas[0].valor_contabil == Decimal("5000.00")

    assert len(relatorio.servicos) == 1
    assert relatorio.total_servicos == Decimal("500.00")


def _gerar_pdf_balancete(caminho: Path) -> None:
    c = canvas.Canvas(str(caminho), pagesize=(700, 800))
    c.setFont("Courier", 10)

    c.drawString(50, 780, "CNPJ: 12.509.263/0001-00  Periodo: 01/11/2025 a 31/12/2025")

    # Cabeçalho de colunas — faixas de X detectadas uma vez a partir daqui.
    c.drawString(300, 740, "Saldo Anterior")
    c.drawString(400, 740, "Debito")
    c.drawString(460, 740, "Credito")
    c.drawString(520, 740, "Saldo Atual")

    # Cabeçalho de grupo colado antes da linha da conta (caso real do doc, §5.1).
    c.drawString(50, 700, "ATIVO CIRCULANTE")

    # Linha da conta — cada coluna numérica em drawString separado, na mesma
    # faixa de X do cabeçalho, simulando extract_words() por geometria.
    c.drawString(50, 680, "58 OUTROS MATERIAIS DE CONSUMO")
    c.drawString(300, 680, "91.769,53D")
    c.drawString(400, 680, "10.782,39")
    c.drawString(460, 680, "0,00")
    c.drawString(520, 680, "102.551,92D")

    c.save()


def test_balancete_parser_extrai_conta_por_posicao(tmp_path):
    caminho = tmp_path / "balancete.pdf"
    _gerar_pdf_balancete(caminho)

    balancete = BalanceteParser().parse(str(caminho))

    assert balancete.cnpj == "12509263000100"
    assert balancete.periodo.inicio.isoformat() == "2025-11-01"

    conta = balancete.por_codigo(58)
    assert conta is not None
    assert conta.descricao == "OUTROS MATERIAIS DE CONSUMO"
    assert conta.grupo is Grupo.ATIVO
    assert conta.saldo_anterior.valor == Decimal("91769.53")
    assert conta.saldo_anterior.natureza is Natureza.DEVEDOR
    assert conta.debito == Decimal("10782.39")
    assert conta.credito == Decimal("0.00")
    assert conta.saldo_atual.valor == Decimal("102551.92")
    assert conta.saldo_atual.natureza is Natureza.DEVEDOR
