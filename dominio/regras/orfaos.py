from __future__ import annotations

from dominio.apontamento import Apontamento, Severidade
from dominio.modelos import Contexto
from dominio.regras.base import Regra
from dominio.regras._util import contem


class P6Orfaos(Regra):
    """Roda por último: reporta acumuladores não consumidos por nenhuma regra
    de amarração e não filtrados pelo padrão 'outras'."""
    id = "P6.ORFAOS"
    ordem = 30
    severidade_padrao = Severidade.ALERTA

    def avaliar(self, ctx: Contexto) -> list[Apontamento]:
        padroes_ignorar = ctx.config.get("amarracao", {}).get("filtro_ignorar", ["outras"])
        resultados: list[Apontamento] = []
        for ac in ctx.fiscal.todos():
            if ctx.foi_consumido(ac):
                continue
            if any(contem(ac.descricao, p) for p in padroes_ignorar):
                continue
            resultados.append(Apontamento(
                regra=self.id, severidade=Severidade.ALERTA,
                descricao=(
                    f"AC {ac.codigo} Não encontrado — {ac.descricao} "
                    f"(seção {ac.secao.value}), sem vínculo contábil configurado"
                ),
                valor_fiscal=ac.valor_contabil,
                origem_fiscal=ac.referencia,
            ))
        return resultados
