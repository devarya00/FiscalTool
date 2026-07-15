from decimal import Decimal

from dominio.apontamento import Severidade
from dominio.modelos import Grupo, Secao
from dominio.regras.grupos import P4GrupoAmarracao
from tests.conftest import acumulador, balancete, conta, contexto, fiscal


def test_frete_soma_confere(config):
    entradas = [acumulador("300", "FRETE SOBRE COMPRAS", "1000.00", Secao.ENTRADAS)]
    contas = [conta(688, "DESPESA COM FRETE", Grupo.RESULTADO, debito="1000.00")]
    ctx = contexto(fiscal(entradas=entradas), balancete(contas=contas), config)

    aps = [a for a in P4GrupoAmarracao().avaliar(ctx) if a.regra == "G.FRETE"]
    assert len(aps) == 1 and aps[0].severidade is Severidade.OK


def test_frete_divergencia(config):
    entradas = [acumulador("300", "FRETE SOBRE COMPRAS", "1000.00", Secao.ENTRADAS)]
    contas = [conta(688, "DESPESA COM FRETE", Grupo.RESULTADO, debito="850.00")]
    ctx = contexto(fiscal(entradas=entradas), balancete(contas=contas), config)

    aps = [a for a in P4GrupoAmarracao().avaliar(ctx) if a.regra == "G.FRETE"]
    assert len(aps) == 1
    assert aps[0].severidade is Severidade.CRITICO
    assert aps[0].diferenca == Decimal("150.00")


def test_frete_conta_ausente_com_valor_fiscal_e_critico(config):
    entradas = [acumulador("300", "FRETE SOBRE COMPRAS", "1000.00", Secao.ENTRADAS)]
    ctx = contexto(fiscal(entradas=entradas), balancete(contas=[]), config)

    aps = [a for a in P4GrupoAmarracao().avaliar(ctx) if a.regra == "G.FRETE"]
    assert len(aps) == 1
    assert aps[0].severidade is Severidade.CRITICO
    assert "688" in aps[0].descricao


def test_frete_sem_valor_fiscal_e_sem_conta_e_na(config):
    ctx = contexto(fiscal(entradas=[]), balancete(contas=[]), config)
    aps = [a for a in P4GrupoAmarracao().avaliar(ctx) if a.regra == "G.FRETE"]
    assert aps == []


def test_imobilizado_busca_valor_encontra_conta_no_escopo(config):
    entradas = [acumulador("110", "AQUISICAO IMOBILIZADO A PRAZO", "50000.00", Secao.ENTRADAS)]
    contas = [
        conta(111, "IMOBILIZADO", Grupo.ATIVO, debito="0"),
        conta(130, "MAQUINAS E EQUIPAMENTOS", Grupo.ATIVO, debito="50000.00"),
    ]
    ctx = contexto(fiscal(entradas=entradas), balancete(contas=contas), config)

    aps = [a for a in P4GrupoAmarracao().avaliar(ctx) if a.regra == "G.IMOBILIZADO"]
    assert len(aps) == 1
    assert aps[0].severidade is Severidade.OK
    assert aps[0].origem_balancete is not None


def test_imobilizado_busca_valor_nao_encontra_e_critico(config):
    entradas = [acumulador("110", "AQUISICAO IMOBILIZADO A PRAZO", "50000.00", Secao.ENTRADAS)]
    contas = [conta(130, "MAQUINAS E EQUIPAMENTOS", Grupo.ATIVO, debito="12345.00")]
    ctx = contexto(fiscal(entradas=entradas), balancete(contas=contas), config)

    aps = [a for a in P4GrupoAmarracao().avaliar(ctx) if a.regra == "G.IMOBILIZADO"]
    assert len(aps) == 1
    assert aps[0].severidade is Severidade.CRITICO


def test_grupo_generico_n_para_n_soma_varios_codigos_e_varias_contas(config):
    """Cenário do pedido: 100 e 101 (fiscal) somados == 55 e 56 (contábil) somados."""
    config["grupos_amarracao"] = [{
        "id": "G.TESTE", "descricao": "Grupo genérico de teste",
        "codigos_fiscais": [100, 101], "contas_contabeis": [55, 56],
        "coluna": "DEBITO", "modo": "soma",
    }]
    entradas = [
        acumulador("100", "ACUMULADOR A", "300.00", Secao.ENTRADAS),
        acumulador("101", "ACUMULADOR B", "200.00", Secao.ENTRADAS),
    ]
    contas = [
        conta(55, "CONTA CONTABIL A", Grupo.ATIVO, debito="300.00"),
        conta(56, "CONTA CONTABIL B", Grupo.ATIVO, debito="200.00"),
    ]
    ctx = contexto(fiscal(entradas=entradas), balancete(contas=contas), config)

    aps = P4GrupoAmarracao().avaliar(ctx)
    assert len(aps) == 1
    assert aps[0].regra == "G.TESTE"
    assert aps[0].severidade is Severidade.OK
    assert aps[0].valor_fiscal == Decimal("500.00")
    assert aps[0].valor_contabil == Decimal("500.00")


def test_grupo_consome_acumuladores_para_nao_virar_orfao(config):
    config["grupos_amarracao"] = [{
        "id": "G.TESTE", "codigos_fiscais": [100], "contas_contabeis": [55],
        "coluna": "DEBITO", "modo": "soma",
    }]
    entradas = [acumulador("100", "ACUMULADOR A", "300.00", Secao.ENTRADAS)]
    contas = [conta(55, "CONTA CONTABIL A", Grupo.ATIVO, debito="300.00")]
    ctx = contexto(fiscal(entradas=entradas), balancete(contas=contas), config)

    P4GrupoAmarracao().avaliar(ctx)
    assert ctx.foi_consumido(entradas[0]) is True
