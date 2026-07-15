"""Amarração N-para-N via configuração (regras.yaml: grupos_amarracao).

Generaliza P3/P4/P5 (amarracao.py, sempre 1 padrão fiscal -> 1 conta) para o
caso em que vários códigos fiscais precisam ser somados e comparados contra a
soma de várias contas contábeis — ou, no modo "busca_valor", contra QUALQUER
conta dentro de um intervalo (ex.: Imobilizado, onde não se sabe de antemão
em qual conta a aquisição foi lançada).

Vínculos aprendidos pela UI (persistidos por CNPJ — ver Repositorio) entram
aqui como entradas extras da mesma lista, mescladas em tempo de execução por
ConferenciaService — nenhum código novo é necessário para "lembrar" o cliente
mês a mês.
"""
from __future__ import annotations

from decimal import Decimal

from dominio.apontamento import Apontamento, Severidade
from dominio.modelos import Acumulador, ContaBalancete, Contexto
from dominio.regras.base import Regra
from dominio.regras._util import contem, ignorado, tolerancia


def _casa_grupo(ac: Acumulador, codigos: set[str], padroes: list[str]) -> bool:
    if ac.codigo in codigos:
        return True
    return any(contem(ac.descricao, p) for p in padroes)


def _somar_fiscal(ctx: Contexto, cfg: dict) -> tuple[Decimal, list[Acumulador]]:
    codigos = {str(c) for c in cfg.get("codigos_fiscais", [])}
    padroes = cfg.get("padroes_fiscais", [])
    total = Decimal("0")
    casados: list[Acumulador] = []
    for ac in ctx.fiscal.todos():
        if ctx.foi_consumido(ac) or ignorado(ac, ctx):
            continue
        if not _casa_grupo(ac, codigos, padroes):
            continue
        total += ac.valor_contabil
        casados.append(ac)
    return total, casados


def _valor_coluna(conta: ContaBalancete, coluna: str) -> Decimal:
    return conta.credito if coluna == "CREDITO" else conta.debito


class P4GrupoAmarracao(Regra):
    """Uma instância, N grupos configurados — cada grupo produz seu próprio
    apontamento (regra = grupo["id"])."""
    id = "P4.GRUPO"
    ordem = 16  # depois de P3-P5 individuais (10-15), antes de Folha (20+)
    severidade_padrao = Severidade.CRITICO

    def avaliar(self, ctx: Contexto) -> list[Apontamento]:
        grupos = ctx.config.get("grupos_amarracao", [])
        resultados: list[Apontamento] = []
        for cfg in grupos:
            resultados.extend(self._avaliar_grupo(ctx, cfg))
        return resultados

    def _avaliar_grupo(self, ctx: Contexto, cfg: dict) -> list[Apontamento]:
        grupo_id = cfg.get("id", "G.GRUPO")
        descricao = cfg.get("descricao", grupo_id)
        coluna = cfg.get("coluna", "DEBITO")
        modo = cfg.get("modo", "soma")

        total_fiscal, casados = _somar_fiscal(ctx, cfg)
        for ac in casados:
            ctx.marcar_consumido(ac)

        if modo == "busca_valor":
            return self._avaliar_busca_valor(ctx, cfg, grupo_id, descricao, coluna, total_fiscal)
        return self._avaliar_soma(ctx, cfg, grupo_id, descricao, coluna, total_fiscal)

    @staticmethod
    def _avaliar_soma(
        ctx: Contexto, cfg: dict, grupo_id: str, descricao: str, coluna: str, total_fiscal: Decimal,
    ) -> list[Apontamento]:
        codigos_contas = cfg.get("contas_contabeis", [])
        contas = [ctx.balancete.por_codigo(c) for c in codigos_contas]
        faltantes = [str(codigos_contas[i]) for i, c in enumerate(contas) if c is None]
        encontradas = [c for c in contas if c is not None]

        if not encontradas:
            if total_fiscal == 0:
                return []  # sem valor fiscal e sem contas: N/A, não é erro
            return [Apontamento(
                regra=grupo_id, severidade=Severidade.CRITICO,
                descricao=f"{descricao}: conta(s) {', '.join(faltantes)} não encontrada(s) no Balancete",
                valor_fiscal=total_fiscal, coluna_esperada=coluna,
            )]

        total_contabil = sum((_valor_coluna(c, coluna) for c in encontradas), Decimal("0"))
        diff = total_fiscal - total_contabil
        tol = tolerancia(ctx)

        if abs(diff) <= tol:
            severidade, texto = Severidade.OK, f"{descricao}: soma confere"
        else:
            severidade, texto = Severidade.CRITICO, f"{descricao}: divergência de valor"
        if faltantes:
            texto += f" (conta(s) {', '.join(faltantes)} não encontrada(s) — soma parcial)"
            severidade = Severidade.CRITICO

        return [Apontamento(
            regra=grupo_id, severidade=severidade, descricao=texto,
            valor_fiscal=total_fiscal, valor_contabil=total_contabil, diferenca=diff,
            coluna_esperada=coluna, coluna_encontrada=coluna if not faltantes else None,
        )]

    @staticmethod
    def _avaliar_busca_valor(
        ctx: Contexto, cfg: dict, grupo_id: str, descricao: str, coluna: str, total_fiscal: Decimal,
    ) -> list[Apontamento]:
        if total_fiscal == 0:
            return []  # nada fiscal no grupo neste período: N/A
        ini, fim = cfg.get("escopo_contas", [0, 0])
        tol = tolerancia(ctx)
        candidatas = ctx.balancete.no_intervalo(ini, fim)
        encontrada = next(
            (c for c in candidatas if abs(_valor_coluna(c, coluna) - total_fiscal) <= tol), None,
        )
        if encontrada is not None:
            return [Apontamento(
                regra=grupo_id, severidade=Severidade.OK,
                descricao=f"{descricao}: confere com a conta {encontrada.codigo} ({encontrada.descricao})",
                valor_fiscal=total_fiscal, valor_contabil=_valor_coluna(encontrada, coluna),
                coluna_esperada=coluna, coluna_encontrada=coluna,
                origem_balancete=encontrada.referencia,
            )]
        return [Apontamento(
            regra=grupo_id, severidade=Severidade.CRITICO,
            descricao=(
                f"{descricao}: nenhuma conta no intervalo [{ini}-{fim}] tem "
                f"{coluna.lower()} igual ao valor fiscal"
            ),
            valor_fiscal=total_fiscal, coluna_esperada=coluna,
        )]
