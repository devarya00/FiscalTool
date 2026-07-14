from __future__ import annotations

from abc import ABC, abstractmethod

from dominio.apontamento import Apontamento, Severidade
from dominio.modelos import Contexto


class Regra(ABC):
    id: str
    ordem: int
    severidade_padrao: Severidade

    @abstractmethod
    def avaliar(self, ctx: Contexto) -> list[Apontamento]:
        ...
