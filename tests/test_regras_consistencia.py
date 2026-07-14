from dominio.apontamento import Severidade
from dominio.modelos import Grupo
from dominio.regras.consistencia import P7ReceitaCusto
from tests.conftest import balancete, conta, contexto, fiscal


def test_receita_com_custo_292_combustivel_ok(config):
    """Decisão: intervalo de custo [292, 500] inclui a conta 292 (Combustível),
    único custo real nos exemplos do doc — leitura literal [295,500] o excluiria."""
    contas = [
        conta(408, "Venda de Mercadorias", Grupo.RESULTADO, credito="1000"),
        conta(292, "Despesa com Combustível", Grupo.RESULTADO, debito="200"),
    ]
    ctx = contexto(fiscal(), balancete(contas=contas), config)
    aps = P7ReceitaCusto().avaliar(ctx)
    assert aps[0].severidade is Severidade.OK


def test_receita_sem_custo_e_critico(config):
    contas = [conta(408, "Venda de Mercadorias", Grupo.RESULTADO, credito="1000")]
    ctx = contexto(fiscal(), balancete(contas=contas), config)
    aps = P7ReceitaCusto().avaliar(ctx)
    assert aps[0].severidade is Severidade.CRITICO


def test_sem_receita_nao_exige_custo(config):
    ctx = contexto(fiscal(), balancete(contas=[]), config)
    aps = P7ReceitaCusto().avaliar(ctx)
    assert aps[0].severidade is Severidade.OK
