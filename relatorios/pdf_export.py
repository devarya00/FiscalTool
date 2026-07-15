from __future__ import annotations

from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from aplicacao.conferencia_service import ResultadoConferencia
from dominio.apontamento import Apontamento, Severidade
from infra.normalizador import formatar_decimal

_COR_SEVERIDADE = {
    Severidade.IMPEDITIVO: colors.HexColor("#7a0000"),
    Severidade.CRITICO: colors.HexColor("#d9534f"),
    Severidade.ALERTA: colors.HexColor("#f0ad4e"),
    Severidade.OK: colors.HexColor("#5cb85c"),
}

_CABECALHO_TABELA = ["Regra", "Status", "Descrição", "Vlr Fiscal", "Vlr Contábil", "Diferença"]

_ESTILO_CELULA = ParagraphStyle("celula_tabela", fontName="Helvetica", fontSize=8, leading=10)


def _linha(ap: Apontamento) -> list:
    # Descrição como Paragraph: string crua não quebra linha na largura da
    # coluna, o texto vaza e sobrepõe a linha seguinte (célula não cresce).
    return [
        ap.regra, ap.severidade.value.upper(), Paragraph(escape(ap.descricao), _ESTILO_CELULA),
        formatar_decimal(ap.valor_fiscal) if ap.valor_fiscal is not None else "",
        formatar_decimal(ap.valor_contabil) if ap.valor_contabil is not None else "",
        formatar_decimal(ap.diferenca) if ap.diferenca is not None else "",
    ]


def _tabela(apontamentos: list[Apontamento]) -> Table:
    dados = [_CABECALHO_TABELA] + [_linha(a) for a in apontamentos]
    tabela = Table(dados, repeatRows=1, colWidths=[3 * cm, 2.2 * cm, 8 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm])
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i, ap in enumerate(apontamentos, start=1):
        cor = _COR_SEVERIDADE.get(ap.severidade)
        if cor:
            estilo.append(("TEXTCOLOR", (1, i), (1, i), cor))
    tabela.setStyle(TableStyle(estilo))
    return tabela


def exportar_pdf(resultado: ResultadoConferencia, caminho: str) -> None:
    doc = SimpleDocTemplate(caminho, pagesize=landscape(A4), title="Conferência Fiscal × Contábil")
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Conferência Fiscal × Contábil", styles["Title"]),
        Paragraph(
            f"CNPJ: {resultado.cnpj} — Período: {resultado.periodo.inicio:%d/%m/%Y} a "
            f"{resultado.periodo.fim:%d/%m/%Y}",
            styles["Normal"],
        ),
        Spacer(1, 0.5 * cm),
    ]

    blocos = [
        ("Cabeçalho", resultado.cabecalho()),
        ("Estrutural", resultado.estrutural()),
        ("Amarração Fiscal × Contábil", resultado.amarracao()),
        ("Fluxo de Caixa", resultado.fluxo_de_caixa()),
        ("Acumuladores Não Mapeados", resultado.orfaos()),
    ]
    for titulo, apontamentos in blocos:
        if not apontamentos:
            continue
        story.append(Paragraph(titulo, styles["Heading2"]))
        story.append(_tabela(apontamentos))
        story.append(Spacer(1, 0.5 * cm))

    doc.build(story)
