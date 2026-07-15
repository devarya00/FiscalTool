from datetime import date
from decimal import Decimal

from openpyxl import Workbook

from dominio.modelos import Grupo, Natureza, Secao
from infra.excel_parser import ler_contabil_excel, ler_fiscal_excel


def _gravar(caminho, cabecalho, linhas):
    wb = Workbook()
    ws = wb.active
    ws.append(cabecalho)
    for linha in linhas:
        ws.append(linha)
    wb.save(caminho)


def test_ler_fiscal_excel_agrupa_por_cnpj_e_soma_varios_meses(tmp_path):
    caminho = tmp_path / "fiscal.xlsx"
    _gravar(caminho,
        ["cnpj", "codigo", "descricao", "valor", "secao", "periodo_inicio", "periodo_fim"],
        [
            ["12.509.263/0001-00", "300", "FRETE JANEIRO", "1.250,50", "entradas", "01/01/2025", "31/01/2025"],
            ["12.509.263/0001-00", "300", "FRETE FEVEREIRO", "500,00", "entradas", "01/02/2025", "28/02/2025"],
            ["99.999.999/0001-99", "110", "IMOBILIZADO", "10.000,00", "entradas", "01/01/2025", "31/01/2025"],
        ],
    )

    resultado = ler_fiscal_excel(str(caminho))

    assert set(resultado) == {"12509263000100", "99999999000199"}
    rel = resultado["12509263000100"]
    assert len(rel.entradas) == 2
    assert sum(a.valor_contabil for a in rel.entradas) == Decimal("1750.50")
    assert rel.periodo.inicio == date(2025, 1, 1)
    assert rel.periodo.fim == date(2025, 2, 28)  # cobertura total dos meses


def test_ler_contabil_excel_reconstroi_conta_balancete(tmp_path):
    caminho = tmp_path / "contabil.xlsx"
    _gravar(caminho,
        ["cnpj", "codigo", "descricao", "grupo", "debito", "credito", "saldo_atual",
         "natureza_atual", "periodo_inicio", "periodo_fim"],
        [
            ["12.509.263/0001-00", 688, "DESPESA COM FRETE", "resultado", "1.750,50", "0,00",
             "1.750,50", "D", "01/01/2025", "31/12/2025"],
        ],
    )

    resultado = ler_contabil_excel(str(caminho))

    assert set(resultado) == {"12509263000100"}
    bal = resultado["12509263000100"]
    conta = bal.por_codigo(688)
    assert conta is not None
    assert conta.debito == Decimal("1750.50")
    assert conta.grupo is Grupo.RESULTADO
    assert conta.saldo_atual.natureza is Natureza.DEVEDOR
    assert bal.periodo.fim == date(2025, 12, 31)


def test_ler_fiscal_excel_aceita_numero_ja_convertido_pelo_openpyxl(tmp_path):
    """openpyxl entrega célula numérica como float/int, não string '1.250,50' —
    o parser precisa lidar com os dois formatos sem quebrar."""
    caminho = tmp_path / "fiscal.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["cnpj", "codigo", "descricao", "valor", "secao", "periodo_inicio", "periodo_fim"])
    ws.append(["12.509.263/0001-00", "300", "FRETE", 1250.5, "entradas", "01/01/2025", "31/01/2025"])
    wb.save(caminho)

    resultado = ler_fiscal_excel(str(caminho))
    assert resultado["12509263000100"].entradas[0].valor_contabil == Decimal("1250.5")


def test_secao_default_para_entradas_quando_ausente_ou_desconhecida(tmp_path):
    caminho = tmp_path / "fiscal.xlsx"
    _gravar(caminho,
        ["cnpj", "codigo", "descricao", "valor", "secao", "periodo_inicio", "periodo_fim"],
        [["12.509.263/0001-00", "300", "FRETE", "100,00", "", "01/01/2025", "31/01/2025"]],
    )
    resultado = ler_fiscal_excel(str(caminho))
    assert resultado["12509263000100"].entradas[0].secao is Secao.ENTRADAS
