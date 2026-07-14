from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

from dominio.apontamento import Apontamento, Severidade

_COR_SEVERIDADE = {
    Severidade.IMPEDITIVO: QColor("#7a0000"),
    Severidade.CRITICO: QColor("#f2b6b3"),
    Severidade.ALERTA: QColor("#fbe1b0"),
    Severidade.OK: QColor("#c9e7c9"),
}

_COLUNAS = [
    "Regra", "Status", "Descrição", "Valor Fiscal", "Valor Contábil",
    "Diferença", "Coluna Esperada", "Coluna Encontrada",
]


class TabelaApontamentos(QTableWidget):
    """Tabela reutilizável: Regra · Valor Fiscal · Valor Contábil · Diferença ·
    Coluna Esperada · Coluna Encontrada · Status — linhas coloridas por severidade."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(_COLUNAS))
        self.setHorizontalHeaderLabels(_COLUNAS)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.horizontalHeader().setStretchLastSection(False)

    def carregar(self, apontamentos: list[Apontamento]) -> None:
        self.setRowCount(len(apontamentos))
        for row, ap in enumerate(apontamentos):
            valores = [
                ap.regra,
                ap.severidade.value.upper(),
                ap.descricao,
                f"{ap.valor_fiscal:.2f}" if ap.valor_fiscal is not None else "",
                f"{ap.valor_contabil:.2f}" if ap.valor_contabil is not None else "",
                f"{ap.diferenca:.2f}" if ap.diferenca is not None else "",
                ap.coluna_esperada or "",
                ap.coluna_encontrada or "",
            ]
            cor = _COR_SEVERIDADE.get(ap.severidade)
            for col, valor in enumerate(valores):
                item = QTableWidgetItem(valor)
                if cor:
                    item.setBackground(cor)
                self.setItem(row, col, item)
        self.resizeColumnsToContents()
