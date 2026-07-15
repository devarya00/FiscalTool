"""§5.4 — gate de plausibilidade e degradação graciosa do fallback de IA.

Não testa Ollama de verdade (não é pré-requisito do ambiente de dev/CI) — só
que o app nunca trava quando o servidor está fora do ar ou a flag é usada.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from dominio.modelos import Balancete, Grupo, Periodo
from infra.balancete_parser import BalanceteParser
from tests.conftest import conta
from tests.test_parsers import _gerar_pdf_balancete

_PERIODO = Periodo(date(2025, 1, 1), date(2025, 1, 31))


def test_confia_exige_minimo_de_contas():
    bal = Balancete(cnpj="1", periodo=_PERIODO, contas=[conta(1, "ATIVO", Grupo.ATIVO)])
    assert BalanceteParser._confia(bal) is False


def test_confia_exige_grupos_ancora():
    contas = [
        conta(1, "ATIVO", Grupo.ATIVO),
        conta(2, "OUTRA CONTA ATIVO", Grupo.ATIVO),
        conta(3, "MAIS UMA ATIVO", Grupo.ATIVO),
    ]
    bal = Balancete(cnpj="1", periodo=_PERIODO, contas=contas)
    assert BalanceteParser._confia(bal) is False  # falta PASSIVO e PL


def test_confia_aceita_com_ancoras_e_volume_minimo():
    contas = [
        conta(1, "ATIVO", Grupo.ATIVO),
        conta(149, "PASSIVO", Grupo.PASSIVO),
        conta(243, "CAPITAL SOCIAL", Grupo.PL),
    ]
    bal = Balancete(cnpj="1", periodo=_PERIODO, contas=contas)
    assert BalanceteParser._confia(bal) is True


def test_parse_com_ia_desligada_marca_incerto_sem_tentar_rede(tmp_path):
    """PDF sintético só com grupo ATIVO — não fecha o gate. Com ia_fallback
    desligado (default), deve voltar parsing_incerto=True sem tentar Ollama."""
    caminho = tmp_path / "balancete_incompleto.pdf"
    _gerar_pdf_balancete(Path(caminho))

    resultado = BalanceteParser(ia_fallback_config={"ativo": False}).parse(str(caminho))
    assert resultado.parsing_incerto is True


def test_parse_com_ia_ligada_e_ollama_fora_do_ar_nao_trava(tmp_path):
    """Ollama não está rodando neste ambiente — deve degradar graciosamente
    (parsing_incerto=True), nunca lançar exceção."""
    caminho = tmp_path / "balancete_incompleto.pdf"
    _gerar_pdf_balancete(Path(caminho))

    resultado = BalanceteParser(ia_fallback_config={
        "ativo": True, "host": "http://localhost:11434", "modelo": "qwen2.5vl:7b",
    }).parse(str(caminho))
    assert resultado.parsing_incerto is True
