from __future__ import annotations

from decimal import Decimal

from dominio.apontamento import Apontamento, Severidade
from dominio.modelos import Contexto, Grupo, Natureza
from dominio.regras.base import Regra
from dominio.regras._util import RETIFICADORAS_PADRAO, contem

_ESPERADO = {Grupo.ATIVO: Natureza.DEVEDOR, Grupo.PASSIVO: Natureza.CREDOR}
_INVERSA = {Natureza.DEVEDOR: Natureza.CREDOR, Natureza.CREDOR: Natureza.DEVEDOR}

_SALDO_ANOMALO_PADRAO = [
    "caixa", "disponivel", "banco", "bancos", "aplicacao financeira", "aplicacoes financeiras",
]
_LIMIAR_MATERIALIDADE_PADRAO = Decimal("10")


class P2Natureza(Regra):
    """Toda conta ATIVO deve fechar D, toda conta PASSIVO deve fechar C — exceto
    contas retificadoras (depreciação acumulada, provisões para perdas, "(-) ..."),
    cuja natureza esperada é a INVERSA do grupo (são estruturais, cadastrais: sem
    isso, toda retificadora vira falso positivo).

    Contas de caixa/banco com saldo credor não são erro cadastral — são anomalia
    financeira que merece investigação, então saem como P2.SALDO_ANOMALO com
    mensagem própria, não "natureza incorreta".

    Severidade configurável (regras.yaml: severidade_natureza_invertida) — default
    CRITICO, não IMPEDITIVO: caixa credor é comum no dia a dia e não deve travar
    a conferência inteira. Abaixo de natureza.limiar_materialidade (R$), a anomalia
    é ruído de arredondamento/estorno — vira ALERTA independente da severidade acima.
    """
    id = "P2.NATUREZA"
    id_saldo_anomalo = "P2.SALDO_ANOMALO"
    ordem = 3
    severidade_padrao = Severidade.CRITICO

    def avaliar(self, ctx: Contexto) -> list[Apontamento]:
        severidade_cfg = ctx.config.get("severidade_natureza_invertida", "critico")
        severidade_base = Severidade.IMPEDITIVO if severidade_cfg == "impeditivo" else Severidade.CRITICO

        cfg_natureza = ctx.config.get("natureza", {})
        padroes_retificadora = cfg_natureza.get("retificadoras", RETIFICADORAS_PADRAO)
        padroes_saldo_anomalo = cfg_natureza.get("saldo_anomalo", _SALDO_ANOMALO_PADRAO)
        limiar_materialidade = Decimal(str(cfg_natureza.get("limiar_materialidade", _LIMIAR_MATERIALIDADE_PADRAO)))

        resultados: list[Apontamento] = []
        for conta in ctx.balancete.contas:
            esperado = _ESPERADO.get(conta.grupo)
            if esperado is None:
                continue
            if any(contem(conta.descricao, p) for p in padroes_retificadora):
                esperado = _INVERSA[esperado]

            natureza_atual = conta.saldo_atual.natureza
            if natureza_atual == esperado:
                continue

            valor = conta.saldo_atual.valor
            severidade = Severidade.ALERTA if valor <= limiar_materialidade else severidade_base

            if any(contem(conta.descricao, p) for p in padroes_saldo_anomalo):
                resultados.append(Apontamento(
                    regra=self.id_saldo_anomalo,
                    severidade=severidade,
                    descricao=(
                        f"Conta {conta.codigo} ({conta.descricao}) com saldo "
                        f"{natureza_atual.value if natureza_atual else '?'} — "
                        f"padrão é {esperado.value}, mas ocorre no dia a dia; investigar motivo"
                    ),
                    valor_contabil=valor,
                    origem_balancete=conta.referencia,
                ))
                continue

            resultados.append(Apontamento(
                regra=self.id,
                severidade=severidade,
                descricao=(
                    f"Conta {conta.codigo} ({conta.descricao}) grupo {conta.grupo.value} "
                    f"com Saldo Atual {natureza_atual.value if natureza_atual else '?'} "
                    f"— esperado {esperado.value}"
                ),
                valor_contabil=valor,
                origem_balancete=conta.referencia,
            ))
        if not resultados:
            resultados.append(Apontamento(
                regra=self.id, severidade=Severidade.OK,
                descricao="Natureza de todos os saldos ATIVO/PASSIVO confere",
            ))
        return resultados
