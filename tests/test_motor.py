from dominio.apontamento import Severidade
from dominio.motor import MotorRegras
from dominio.regras import todas_as_regras
from tests.conftest import balancete, contexto, fiscal


def test_motor_aborta_no_primeiro_impeditivo_e_nao_roda_o_resto(config):
    ctx = contexto(
        fiscal(cnpj="12509263000100"), balancete(cnpj="00000000000000"), config,
    )
    resultado = MotorRegras(todas_as_regras()).executar(ctx)

    assert any(a.severidade is Severidade.IMPEDITIVO for a in resultado)
    # break é imediato: nem P1.PERIODO (ordem seguinte) chega a rodar
    regras_executadas = {a.regra for a in resultado}
    assert regras_executadas == {"P1.CNPJ"}


def test_motor_roda_tudo_quando_nao_ha_impeditivo(config):
    ctx = contexto(fiscal(), balancete(contas=[]), config)
    resultado = MotorRegras(todas_as_regras()).executar(ctx)

    assert not any(a.severidade is Severidade.IMPEDITIVO for a in resultado)
    regras_executadas = {a.regra for a in resultado}
    assert "P1.CNPJ" in regras_executadas
    assert "P7.RECEITA_CUSTO" in regras_executadas
