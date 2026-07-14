from decimal import Decimal

from dominio.apontamento import Severidade
from dominio.modelos import Grupo
from dominio.regras.folha import P6FolhaIntegralizacao, P7FolhaPagamento
from tests.conftest import balancete, conta, contexto, fiscal


def _contas_exemplo_doc() -> list:
    """Números do exemplo real no documento de arquitetura (§6.3/§6.4)."""
    return [
        conta(331, "Salários e Ordenados", Grupo.RESULTADO, debito="10000", credito="0"),  # gatilho folha
        conta(178, "IRRF a Recolher", Grupo.PASSIVO, saldo_anterior="47.16", debito="0", credito="0"),
        conta(187, "Salários e Ordenados a Pagar", Grupo.PASSIVO, saldo_anterior="6062.82", debito="4935.38", credito="8451.99"),
        conta(191, "INSS a Recolher", Grupo.PASSIVO, saldo_anterior="590.91", debito="3.77", credito="615.91"),
        conta(192, "FGTS a Recolher", Grupo.PASSIVO, saldo_anterior="536.06", debito="0", credito="551.15"),
        conta(194, "Provisões para Férias", Grupo.PASSIVO, credito="312.40"),
        conta(195, "Provisões para 13º Salário", Grupo.PASSIVO, credito="234.31"),
        conta(198, "FGTS sobre Provisões para Férias", Grupo.PASSIVO, credito="24.99"),
        conta(199, "FGTS sobre Provisões para 13º", Grupo.PASSIVO, credito="22.08"),
    ]


def test_folha_integralizacao_alerta_para_irrf_zerado(config):
    ctx = contexto(fiscal(), balancete(contas=_contas_exemplo_doc()), config)
    resultado = P6FolhaIntegralizacao().avaliar(ctx)

    irrf = next(a for a in resultado if "178" in a.descricao)
    assert irrf.severidade is Severidade.ALERTA

    salarios = next(a for a in resultado if "187" in a.descricao)
    assert salarios.severidade is Severidade.OK


def test_folha_integralizacao_pula_se_nao_houve_folha(config):
    contas = [c for c in _contas_exemplo_doc() if c.codigo != 331]  # sem gatilho
    ctx = contexto(fiscal(), balancete(contas=contas), config)
    assert P6FolhaIntegralizacao().avaliar(ctx) == []


def test_folha_pagamento_diverge_conforme_exemplo_doc(config):
    ctx = contexto(fiscal(), balancete(contas=_contas_exemplo_doc()), config)
    aps = P7FolhaPagamento().avaliar(ctx)
    por_conta = {a.descricao.split(" ")[1]: a for a in aps}

    assert por_conta["187"].severidade is Severidade.CRITICO
    assert por_conta["187"].diferenca == Decimal("1127.44")
    assert por_conta["191"].severidade is Severidade.CRITICO
    assert por_conta["191"].diferenca == Decimal("587.14")
    assert por_conta["192"].severidade is Severidade.CRITICO  # FGTS não pago
    assert por_conta["178"].severidade is Severidade.CRITICO  # IRRF não pago


def test_folha_pagamento_override_manual_forca_execucao(config):
    contas = [c for c in _contas_exemplo_doc() if c.codigo != 331]
    ctx = contexto(fiscal(), balancete(contas=contas), config, houve_folha_override=True)
    aps = P7FolhaPagamento().avaliar(ctx)
    assert len(aps) == 4
