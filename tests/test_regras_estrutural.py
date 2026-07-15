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
    contas = [conta(5, "CAIXA GERAL", Grupo.ATIVO, saldo_atual="13972.35", natureza_atual=Natureza.CREDOR)]
    ctx = contexto(fiscal(), balancete(contas=contas), config)
    aps = P2Natureza().avaliar(ctx)
    assert aps[0].severidade is Severidade.IMPEDITIVO


def test_anomalia_abaixo_do_limiar_de_materialidade_vira_alerta(config):
    """R$ 3,77 credor é ruído de arredondamento/estorno — não merece CRITICO
    lado a lado com divergências de milhares. Caso real: TRIBUTOS A RECUPERAR."""
    contas = [
        conta(28, "TRIBUTOS A RECUPERAR/COMPENSAR", Grupo.ATIVO, saldo_atual="3.77", natureza_atual=Natureza.CREDOR),
    ]
    ctx = contexto(fiscal(), balancete(contas=contas), config)
    aps = P2Natureza().avaliar(ctx)
    assert len(aps) == 1
    assert aps[0].regra == "P2.NATUREZA"
    assert aps[0].severidade is Severidade.ALERTA


def test_disponivel_e_caixa_recebem_mesmo_tratamento(config):
    """DISPONÍVEL (conta-título) e CAIXA GERAL (conta-filha) são o mesmo dinheiro
    em níveis hierárquicos diferentes — ambas devem cair em P2.SALDO_ANOMALO."""
    contas = [
        conta(3, "DISPONÍVEL", Grupo.ATIVO, saldo_atual="13972.35", natureza_atual=Natureza.CREDOR),
        conta(5, "CAIXA GERAL", Grupo.ATIVO, saldo_atual="13972.35", natureza_atual=Natureza.CREDOR),
    ]
    ctx = contexto(fiscal(), balancete(contas=contas), config)
    aps = P2Natureza().avaliar(ctx)
    assert len(aps) == 2
    assert all(a.regra == "P2.SALDO_ANOMALO" for a in aps)


def test_caixa_credor_vira_saldo_anomalo_nao_natureza(config):
    """Caixa/banco credor não é erro cadastral: regra própria P2.SALDO_ANOMALO,
    mensagem de investigação, não 'natureza incorreta'."""
    contas = [conta(5, "CAIXA GERAL", Grupo.ATIVO, saldo_atual="13972.35", natureza_atual=Natureza.CREDOR)]
    ctx = contexto(fiscal(), balancete(contas=contas), config)
    aps = P2Natureza().avaliar(ctx)
    assert len(aps) == 1
    assert aps[0].regra == "P2.SALDO_ANOMALO"
    assert aps[0].severidade is Severidade.CRITICO
    assert "investigar" in aps[0].descricao.lower()


def test_retificadora_depreciacao_acumulada_nao_gera_falso_positivo(config):
    """Depreciação acumulada é conta retificadora do ATIVO: natureza esperada é
    CREDOR (inversa do grupo). Sem a tabela de retificadoras, isso vira P2.NATUREZA
    crítico espúrio."""
    contas = [
        conta(60, "(-) DEPRECIACAO ACUMULADA", Grupo.ATIVO, saldo_atual="500", natureza_atual=Natureza.CREDOR),
    ]
    ctx = contexto(fiscal(), balancete(contas=contas), config)
    aps = P2Natureza().avaliar(ctx)
    assert len(aps) == 1 and aps[0].severidade is Severidade.OK


def test_retificadora_com_natureza_normal_ainda_acusa(config):
    """Se a retificadora fechar DEVEDOR (natureza normal do ATIVO, não a inversa
    esperada para ela), ainda é apontamento — a inversão vale só quando bate."""
    contas = [
        conta(60, "(-) DEPRECIACAO ACUMULADA", Grupo.ATIVO, saldo_atual="500", natureza_atual=Natureza.DEVEDOR),
    ]
    ctx = contexto(fiscal(), balancete(contas=contas), config)
    aps = P2Natureza().avaliar(ctx)
    assert len(aps) == 1
    assert aps[0].regra == "P2.NATUREZA"
    assert aps[0].severidade is Severidade.CRITICO
