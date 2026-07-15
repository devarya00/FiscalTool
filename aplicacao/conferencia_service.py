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
from infra.repositorio import Repositorio

_CONFIG_PADRAO = Path(__file__).resolve().parent.parent / "config" / "regras.yaml"
_DB_PADRAO = Path(__file__).resolve().parent.parent / "data" / "fiscaltool.db"


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
        return self.por_regra_prefixo("P0.", "P1.")

    def estrutural(self) -> list[Apontamento]:
        return self.por_regra_prefixo("P2.", "P8.")

    def amarracao(self) -> list[Apontamento]:
        return self.por_regra_prefixo("P3.", "P4.", "P5.", "G.")

    def fluxo_de_caixa(self) -> list[Apontamento]:
        return self.por_regra_prefixo("P6.FOLHA_INTEGRALIZACAO", "P7.")

    def orfaos(self) -> list[Apontamento]:
        return self.por_regra_prefixo("P6.ORFAOS")


class ConferenciaService:
    def __init__(self, config_path: str | Path = _CONFIG_PADRAO, db_path: str | Path = _DB_PADRAO):
        with open(config_path, encoding="utf-8") as f:
            self._config: dict[str, Any] = yaml.safe_load(f)
        self._fiscal_parser = FiscalParser()
        self._balancete_parser = BalanceteParser(self._config.get("ia_fallback"))
        self._motor = MotorRegras(todas_as_regras())

        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._repositorio = Repositorio(str(db_path))

    def executar(
        self, pdf_fiscal: str, pdf_balancete: str, houve_folha_override: bool | None = None,
    ) -> ResultadoConferencia:
        fiscal = self._fiscal_parser.parse(pdf_fiscal)
        balancete = self._balancete_parser.parse(pdf_balancete)

        config = self._config_com_vinculos_aprendidos(fiscal.cnpj)
        ctx = Contexto(
            fiscal=fiscal, balancete=balancete, config=config,
            houve_folha_override=houve_folha_override,
        )
        apontamentos = self._motor.executar(ctx)

        if balancete.parsing_incerto:
            apontamentos = [Apontamento(
                regra="P0.PARSING", severidade=Severidade.ALERTA,
                descricao=(
                    "Parsing incerto — conferir manualmente. O parser posicional não se "
                    "validou e o fallback de IA (se ativo) também não confirmou o resultado."
                ),
            ), *apontamentos]

        return ResultadoConferencia(fiscal=fiscal, balancete=balancete, apontamentos=apontamentos)

    def _config_com_vinculos_aprendidos(self, cnpj: str) -> dict[str, Any]:
        """Mescla vínculos aprendidos (aprendidos via configurar_vinculo, por
        CNPJ) na lista de grupos_amarracao do YAML — cópia rasa, não muta o
        config compartilhado entre execuções."""
        vinculos = self._repositorio.vinculos_do_cliente(cnpj)
        if not vinculos:
            return self._config
        config = dict(self._config)
        config["grupos_amarracao"] = [*config.get("grupos_amarracao", []), *vinculos]
        return config

    def configurar_vinculo(
        self, cnpj: str, codigo_acumulador: str, contas_contabeis: list[int],
        coluna: str = "DEBITO", descricao: str = "",
    ) -> None:
        """Aprende o vínculo de um acumulador órfão para este cliente — a
        próxima conferência já entra sem precisar reconfigurar."""
        self._repositorio.salvar_vinculo(cnpj, codigo_acumulador, contas_contabeis, coluna, descricao)
