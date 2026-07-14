from __future__ import annotations

from dominio.apontamento import Apontamento, Severidade
from dominio.modelos import Contexto, Grupo, Natureza
from dominio.regras.base import Regra

_ESPERADO = {Grupo.ATIVO: Natureza.DEVEDOR, Grupo.PASSIVO: Natureza.CREDOR}


class P2Natureza(Regra):
    """Toda conta ATIVO deve fechar D, toda conta PASSIVO deve fechar C.

    Severidade configurável (regras.yaml: severidade_natureza_invertida) — default
    CRITICO, não IMPEDITIVO: caixa credor é comum no dia a dia e não deve travar
    a conferência inteira.
    """
    id = "P2.NATUREZA"
    ordem = 3
    severidade_padrao = Severidade.CRITICO

    def avaliar(self, ctx: Contexto) -> list[Apontamento]:
        severidade_cfg = ctx.config.get("severidade_natureza_invertida", "critico")
        severidade = Severidade.IMPEDITIVO if severidade_cfg == "impeditivo" else Severidade.CRITICO

        resultados: list[Apontamento] = []
        for conta in ctx.balancete.contas:
            esperado = _ESPERADO.get(conta.grupo)
            if esperado is None:
                continue
            natureza_atual = conta.saldo_atual.natureza
            if natureza_atual == esperado:
                continue
            resultados.append(Apontamento(
                regra=self.id,
                severidade=severidade,
                descricao=(
                    f"Conta {conta.codigo} ({conta.descricao}) grupo {conta.grupo.value} "
                    f"com Saldo Atual {natureza_atual.value if natureza_atual else '?'} "
                    f"— esperado {esperado.value}"
                ),
                valor_contabil=conta.saldo_atual.valor,
                origem_balancete=conta.referencia,
            ))
        if not resultados:
            resultados.append(Apontamento(
                regra=self.id, severidade=Severidade.OK,
                descricao="Natureza de todos os saldos ATIVO/PASSIVO confere",
            ))
        return resultados
