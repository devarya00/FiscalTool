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
from tests.conftest import conta


def _gerar_pdf_fiscal(caminho: Path) -> None:
    c = canvas.Canvas(str(caminho), pagesize=(600, 800))
    c.setFont("Courier", 10)

    c.drawString(50, 780, "CNPJ: 12.509.263/0001-00")
    c.drawString(50, 765, "Periodo: 01/11/2025 a 31/12/2025")

    # "Base ICMS/ISS" fica bem à direita — dá folga para a descrição mais
    # longa + valor não vazarem para fora da "zona misturada" (mesmo formato
    # do relatório real: Vlr Contábil / Base ICMS bem separados do código).
    c.drawString(50, 740, "ENTRADAS")
    c.drawString(50, 725, "Codigo Descricao Vlr Contabil" + " " * 40 + "Base ICMS")
    c.drawString(50, 710, "107 COMPRA DE USO E CONSUMO A PRAZO 10.782,39")

    c.drawString(50, 685, "SAIDAS")
    c.drawString(50, 670, "Codigo Descricao Vlr Contabil" + " " * 40 + "Base ICMS")
    c.drawString(50, 655, "401 VENDA DE MERCADORIAS 5.000,00")

    c.drawString(50, 630, "SERVICOS")
    c.drawString(50, 615, "Cod Descricao Vlr Contabil" + " " * 40 + "Base ISS")
    c.drawString(50, 600, "900 PRESTACAO DE SERVICOS 500,00")
    c.drawString(50, 585, "TOTAL SERVICOS 500,00")

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
    # Colunas espaçadas o suficiente para caber "999.999,99D" (11 chars) sem
    # que o último caractere vaze para a faixa vizinha.
    c.drawString(280, 740, "Saldo Anterior")
    c.drawString(400, 740, "Debito")
    c.drawString(480, 740, "Credito")
    c.drawString(560, 740, "Saldo Atual")

    # Cabeçalho de grupo — código próprio, sem linha textual separada (caso
    # real do doc: "ATIVO"/"PASSIVO" são elas mesmas contas numeradas).
    c.drawString(50, 700, "1 ATIVO")

    # Linha da conta — cada coluna numérica em drawString separado, na mesma
    # faixa de X do cabeçalho, simulando extract_words() por geometria.
    c.drawString(50, 680, "58 OUTROS MATERIAIS DE CONSUMO")
    c.drawString(280, 680, "91.769,53D")
    c.drawString(400, 680, "10.782,39")
    c.drawString(480, 680, "0,00")
    c.drawString(560, 680, "102.551,92D")

    c.save()


def test_consolidar_contas_soma_movimento_e_usa_saldo_atual_do_ultimo_mes():
    """Caso real (CONCREMEX): PDF com 12 balancetes mensais concatenados —
    conta 5 CAIXA GERAL aparece uma vez por mês, mesmo código. Sem
    consolidação, por_codigo() devolve janeiro (saldo_atual bem menor que o
    saldo real de dezembro), e débito/crédito de um mês só, não do ano."""
    meses = [
        conta(5, "CAIXA GERAL", Grupo.ATIVO, saldo_anterior="142468.72", debito="0",
              credito="0", saldo_atual="142468.72", natureza_atual=Natureza.DEVEDOR, linha=1),
        conta(5, "CAIXA GERAL", Grupo.ATIVO, saldo_anterior="142468.72", debito="100442.92",
              credito="44220.77", saldo_atual="198690.87", natureza_atual=Natureza.DEVEDOR, linha=1),
        conta(5, "CAIXA GERAL", Grupo.ATIVO, saldo_anterior="262022.81", debito="0",
              credito="10624.00", saldo_atual="251398.81", natureza_atual=Natureza.DEVEDOR, linha=1),
    ]
    consolidadas = BalanceteParser._consolidar_contas(meses)

    assert len(consolidadas) == 1
    c = consolidadas[0]
    assert c.saldo_anterior.valor == Decimal("142468.72")  # abertura do 1o mes
    assert c.debito == Decimal("100442.92")
    assert c.credito == Decimal("54844.77")  # 44220.77 + 10624.00
    assert c.saldo_atual.valor == Decimal("251398.81")  # fechamento do ultimo mes


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


def _gerar_pdf_balancete_fonte_sobreposta(caminho: Path) -> None:
    """Reproduz o bug real do Balancete jovane.pdf: a linha da conta tem duas
    camadas de texto na MESMA posição (rótulo limpo em fonte maior + código e
    valores em fonte menor). extract_text()/leitura ingênua por x0 embaralha
    caractere a caractere: 'O58U TOURTOROSS MMATAETRIEARISI...' — texto que
    nem começa com dígito, então a conta inteira desaparecia antes do fix em
    _resolver_chars_linha."""
    c = canvas.Canvas(str(caminho), pagesize=(700, 800))
    c.setFont("Courier", 10)
    c.drawString(50, 780, "CNPJ: 12.509.263/0001-00  Periodo: 01/11/2025 a 31/12/2025")
    c.drawString(280, 740, "Saldo Anterior")
    c.drawString(400, 740, "Debito")
    c.drawString(480, 740, "Credito")
    c.drawString(560, 740, "Saldo Atual")
    c.drawString(50, 700, "1 ATIVO")

    c.setFont("Courier-Bold", 12)
    c.drawString(50, 680, "OUTROS MATERIAIS DE CONSUMO")
    c.setFont("Courier", 8)
    c.drawString(50, 680, "58 OUTROS MATERIAIS DE CONSUMO")
    c.drawString(280, 680, "91.769,53D")
    c.drawString(400, 680, "10.782,39")
    c.drawString(480, 680, "0,00")
    c.drawString(560, 680, "102.551,92D")
    c.save()


def test_balancete_parser_resolve_linha_com_fonte_sobreposta(tmp_path):
    caminho = tmp_path / "balancete_sobreposto.pdf"
    _gerar_pdf_balancete_fonte_sobreposta(caminho)

    balancete = BalanceteParser().parse(str(caminho))

    conta = balancete.por_codigo(58)
    assert conta is not None
    assert conta.descricao == "OUTROS MATERIAIS DE CONSUMO"
    assert conta.debito == Decimal("10782.39")
    assert conta.saldo_atual.valor == Decimal("102551.92")


def test_extrair_campos_nao_engole_digito_da_descricao_no_codigo():
    """Descrição que começa com dígito ('13º Salário') não pode virar parte do
    código. O corte é por GAP de posição x (espaço real), não pelo primeiro
    caractere não-dígito. reportlab não reproduz esse cenário (bbox monospace
    sintético não tem gap real entre glifos) — coordenadas abaixo são as
    medidas de verdade no Balancete jovane.pdf: ~35pt entre código e descrição
    contra <0.1pt de kerning intra-código."""
    def ch(texto: str, x0: float, x1: float) -> dict:
        return {"text": texto, "x0": x0, "x1": x1, "top": 10.0, "size": 6.18}

    faixas = {
        "saldo_anterior": (300.0, 380.0), "debito": (380.0, 440.0),
        "credito": (440.0, 500.0), "saldo_atual": (500.0, 600.0),
    }
    chars_linha = [
        ch("3", 15.00, 18.37), ch("3", 18.36, 21.74), ch("4", 21.72, 25.10),
        # gap real ~35pt (medido) entre o fim do código e o início da descrição
        ch("1", 60.30, 63.67), ch("3", 63.67, 67.04), ch("º", 67.04, 70.09),
        ch(" ", 70.08, 72.01),
        ch("S", 72.01, 75.45), ch("A", 75.45, 79.15), ch("L", 79.15, 82.23),
        ch("Á", 82.22, 85.93), ch("R", 85.93, 89.76), ch("I", 89.76, 92.06), ch("O", 92.06, 96.43),
    ]

    campos = BalanceteParser._extrair_campos(chars_linha, faixas)
    assert campos is not None
    codigo, descricao, *_ = campos
    assert codigo == "334"
    assert descricao == "13º SALÁRIO"
