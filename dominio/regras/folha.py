from __future__ import annotations

from dominio.apontamento import Apontamento, Severidade
from dominio.modelos import Contexto
from dominio.regras.base import Regra


def _houve_folha(ctx: Contexto) -> bool:
    if ctx.houve_folha_override is not None:
        return ctx.houve_folha_override
    cfg = ctx.config.get("folha", {})
    conta_gatilho = cfg.get("conta_gatilho", 331)
    conta = ctx.balancete.por_codigo(conta_gatilho)
    return conta is not None and conta.tem_movimento


class P6FolhaIntegralizacao(Regra):
    id = "P6.FOLHA_INTEGRALIZACAO"
    ordem = 20
    severidade_padrao = Severidade.ALERTA

    def avaliar(self, ctx: Contexto) -> list[Apontamento]:
        if not _houve_folha(ctx):
            return []

        cfg = ctx.config.get("folha", {})
        resultados: list[Apontamento] = []
        for item in cfg.get("contas_integralizacao", []):
            codigo = item["codigo"]
            descricao = item["descricao"]
            conta = ctx.balancete.por_codigo(codigo)
            if conta is None or conta.credito == 0:
                resultados.append(Apontamento(
                    regra=self.id, severidade=Severidade.ALERTA,
                    descricao=f"{descricao} (conta {codigo}): sem crédito no período",
                    valor_contabil=conta.credito if conta else None,
                    coluna_esperada="CREDITO",
                    origem_balancete=conta.referencia if conta else None,
                ))
            else:
                resultados.append(Apontamento(
                    regra=self.id, severidade=Severidade.OK,
                    descricao=f"{descricao} (conta {codigo}): integralizado",
                    valor_contabil=conta.credito,
                    coluna_esperada="CREDITO", coluna_encontrada="CREDITO",
                    origem_balancete=conta.referencia,
                ))
        return resultados


class P7FolhaPagamento(Regra):
    id = "P7.FOLHA_PAGAMENTO"
    ordem = 21
    severidade_padrao = Severidade.CRITICO

    def avaliar(self, ctx: Contexto) -> list[Apontamento]:
        if not _houve_folha(ctx):
            return []

        cfg = ctx.config.get("folha", {})
        contas_pagamento = cfg.get("contas_pagamento", [178, 187, 191, 192])
        resultados: list[Apontamento] = []
        for codigo in contas_pagamento:
            conta = ctx.balancete.por_codigo(codigo)
            if conta is None:
                continue
            esperado = conta.saldo_anterior.valor
            pago = conta.debito
            diferenca = esperado - pago
            if pago == esperado:
                resultados.append(Apontamento(
                    regra=self.id, severidade=Severidade.OK,
                    descricao=f"Conta {codigo} ({conta.descricao}): pagamento confere",
                    valor_contabil=pago, diferenca=diferenca,
                    coluna_esperada="DEBITO", coluna_encontrada="DEBITO",
                    origem_balancete=conta.referencia,
                ))
            else:
                resultados.append(Apontamento(
                    regra=self.id, severidade=Severidade.CRITICO,
                    descricao=(
                        f"Conta {codigo} ({conta.descricao}): pagamento divergente "
                        f"— saldo anterior {esperado}, débito {pago}"
                    ),
                    valor_contabil=pago, diferenca=diferenca,
                    coluna_esperada="DEBITO", coluna_encontrada="DEBITO",
                    origem_balancete=conta.referencia,
                ))
        return resultados
