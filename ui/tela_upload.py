from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from infra.sanitize_pdf import GhostscriptError, sanitize_pdf


class TelaUpload(QWidget):
    conferir_solicitado = Signal(str, str, object)  # pdf_fiscal, pdf_balancete, houve_folha_override|None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._caminho_fiscal: str | None = None
        self._caminho_balancete: str | None = None

        layout = QVBoxLayout(self)

        layout.addWidget(self._linha_arquivo(
            "Resumo por Acumulador (Fiscal):", self._selecionar_fiscal, "_label_fiscal",
        ))
        layout.addWidget(self._linha_arquivo(
            "Balancete (Contábil):", self._selecionar_balancete, "_label_balancete",
        ))

        self._checkbox_sanitizar = QCheckBox("Sanitizar PDFs com Ghostscript antes de conferir")
        layout.addWidget(self._checkbox_sanitizar)
        layout.addWidget(QLabel(
            "Reconstrói o PDF para corrigir colunas coladas e linhas fantasma antes da "
            "extração. Se o Ghostscript falhar, segue com o PDF original (não trava)."
        ))

        self._checkbox_folha = QCheckBox("Houve folha de pagamento no período (override manual)")
        self._checkbox_folha.setTristate(True)
        layout.addWidget(self._checkbox_folha)
        layout.addWidget(QLabel(
            "Deixe indeterminado para inferir automaticamente pelo movimento na conta 331."
        ))

        self._botao_conferir = QPushButton("Conferir")
        self._botao_conferir.setEnabled(False)
        self._botao_conferir.clicked.connect(self._conferir)
        layout.addWidget(self._botao_conferir)
        layout.addStretch()

    def _linha_arquivo(self, rotulo: str, slot, atributo_label: str) -> QWidget:
        container = QWidget()
        h = QHBoxLayout(container)
        h.addWidget(QLabel(rotulo))
        label_arquivo = QLabel("(nenhum arquivo selecionado)")
        setattr(self, atributo_label, label_arquivo)
        h.addWidget(label_arquivo, stretch=1)
        botao = QPushButton("Selecionar PDF...")
        botao.clicked.connect(slot)
        h.addWidget(botao)
        return container

    def _selecionar_fiscal(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(self, "Selecionar Resumo por Acumulador", "", "PDF (*.pdf)")
        if caminho:
            self._caminho_fiscal = caminho
            self._label_fiscal.setText(caminho)
            self._atualizar_botao()

    def _selecionar_balancete(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(self, "Selecionar Balancete", "", "PDF (*.pdf)")
        if caminho:
            self._caminho_balancete = caminho
            self._label_balancete.setText(caminho)
            self._atualizar_botao()

    def _atualizar_botao(self) -> None:
        self._botao_conferir.setEnabled(bool(self._caminho_fiscal and self._caminho_balancete))

    def _sanitizar_se_solicitado(self, caminho: str) -> str:
        if not self._checkbox_sanitizar.isChecked():
            return caminho
        destino = Path(tempfile.gettempdir()) / f"sanitizado_{Path(caminho).stem}.pdf"
        try:
            return str(sanitize_pdf(caminho, destino))
        except GhostscriptError as exc:
            QMessageBox.warning(
                self, "Sanitização falhou",
                f"Ghostscript indisponível ou falhou — seguindo com o PDF original.\n\n{exc}",
            )
            return caminho

    def _conferir(self) -> None:
        estado = self._checkbox_folha.checkState()
        if estado.name == "PartiallyChecked":
            override = None
        else:
            override = estado.name == "Checked"

        caminho_fiscal = self._sanitizar_se_solicitado(self._caminho_fiscal)
        caminho_balancete = self._sanitizar_se_solicitado(self._caminho_balancete)
        self.conferir_solicitado.emit(caminho_fiscal, caminho_balancete, override)
