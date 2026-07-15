"""§5.4 — Fallback de parsing via VLM local (Ollama). Só é importado quando
ia_fallback.ativo=true. Contrato: parse_via_ia devolve list[ContaBalancete]
de UMA página; qualquer falha (Ollama fora, JSON inválido, schema quebrado)
vira FalhaIAFallback — o chamador decide degradar para parsing_incerto."""
from __future__ import annotations

import base64
import json
import re
from decimal import Decimal, InvalidOperation

import httpx

from dominio.modelos import ContaBalancete, Grupo, Natureza, Saldo

_TIMEOUT = 120.0  # VLM em CPU é lento; melhor timeout largo que falso negativo

_GRUPO_MAP = {
    "ATIVO": Grupo.ATIVO, "PASSIVO": Grupo.PASSIVO,
    "PL": Grupo.PL, "RESULTADO": Grupo.RESULTADO,
}

_PROMPT = """Você extrai contas de um balancete contábil brasileiro.
Responda APENAS um array JSON, sem markdown, sem texto antes ou depois.
Cada item: {"codigo": int, "descricao": str, "grupo": "ATIVO|PASSIVO|PL|RESULTADO",
"saldo_anterior": float, "debito": float, "credito": float,
"saldo_atual": float, "saldo_atual_natureza": "D|C"}
Regras:
- Use ponto decimal (10782.39), nunca vírgula.
- Ignore linhas de cabeçalho, rodapé e assinaturas.
- grupo herda o último título de grupo visto acima da linha.
- Se um valor estiver vazio, use 0.0."""


class FalhaIAFallback(Exception):
    """Erro recuperável — o chamador degrada para parsing_incerto."""


def parse_via_ia(imagem_png: bytes, pagina_idx: int, modelo: str, host: str) -> list[ContaBalancete]:
    b64 = base64.b64encode(imagem_png).decode("ascii")
    payload = {
        "model": modelo,
        "prompt": _PROMPT,
        "images": [b64],
        "stream": False,
        "format": "json",       # força saída JSON no Ollama
        "options": {"temperature": 0.0},  # determinismo máximo possível
    }
    try:
        with httpx.Client(timeout=_TIMEOUT) as cli:
            r = cli.post(f"{host.rstrip('/')}/api/generate", json=payload)
            r.raise_for_status()
            bruto = r.json().get("response", "")
    except (httpx.HTTPError, ValueError) as e:
        raise FalhaIAFallback(f"Ollama indisponível/resposta inválida: {e}") from e

    itens = _extrair_json_array(bruto)
    if not itens:
        raise FalhaIAFallback("VLM não retornou array JSON utilizável")

    contas: list[ContaBalancete] = []
    for it in itens:
        conta = _montar(it, pagina_idx)
        if conta is not None:
            contas.append(conta)
    if not contas:
        raise FalhaIAFallback("Nenhuma conta válida no retorno do VLM")
    return contas


def _extrair_json_array(texto: str) -> list | None:
    """format=json geralmente já entrega limpo, mas modelos pequenos às vezes
    embrulham em prosa ou ```json. Tenta parse direto; se falhar, recorta o
    primeiro '[' até o último ']'."""
    try:
        dados = json.loads(texto)
        return dados if isinstance(dados, list) else dados.get("contas")
    except (json.JSONDecodeError, AttributeError):
        pass
    m = re.search(r"\[.*\]", texto, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _decimal(valor) -> Decimal:
    return Decimal(str(valor))


def _montar(it: dict, pagina_idx: int) -> ContaBalancete | None:
    try:
        natureza = Natureza.CREDOR if str(it.get("saldo_atual_natureza", "D")).upper() == "C" else Natureza.DEVEDOR
        valor_atual = _decimal(it["saldo_atual"])
        return ContaBalancete(
            codigo=int(it["codigo"]),
            descricao=str(it["descricao"]).strip(),
            grupo=_GRUPO_MAP[str(it["grupo"]).upper()],
            saldo_anterior=Saldo(_decimal(it.get("saldo_anterior", 0.0)), None),
            debito=_decimal(it.get("debito", 0.0)),
            credito=_decimal(it.get("credito", 0.0)),
            saldo_atual=Saldo(valor_atual, natureza if valor_atual != 0 else None),
            pagina=pagina_idx,
            linha=0,  # VLM não preserva linha física; 0 = origem IA
        )
    except (KeyError, ValueError, TypeError, InvalidOperation):
        return None  # linha malformada é descartada, não derruba a página