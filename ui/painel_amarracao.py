from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

from dominio.apontamento import Apontamento, Severidade
from infra.normalizador import formatar_decimal

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
        self._apontamentos: list[Apontamento] = []

    def apontamento_selecionado(self) -> Apontamento | None:
        linha = self.currentRow()
        if 0 <= linha < len(self._apontamentos):
            return self._apontamentos[linha]
        return None

    def carregar(self, apontamentos: list[Apontamento]) -> None:
        self._apontamentos = list(apontamentos)
        self.setRowCount(len(apontamentos))
        for row, ap in enumerate(apontamentos):
            valores = [
                ap.regra,
                ap.severidade.value.upper(),
                ap.descricao,
                formatar_decimal(ap.valor_fiscal) if ap.valor_fiscal is not None else "",
                formatar_decimal(ap.valor_contabil) if ap.valor_contabil is not None else "",
                formatar_decimal(ap.diferenca) if ap.diferenca is not None else "",
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
