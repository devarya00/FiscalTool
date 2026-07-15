"""CLI da conciliação em lote multi-CNPJ (Fiscal x Contábil via Excel).

Uso:
    python conciliar_lote.py fiscal.xlsx contabil.xlsx [-o relatorio_conferencia.xlsx]
"""
from __future__ import annotations

import argparse
import sys

from aplicacao.conciliacao_lote import conciliar_lote


def main() -> int:
    parser = argparse.ArgumentParser(description="Conciliação em lote Fiscal x Contábil, multi-CNPJ.")
    parser.add_argument("fiscal", help="Excel com os acumuladores fiscais (mensal, todas as empresas).")
    parser.add_argument("contabil", help="Excel com as contas contábeis (anual, todas as empresas).")
    parser.add_argument(
        "-o", "--saida", default="relatorio_conferencia.xlsx",
        help="Caminho do Excel de saída (default: relatorio_conferencia.xlsx).",
    )
    args = parser.parse_args()

    resumos = conciliar_lote(args.fiscal, args.contabil, args.saida)
    divergentes = sum(1 for r in resumos if r.status == "DIVERGENTE")
    print(f"{len(resumos)} CNPJ(s) processado(s) — {divergentes} divergente(s). Relatório: {args.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
