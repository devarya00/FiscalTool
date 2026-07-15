"""Persistência SQLite local — histórico de conferências por CNPJ/período e
vínculos de amarração aprendidos por cliente (grupos_amarracao configurados
via UI em vez de regras.yaml).

Depende só do domínio (Apontamento, Periodo), nunca da camada de aplicação —
mantém a regra de dependência da arquitetura (infra não conhece camadas acima).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from decimal import Decimal

from dominio.apontamento import Apontamento, Severidade
from dominio.modelos import Periodo, Referencia

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conferencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cnpj TEXT NOT NULL,
    periodo_inicio TEXT NOT NULL,
    periodo_fim TEXT NOT NULL,
    executado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS apontamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conferencia_id INTEGER NOT NULL REFERENCES conferencias(id) ON DELETE CASCADE,
    regra TEXT NOT NULL,
    severidade TEXT NOT NULL,
    descricao TEXT NOT NULL,
    valor_fiscal TEXT,
    valor_contabil TEXT,
    diferenca TEXT,
    coluna_esperada TEXT,
    coluna_encontrada TEXT,
    origem_fiscal_pagina INTEGER,
    origem_fiscal_linha INTEGER,
    origem_balancete_pagina INTEGER,
    origem_balancete_linha INTEGER
);

CREATE INDEX IF NOT EXISTS idx_conferencias_cnpj ON conferencias(cnpj);

CREATE TABLE IF NOT EXISTS vinculos_acumulador (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cnpj TEXT NOT NULL,
    codigo_acumulador TEXT NOT NULL,
    descricao TEXT,
    contas_contabeis TEXT NOT NULL,  -- JSON: lista de códigos de conta (int)
    coluna TEXT NOT NULL,            -- "DEBITO" | "CREDITO"
    criado_em TEXT NOT NULL,
    UNIQUE(cnpj, codigo_acumulador)
);
"""


class Repositorio:
    def __init__(self, caminho_db: str):
        self._conn = sqlite3.connect(caminho_db)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def salvar(self, cnpj: str, periodo: Periodo, apontamentos: list[Apontamento]) -> int:
        cur = self._conn.execute(
            "INSERT INTO conferencias (cnpj, periodo_inicio, periodo_fim, executado_em) "
            "VALUES (?, ?, ?, ?)",
            (cnpj, periodo.inicio.isoformat(), periodo.fim.isoformat(), datetime.now().isoformat()),
        )
        conferencia_id = cur.lastrowid
        self._conn.executemany(
            "INSERT INTO apontamentos ("
            "conferencia_id, regra, severidade, descricao, valor_fiscal, valor_contabil, "
            "diferenca, coluna_esperada, coluna_encontrada, "
            "origem_fiscal_pagina, origem_fiscal_linha, origem_balancete_pagina, origem_balancete_linha"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    conferencia_id, ap.regra, ap.severidade.value, ap.descricao,
                    str(ap.valor_fiscal) if ap.valor_fiscal is not None else None,
                    str(ap.valor_contabil) if ap.valor_contabil is not None else None,
                    str(ap.diferenca) if ap.diferenca is not None else None,
                    ap.coluna_esperada, ap.coluna_encontrada,
                    ap.origem_fiscal.pagina if ap.origem_fiscal else None,
                    ap.origem_fiscal.linha if ap.origem_fiscal else None,
                    ap.origem_balancete.pagina if ap.origem_balancete else None,
                    ap.origem_balancete.linha if ap.origem_balancete else None,
                )
                for ap in apontamentos
            ],
        )
        self._conn.commit()
        return conferencia_id

    def salvar_vinculo(
        self, cnpj: str, codigo_acumulador: str, contas_contabeis: list[int],
        coluna: str, descricao: str = "",
    ) -> None:
        """Aprende (ou atualiza) o vínculo de um acumulador órfão para este
        cliente — reaproveitado automaticamente nas próximas conferências
        (ver ConferenciaService), sem precisar editar regras.yaml."""
        self._conn.execute(
            "INSERT INTO vinculos_acumulador "
            "(cnpj, codigo_acumulador, descricao, contas_contabeis, coluna, criado_em) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(cnpj, codigo_acumulador) DO UPDATE SET "
            "descricao=excluded.descricao, contas_contabeis=excluded.contas_contabeis, "
            "coluna=excluded.coluna, criado_em=excluded.criado_em",
            (
                cnpj, codigo_acumulador, descricao, json.dumps(contas_contabeis),
                coluna, datetime.now().isoformat(),
            ),
        )
        self._conn.commit()

    def vinculos_do_cliente(self, cnpj: str) -> list[dict]:
        """Vínculos aprendidos no formato de entrada de config/regras.yaml
        (grupos_amarracao) — ConferenciaService só precisa concatenar na lista
        vinda do YAML, o motor de regras (P4.GRUPO) não distingue a origem."""
        linhas = self._conn.execute(
            "SELECT codigo_acumulador, descricao, contas_contabeis, coluna "
            "FROM vinculos_acumulador WHERE cnpj = ?",
            (cnpj,),
        ).fetchall()
        return [
            {
                "id": f"G.VINCULO.{linha['codigo_acumulador']}",
                "descricao": linha["descricao"] or f"Vínculo aprendido — AC {linha['codigo_acumulador']}",
                "codigos_fiscais": [linha["codigo_acumulador"]],
                "contas_contabeis": json.loads(linha["contas_contabeis"]),
                "coluna": linha["coluna"],
                "modo": "soma",
            }
            for linha in linhas
        ]

    def historico(self, cnpj: str) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM conferencias WHERE cnpj = ? ORDER BY executado_em DESC", (cnpj,)
        ).fetchall()

    def apontamentos_de(self, conferencia_id: int) -> list[Apontamento]:
        linhas = self._conn.execute(
            "SELECT * FROM apontamentos WHERE conferencia_id = ?", (conferencia_id,)
        ).fetchall()
        return [self._linha_para_apontamento(linha) for linha in linhas]

    @staticmethod
    def _linha_para_apontamento(linha: sqlite3.Row) -> Apontamento:
        def dec(campo: str) -> Decimal | None:
            valor = linha[campo]
            return Decimal(valor) if valor is not None else None

        origem_fiscal = None
        if linha["origem_fiscal_pagina"] is not None:
            origem_fiscal = Referencia(linha["origem_fiscal_pagina"], linha["origem_fiscal_linha"])
        origem_balancete = None
        if linha["origem_balancete_pagina"] is not None:
            origem_balancete = Referencia(linha["origem_balancete_pagina"], linha["origem_balancete_linha"])

        return Apontamento(
            regra=linha["regra"], severidade=Severidade(linha["severidade"]), descricao=linha["descricao"],
            valor_fiscal=dec("valor_fiscal"), valor_contabil=dec("valor_contabil"), diferenca=dec("diferenca"),
            coluna_esperada=linha["coluna_esperada"], coluna_encontrada=linha["coluna_encontrada"],
            origem_fiscal=origem_fiscal, origem_balancete=origem_balancete,
        )
