"""Parser do Resumo por Acumulador (relatório fiscal).

Descoberta em PDF real (não estava prevista na arquitetura original): quando a
descrição do acumulador é longa, ela invade fisicamente a coluna "Vlr
Contábil" adjacente. O pdfplumber, ao clusterizar caracteres em "palavras",
intercala caractere a caractere as duas correntes de texto sobrepostas —
"COMPRA...A PRAZO" + "10.782,39" viram um único token "P1R0A.Z7O82,39".

Extração linear (extract_text/extract_words) não sobrevive a isso. A correção
usa page.chars (posição por caractere, não por palavra) e separa as duas
correntes por classe de caractere: dígitos/'.'/',' → valor; o resto →
descrição — preservando a ordem x0 de cada corrente. Mesmo princípio
posicional do BalanceteParser (§5.2).

ENTRADAS e SERVIÇOS têm layouts de coluna diferentes na mesma página, cada
um com seu próprio cabeçalho — por isso as faixas de coluna são recalculadas
a cada cabeçalho de seção encontrado, não uma vez por página.
"""
from __future__ import annotations

import re
from decimal import Decimal

import pdfplumber

from dominio.modelos import Acumulador, RelatorioFiscal, Secao
from infra.normalizador import extrair_cnpj, parse_periodo, to_decimal

_SECAO_RE = re.compile(r"^(ENTRADAS|SA[ÍI]DAS|SERVI[ÇC]OS)\b", re.IGNORECASE)
_TOTAL_RE = re.compile(r"^TOTAL\b", re.IGNORECASE)
_VALOR_RE = re.compile(r"[\d.]+,\d{2}")
_CABECALHO_CODIGO_RE = re.compile(r"^(C[oó]digo|C[oó]d)$", re.IGNORECASE)
_CABECALHO_VLR_RE = re.compile(r"^vlr$", re.IGNORECASE)
_CABECALHO_CONTABIL_RE = re.compile(r"^cont[aá]bil$", re.IGNORECASE)

_MAPA_SECAO = {
    "entradas": Secao.ENTRADAS,
    "saidas": Secao.SAIDAS,
    "saídas": Secao.SAIDAS,
    "servicos": Secao.SERVICOS,
    "serviços": Secao.SERVICOS,
}

_VALOR_CHARS = set("0123456789.,")


class FiscalParser:
    def parse(self, caminho: str) -> RelatorioFiscal:
        with pdfplumber.open(caminho) as pdf:
            texto_completo = "\n".join(p.extract_text() or "" for p in pdf.pages)
            cnpj = extrair_cnpj(texto_completo)
            if cnpj is None:
                raise ValueError("CNPJ não encontrado no Resumo por Acumulador")
            periodo = parse_periodo(texto_completo)

            entradas: list[Acumulador] = []
            saidas: list[Acumulador] = []
            servicos: list[Acumulador] = []
            total_servicos = None
            secao_atual: Secao | None = None

            for pagina_idx, pagina in enumerate(pdf.pages, start=1):
                cabecalhos = self._localizar_cabecalhos_coluna(pagina)
                colunas_atuais: tuple[float, float] | None = None

                for linha_idx, chars_linha in enumerate(self._agrupar_por_linha(pagina.chars), start=1):
                    top_linha = chars_linha[0]["top"]
                    for top_cab, margem, fim in cabecalhos:
                        if top_cab <= top_linha + 1.0:
                            colunas_atuais = (margem, fim)
                        else:
                            break

                    # "Total:" costuma começar mais à esquerda que a coluna de
                    # código (x0 perto de 0) — detecção de seção/total usa a
                    # linha SEM o corte de margem, que só serve para descartar
                    # anotações marginais na hora de extrair código/descrição.
                    texto_linha_completo = "".join(c["text"] for c in chars_linha).strip()
                    if not texto_linha_completo:
                        continue

                    m_secao = _SECAO_RE.match(texto_linha_completo)
                    if m_secao:
                        secao_atual = _MAPA_SECAO[m_secao.group(1).lower()]
                        continue

                    if secao_atual is None or colunas_atuais is None:
                        continue

                    if _TOTAL_RE.match(texto_linha_completo):
                        if secao_atual is Secao.SERVICOS:
                            m_valor = _VALOR_RE.search(texto_linha_completo)
                            if m_valor:
                                total_servicos = to_decimal(m_valor.group(0))
                        continue

                    margem_esquerda = colunas_atuais[0]
                    chars_filtrados = [c for c in chars_linha if c["x0"] >= margem_esquerda]
                    resultado = self._extrair_linha(chars_filtrados, colunas_atuais[1])
                    if resultado is None:
                        continue
                    codigo, descricao, valor = resultado

                    ac = Acumulador(
                        codigo=codigo, descricao=descricao, valor_contabil=valor,
                        secao=secao_atual, pagina=pagina_idx, linha=linha_idx,
                    )
                    {
                        Secao.ENTRADAS: entradas, Secao.SAIDAS: saidas, Secao.SERVICOS: servicos,
                    }[secao_atual].append(ac)

        return RelatorioFiscal(
            cnpj=cnpj, periodo=periodo, entradas=entradas, saidas=saidas,
            servicos=servicos, total_servicos=total_servicos,
        )

    @staticmethod
    def _agrupar_por_linha(chars: list[dict], tolerancia: float = 2.0) -> list[list[dict]]:
        chars_ordenados = sorted(chars, key=lambda c: (c["top"], c["x0"]))
        linhas: list[list[dict]] = []
        for c in chars_ordenados:
            if linhas and abs(c["top"] - linhas[-1][0]["top"]) <= tolerancia:
                linhas[-1].append(c)
            else:
                linhas.append([c])
        for linha in linhas:
            linha.sort(key=lambda c: c["x0"])
        return linhas

    def _localizar_cabecalhos_coluna(self, pagina) -> list[tuple[float, float, float]]:
        """Retorna [(top, margem_esquerda_codigo, fim_zona_valor), ...] — um
        registro por cabeçalho de coluna encontrado na página (ENTRADAS e
        SERVIÇOS têm o seu próprio), ordenado por top."""
        palavras = pagina.extract_words()
        linhas_palavras = self._agrupar_palavras_por_linha(palavras)

        resultado: list[tuple[float, float, float]] = []
        for linha in linhas_palavras:
            idx_codigo = next((i for i, p in enumerate(linha) if _CABECALHO_CODIGO_RE.match(p["text"])), None)
            if idx_codigo is None:
                continue
            idx_vlr = next(
                (i for i, p in enumerate(linha)
                 if _CABECALHO_VLR_RE.match(p["text"]) and i + 1 < len(linha)
                 and _CABECALHO_CONTABIL_RE.match(linha[i + 1]["text"])),
                None,
            )
            if idx_vlr is None or idx_vlr + 2 >= len(linha):
                continue
            top = linha[idx_codigo]["top"]
            margem = linha[idx_codigo]["x0"] - 3.0
            fim = linha[idx_vlr + 2]["x0"]
            resultado.append((top, margem, fim))

        resultado.sort(key=lambda r: r[0])
        return resultado

    @staticmethod
    def _agrupar_palavras_por_linha(palavras: list[dict], tolerancia: float = 2.0) -> list[list[dict]]:
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

    @staticmethod
    def _extrair_linha(chars_zona: list[dict], fim_zona_valor: float) -> tuple[str, str, Decimal] | None:
        chars_mistos = [c for c in chars_zona if c["x0"] < fim_zona_valor]
        if not chars_mistos:
            return None

        i = 0
        digitos_codigo = []
        while i < len(chars_mistos) and chars_mistos[i]["text"].isdigit():
            digitos_codigo.append(chars_mistos[i]["text"])
            i += 1
        if not digitos_codigo:
            return None
        codigo = "".join(digitos_codigo)

        descricao_chars: list[str] = []
        valor_chars: list[str] = []
        for c in chars_mistos[i:]:
            if c["text"] in _VALOR_CHARS:
                valor_chars.append(c["text"])
            else:
                descricao_chars.append(c["text"])

        descricao = re.sub(r"\s+", " ", "".join(descricao_chars)).strip()
        valor_txt = "".join(valor_chars)
        if not descricao or not valor_txt:
            return None

        return codigo, descricao, to_decimal(valor_txt)
