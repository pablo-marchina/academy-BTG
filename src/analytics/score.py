from __future__ import annotations
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

PESOS = {
    "premio_curva": 0.30,
    "rating": 0.20,
    "garantia": 0.15,
    "liquidez": 0.10,
    "timing": 0.10,
    "origem": 0.10,
    "complexidade": 0.05,
}

RATING_PONTOS = {
    "AAA": 100, "AA+": 95, "AA": 90, "AA-": 85,
    "A+": 80, "A": 75, "A-": 70,
    "BBB+": 65, "BBB": 60, "BBB-": 55,
    "BB+": 45, "BB": 40, "BB-": 35,
    "B+": 25, "B": 20, "B-": 15,
    "CCC": 5, "CC": 3, "C": 1, "D": 0,
}

GARANTIA_PONTOS = {
    "real": 100,
    "fidejussoria": 70,
    "flutuante": 60,
    "pessoal": 50,
    "quirografaria": 30,
    "": 20,
}

PRODUTO_PESO_LIQUIDEZ = {
    "cdb": 80, "lci": 70, "lca": 70,
    "debenture": 60, "cri": 50, "cra": 50,
    "fii": 40, "fip": 30,
}

COORDENADOR_PESO = {
    "btg": 100, "xp": 95, "itaú": 90, "bradesco": 85,
    "santander": 80, "genial": 70,
}


def calcular_rating_pontos(rating: Optional[str]) -> float:
    if not rating:
        return 0
    r = rating.upper().strip()
    for chave, pts in RATING_PONTOS.items():
        if r == chave or r.startswith(chave):
            return pts
    return 0


def calcular_garantia_pontos(garantia: str) -> float:
    g = garantia.lower().strip()
    for chave, pts in GARANTIA_PONTOS.items():
        if chave and chave in g:
            return pts
    return GARANTIA_PONTOS.get("", 20)


def calcular_score(
    oferta: Dict[str, Any],
    normalizado: Optional[Dict[str, Any]] = None,
    contexto_macro: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    premio_curva = 0.0
    spread = None
    if normalizado:
        spread = normalizado.get("spread_bps")

    if spread is not None:
        if spread > 100:
            premio_curva = 100
        elif spread > 50:
            premio_curva = 80
        elif spread > 25:
            premio_curva = 60
        elif spread > 10:
            premio_curva = 40
        elif spread > 0:
            premio_curva = 20
        else:
            premio_curva = 0

    rating_str = oferta.get("rating")
    rating_pts = calcular_rating_pontos(rating_str)

    garantia = oferta.get("garantias", "")
    garantia_pts = calcular_garantia_pontos(garantia)

    produto = oferta.get("produto", "").lower()
    liquidez_pts = PRODUTO_PESO_LIQUIDEZ.get(produto, 50)

    timing_pts = 50.0
    if contexto_macro:
        selic = contexto_macro.get("selic_atual")
        ipca = contexto_macro.get("ipca_12m")
        regime = contexto_macro.get("regime_mercado", "")
        if selic and ipca:
            juro_real = selic - ipca
            if juro_real > 6:
                timing_pts = 70
            elif juro_real > 4:
                timing_pts = 60
            elif juro_real > 2:
                timing_pts = 50
            else:
                timing_pts = 30
        if "acomodação" in regime or "afrouxamento" in regime:
            timing_pts = min(timing_pts + 15, 100)
        elif "aperto" in regime:
            timing_pts = max(timing_pts - 10, 0)

    coordenador = oferta.get("coordenador", "") or ""
    origem_pts = 50
    for chave, pts in COORDENADOR_PESO.items():
        if chave in coordenador.lower():
            origem_pts = pts
            break

    complexidade_pts = 80.0
    erro_count = len(oferta.get("erros", [])) if isinstance(oferta.get("erros"), list) else 0
    if erro_count > 3:
        complexidade_pts = 40
    elif erro_count > 1:
        complexidade_pts = 60

    score_total = (
        premio_curva * PESOS["premio_curva"]
        + rating_pts * PESOS["rating"]
        + garantia_pts * PESOS["garantia"]
        + liquidez_pts * PESOS["liquidez"]
        + timing_pts * PESOS["timing"]
        + origem_pts * PESOS["origem"]
        + complexidade_pts * PESOS["complexidade"]
    )

    confidence_score = 1.0
    if not oferta.get("codigo"):
        confidence_score -= 0.2
    if not oferta.get("taxa_raw"):
        confidence_score -= 0.3
    if not oferta.get("vencimento"):
        confidence_score -= 0.15
    if erro_count > 0:
        confidence_score -= 0.1 * min(erro_count, 5)
    confidence_score = max(0.0, confidence_score)

    decomposicao = {
        "premio_curva": round(premio_curva * PESOS["premio_curva"], 1),
        "rating": round(rating_pts * PESOS["rating"], 1),
        "garantia": round(garantia_pts * PESOS["garantia"], 1),
        "liquidez": round(liquidez_pts * PESOS["liquidez"], 1),
        "timing": round(timing_pts * PESOS["timing"], 1),
        "origem": round(origem_pts * PESOS["origem"], 1),
        "complexidade": round(complexidade_pts * PESOS["complexidade"], 1),
    }

    return {
        "score_total": round(score_total, 1),
        "score_confianca": round(confidence_score, 2),
        "decomposicao": decomposicao,
        "componentes": {
            "premio_curva": premio_curva,
            "rating_pts": rating_pts,
            "garantia_pts": garantia_pts,
            "liquidez_pts": liquidez_pts,
            "timing_pts": timing_pts,
            "origem_pts": origem_pts,
            "complexidade_pts": complexidade_pts,
        },
        "spread_bps": spread,
        "rating": rating_str,
    }
