"""Modelos de domínio — dataclasses imutáveis, sem I/O."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any


class Secao(Enum):
    ENTRADAS = "entradas"
    SAIDAS = "saidas"
    SERVICOS = "servicos"


class Grupo(Enum):
    ATIVO = "ativo"
    PASSIVO = "passivo"
    PL = "pl"
    RESULTADO = "resultado"


class Natureza(Enum):
    DEVEDOR = "D"
    CREDOR = "C"


@dataclass(frozen=True)
class Periodo:
    inicio: date
    fim: date


@dataclass(frozen=True)
class Saldo:
    valor: Decimal
    natureza: Natureza | None


@dataclass(frozen=True)
class Referencia:
    pagina: int
    linha: int


@dataclass(frozen=True)
class Acumulador:
    codigo: str
    descricao: str
    valor_contabil: Decimal
    secao: Secao
    pagina: int
    linha: int

    @property
    def referencia(self) -> Referencia:
        return Referencia(self.pagina, self.linha)


@dataclass(frozen=True)
class RelatorioFiscal:
    cnpj: str
    periodo: Periodo
    entradas: list[Acumulador]
    saidas: list[Acumulador]
    servicos: list[Acumulador]
    total_servicos: Decimal | None = None

    def todos(self) -> list[Acumulador]:
        return [*self.entradas, *self.saidas, *self.servicos]


@dataclass(frozen=True)
class ContaBalancete:
    codigo: int
    descricao: str
    grupo: Grupo
    saldo_anterior: Saldo
    debito: Decimal
    credito: Decimal
    saldo_atual: Saldo
    pagina: int
    linha: int

    @property
    def referencia(self) -> Referencia:
        return Referencia(self.pagina, self.linha)

    @property
    def tem_movimento(self) -> bool:
        return self.debito != 0 or self.credito != 0


@dataclass(frozen=True)
class Balancete:
    cnpj: str
    periodo: Periodo
    contas: list[ContaBalancete]

    def por_codigo(self, cod: int) -> ContaBalancete | None:
        for conta in self.contas:
            if conta.codigo == cod:
                return conta
        return None

    def no_intervalo(self, ini: int, fim: int) -> list[ContaBalancete]:
        lo, hi = min(ini, fim), max(ini, fim)
        return [c for c in self.contas if lo <= c.codigo <= hi]


@dataclass
class Contexto:
    """Estado passado a cada regra durante a execução do motor."""
    fiscal: RelatorioFiscal
    balancete: Balancete
    config: dict[str, Any]
    houve_folha_override: bool | None = None  # override manual da tela de upload
    acumuladores_consumidos: set[tuple[Secao, str, int]] = field(default_factory=set)

    def marcar_consumido(self, ac: Acumulador) -> None:
        self.acumuladores_consumidos.add((ac.secao, ac.codigo, ac.linha))

    def foi_consumido(self, ac: Acumulador) -> bool:
        return (ac.secao, ac.codigo, ac.linha) in self.acumuladores_consumidos
