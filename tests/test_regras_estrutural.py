from dominio.apontamento import Severidade
from dominio.modelos import Grupo, Natureza
from dominio.regras.estrutural import P2Natureza
from tests.conftest import balancete, conta, contexto, fiscal


def test_ativo_devedor_e_passivo_credor_ok(config):
    contas = [
        conta(58, "Outros Materiais de Consumo", Grupo.ATIVO, saldo_atual="100", natureza_atual=Natureza.DEVEDOR),
        conta(187, "Salários e Ordenados a Pagar", Grupo.PASSIVO, saldo_atual="50", natureza_atual=Natureza.CREDOR),
    ]
    ctx = contexto(fiscal(), balancete(contas=contas), config)
    aps = P2Natureza().avaliar(ctx)
    assert len(aps) == 1 and aps[0].severidade is Severidade.OK


def test_caixa_credor_gera_critico_nao_impeditivo(config):
    """Exemplo real do doc: conta 3/5 DISPONÍVEL / CAIXA GERAL sob ATIVO com saldo
    13.972,35C. Decisão do usuário: CRITICO (não trava a execução), não IMPEDITIVO."""
    contas = [
        conta(5, "CAIXA GERAL", Grupo.ATIVO, saldo_atual="13972.35", natureza_atual=Natureza.CREDOR),
    ]
    ctx = contexto(fiscal(), balancete(contas=contas), config)
    aps = P2Natureza().avaliar(ctx)
    assert len(aps) == 1
    assert aps[0].severidade is Severidade.CRITICO


def test_severidade_configuravel_para_impeditivo(config):
    config["severidade_natureza_invertida"] = "impeditivo"
    contas = [conta(5, "CAIXA GERAL", Grupo.ATIVO, saldo_atual="1", natureza_atual=Natureza.CREDOR)]
    ctx = contexto(fiscal(), balancete(contas=contas), config)
    aps = P2Natureza().avaliar(ctx)
    assert aps[0].severidade is Severidade.IMPEDITIVO
