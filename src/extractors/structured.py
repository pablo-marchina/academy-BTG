from __future__ import annotations
import logging
import json
import re
from typing import Optional, List
from pathlib import Path

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from ..config import settings
from ..models.extracted import ProspectoExtraido, ExtracaoResult
from .prospecto import extrair_texto_pdf, amostrar_texto

logger = logging.getLogger(__name__)

SISTEMA_PROMPT = """Você é um especialista em prospectos de ofertas primárias de renda fixa brasileiras.
Extraia os campos estruturados do prospecto abaixo.

Regras:
- Se um campo não for encontrado, deixe vazio ou null
- Taxas percentuais: retorne como float (ex: 1.35 para "CDI + 1,35% a.a.")
- Prazos: converta para meses quando possível
- Volume: em reais (R$), como float
- Rating: normalize (AAA, AA+, AA, AA-, A+, A, A-, BBB+ etc.)
- Indexador: normalize para CDI, IPCA, PRE, SELIC, IGPM
- Produto: normalize para debenture, cri, cra, cdb, lci, lca, fii, fip
- Garantias: real, fidejussoria, flutuante, quirografaria, pessoal
- Covenants: lista de strings com descrições curtas
- confidence_score: 0-1 baseado na completeza e clareza dos dados encontrados

Responda APENAS com um JSON válido no formato especificado, sem texto extra."""

SYSTEM_PROMPT = SISTEMA_PROMPT


def extrair_prospecto(
    caminho_pdf: str,
    max_paginas: int = 50,
    modelo_llm: str = "llama-3.3-70b-versatile",
) -> ExtracaoResult:
    resultado = ExtracaoResult(
        caminho_pdf=caminho_pdf,
    )

    texto, total_pag, pag_extraidas = extrair_texto_pdf(caminho_pdf, max_paginas)
    resultado.paginas_total = total_pag
    resultado.paginas_extraidas = pag_extraidas
    resultado.tamanho_texto = len(texto)
    resultado.texto_amostra = amostrar_texto(texto, 2000)

    if not texto.strip():
        resultado.extraido.erros.append("Texto vazio extraído do PDF")
        return resultado

    if not settings.GROQ_API_KEY:
        resultado.extraido.erros.append("GROQ_API_KEY não configurada")
        return resultado

    try:
        llm = ChatGroq(model=modelo_llm, temperature=0)

        schema_json = ProspectoExtraido.model_json_schema()

        prompt = f"""Extraia os seguintes campos do prospecto abaixo e retorne UM JSON válido.

Schema esperado:
```json
{json.dumps(schema_json, indent=2, ensure_ascii=False)}
```

PROSPECTO:
{amostrar_texto(texto, 8000)}

Retorne APENAS o JSON, sem texto adicional."""

        resposta = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])

        raw = resposta.content.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        dados = json.loads(raw)
        extraido = ProspectoExtraido(**dados)
        resultado.extraido = extraido
        resultado.sucesso = True

        logger.info(
            f"[Extrair] {Path(caminho_pdf).name}: {extraido.emissor} | "
            f"{extraido.produto} | {extraido.indexador} | "
            f"confiança={extraido.confidence_score:.2f}"
        )

    except json.JSONDecodeError as e:
        resultado.extraido.erros.append(f"Erro decodificando JSON: {e}")
        logger.error(f"[Extrair] JSON mal formatado: {e}")
    except Exception as e:
        resultado.extraido.erros.append(str(e))
        logger.error(f"[Extrair] Erro: {e}")

    return resultado


def extrair_prospecto_batch(
    caminhos_pdf: List[str],
    max_paginas: int = 30,
    max_concurrent: int = 3,
) -> List[ExtracaoResult]:
    import asyncio

    async def _extrair(caminho: str) -> ExtracaoResult:
        return extrair_prospecto(caminho, max_paginas)

    async def _batch():
        sem = asyncio.Semaphore(max_concurrent)

        async def _limitada(caminho: str):
            async with sem:
                return await _extrair(caminho)

        tarefas = [_limitada(c) for c in caminhos_pdf]
        return await asyncio.gather(*tarefas, return_exceptions=True)

    resultados = asyncio.run(_batch())
    final = []
    for r in resultados:
        if isinstance(r, Exception):
            logger.error(f"[Extrair] Erro batch: {r}")
        else:
            final.append(r)
    return final
