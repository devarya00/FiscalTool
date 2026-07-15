from __future__ import annotations

from decimal import Decimal

from dominio.apontamento import Apontamento, Severidade
from dominio.modelos import Acumulador, Contexto, ContaBalancete
from dominio.regras.base import Regra
from dominio.regras._util import contem, ignorado, tolerancia as _tolerancia


def _localizar_conta(ctx: Contexto, codigo_conta: int, padrao_balancete: str) -> ContaBalancete | None:
    """Código exato primeiro; se não bater (numeração de plano de contas varia por
    cliente), cai para substring normalizado na descrição. padrao_balancete deve ser
    uma raiz curta (ex.: "combust"), não o rótulo completo — "Combustível" (singular)
    não é substring de "COMBUSTÍVEIS E ENERGIA ELÉTRICA" (plural irregular -vel/-veis
    não é sufixo simples), mas "combust" casa com ambos. Sem isso, conta que existe
    vira falso "não encontrada"."""
    conta = ctx.balancete.por_codigo(codigo_conta)
    if conta is not None:
        return conta
    return next((c for c in ctx.balancete.contas if contem(c.descricao, padrao_balancete)), None)


def _somar_por_padrao(
    acumuladores: list[Acumulador], padrao: str, ctx: Contexto,
    excluir: str | None = None,
) -> tuple[Decimal, list[Acumulador]]:
    total = Decimal("0")
    casados: list[Acumulador] = []
    for ac in acumuladores:
        if ctx.foi_consumido(ac) or ignorado(ac, ctx):
            continue
        if not contem(ac.descricao, padrao):
            continue
        if excluir and contem(ac.descricao, excluir):
            continue
        total += ac.valor_contabil
        casados.append(ac)
    return total, casados


def _comparar(
    *, regra_id: str, valor_fiscal: Decimal, conta: ContaBalancete | None,
    coluna_esperada: str, ctx: Contexto, descricao_conta: str,
    origem_fiscal_ref=None,
) -> Apontamento | None:
    tolerancia = _tolerancia(ctx)

    if conta is None:
        if valor_fiscal == 0:
            return None  # sem valor fiscal e sem conta: N/A (não é erro)
        return Apontamento(
            regra=regra_id, severidade=Severidade.CRITICO,
            descricao=f"Conta '{descricao_conta}' não encontrada no Balancete",
            valor_fiscal=valor_fiscal, coluna_esperada=coluna_esperada,
            origem_fiscal=origem_fiscal_ref,
        )

    esperado_valor = conta.credito if coluna_esperada == "CREDITO" else conta.debito
    oposto_valor = conta.debito if coluna_esperada == "CREDITO" else conta.credito
    coluna_oposta = "DEBITO" if coluna_esperada == "CREDITO" else "CREDITO"

    diff = valor_fiscal - esperado_valor
    if abs(diff) <= tolerancia:
        return Apontamento(
            regra=regra_id, severidade=Severidade.OK,
            descricao=f"{descricao_conta} (conta {conta.codigo}) confere",
            valor_fiscal=valor_fiscal, valor_contabil=esperado_valor, diferenca=diff,
            coluna_esperada=coluna_esperada, coluna_encontrada=coluna_esperada,
            origem_fiscal=origem_fiscal_ref, origem_balancete=conta.referencia,
        )

    diff_oposto = valor_fiscal - oposto_valor
    if abs(diff_oposto) <= tolerancia:
        return Apontamento(
            regra=regra_id, severidade=Severidade.CRITICO,
            descricao=f"{descricao_conta} (conta {conta.codigo}): valor lançado na coluna oposta",
            valor_fiscal=valor_fiscal, valor_contabil=oposto_valor, diferenca=diff_oposto,
            coluna_esperada=coluna_esperada, coluna_encontrada=coluna_oposta,
            origem_fiscal=origem_fiscal_ref, origem_balancete=conta.referencia,
        )

    return Apontamento(
        regra=regra_id, severidade=Severidade.CRITICO,
        descricao=f"{descricao_conta} (conta {conta.codigo}): divergência de valor",
        valor_fiscal=valor_fiscal, valor_contabil=esperado_valor, diferenca=diff,
        coluna_esperada=coluna_esperada, coluna_encontrada=coluna_esperada,
        origem_fiscal=origem_fiscal_ref, origem_balancete=conta.referencia,
    )


class P3Servico(Regra):
    id = "P3.SERV"
    ordem = 10
    severidade_padrao = Severidade.CRITICO

    def avaliar(self, ctx: Contexto) -> list[Apontamento]:
        cfg = ctx.config.get("amarracao", {}).get("p3_servico", {})
        padrao = cfg.get("padrao_conta_balancete", "servico prestado")
        padrao_excluir = cfg.get("padrao_excluir", "terceiros")
        valor_fiscal = ctx.fiscal.total_servicos or Decimal("0")

        conta = next(
            (c for c in ctx.balancete.contas
             if contem(c.descricao, padrao) and not contem(c.descricao, padrao_excluir)),
            None,
        )
        ap = _comparar(
            regra_id=self.id, valor_fiscal=valor_fiscal, conta=conta,
            coluna_esperada="CREDITO", ctx=ctx, descricao_conta="Serviço Prestado",
        )
        for ac in ctx.fiscal.servicos:
            ctx.marcar_consumido(ac)
        return [ap] if ap else []


class P4Tomados(Regra):
    id = "P4.TOMADOS"
    ordem = 11
    severidade_padrao = Severidade.CRITICO

    def avaliar(self, ctx: Contexto) -> list[Apontamento]:
        cfg = ctx.config.get("amarracao", {}).get("p4_tomados", {})
        padrao = cfg.get("padrao_acumulador", "servicos tomados")
        codigo_conta = cfg.get("conta_balancete", 325)
        descricao_conta = cfg.get("descricao_conta", "Serviços Prestados por Terceiros")
        padrao_balancete = cfg.get("padrao_conta_balancete", descricao_conta)

        total, casados = _somar_por_padrao(ctx.fiscal.entradas, padrao, ctx)
        for ac in casados:
            ctx.marcar_consumido(ac)

        conta = _localizar_conta(ctx, codigo_conta, padrao_balancete)
        ap = _comparar(
            regra_id=self.id, valor_fiscal=total, conta=conta,
            coluna_esperada="DEBITO", ctx=ctx, descricao_conta=descricao_conta,
        )
        return [ap] if ap else []


class P4Combustivel(Regra):
    id = "P4.COMB"
    ordem = 12
    severidade_padrao = Severidade.CRITICO

    def avaliar(self, ctx: Contexto) -> list[Apontamento]:
        cfg = ctx.config.get("amarracao", {}).get("p4_combustivel", {})
        padrao = cfg.get("padrao_acumulador", "compra de combustivel")
        codigo_conta = cfg.get("conta_balancete", 292)
        descricao_conta = cfg.get("descricao_conta", "Combustível")
        padrao_balancete = cfg.get("padrao_conta_balancete", descricao_conta)

        total, casados = _somar_por_padrao(ctx.fiscal.entradas, padrao, ctx)
        for ac in casados:
            ctx.marcar_consumido(ac)

        conta = _localizar_conta(ctx, codigo_conta, padrao_balancete)
        ap = _comparar(
            regra_id=self.id, valor_fiscal=total, conta=conta,
            coluna_esperada="DEBITO", ctx=ctx, descricao_conta=descricao_conta,
        )
        return [ap] if ap else []


class P4Consumo(Regra):
    id = "P4.CONSUMO"
    ordem = 13
    severidade_padrao = Severidade.CRITICO

    def avaliar(self, ctx: Contexto) -> list[Apontamento]:
        cfg = ctx.config.get("amarracao", {}).get("p4_consumo", {})
        padrao = cfg.get("padrao_acumulador", "uso e consumo")
        codigo_conta = cfg.get("conta_balancete", 58)
        descricao_conta = cfg.get("descricao_conta", "Outros Materiais de Consumo")
        padrao_balancete = cfg.get("padrao_conta_balancete", descricao_conta)

        total, casados = _somar_por_padrao(ctx.fiscal.entradas, padrao, ctx)
        for ac in casados:
            ctx.marcar_consumido(ac)

        conta = _localizar_conta(ctx, codigo_conta, padrao_balancete)
        ap = _comparar(
            regra_id=self.id, valor_fiscal=total, conta=conta,
            coluna_esperada="DEBITO", ctx=ctx, descricao_conta=descricao_conta,
        )
        return [ap] if ap else []


class P4Revenda(Regra):
    """Roda depois de P4.CONSUMO (ordem 14 > 13): 'uso e consumo' já foi consumido
    e não será re-contado aqui, garantindo que cada acumulador caia em exatamente
    uma regra."""
    id = "P4.REVENDA"
    ordem = 14
    severidade_padrao = Severidade.CRITICO

    def avaliar(self, ctx: Contexto) -> list[Apontamento]:
        cfg = ctx.config.get("amarracao", {}).get("p4_revenda", {})
        padrao = cfg.get("padrao_acumulador", "compra de mercadoria")
        padrao_excluir = cfg.get("padrao_excluir", "uso e consumo")
        codigo_conta = cfg.get("conta_balancete", 55)
        descricao_conta = cfg.get("descricao_conta", "Outras Mercadorias para Revenda")
        padrao_balancete = cfg.get("padrao_conta_balancete", descricao_conta)

        total, casados = _somar_por_padrao(ctx.fiscal.entradas, padrao, ctx, excluir=padrao_excluir)
        for ac in casados:
            ctx.marcar_consumido(ac)

        conta = _localizar_conta(ctx, codigo_conta, padrao_balancete)
        ap = _comparar(
            regra_id=self.id, valor_fiscal=total, conta=conta,
            coluna_esperada="DEBITO", ctx=ctx, descricao_conta=descricao_conta,
        )
        return [ap] if ap else []


class P5Venda(Regra):
    id = "P5.VENDA"
    ordem = 15
    severidade_padrao = Severidade.CRITICO

    def avaliar(self, ctx: Contexto) -> list[Apontamento]:
        cfg = ctx.config.get("amarracao", {}).get("p5_venda", {})
        padrao = cfg.get("padrao_acumulador", "venda")
        codigo_conta = cfg.get("conta_balancete", 408)
        descricao_conta = cfg.get("descricao_conta", "Venda de Mercadorias")
        padrao_balancete = cfg.get("padrao_conta_balancete", descricao_conta)

        total, casados = _somar_por_padrao(ctx.fiscal.saidas, padrao, ctx)
        for ac in casados:
            ctx.marcar_consumido(ac)

        conta = _localizar_conta(ctx, codigo_conta, padrao_balancete)
        ap = _comparar(
            regra_id=self.id, valor_fiscal=total, conta=conta,
            coluna_esperada="CREDITO", ctx=ctx, descricao_conta=descricao_conta,
        )
        return [ap] if ap else []
