"""Auditoria hierárquica de depreciação: toda conta de bem do Imobilizado com
saldo ou movimento no período deve ter uma conta de depreciação acumulada
correspondente com crédito lançado no período.

Detecção do par bem <-> retificadora por fuzzy matching (difflib, stdlib —
determinístico, sem dependência nova): compara tokens significativos e
similaridade de sequência do nome do bem (ex.: "AMAROK") contra o nome da
retificadora com o prefixo removido (ex.: "(-) DEPRECIAÇÃO AMAROK" -> "AMAROK").
"""
from __future__ import annotations

from difflib import SequenceMatcher

from dominio.apontamento import Apontamento, Severidade
from dominio.modelos import ContaBalancete, Contexto
from dominio.regras.base import Regra
from dominio.regras._util import RETIFICADORAS_PADRAO, contem, normalizar

_LIMIAR_FUZZY_PADRAO = 0.3
_TAMANHO_MINIMO_TOKEN = 4


def _tokens_significativos(txt_normalizado: str) -> set[str]:
    return {t for t in txt_normalizado.split() if len(t) >= _TAMANHO_MINIMO_TOKEN}


def _remover_prefixo_retificadora(txt_normalizado: str, padroes: list[str]) -> str:
    resultado = txt_normalizado
    for p in padroes:
        resultado = resultado.replace(normalizar(p), "")
    return resultado.strip(" -()")


def _melhor_par(
    bem: ContaBalancete, retificadoras: list[ContaBalancete], padroes: list[str], limiar: float,
) -> ContaBalancete | None:
    """Prioriza overlap de tokens (nome do bem, ex.: "amarok", literalmente
    presente no nome da retificadora) — é o sinal forte e específico. Só cai
    para similaridade de sequência (difflib) quando não há token significativo
    de nenhum dos lados; caso contrário, duas contas de nomes genéricos sem
    nenhuma palavra em comum acabam "parecidas" o suficiente por coincidência
    de letras comuns do português, gerando vínculo falso."""
    nome_bem = normalizar(bem.descricao)
    tokens_bem = _tokens_significativos(nome_bem)

    melhor: ContaBalancete | None = None
    melhor_score = 0.0
    for candidata in retificadoras:
        nome_candidata = _remover_prefixo_retificadora(normalizar(candidata.descricao), padroes)
        tokens_candidata = _tokens_significativos(nome_candidata)

        if tokens_bem and tokens_candidata:
            score = len(tokens_bem & tokens_candidata) / len(tokens_bem)
        else:
            score = SequenceMatcher(None, nome_bem, nome_candidata).ratio()

        if score > melhor_score:
            melhor_score, melhor = score, candidata

    return melhor if melhor_score >= limiar else None


class P8Depreciacao(Regra):
    id = "P8.DEPRECIACAO"
    ordem = 24  # depois de Receita×Custo (23), antes de Órfãos (30)
    severidade_padrao = Severidade.CRITICO

    def avaliar(self, ctx: Contexto) -> list[Apontamento]:
        cfg = ctx.config.get("depreciacao", {})
        ini, fim = cfg.get("escopo_contas", [0, 0])
        limiar = float(cfg.get("limiar_fuzzy", _LIMIAR_FUZZY_PADRAO))
        padroes_retificadora = ctx.config.get("natureza", {}).get("retificadoras", RETIFICADORAS_PADRAO)

        contas_escopo = ctx.balancete.no_intervalo(ini, fim)
        retificadoras = [c for c in contas_escopo if any(contem(c.descricao, p) for p in padroes_retificadora)]
        bens = [c for c in contas_escopo if c not in retificadoras]

        resultados: list[Apontamento] = []
        for bem in bens:
            tem_atividade = bem.tem_movimento or bem.saldo_atual.valor != 0
            if not tem_atividade:
                continue

            par = _melhor_par(bem, retificadoras, padroes_retificadora, limiar)
            if par is None:
                continue  # sem par identificável — fora do escopo desta auditoria, não gera ruído

            if par.credito == 0:
                resultados.append(Apontamento(
                    regra=self.id, severidade=Severidade.CRITICO,
                    descricao=(
                        f"Conta {bem.codigo} possui bem imobilizado {bem.descricao} mas não "
                        f"apresenta crédito de depreciação no período "
                        f"(conta {par.codigo} — {par.descricao})"
                    ),
                    valor_contabil=bem.saldo_atual.valor,
                    origem_balancete=bem.referencia,
                ))
            else:
                # relatório precisa dos valores mesmo quando confere — não só
                # nas falhas — para não esconder o que foi de fato auditado.
                resultados.append(Apontamento(
                    regra=self.id, severidade=Severidade.OK,
                    descricao=(
                        f"Conta {bem.codigo} ({bem.descricao}): depreciação confere "
                        f"(conta {par.codigo} — {par.descricao}, crédito {par.credito})"
                    ),
                    valor_contabil=bem.saldo_atual.valor, diferenca=par.credito,
                    origem_balancete=bem.referencia,
                ))

        if not resultados:
            resultados.append(Apontamento(
                regra=self.id, severidade=Severidade.OK,
                descricao="Nenhum bem imobilizado com atividade no período dentro do escopo configurado",
            ))
        return resultados
