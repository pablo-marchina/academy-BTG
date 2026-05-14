from __future__ import annotations
import logging
import subprocess
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)


def extrair_texto_ocr(caminho_pdf: str, max_paginas: int = 10) -> Tuple[str, int]:
    caminho = Path(caminho_pdf)
    if not caminho.exists():
        return "", 0

    try:
        import fitz
        doc = fitz.open(str(caminho))
        total = len(doc)
        paginas = min(total, max_paginas)

        imagens = []
        for i in range(paginas):
            pix = doc[i].get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            imagens.append(img_bytes)
        doc.close()

        import pytesseract
        from PIL import Image
        import io

        textos = []
        for img_bytes in imagens:
            img = Image.open(io.BytesIO(img_bytes))
            texto = pytesseract.image_to_string(img, lang="por")
            textos.append(texto)

        texto_completo = "\n".join(textos)
        logger.info(f"[OCR] {caminho.name}: {total}pgs, OCR {paginas}pgs, {len(texto_completo)} chars")
        return texto_completo, total

    except ImportError as e:
        logger.warning(f"[OCR] Dependencia faltando: {e}")
        return "", 0
    except Exception as e:
        logger.error(f"[OCR] Erro: {e}")
        return "", 0


def extrair_com_fallback(caminho_pdf: str, max_paginas: int = 30) -> str:
    from .prospecto import extrair_texto_pdf

    texto, total, lidas = extrair_texto_pdf(caminho_pdf, max_paginas)
    if texto.strip() and len(texto) > 100:
        return texto

    logger.info(f"[OCR] Fallback para OCR: {caminho_pdf}")
    texto_ocr, _ = extrair_texto_ocr(caminho_pdf, max_paginas)
    return texto_ocr if texto_ocr else texto
