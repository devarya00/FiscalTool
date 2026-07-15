"""Persistência de vínculos aprendidos (por CNPJ) — Repositorio e a mescla
feita por ConferenciaService antes de rodar o motor de regras."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from aplicacao.conferencia_service import ConferenciaService
from infra.repositorio import Repositorio

_CNPJ = "12509263000100"


@pytest.fixture
def db_path(tmp_path) -> str:
    return str(tmp_path / "teste.db")


def test_salvar_e_buscar_vinculo(db_path):
    repo = Repositorio(db_path)
    repo.salvar_vinculo(_CNPJ, "900", [55, 56], "DEBITO", descricao="Vínculo teste")

    vinculos = repo.vinculos_do_cliente(_CNPJ)
    assert len(vinculos) == 1
    v = vinculos[0]
    assert v["codigos_fiscais"] == ["900"]
    assert v["contas_contabeis"] == [55, 56]
    assert v["coluna"] == "DEBITO"
    assert v["modo"] == "soma"
    assert v["id"] == "G.VINCULO.900"
    repo.close()


def test_vinculo_e_isolado_por_cnpj(db_path):
    repo = Repositorio(db_path)
    repo.salvar_vinculo(_CNPJ, "900", [55], "DEBITO")
    repo.salvar_vinculo("99999999000199", "900", [77], "CREDITO")

    assert len(repo.vinculos_do_cliente(_CNPJ)) == 1
    assert repo.vinculos_do_cliente(_CNPJ)[0]["contas_contabeis"] == [55]
    assert repo.vinculos_do_cliente("99999999000199")[0]["contas_contabeis"] == [77]
    repo.close()


def test_salvar_vinculo_duas_vezes_atualiza_nao_duplica(db_path):
    repo = Repositorio(db_path)
    repo.salvar_vinculo(_CNPJ, "900", [55], "DEBITO")
    repo.salvar_vinculo(_CNPJ, "900", [999], "CREDITO")  # reconfigurar o mesmo AC

    vinculos = repo.vinculos_do_cliente(_CNPJ)
    assert len(vinculos) == 1
    assert vinculos[0]["contas_contabeis"] == [999]
    assert vinculos[0]["coluna"] == "CREDITO"
    repo.close()


def test_cliente_sem_vinculo_retorna_lista_vazia(db_path):
    repo = Repositorio(db_path)
    assert repo.vinculos_do_cliente(_CNPJ) == []
    repo.close()


@pytest.fixture
def config_path(tmp_path) -> Path:
    caminho = tmp_path / "regras.yaml"
    caminho.write_text(yaml.safe_dump({"grupos_amarracao": [{"id": "G.EXISTENTE"}]}), encoding="utf-8")
    return caminho


def test_service_mescla_vinculos_aprendidos_no_config(config_path, db_path):
    servico = ConferenciaService(config_path=config_path, db_path=db_path)
    servico.configurar_vinculo(_CNPJ, "900", [55, 56], "DEBITO", descricao="Frete aprendido")

    config = servico._config_com_vinculos_aprendidos(_CNPJ)
    ids = [g["id"] for g in config["grupos_amarracao"]]
    assert "G.EXISTENTE" in ids  # config original preservado
    assert "G.VINCULO.900" in ids  # vínculo aprendido entrou


def test_service_nao_muta_config_original(config_path, db_path):
    servico = ConferenciaService(config_path=config_path, db_path=db_path)
    servico.configurar_vinculo(_CNPJ, "900", [55], "DEBITO")

    servico._config_com_vinculos_aprendidos(_CNPJ)
    assert len(servico._config["grupos_amarracao"]) == 1  # original intocado


def test_service_outro_cnpj_nao_ve_vinculo_do_primeiro(config_path, db_path):
    servico = ConferenciaService(config_path=config_path, db_path=db_path)
    servico.configurar_vinculo(_CNPJ, "900", [55], "DEBITO")

    config_outro = servico._config_com_vinculos_aprendidos("00000000000000")
    ids = [g["id"] for g in config_outro["grupos_amarracao"]]
    assert "G.VINCULO.900" not in ids
