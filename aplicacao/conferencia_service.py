"""Orquestração: pega dois PDFs, produz o relatório de apontamentos."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from dominio.apontamento import Apontamento, Severidade
from dominio.modelos import Balancete, Contexto, Periodo, RelatorioFiscal
from dominio.motor import MotorRegras
from dominio.regras import todas_as_regras
from infra.balancete_parser import BalanceteParser
from infra.fiscal_parser import FiscalParser

_CONFIG_PADRAO = Path(__file__).resolve().parent.parent / "config" / "regras.yaml"


@dataclass
class ResultadoConferencia:
    fiscal: RelatorioFiscal
    balancete: Balancete
    apontamentos: list[Apontamento]

    @property
    def abortado(self) -> bool:
        return any(a.severidade is Severidade.IMPEDITIVO for a in self.apontamentos)

    @property
    def cnpj(self) -> str:
        return self.fiscal.cnpj

    @property
    def periodo(self) -> Periodo:
        return self.fiscal.periodo

    def por_severidade(self, severidade: Severidade) -> list[Apontamento]:
        return [a for a in self.apontamentos if a.severidade is severidade]

    def por_regra_prefixo(self, *prefixos: str) -> list[Apontamento]:
        return [a for a in self.apontamentos if a.regra.startswith(prefixos)]

    def cabecalho(self) -> list[Apontamento]:
        return self.por_regra_prefixo("P1.")

    def estrutural(self) -> list[Apontamento]:
        return self.por_regra_prefixo("P2.")

    def amarracao(self) -> list[Apontamento]:
        return self.por_regra_prefixo("P3.", "P4.", "P5.")

    def fluxo_de_caixa(self) -> list[Apontamento]:
        return self.por_regra_prefixo("P6.FOLHA_INTEGRALIZACAO", "P7.")

    def orfaos(self) -> list[Apontamento]:
        return self.por_regra_prefixo("P6.ORFAOS")


class ConferenciaService:
    def __init__(self, config_path: str | Path = _CONFIG_PADRAO):
        with open(config_path, encoding="utf-8") as f:
            self._config: dict[str, Any] = yaml.safe_load(f)
        self._fiscal_parser = FiscalParser()
        self._balancete_parser = BalanceteParser()
        self._motor = MotorRegras(todas_as_regras())

    def executar(
        self, pdf_fiscal: str, pdf_balancete: str, houve_folha_override: bool | None = None,
    ) -> ResultadoConferencia:
        fiscal = self._fiscal_parser.parse(pdf_fiscal)
        balancete = self._balancete_parser.parse(pdf_balancete)

        ctx = Contexto(
            fiscal=fiscal, balancete=balancete, config=self._config,
            houve_folha_override=houve_folha_override,
        )
        apontamentos = self._motor.executar(ctx)

        return ResultadoConferencia(fiscal=fiscal, balancete=balancete, apontamentos=apontamentos)
