from __future__ import annotations

from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QStackedWidget,
    QTabWidget, QVBoxLayout, QWidget,
)

from aplicacao.conferencia_service import ConferenciaService, ResultadoConferencia
from dominio.apontamento import Severidade
from relatorios.pdf_export import exportar_pdf
from relatorios.xlsx_export import exportar_xlsx
from ui.painel_amarracao import TabelaApontamentos
from ui.painel_fluxo import PainelFluxo
from ui.tela_upload import TelaUpload


class JanelaPrincipal(QWidget):
    def __init__(self, servico: ConferenciaService | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Conferência Fiscal × Contábil")
        self.resize(1100, 700)
        self._servico = servico or ConferenciaService()
        self._resultado: ResultadoConferencia | None = None

        self._pilha = QStackedWidget()
        layout = QVBoxLayout(self)
        layout.addWidget(self._pilha)

        self._tela_upload = TelaUpload()
        self._tela_upload.conferir_solicitado.connect(self._conferir)
        self._pilha.addWidget(self._tela_upload)

        self._tela_banner = QLabel()
        self._tela_banner.setStyleSheet(
            "background-color:#7a0000; color:white; font-size:16px; padding:24px;"
        )
        self._tela_banner.setWordWrap(True)
        self._pilha.addWidget(self._tela_banner)

        self._abas = QTabWidget()
        self._tabela_cabecalho = TabelaApontamentos()
        self._tabela_estrutural = TabelaApontamentos()
        self._tabela_amarracao = TabelaApontamentos()
        self._painel_fluxo = PainelFluxo()
        self._tabela_orfaos = TabelaApontamentos()

        self._abas.addTab(self._tabela_cabecalho, "Cabeçalho")
        self._abas.addTab(self._tabela_estrutural, "Estrutural")
        self._abas.addTab(self._tabela_amarracao, "Amarração")
        self._abas.addTab(self._painel_fluxo, "Fluxo de Caixa")
        self._abas.addTab(self._tabela_orfaos, "Não Mapeados")

        botoes_exportar = QWidget()
        h = QHBoxLayout(botoes_exportar)
        h.setContentsMargins(0, 0, 0, 0)
        botao_pdf = QPushButton("Exportar PDF")
        botao_pdf.clicked.connect(self.exportar_pdf)
        botao_xlsx = QPushButton("Exportar Excel")
        botao_xlsx.clicked.connect(self.exportar_xlsx)
        h.addWidget(botao_pdf)
        h.addWidget(botao_xlsx)
        self._abas.setCornerWidget(botoes_exportar)

        self._pilha.addWidget(self._abas)

        self._pilha.setCurrentWidget(self._tela_upload)

    def _conferir(self, pdf_fiscal: str, pdf_balancete: str, houve_folha_override) -> None:
        try:
            self._resultado = self._servico.executar(pdf_fiscal, pdf_balancete, houve_folha_override)
        except Exception as exc:  # noqa: BLE001 — erro de parsing/arquivo vai pro usuário, não crash
            QMessageBox.critical(self, "Erro ao processar", str(exc))
            return

        if self._resultado.abortado:
            impeditivos = self._resultado.por_severidade(Severidade.IMPEDITIVO)
            texto = "\n".join(a.descricao for a in impeditivos)
            self._tela_banner.setText(f"CONFERÊNCIA ABORTADA\n\n{texto}")
            self._pilha.setCurrentWidget(self._tela_banner)
            return

        self._tabela_cabecalho.carregar(self._resultado.cabecalho())
        self._tabela_estrutural.carregar(self._resultado.estrutural())
        self._tabela_amarracao.carregar(self._resultado.amarracao())
        self._painel_fluxo.carregar(self._resultado)
        self._tabela_orfaos.carregar(self._resultado.orfaos())
        self._pilha.setCurrentWidget(self._abas)

    def exportar_pdf(self) -> None:
        if self._resultado is None:
            return
        caminho, _ = QFileDialog.getSaveFileName(self, "Exportar PDF", "conferencia.pdf", "PDF (*.pdf)")
        if caminho:
            exportar_pdf(self._resultado, caminho)

    def exportar_xlsx(self) -> None:
        if self._resultado is None:
            return
        caminho, _ = QFileDialog.getSaveFileName(self, "Exportar Excel", "conferencia.xlsx", "Excel (*.xlsx)")
        if caminho:
            exportar_xlsx(self._resultado, caminho)
