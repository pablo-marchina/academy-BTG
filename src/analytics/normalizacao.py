from __future__ import annotations
import re
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# IR regressivo por prazo (Res. 15827/2018): aliquota por faixa de dias
TABELA_IR = [
    (180, 22.5),
    (360, 20.0),
    (720, 17.5),
    (float("inf"), 15.0),
]

# Produtos isentos de IR para pessoa física
PRODUTOS_ISENTOS = {"lci", "lca", "cra", "cri"}


def normalizar_taxa(taxa_raw: str, indexador: str) -> Dict[str, Optional[float]]:
    if not taxa_raw:
        return {"taxa_cdi": None, "taxa_ipca": None, "taxa_pre": None}

    taxa_raw = taxa_raw.strip().replace(",", ".").replace("%", "").strip()
    indexador = (indexador or "").upper().strip()

    resultado = {"taxa_cdi": None, "taxa_ipca": None, "taxa_pre": None}

    try:
        valor = float(taxa_raw)
    except ValueError:
        match = re.search(r"(\d+\.?\d*)", taxa_raw)
        if match:
            valor = float(match.group(1))
        else:
            return resultado

    if "CDI" in indexador:
        resultado["taxa_cdi"] = valor
        resultado["taxa_ipca"] = None
        resultado["taxa_pre"] = None if "PRÉ" not in indexador and "PRE" not in indexador else valor
    elif "IPCA" in indexador:
        resultado["taxa_ipca"] = valor
        resultado["taxa_cdi"] = None
    elif "SELIC" in indexador:
        resultado["taxa_cdi"] = valor * 0.935
        resultado["taxa_pre"] = None
    elif "IGPM" in indexador or "IGP-M" in indexador:
        resultado["taxa_pre"] = valor
    else:
        if any(p in indexador for p in ["PRÉ", "PRE", "PREFIXADO"]):
            resultado["taxa_pre"] = valor
        else:
            resultado["taxa_cdi"] = valor

    return resultado


def gross_up_ir(taxa: float, produto: str, prazo_dias: int = 365) -> Dict[str, float]:
    if produto.lower() in PRODUTOS_ISENTOS:
        return {"taxa_bruta": taxa, "taxa_liquida": taxa, "aliquota_ir": 0.0}

    aliquota = 15.0
    for limite, alq in TABELA_IR:
        if prazo_dias <= limite:
            aliquota = alq
            break

    taxa_liquida = taxa * (1 - aliquota / 100)
    return {
        "taxa_bruta": round(taxa, 4),
        "taxa_liquida": round(taxa_liquida, 4),
        "aliquota_ir": aliquota,
    }


def spread_vs_curva(
    taxa: float,
    indexador: str,
    prazo_meses: int,
    curvas: Dict[str, Any],
) -> Dict[str, Optional[float]]:
    indexador = (indexador or "").upper().strip()
    spread = None
    taxa_curva = None

    if "CDI" in indexador and "di_pre" in curvas:
        curva = curvas["di_pre"]
        if isinstance(curva, dict) and prazo_meses in curva:
            taxa_curva = curva[prazo_meses]
    elif "IPCA" in indexador and "ntnb" in curvas:
        curva = curvas["ntnb"]
        if isinstance(curva, dict) and prazo_meses in curva:
            taxa_curva = curva[prazo_meses]

    if taxa_curva is not None and taxa_curva != 0:
        spread = round((taxa - taxa_curva) * 100, 2)

    return {
        "spread_bps": spread,
        "taxa_curva": round(taxa_curva, 4) if taxa_curva is not None else None,
    }


def normalizar_oferta(
    oferta: Dict[str, Any],
    curvas: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    indexador = oferta.get("indexador", "")
    taxa_raw = oferta.get("taxa_raw", "")
    produto = oferta.get("produto", "")

    taxas = normalizar_taxa(taxa_raw, indexador)

    taxa = taxas.get("taxa_cdi") or taxas.get("taxa_ipca") or taxas.get("taxa_pre") or 0.0

    prazo_dias = 365
    venc = oferta.get("vencimento", "")
    if venc and len(str(venc)) >= 10:
        try:
            from datetime import datetime, date
            if isinstance(venc, date):
                prazo_dias = (venc - date.today()).days
            else:
                dv = datetime.strptime(str(venc)[:10], "%Y-%m-%d")
                prazo_dias = max((dv.date() - date.today()).days, 1)
        except ValueError:
            pass

    ir = gross_up_ir(taxa, produto, prazo_dias)

    resultado = {
        **taxas,
        **ir,
        "prazo_dias": prazo_dias,
        "prazo_meses": max(prazo_dias // 30, 1),
    }

    if curvas:
        spread = spread_vs_curva(
            taxa, indexador, resultado["prazo_meses"], curvas
        )
        resultado.update(spread)

    return resultado
