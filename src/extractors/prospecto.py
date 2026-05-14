from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)


def extrair_texto_pdf(caminho: str, max_paginas: int = 50) -> Tuple[str, int, int]:
    caminho = Path(caminho)
    if not caminho.exists():
        logger.error(f"PDF não encontrado: {caminho}")
        return "", 0, 0

    try:
        import fitz
        doc = fitz.open(str(caminho))
        total = len(doc)
        paginas_ler = min(total, max_paginas)
        partes = []
        for i in range(paginas_ler):
            texto = doc[i].get_text()
            if texto.strip():
                partes.append(texto)
        doc.close()
        texto = "\n".join(partes)
        logger.info(f"[PDF] {caminho.name}: {total}pgs, extraídas {paginas_ler}, {len(texto)} chars")
        return texto, total, paginas_ler
    except ImportError:
        logger.warning("PyMuPDF não instalado, tentando pdfplumber...")
    except Exception as e:
        logger.warning(f"PyMuPDF falhou para {caminho.name}: {e}")

    try:
        import pdfplumber
        with pdfplumber.open(str(caminho)) as pdf:
            total = len(pdf.pages)
            paginas_ler = min(total, max_paginas)
            partes = []
            for i in range(paginas_ler):
                texto = pdf.pages[i].extract_text() or ""
                if texto.strip():
                    partes.append(texto)
        texto = "\n".join(partes)
        logger.info(f"[PDF] {caminho.name}: {total}pgs, extraídas {paginas_ler}, {len(texto)} chars")
        return texto, total, paginas_ler
    except Exception as e:
        logger.error(f"pdfplumber falhou para {caminho.name}: {e}")
        return "", 0, 0


def extrair_tabelas_pdf(caminho: str, max_paginas: int = 30) -> List[dict]:
    tabelas = []
    try:
        import pdfplumber
        with pdfplumber.open(str(caminho)) as pdf:
            for i, pagina in enumerate(pdf.pages):
                if i >= max_paginas:
                    break
                tabs = pagina.extract_tables()
                for t in tabs:
                    if t:
                        cabecalho = t[0]
                        linhas = t[1:] if len(t) > 1 else []
                        tabelas.append({
                            "pagina": i + 1,
                            "cabecalho": cabecalho,
                            "linhas": linhas[:20],
                        })
    except Exception as e:
        logger.warning(f"Extração de tabelas falhou: {e}")
    return tabelas


def amostrar_texto(texto: str, max_chars: int = 3000) -> str:
    if len(texto) <= max_chars:
        return texto
    inicio = texto[: max_chars // 2]
    fim = texto[-(max_chars // 2):]
    return inicio + "\n\n[... TRUNCADO ...]\n\n" + fim
