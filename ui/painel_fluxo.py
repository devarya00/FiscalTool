from __future__ import annotations

from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QWidget

from aplicacao.conferencia_service import ResultadoConferencia
from ui.painel_amarracao import TabelaApontamentos


class PainelFluxo(QWidget):
    """Seção separada (exigência explícita): Pagamento da Folha · Simples
    Nacional · Receita × Custo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self._folha = TabelaApontamentos()
        self._simples = TabelaApontamentos()
        self._receita_custo = TabelaApontamentos()

        for titulo, tabela in [
            ("Folha de Pagamento", self._folha),
            ("Simples Nacional", self._simples),
            ("Receita × Custo", self._receita_custo),
        ]:
            grupo = QGroupBox(titulo)
            grupo_layout = QVBoxLayout(grupo)
            grupo_layout.addWidget(tabela)
            layout.addWidget(grupo)

    def carregar(self, resultado: ResultadoConferencia) -> None:
        self._folha.carregar(resultado.por_regra_prefixo("P6.FOLHA_INTEGRALIZACAO", "P7.FOLHA_PAGAMENTO"))
        self._simples.carregar(resultado.por_regra_prefixo("P7.SIMPLES"))
        self._receita_custo.carregar(resultado.por_regra_prefixo("P7.RECEITA_CUSTO"))
