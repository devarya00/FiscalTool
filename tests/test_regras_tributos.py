from dominio.apontamento import Severidade
from dominio.modelos import Grupo
from dominio.regras.tributos import P7Simples
from tests.conftest import balancete, conta, contexto, fiscal


def test_simples_provisionado_e_nao_pago_conforme_exemplo_doc(config):
    contas = [conta(479, "Simples Nacional a Recolher", Grupo.PASSIVO, credito="878.63", debito="0")]
    ctx = contexto(fiscal(), balancete(contas=contas), config)
    aps = P7Simples().avaliar(ctx)
    assert aps[0].severidade is Severidade.ALERTA
    assert "não pago" in aps[0].descricao


def test_simples_integralizado_e_pago(config):
    contas = [conta(479, "Simples Nacional a Recolher", Grupo.PASSIVO, credito="878.63", debito="878.63")]
    ctx = contexto(fiscal(), balancete(contas=contas), config)
    aps = P7Simples().avaliar(ctx)
    assert aps[0].severidade is Severidade.OK


def test_simples_sem_integralizacao(config):
    contas = [conta(479, "Simples Nacional a Recolher", Grupo.PASSIVO, credito="0", debito="0")]
    ctx = contexto(fiscal(), balancete(contas=contas), config)
    aps = P7Simples().avaliar(ctx)
    assert aps[0].severidade is Severidade.OK
