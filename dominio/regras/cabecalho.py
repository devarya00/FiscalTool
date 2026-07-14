from __future__ import annotations

from dominio.apontamento import Apontamento, Severidade
from dominio.modelos import Contexto
from dominio.regras.base import Regra


class P1CNPJ(Regra):
    id = "P1.CNPJ"
    ordem = 1
    severidade_padrao = Severidade.IMPEDITIVO

    def avaliar(self, ctx: Contexto) -> list[Apontamento]:
        fiscal_cnpj = ctx.fiscal.cnpj
        balancete_cnpj = ctx.balancete.cnpj
        if fiscal_cnpj == balancete_cnpj:
            return [Apontamento(
                regra=self.id, severidade=Severidade.OK,
                descricao=f"CNPJ confere: {fiscal_cnpj}",
            )]
        return [Apontamento(
            regra=self.id, severidade=Severidade.IMPEDITIVO,
            descricao=(
                f"CNPJ divergente: Fiscal={fiscal_cnpj} × Balancete={balancete_cnpj}"
            ),
        )]


class P1Periodo(Regra):
    id = "P1.PERIODO"
    ordem = 2
    severidade_padrao = Severidade.IMPEDITIVO

    def avaliar(self, ctx: Contexto) -> list[Apontamento]:
        p_fiscal = ctx.fiscal.periodo
        p_balancete = ctx.balancete.periodo
        if p_fiscal == p_balancete:
            return [Apontamento(
                regra=self.id, severidade=Severidade.OK,
                descricao=f"Período confere: {p_fiscal.inicio:%d/%m/%Y} a {p_fiscal.fim:%d/%m/%Y}",
            )]
        return [Apontamento(
            regra=self.id, severidade=Severidade.IMPEDITIVO,
            descricao=(
                f"Período divergente: Fiscal={p_fiscal.inicio:%d/%m/%Y}-{p_fiscal.fim:%d/%m/%Y} "
                f"× Balancete={p_balancete.inicio:%d/%m/%Y}-{p_balancete.fim:%d/%m/%Y}"
            ),
        )]
