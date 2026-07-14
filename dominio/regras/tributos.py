from __future__ import annotations

from dominio.apontamento import Apontamento, Severidade
from dominio.modelos import Contexto
from dominio.regras.base import Regra


class P7Simples(Regra):
    """Conta do Simples Nacional: demonstra integralização (crédito) e pagamento
    (débito) — não é uma comparação fiscal×contábil, é auditoria de fluxo."""
    id = "P7.SIMPLES"
    ordem = 22
    severidade_padrao = Severidade.ALERTA

    def avaliar(self, ctx: Contexto) -> list[Apontamento]:
        cfg = ctx.config.get("tributos", {}).get("simples_nacional", {})
        codigo = cfg.get("conta", 479)
        conta = ctx.balancete.por_codigo(codigo)
        if conta is None:
            return []

        integralizado = conta.credito != 0
        pago = conta.debito != 0

        if not integralizado:
            return [Apontamento(
                regra=self.id, severidade=Severidade.OK,
                descricao=f"Simples Nacional (conta {codigo}): sem integralização no período",
                origem_balancete=conta.referencia,
            )]

        if pago:
            return [Apontamento(
                regra=self.id, severidade=Severidade.OK,
                descricao=(
                    f"Simples Nacional (conta {codigo}): integralizado "
                    f"{conta.credito} e pago {conta.debito}"
                ),
                valor_contabil=conta.debito,
                origem_balancete=conta.referencia,
            )]

        return [Apontamento(
            regra=self.id, severidade=Severidade.ALERTA,
            descricao=(
                f"Simples Nacional (conta {codigo}): integralizado "
                f"{conta.credito} e não pago (débito 0,00)"
            ),
            valor_contabil=conta.credito,
            origem_balancete=conta.referencia,
        )]
