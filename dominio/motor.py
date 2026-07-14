from __future__ import annotations

from dominio.apontamento import Apontamento, Severidade
from dominio.modelos import Contexto
from dominio.regras.base import Regra


class MotorRegras:
    def __init__(self, regras: list[Regra]):
        self.regras = regras

    def executar(self, ctx: Contexto) -> list[Apontamento]:
        resultados: list[Apontamento] = []
        for regra in sorted(self.regras, key=lambda r: r.ordem):
            aps = regra.avaliar(ctx)
            resultados.extend(aps)
            if any(a.severidade is Severidade.IMPEDITIVO for a in aps):
                break  # fail-fast: Passos 1 e 2
        return resultados
