from dominio.apontamento import Severidade
from dominio.modelos import Grupo
from dominio.regras.depreciacao import P8Depreciacao
from tests.conftest import balancete, conta, contexto, fiscal


def test_bem_sem_credito_de_depreciacao_e_critico(config):
    """Caso do pedido: bem 'AMAROK' com saldo, retificadora '(-) DEPRECIAÇÃO
    AMAROK' encontrada por fuzzy match, mas sem crédito no período."""
    contas = [
        conta(120, "VEICULOS AMAROK", Grupo.ATIVO, saldo_atual="80000.00"),
        conta(125, "(-) DEPRECIACAO AMAROK", Grupo.ATIVO, credito="0", saldo_atual="5000.00"),
    ]
    ctx = contexto(fiscal(), balancete(contas=contas), config)

    aps = P8Depreciacao().avaliar(ctx)
    assert len(aps) == 1
    assert aps[0].severidade is Severidade.CRITICO
    assert "120" in aps[0].descricao
    assert "AMAROK" in aps[0].descricao


def test_bem_com_credito_de_depreciacao_confere(config):
    contas = [
        conta(120, "VEICULOS AMAROK", Grupo.ATIVO, saldo_atual="80000.00"),
        conta(125, "(-) DEPRECIACAO AMAROK", Grupo.ATIVO, credito="1500.00", saldo_atual="6500.00"),
    ]
    ctx = contexto(fiscal(), balancete(contas=contas), config)

    aps = P8Depreciacao().avaliar(ctx)
    assert len(aps) == 1 and aps[0].severidade is Severidade.OK


def test_bem_sem_atividade_no_periodo_nao_gera_apontamento(config):
    contas = [
        conta(120, "VEICULOS AMAROK", Grupo.ATIVO, saldo_atual="0"),
        conta(125, "(-) DEPRECIACAO AMAROK", Grupo.ATIVO, credito="0", saldo_atual="0"),
    ]
    ctx = contexto(fiscal(), balancete(contas=contas), config)

    aps = P8Depreciacao().avaliar(ctx)
    assert len(aps) == 1 and aps[0].severidade is Severidade.OK


def test_bem_sem_par_identificavel_nao_gera_ruido(config):
    """Bem sem nenhuma retificadora minimamente parecida no escopo — não reporta
    (evitar falso vínculo/ruído), mesmo tendo saldo."""
    contas = [
        conta(120, "VEICULOS CAMINHAO", Grupo.ATIVO, saldo_atual="80000.00"),
        conta(125, "(-) DEPRECIACAO MAQUINAS", Grupo.ATIVO, credito="0"),
    ]
    ctx = contexto(fiscal(), balancete(contas=contas), config)

    aps = P8Depreciacao().avaliar(ctx)
    assert len(aps) == 1 and aps[0].severidade is Severidade.OK


def test_fora_do_escopo_configurado_e_ignorado(config):
    config["depreciacao"] = {"escopo_contas": [111, 148], "limiar_fuzzy": 0.3}
    contas = [
        conta(500, "VEICULOS AMAROK FORA DO ESCOPO", Grupo.RESULTADO, saldo_atual="80000.00"),
        conta(501, "(-) DEPRECIACAO AMAROK FORA DO ESCOPO", Grupo.RESULTADO, credito="0"),
    ]
    ctx = contexto(fiscal(), balancete(contas=contas), config)

    aps = P8Depreciacao().avaliar(ctx)
    assert len(aps) == 1 and aps[0].severidade is Severidade.OK
