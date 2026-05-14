from __future__ import annotations
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

RATING_ESCALAS: Dict[str, Dict[str, int]] = {
    "standard & poors": {"AAA": 22, "AA+": 21, "AA": 20, "AA-": 19, "A+": 18, "A": 17, "A-": 16, "BBB+": 15, "BBB": 14, "BBB-": 13, "BB+": 12, "BB": 11, "BB-": 10, "B+": 9, "B": 8, "B-": 7, "CCC+": 6, "CCC": 5, "CCC-": 4, "CC": 3, "C": 2, "D": 1},
    "moodys": {"Aaa": 22, "Aa1": 21, "Aa2": 20, "Aa3": 19, "A1": 18, "A2": 17, "A3": 16, "Baa1": 15, "Baa2": 14, "Baa3": 13, "Ba1": 12, "Ba2": 11, "Ba3": 10, "B1": 9, "B2": 8, "B3": 7, "Caa1": 6, "Caa2": 5, "Caa3": 4, "Ca": 3, "C": 2},
    "fitch": {"AAA": 22, "AA+": 21, "AA": 20, "AA-": 19, "A+": 18, "A": 17, "A-": 16, "BBB+": 15, "BBB": 14, "BBB-": 13, "BB+": 12, "BB": 11, "BB-": 10, "B+": 9, "B": 8, "B-": 7, "CCC+": 6, "CCC": 5, "CCC-": 4, "CC": 3, "C": 2, "D": 1},
}

RATING_PADRAO_BR = {
    "AAA": 22, "AA+": 21, "AA": 20, "AA-": 19,
    "A+": 18, "A": 17, "A-": 16,
    "BBB+": 15, "BBB": 14, "BBB-": 13,
    "BB+": 12, "BB": 11, "BB-": 10,
    "B+": 9, "B": 8, "B-": 7,
    "CCC+": 6, "CCC": 5, "CCC-": 4,
    "CC": 3, "C": 2, "D": 1,
}

RATING_PADRAO_REVERSO = {v: k for k, v in RATING_PADRAO_BR.items()}


def padronizar_rating(
    rating_raw: Optional[str],
    agencia: Optional[str] = None,
) -> Dict[str, Any]:
    if not rating_raw:
        return {"rating_padrao": None, "rating_num": None, "agencia_detectada": None}

    rating_str = rating_raw.strip().upper()
    agencia_str = (agencia or "").lower().strip()

    for nome_agencia, escala in RATING_ESCALAS.items():
        if agencia_str and nome_agencia.startswith(agencia_str) or nome_agencia in agencia_str:
            if rating_str in escala:
                v = escala[rating_str]
                return {
                    "rating_padrao": RATING_PADRAO_REVERSO.get(v, rating_str),
                    "rating_num": v,
                    "agencia_detectada": nome_agencia,
                }

    if rating_str in RATING_PADRAO_BR:
        return {
            "rating_padrao": rating_str,
            "rating_num": RATING_PADRAO_BR[rating_str],
            "agencia_detectada": agencia or "nacional",
        }

    for prefixo, valor in sorted(RATING_PADRAO_BR.items(), key=lambda x: -x[1]):
        if rating_str.startswith(prefixo):
            return {
                "rating_padrao": prefixo,
                "rating_num": valor,
                "agencia_detectada": agencia or "desconhecida",
            }

    return {"rating_padrao": rating_raw, "rating_num": None, "agencia_detectada": agencia}


def enriquecer_com_rating(
    oferta: Dict[str, Any],
) -> Dict[str, Any]:
    rating_raw = oferta.get("rating")
    agencia = oferta.get("rating_agencia")
    resultado = padronizar_rating(rating_raw, agencia)
    return {**oferta, **{f"rating_{k}": v for k, v in resultado.items()}}
