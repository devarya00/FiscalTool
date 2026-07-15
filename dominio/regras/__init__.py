from __future__ import annotations

from dominio.regras.base import Regra
from dominio.regras.cabecalho import P1CNPJ, P1Periodo
from dominio.regras.estrutural import P2Natureza
from dominio.regras.amarracao import (
    P3Servico, P4Tomados, P4Combustivel, P4Consumo, P4Revenda, P5Venda,
)
from dominio.regras.grupos import P4GrupoAmarracao
from dominio.regras.folha import P6FolhaIntegralizacao, P7FolhaPagamento
from dominio.regras.tributos import P7Simples
from dominio.regras.consistencia import P7ReceitaCusto
from dominio.regras.depreciacao import P8Depreciacao
from dominio.regras.orfaos import P6Orfaos


def todas_as_regras() -> list[Regra]:
    """Conjunto default de regras, na ordem de cadastro (o motor reordena por .ordem)."""
    return [
        P1CNPJ(), P1Periodo(),
        P2Natureza(),
        P3Servico(), P4Tomados(), P4Combustivel(), P4Consumo(), P4Revenda(), P5Venda(),
        P4GrupoAmarracao(),
        P6FolhaIntegralizacao(), P7FolhaPagamento(),
        P7Simples(),
        P7ReceitaCusto(),
        P8Depreciacao(),
        P6Orfaos(),
    ]
