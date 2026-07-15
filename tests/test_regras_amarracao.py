from decimal import Decimal

from dominio.apontamento import Severidade
from dominio.modelos import Grupo, Secao
from dominio.motor import MotorRegras
from dominio.regras import todas_as_regras
from tests.conftest import acumulador, balancete, conta, contexto, fiscal


def _motor() -> MotorRegras:
    return MotorRegras(todas_as_regras())


def test_p3_servico_bate_na_conta_por_nome(config):
    entradas = []
    servicos = [acumulador("900", "PRESTAÇÃO DE SERVIÇOS", "500.00", Secao.SERVICOS)]
    fiscal_ = fiscal(entradas=entradas, servicos=servicos, total_servicos="500.00")
    contas = [conta(601, "SERVIÇO PRESTADO", Grupo.RESULTADO, credito="500.00")]
    ctx = contexto(fiscal_, balancete(contas=contas), config)

    aps = [a for a in _motor().executar(ctx) if a.regra == "P3.SERV"]
    assert aps[0].severidade is Severidade.OK


def test_p3_servico_nao_confunde_com_servicos_tomados_por_terceiros(config):
    """Caso real (Balancete jovane.pdf): 'SERVIÇOS PRESTADOS POR TERCEIROS' (325,
    despesa) aparece na lista ANTES de 'SERVIÇOS PRESTADOS' (411, receita). Sem
    excluir 'terceiros', P3.SERV pega a 325 por ser a primeira a casar 'prestad'
    — conta errada, resultado errado. P4.TOMADOS é quem deve olhar a 325."""
    servicos = [acumulador("900", "PRESTAÇÃO DE SERVIÇOS", "37600.00", Secao.SERVICOS)]
    fiscal_ = fiscal(servicos=servicos, total_servicos="37600.00")
    contas = [
        conta(325, "SERVIÇOS PRESTADOS POR TERCEIROS", Grupo.RESULTADO, debito="960.00"),
        conta(411, "SERVIÇOS PRESTADOS", Grupo.RESULTADO, credito="37600.00"),
    ]
    ctx = contexto(fiscal_, balancete(contas=contas), config)

    aps = [a for a in _motor().executar(ctx) if a.regra == "P3.SERV"]
    assert aps[0].severidade is Severidade.OK
    assert "conta 411" in aps[0].descricao


def test_p3_servico_coluna_errada(config):
    fiscal_ = fiscal(servicos=[], total_servicos="500.00")
    contas = [conta(601, "SERVIÇO PRESTADO", Grupo.RESULTADO, debito="500.00", credito="0")]
    ctx = contexto(fiscal_, balancete(contas=contas), config)

    aps = [a for a in _motor().executar(ctx) if a.regra == "P3.SERV"]
    assert aps[0].severidade is Severidade.CRITICO
    assert aps[0].coluna_esperada == "CREDITO"
    assert aps[0].coluna_encontrada == "DEBITO"


def test_p4_consumo_soma_varios_acumuladores(config):
    entradas = [
        acumulador("107", "COMPRA DE USO E CONSUMO A PRAZO", "700.00", Secao.ENTRADAS, linha=1),
        acumulador("108", "COMPRA DE USO E CONSUMO A VISTA", "300.00", Secao.ENTRADAS, linha=2),
    ]
    contas = [conta(58, "Outros Materiais de Consumo", Grupo.ATIVO, debito="1000.00")]
    ctx = contexto(fiscal(entradas=entradas), balancete(contas=contas), config)

    aps = [a for a in _motor().executar(ctx) if a.regra == "P4.CONSUMO"]
    assert aps[0].severidade is Severidade.OK
    assert aps[0].valor_fiscal == Decimal("1000.00")


def test_precedencia_uso_e_consumo_nao_cai_em_revenda(config):
    """'COMPRA DE USO E CONSUMO A PRAZO' deve ser consumido só por P4.CONSUMO,
    nunca chegar a P4.REVENDA — cada acumulador cai em exatamente uma regra."""
    entradas = [acumulador("107", "COMPRA DE MERCADORIA PARA USO E CONSUMO A PRAZO", "700.00", Secao.ENTRADAS)]
    contas = [
        conta(58, "Outros Materiais de Consumo", Grupo.ATIVO, debito="700.00"),
        # conta 55 propositalmente ausente do balancete
    ]
    ctx = contexto(fiscal(entradas=entradas), balancete(contas=contas), config)

    resultado = _motor().executar(ctx)
    ap_consumo = next(a for a in resultado if a.regra == "P4.CONSUMO")
    ap_revenda = next((a for a in resultado if a.regra == "P4.REVENDA"), None)

    assert ap_consumo.severidade is Severidade.OK
    # revenda: valor_fiscal=0 (acumulador já consumido por P4.CONSUMO) e conta 55
    # ausente -> N/A, sem apontamento
    assert ap_revenda is None
    assert not any(a.regra == "P6.ORFAOS" for a in resultado)  # não sobra órfão


def test_filtro_outras_e_totalmente_ignorado(config):
    entradas = [acumulador("999", "OUTRAS DESPESAS DIVERSAS", "50.00", Secao.ENTRADAS)]
    ctx = contexto(fiscal(entradas=entradas), balancete(contas=[]), config)

    resultado = _motor().executar(ctx)
    assert not any(a.regra == "P6.ORFAOS" for a in resultado)


def test_conta_ausente_com_valor_fiscal_e_critico(config):
    entradas = [acumulador("292", "COMPRA DE COMBUSTIVEL", "150.00", Secao.ENTRADAS)]
    ctx = contexto(fiscal(entradas=entradas), balancete(contas=[]), config)

    aps = [a for a in _motor().executar(ctx) if a.regra == "P4.COMB"]
    assert aps[0].severidade is Severidade.CRITICO
    assert "não encontrada" in aps[0].descricao


def test_p4_comb_casa_conta_por_substring_quando_codigo_nao_bate(config):
    """Plano de contas do cliente numera diferente do configurado (292): a conta
    existe mas sob outro código. Índice normalizado por descrição resolve —
    'Combustível' casa com 'DESPESA COM COMBUSTÍVEL'."""
    entradas = [acumulador("41", "COMPRA COMBUSTIVEL A PRAZO", "150.00", Secao.ENTRADAS)]
    contas = [conta(9001, "DESPESA COM COMBUSTIVEL", Grupo.ATIVO, debito="150.00")]
    ctx = contexto(fiscal(entradas=entradas), balancete(contas=contas), config)

    aps = [a for a in _motor().executar(ctx) if a.regra == "P4.COMB"]
    assert aps[0].severidade is Severidade.OK


def test_p4_tomados_conta_existente_com_codigo_diferente_vira_divergencia_de_valor(config):
    """Conta existe (960,00) sob código diferente do configurado (325); resolvida
    por substring. Achado real é divergência de valor, não 'conta não encontrada'."""
    entradas = [acumulador("50", "SERVICOS TOMADOS COM RETENCAO", "10960.00", Secao.ENTRADAS)]
    contas = [conta(9002, "Serviços Prestados por Terceiros", Grupo.ATIVO, debito="960.00")]
    ctx = contexto(fiscal(entradas=entradas), balancete(contas=contas), config)

    aps = [a for a in _motor().executar(ctx) if a.regra == "P4.TOMADOS"]
    assert len(aps) == 1
    assert aps[0].severidade is Severidade.CRITICO
    assert "divergência de valor" in aps[0].descricao
    assert aps[0].diferenca == Decimal("10000.00")


def test_p4_comb_casa_plural_irregular_da_conta_real(config):
    """Caso real (Balancete jovane.pdf): plano de contas usa código 290, não o 292
    configurado, e descrição no PLURAL 'COMBUSTÍVEIS E ENERGIA ELÉTRICA'. 'Combustível'
    singular não é substring de 'combustiveis' (plural -vel/-veis não é sufixo simples)
    — por isso o padrão de matching usa a raiz 'combust', não o rótulo completo."""
    entradas = [acumulador("41", "COMPRA COMBUSTIVEL A PRAZO", "54932.11", Secao.ENTRADAS)]
    contas = [conta(290, "COMBUSTÍVEIS E ENERGIA ELÉTRICA", Grupo.RESULTADO, debito="54932.11")]
    ctx = contexto(fiscal(entradas=entradas), balancete(contas=contas), config)

    aps = [a for a in _motor().executar(ctx) if a.regra == "P4.COMB"]
    assert aps[0].severidade is Severidade.OK


def test_acumulador_nao_mapeado_vira_orfao(config):
    entradas = [acumulador("777", "ALGO SEM REGRA CORRESPONDENTE", "10.00", Secao.ENTRADAS)]
    ctx = contexto(fiscal(entradas=entradas), balancete(contas=[]), config)

    resultado = _motor().executar(ctx)
    orfaos = [a for a in resultado if a.regra == "P6.ORFAOS"]
    assert len(orfaos) == 1
    assert "777" in orfaos[0].descricao
