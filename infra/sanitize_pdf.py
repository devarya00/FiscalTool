"""Sanitização de PDF via Ghostscript — reconstrói balancetes com colunas
aglutinadas e linhas fantasma (corrupção estrutural do sistema contábil de
origem) antes da extração posicional (infra/balancete_parser.py). Opcional:
falha aqui nunca deve travar a aplicação — o chamador decide se segue com o
PDF original ou aborta."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_TIMEOUT_SEGUNDOS = 60


class GhostscriptError(Exception):
    """Erro recuperável — chamador decide como degradar (ex.: seguir com o PDF original)."""

    def __init__(
        self, mensagem: str, *, codigo_saida: int | None = None, stderr: str = "", binario: str = "",
    ):
        super().__init__(mensagem)
        self.codigo_saida = codigo_saida
        self.stderr = stderr
        self.binario = binario


def _resolve_ghostscript_binary() -> str:
    """Dev (Arch Linux e demais não-Windows): usa `gs` do PATH. Produção (.exe
    PyInstaller no Windows): binário portátil embarcado em resources/ghostscript/win,
    desempacotado por PyInstaller em sys._MEIPASS (ver .spec: datas)."""
    if sys.platform != "win32":
        return "gs"  # ambiente de desenvolvimento — nunca roda assim em produção

    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS) / "resources" / "ghostscript" / "win"  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent.parent / "resources" / "ghostscript" / "win"

    binario = base / "bin" / "gswin64c.exe"
    if not binario.exists():
        raise GhostscriptError(
            f"Binário do Ghostscript não encontrado em: {binario}. "
            "Verifique se resources/ghostscript/win foi embutido no build (.spec: datas).",
            binario=str(binario),
        )
    return str(binario)


def sanitize_pdf(input_path: str | Path, output_path: str | Path) -> Path:
    """Reconstrói o PDF via Ghostscript (-dPDFSETTINGS=/prepress). Levanta
    GhostscriptError em qualquer falha (binário ausente, timeout, exit code != 0)
    — nunca deixa arquivo parcial/corrompido em output_path."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    if not input_path.exists():
        raise GhostscriptError(f"PDF de entrada não existe: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    binario = _resolve_ghostscript_binary()

    args = [
        binario,
        "-sDEVICE=pdfwrite",
        "-dPDFSETTINGS=/prepress",
        "-dCompatibilityLevel=1.5",
        "-dNOPAUSE",
        "-dBATCH",
        "-dSAFER",  # sandbox do próprio Ghostscript — bloqueia acesso a arquivos fora do esperado
        "-dQUIET",
        f"-sOutputFile={output_path}",
        str(input_path),
    ]

    try:
        resultado = subprocess.run(
            args, capture_output=True, text=True, timeout=_TIMEOUT_SEGUNDOS, check=False,
        )
    except FileNotFoundError as exc:
        raise GhostscriptError(
            f"Binário do Ghostscript não encontrado: {binario!r} "
            "(verifique o PATH em dev, ou o empacotamento em produção)",
            binario=binario,
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise GhostscriptError(
            f"Ghostscript excedeu o tempo limite de {_TIMEOUT_SEGUNDOS}s", binario=binario,
        ) from exc

    if resultado.returncode != 0:
        raise GhostscriptError(
            f"Ghostscript falhou (código {resultado.returncode})",
            codigo_saida=resultado.returncode, stderr=resultado.stderr, binario=binario,
        )

    if not output_path.exists():
        raise GhostscriptError(
            f"Ghostscript retornou código 0 mas não gerou o arquivo de saída: {output_path}",
            codigo_saida=0, stderr=resultado.stderr, binario=binario,
        )

    return output_path
