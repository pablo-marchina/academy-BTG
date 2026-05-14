from __future__ import annotations
import logging

from ..state import PipelineState

logger = logging.getLogger(__name__)


def node_sintetizar(state: PipelineState) -> PipelineState:
    ofertas = state.get("ofertas_normalizadas", state.get("ofertas", []))
    macro = state.get("macro", {})
    scores = state.get("analise", {}).get("scores", [])
    extracoes = state.get("extracoes", [])
    n_analisadas = len(ofertas)

    linhas = [
        f"Pipeline concluido: {n_analisadas} ofertas analisadas.",
        f"SELIC: {macro.get('selic_atual', 'N/D')}% | IPCA 12m: {macro.get('ipca_12m', 'N/D')}%",
    ]

    if n_analisadas:
        por_produto = {}
        for o in ofertas:
            p = o.get("produto", "outro")
            por_produto[p] = por_produto.get(p, 0) + 1
        linhas.append("Breakdown: " + ", ".join(f"{k}={v}" for k, v in sorted(por_produto.items())))

        scores_validos = [s for s in scores if s.get("score_total", 0) > 0]
        if scores_validos:
            media = sum(s["score_total"] for s in scores_validos) / len(scores_validos)
            melhor = max(scores_validos, key=lambda s: s["score_total"])
            linhas.append(f"Score medio: {media:.1f} | Melhor: {melhor['score_total']:.1f}")

    if extracoes:
        sucessos = sum(1 for e in extracoes if e.get("sucesso"))
        linhas.append(f"Extracoes PDF: {sucessos}/{len(extracoes)}")

    detectacoes = state.get("detectacoes_pre_publica", [])
    if detectacoes:
        linhas.append(f"Deteccoes pre-publica: {len(detectacoes)}")

    erros = state.get("erros", [])
    if erros:
        linhas.append(f"Erros: {len(erros)}")

    state["analise"]["resumo"] = "\n".join(linhas)
    return state
