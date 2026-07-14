from datetime import date

from dominio.apontamento import Severidade
from dominio.modelos import Periodo
from dominio.regras.cabecalho import P1CNPJ, P1Periodo
from tests.conftest import balancete, contexto, fiscal


def test_p1_cnpj_confere(config):
    ctx = contexto(fiscal(cnpj="12509263000100"), balancete(cnpj="12509263000100"), config)
    aps = P1CNPJ().avaliar(ctx)
    assert len(aps) == 1 and aps[0].severidade is Severidade.OK


def test_p1_cnpj_diverge_e_impede(config):
    ctx = contexto(fiscal(cnpj="12509263000100"), balancete(cnpj="99999999000199"), config)
    aps = P1CNPJ().avaliar(ctx)
    assert len(aps) == 1 and aps[0].severidade is Severidade.IMPEDITIVO


def test_p1_periodo_confere(config):
    ctx = contexto(fiscal(), balancete(), config)
    aps = P1Periodo().avaliar(ctx)
    assert aps[0].severidade is Severidade.OK


def test_p1_periodo_diverge_e_impede(config):
    periodo_diferente = Periodo(date(2025, 10, 1), date(2025, 10, 31))
    ctx = contexto(fiscal(), balancete(periodo_=periodo_diferente), config)
    aps = P1Periodo().avaliar(ctx)
    assert aps[0].severidade is Severidade.IMPEDITIVO
