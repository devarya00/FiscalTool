"""Parser posicional do Balancete (relatório contábil) — ver §5.2 da arquitetura.

Texto linear quebra com colunas coladas e descrições duplicadas. Em vez disso,
usamos pdfplumber.extract_words() e atribuímos cada palavra à coluna cuja faixa
de X contém seu centro. As faixas são detectadas uma vez a partir do cabeçalho
("Saldo Anterior", "Débito", "Crédito", "Saldo Atual") e reaproveitadas em
todas as páginas.
"""
from __future__ import annotations

import re
import unicodedata

import pdfplumber

from dominio.modelos import Balancete, ContaBalancete, Grupo
from infra.normalizador import extrair_cnpj, parse_periodo, to_decimal, to_saldo

FaixaX = tuple[float, float]

_TOKENS_COLUNA = {
    "saldo_anterior": ("saldo", "anterior"),
    "debito": ("debito",),
    "credito": ("credito",),
    "saldo_atual": ("saldo", "atual"),
}
_MARGEM_BORDA = 15.0  # pt — folga nas bordas externas das colunas extremas

_GRUPO_RE_ATIVO = "ativo"
_GRUPO_RE_PASSIVO = "passivo"
_LINHA_CONTA_RE = re.compile(r"^(\d+)\s+(.+)$")


def _normalizar(txt: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode("ascii")
    return sem_acento.lower().strip()


def _grupo_de(rotulo_normalizado: str) -> Grupo | None:
    if rotulo_normalizado.startswith(_GRUPO_RE_ATIVO):
        return Grupo.ATIVO
    if rotulo_normalizado.startswith(_GRUPO_RE_PASSIVO):
        return Grupo.PASSIVO
    if "patrimonio liquido" in rotulo_normalizado:
        return Grupo.PL
    if rotulo_normalizado.startswith("resultado"):
        return Grupo.RESULTADO
    return None


class BalanceteParser:
    def parse(self, caminho: str) -> Balancete:
        with pdfplumber.open(caminho) as pdf:
            texto_completo = "\n".join(p.extract_text() or "" for p in pdf.pages)
            cnpj = extrair_cnpj(texto_completo)
            if cnpj is None:
                raise ValueError("CNPJ não encontrado no Balancete")
            periodo = parse_periodo(texto_completo)

            faixas: dict[str, FaixaX] | None = None
            grupo_atual: Grupo | None = None
            contas: list[ContaBalancete] = []

            for pagina_idx, pagina in enumerate(pdf.pages, start=1):
                palavras = pagina.extract_words()
                if not palavras:
                    continue
                if faixas is None:
                    faixas = self._mapear_colunas(palavras)
                    if faixas is None:
                        continue  # cabeçalho ainda não apareceu; tenta próxima página

                for linha_idx, palavras_da_linha in enumerate(self._agrupar_por_linha(palavras), start=1):
                    texto_linha_norm = _normalizar(" ".join(p["text"] for p in palavras_da_linha))

                    grupo_detectado = _grupo_de(texto_linha_norm)
                    if grupo_detectado is not None:
                        grupo_atual = grupo_detectado
                        continue

                    m = _LINHA_CONTA_RE.match(" ".join(p["text"] for p in palavras_da_linha))
                    if not m or grupo_atual is None:
                        continue

                    conta = self._extrair_linha(palavras_da_linha, faixas, grupo_atual, pagina_idx, linha_idx)
                    if conta is not None:
                        contas.append(conta)

        return Balancete(cnpj=cnpj, periodo=periodo, contas=contas)

    @staticmethod
    def _agrupar_por_linha(palavras: list[dict], tolerancia: float = 2.0) -> list[list[dict]]:
        palavras_ordenadas = sorted(palavras, key=lambda p: (p["top"], p["x0"]))
        linhas: list[list[dict]] = []
        for p in palavras_ordenadas:
            if linhas and abs(p["top"] - linhas[-1][0]["top"]) <= tolerancia:
                linhas[-1].append(p)
            else:
                linhas.append([p])
        for linha in linhas:
            linha.sort(key=lambda p: p["x0"])
        return linhas

    def _mapear_colunas(self, palavras: list[dict]) -> dict[str, FaixaX] | None:
        for palavras_da_linha in self._agrupar_por_linha(palavras):
            tokens = [(_normalizar(p["text"]), p) for p in palavras_da_linha]
            achados: dict[str, tuple[float, float]] = {}
            for chave, tokens_esperados in _TOKENS_COLUNA.items():
                pos = self._localizar_sequencia(tokens, tokens_esperados)
                if pos is not None:
                    i0, i1 = pos
                    achados[chave] = (palavras_da_linha[i0]["x0"], palavras_da_linha[i1]["x1"])
            if len(achados) == len(_TOKENS_COLUNA):
                return self._derivar_faixas(achados)
        return None

    @staticmethod
    def _localizar_sequencia(tokens: list[tuple[str, dict]], esperados: tuple[str, ...]) -> tuple[int, int] | None:
        n = len(esperados)
        for i in range(len(tokens) - n + 1):
            if all(tokens[i + j][0].startswith(esperados[j]) for j in range(n)):
                return i, i + n - 1
        return None

    @staticmethod
    def _derivar_faixas(achados: dict[str, tuple[float, float]]) -> dict[str, FaixaX]:
        ordem = sorted(achados.items(), key=lambda kv: kv[1][0])
        faixas: dict[str, FaixaX] = {}
        for idx, (chave, (x0, x1)) in enumerate(ordem):
            esq = (ordem[idx - 1][1][1] + x0) / 2 if idx > 0 else x0 - _MARGEM_BORDA
            dir_ = (x1 + ordem[idx + 1][1][0]) / 2 if idx < len(ordem) - 1 else x1 + _MARGEM_BORDA
            faixas[chave] = (esq, dir_)
        return faixas

    @staticmethod
    def _extrair_linha(
        palavras_da_linha: list[dict], faixas: dict[str, FaixaX], grupo: Grupo,
        pagina: int, linha: int,
    ) -> ContaBalancete | None:
        colunas: dict[str, list[str]] = {k: [] for k in faixas}
        descricao_tokens: list[str] = []
        codigo: str | None = None
        limite_descricao = min(faixa[0] for faixa in faixas.values())

        for p in palavras_da_linha:
            centro = (p["x0"] + p["x1"]) / 2
            if centro < limite_descricao:
                if codigo is None and p["text"].isdigit():
                    codigo = p["text"]
                else:
                    descricao_tokens.append(p["text"])
                continue
            for chave, (esq, dir_) in faixas.items():
                if esq <= centro < dir_:
                    colunas[chave].append(p["text"])
                    break

        if codigo is None:
            return None

        try:
            saldo_anterior = to_saldo(" ".join(colunas["saldo_anterior"]) or "0,00")
            debito = to_decimal(" ".join(colunas["debito"]) or "0,00")
            credito = to_decimal(" ".join(colunas["credito"]) or "0,00")
            saldo_atual = to_saldo(" ".join(colunas["saldo_atual"]) or "0,00")
        except ValueError:
            return None

        return ContaBalancete(
            codigo=int(codigo), descricao=" ".join(descricao_tokens).strip(),
            grupo=grupo, saldo_anterior=saldo_anterior, debito=debito, credito=credito,
            saldo_atual=saldo_atual, pagina=pagina, linha=linha,
        )
