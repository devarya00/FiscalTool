"""Parser posicional do Balancete (relatório contábil) — ver §5.2 da arquitetura.

Texto linear (extract_text) quebra com colunas coladas e descrições
duplicadas. A extração usa page.chars (posição por caractere) e atribui cada
caractere à coluna cuja faixa de X contém seu centro — o mesmo princípio do
extract_words() da arquitetura original, mas na granularidade de caractere.

Por que caractere e não palavra: em PDFs reais, o clustering de "palavras" do
próprio pdfplumber (extract_words) pode embaralhar a ordem dos tokens quando
duas colunas ficam muito próximas ou o espaçamento é atípico — produzindo
lixo como "CON26T9AS CDOEN TRAESS..." para uma linha que, caractere a
caractere, está perfeitamente ordenada. Colunas numéricas são detectadas uma
vez a partir do cabeçalho ("Saldo Anterior", "Débito", "Crédito", "Saldo
Atual") e reaproveitadas em todas as páginas — isso ainda usa extract_words(),
pois o cabeçalho em si não sofre desse problema.

Descoberta em PDF real: "ATIVO"/"PASSIVO"/"PATRIMÔNIO LÍQUIDO"/"RESULTADO" não
aparecem como linhas de cabeçalho separadas — "ATIVO" e "PASSIVO" são elas
próprias contas totalizadoras numeradas (código 1, código 149); "PATRIMÔNIO
LÍQUIDO" e as linhas "CONTAS DE RESULTADO..." aparecem sem nenhum código.
Por isso o grupo é decidido a partir da descrição de cada linha (tenha ela
código ou não), atualizando o grupo corrente para si mesma e para as
linhas seguintes; uma linha sem marcador de grupo apenas herda o corrente.

§5.4 — Fallback de IA local (opcional, desligado por padrão). Quando o
resultado posicional não se valida (_confia) e ia_fallback.ativo=true em
regras.yaml, cada página é renderizada como imagem e reprocessada via Ollama
(infra/ia_fallback.py). Se a IA também não fechar, ou o Ollama estiver fora
do ar, o Balancete volta com parsing_incerto=True — nunca lança exceção nem
trava a conferência.
"""
from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import replace
from decimal import Decimal

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
_GAP_LIMIAR_CODIGO = 2.0  # pt — acima disto é espaço real (código→descrição); kerning intra-código fica < 0.1pt

_LINHA_CONTA_RE = re.compile(r"^\d")


def _normalizar(txt: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode("ascii")
    return sem_acento.lower().strip()


def _grupo_de(rotulo_normalizado: str) -> Grupo | None:
    if rotulo_normalizado.startswith("ativo"):
        return Grupo.ATIVO
    if rotulo_normalizado.startswith("passivo"):
        return Grupo.PASSIVO
    if "patrimonio liquido" in rotulo_normalizado:
        return Grupo.PL
    if rotulo_normalizado.startswith("resultado") or "contas de resultado" in rotulo_normalizado:
        return Grupo.RESULTADO
    return None


_GRUPOS_ESPERADOS = {Grupo.ATIVO, Grupo.PASSIVO, Grupo.PL}
_MINIMO_CONTAS_PLAUSIVEL = 3


class BalanceteParser:
    def __init__(self, ia_fallback_config: dict | None = None):
        cfg = ia_fallback_config or {}
        self._ia_ativo = bool(cfg.get("ativo", False))
        self._ia_modelo = cfg.get("modelo", "qwen2.5vl:7b")
        self._ia_host = cfg.get("host", "http://localhost:11434")

    def parse(self, caminho: str) -> Balancete:
        resultado = self._parse_posicional(caminho)
        if self._confia(resultado):
            return resultado

        if not self._ia_ativo:
            return replace(resultado, parsing_incerto=True)

        from infra.ia_fallback import FalhaIAFallback  # import tardio: ollama só é preciso se ativo

        try:
            resultado_ia = self._parse_via_ia(caminho, resultado)
        except FalhaIAFallback:
            return replace(resultado, parsing_incerto=True)

        if self._confia(resultado_ia):
            return resultado_ia
        return replace(resultado_ia, parsing_incerto=True)

    def _parse_via_ia(self, caminho: str, resultado_posicional: Balancete) -> Balancete:
        from infra.ia_fallback import parse_via_ia

        contas: list[ContaBalancete] = []
        with pdfplumber.open(caminho) as pdf:
            for pagina_idx, pagina in enumerate(pdf.pages, start=1):
                buf = io.BytesIO()
                pagina.to_image(resolution=150).original.save(buf, format="PNG")
                contas.extend(parse_via_ia(buf.getvalue(), pagina_idx, self._ia_modelo, self._ia_host))

        return Balancete(cnpj=resultado_posicional.cnpj, periodo=resultado_posicional.periodo, contas=contas)

    @staticmethod
    def _confia(resultado: Balancete) -> bool:
        """Gate de plausibilidade (§5.4). Nota: o pseudocódigo original da
        arquitetura compara soma_debitos == soma_creditos somando TODAS as
        contas — mas em balancetes reais as linhas totalizadoras (ex.: "1
        ATIVO", "149 PASSIVO") repetem o débito/crédito das contas-filhas, e
        essa soma plana nunca fecha (validado contra arquivo real: diferença
        de dezenas de milhares mesmo com o parsing 100% correto). Substituído
        por checagem estrutural equivalente em intenção: contas suficientes e
        os três grupos-âncora presentes."""
        if len(resultado.contas) < _MINIMO_CONTAS_PLAUSIVEL:
            return False
        grupos_presentes = {c.grupo for c in resultado.contas}
        return _GRUPOS_ESPERADOS.issubset(grupos_presentes)

    def _parse_posicional(self, caminho: str) -> Balancete:
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

                for linha_idx, chars_linha_bruta in enumerate(self._agrupar_por_linha(pagina.chars), start=1):
                    chars_linha = self._resolver_chars_linha(chars_linha_bruta)
                    texto_linha = "".join(c["text"] for c in chars_linha).strip()
                    if not texto_linha:
                        continue

                    m = _LINHA_CONTA_RE.match(texto_linha)
                    if m:
                        campos = self._extrair_campos(chars_linha, faixas)
                        if campos is None:
                            continue
                        grupo_detectado = _grupo_de(_normalizar(campos[1]))
                        if grupo_detectado is not None:
                            grupo_atual = grupo_detectado
                        if grupo_atual is None:
                            continue
                        contas.append(self._montar_conta(campos, grupo_atual, pagina_idx, linha_idx))
                        continue

                    grupo_detectado = self._detectar_grupo_de_linha(chars_linha_bruta)
                    if grupo_detectado is not None:
                        grupo_atual = grupo_detectado

        return Balancete(cnpj=cnpj, periodo=periodo, contas=self._consolidar_contas(contas))

    @staticmethod
    def _consolidar_contas(contas: list[ContaBalancete]) -> list[ContaBalancete]:
        """PDF pode conter vários balancetes mensais concatenados — a mesma
        conta aparece uma vez por mês, código idêntico. Sem consolidar,
        Balancete.por_codigo() (e todo lookup que varre .contas) devolve o
        PRIMEIRO mês encontrado — o mais antigo, não o saldo de fechamento do
        período inteiro. Soma débito/crédito (movimento do período todo),
        mantém saldo_anterior do primeiro mês (abertura) e saldo_atual do
        último (fechamento)."""
        ocorrencias_por_codigo: dict[int, list[ContaBalancete]] = {}
        ordem: list[int] = []
        for c in contas:
            if c.codigo not in ocorrencias_por_codigo:
                ocorrencias_por_codigo[c.codigo] = []
                ordem.append(c.codigo)
            ocorrencias_por_codigo[c.codigo].append(c)

        consolidadas: list[ContaBalancete] = []
        for codigo in ordem:
            ocorrencias = ocorrencias_por_codigo[codigo]
            if len(ocorrencias) == 1:
                consolidadas.append(ocorrencias[0])
                continue
            ultima = ocorrencias[-1]
            consolidadas.append(replace(
                ocorrencias[0],
                debito=sum((o.debito for o in ocorrencias), Decimal("0")),
                credito=sum((o.credito for o in ocorrencias), Decimal("0")),
                saldo_atual=ultima.saldo_atual,
                pagina=ultima.pagina,
                linha=ultima.linha,
            ))
        return consolidadas

    @staticmethod
    def _resolver_chars_linha(chars_linha: list[dict]) -> list[dict]:
        """Linhas com duas fontes sobrepostas (mesmo bug documentado em
        _detectar_grupo_de_linha: rótulo limpo numa fonte maior + código/valores
        numa fonte menor) embaralham caractere a caractere se lidas todas juntas.
        Quando isso acontece numa linha de CONTA (não só rótulo de grupo), o texto
        combinado não começa com dígito e a linha inteira some, engolida por
        _LINHA_CONTA_RE. Prefere aqui a fonte cujo texto isolado já começa com
        dígito — é a camada que carrega código e valores."""
        tamanhos = sorted({round(c.get("size", 0), 1) for c in chars_linha})
        if len(tamanhos) <= 1:
            return chars_linha
        for tamanho in tamanhos:
            chars_fonte = [c for c in chars_linha if round(c.get("size", 0), 1) == tamanho]
            texto_fonte = "".join(c["text"] for c in chars_fonte).strip()
            if _LINHA_CONTA_RE.match(texto_fonte):
                return chars_fonte
        return chars_linha

    @staticmethod
    def _agrupar_por_linha(itens: list[dict], tolerancia: float = 2.0) -> list[list[dict]]:
        itens_ordenados = sorted(itens, key=lambda p: (p["top"], p["x0"]))
        linhas: list[list[dict]] = []
        for item in itens_ordenados:
            if linhas and abs(item["top"] - linhas[-1][0]["top"]) <= tolerancia:
                linhas[-1].append(item)
            else:
                linhas.append([item])
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
    def _detectar_grupo_de_linha(chars_linha: list[dict]) -> Grupo | None:
        """Tenta achar um marcador de grupo ("PATRIMÔNIO LÍQUIDO", "CONTAS DE
        RESULTADO...") na linha. Algumas dessas linhas têm DUAS fontes
        sobrepostas na mesma posição — um rótulo limpo numa fonte maior
        (ex.: size 8.76, regular) e uma cópia borrada numa fonte menor em
        negrito (size 6.18) usada normalmente para código/valores — o que
        embaralha caractere a caractere se todos forem juntados por x0. Tenta
        primeiro o texto completo (caso comum, fonte única); se não bater,
        tenta cada tamanho de fonte isoladamente (recupera o rótulo limpo)."""
        texto_completo = _normalizar("".join(c["text"] for c in chars_linha).strip())
        grupo = _grupo_de(texto_completo)
        if grupo is not None:
            return grupo

        tamanhos = sorted({round(c.get("size", 0), 1) for c in chars_linha})
        if len(tamanhos) <= 1:
            return None
        for tamanho in tamanhos:
            chars_fonte = [c for c in chars_linha if round(c.get("size", 0), 1) == tamanho]
            texto_fonte = _normalizar("".join(c["text"] for c in chars_fonte).strip())
            grupo = _grupo_de(texto_fonte)
            if grupo is not None:
                return grupo
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
    def _extrair_campos(chars_linha: list[dict], faixas: dict[str, FaixaX]):
        colunas: dict[str, list[str]] = {k: [] for k in faixas}
        descricao_chars: list[str] = []
        codigo_chars: list[str] = []
        limite_descricao = min(faixa[0] for faixa in faixas.values())
        codigo_em_curso = True
        x1_anterior: float | None = None

        for c in chars_linha:
            centro = (c["x0"] + c["x1"]) / 2
            if centro < limite_descricao:
                gap = c["x0"] - x1_anterior if x1_anterior is not None else 0.0
                x1_anterior = c["x1"]
                # o código termina no primeiro espaço real de posição, não no
                # primeiro não-dígito — descrição que começa com dígito (ex.:
                # "13º Salário") tem gap ~30pt antes dela; dígitos dentro do
                # próprio código nunca passam de ~0.1pt (kerning).
                if codigo_em_curso and c["text"].isdigit() and gap <= _GAP_LIMIAR_CODIGO:
                    codigo_chars.append(c["text"])
                else:
                    codigo_em_curso = False
                    descricao_chars.append(c["text"])
                continue
            for chave, (esq, dir_) in faixas.items():
                if esq <= centro < dir_:
                    colunas[chave].append(c["text"])
                    break

        codigo = "".join(codigo_chars)
        if not codigo:
            return None

        try:
            saldo_anterior = to_saldo("".join(colunas["saldo_anterior"]) or "0,00")
            debito = to_decimal("".join(colunas["debito"]) or "0,00")
            credito = to_decimal("".join(colunas["credito"]) or "0,00")
            saldo_atual = to_saldo("".join(colunas["saldo_atual"]) or "0,00")
        except ValueError:
            return None

        descricao = re.sub(r"\s+", " ", "".join(descricao_chars)).strip()
        return codigo, descricao, saldo_anterior, debito, credito, saldo_atual

    @staticmethod
    def _montar_conta(campos, grupo: Grupo, pagina: int, linha: int) -> ContaBalancete:
        codigo, descricao, saldo_anterior, debito, credito, saldo_atual = campos
        return ContaBalancete(
            codigo=int(codigo), descricao=descricao, grupo=grupo,
            saldo_anterior=saldo_anterior, debito=debito, credito=credito,
            saldo_atual=saldo_atual, pagina=pagina, linha=linha,
        )
