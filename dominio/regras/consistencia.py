from __future__ import annotations

from dominio.apontamento import Apontamento, Severidade
from dominio.modelos import Contexto
from dominio.regras.base import Regra


class P7ReceitaCusto(Regra):
    """Receita reconhecida (bloco [402,412]) exige contrapartida de custo/despesa.

    Intervalo de custo default [292, 500]: inclui a conta 292 (Combustível),
    decisão tomada porque a leitura literal do texto original ("entre 500 e 295")
    excluiria o único custo real observado nos exemplos. Ajustável em regras.yaml.

    [292,500] engloba [402,412] (a própria faixa de receita) — por isso as
    contas de receita são excluídas da checagem de custo, senão a receita
    validaria a si mesma como sua própria contrapartida.
    """
    id = "P7.RECEITA_CUSTO"
    ordem = 23
    severidade_padrao = Severidade.CRITICO

    def avaliar(self, ctx: Contexto) -> list[Apontamento]:
        cfg = ctx.config.get("consistencia", {}).get("receita_custo", {})
        ini_r, fim_r = cfg.get("intervalo_receita", [402, 412])
        ini_c, fim_c = cfg.get("intervalo_custo", [292, 500])

        receita = any(c.tem_movimento for c in ctx.balancete.no_intervalo(ini_r, fim_r))
        custo = any(
            c.tem_movimento for c in ctx.balancete.no_intervalo(ini_c, fim_c)
            if not (ini_r <= c.codigo <= fim_r)
        )

        if receita and not custo:
            return [Apontamento(
                regra=self.id, severidade=Severidade.CRITICO,
                descricao="Receita reconhecida sem contrapartida de custo/despesa",
            )]
        return [Apontamento(
            regra=self.id, severidade=Severidade.OK,
            descricao="Consistência Receita × Custo confere",
        )]
