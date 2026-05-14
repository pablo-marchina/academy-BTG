from __future__ import annotations
import logging
from collections import defaultdict
from typing import List, Dict, Any, Optional

from ..db.engine import SessionLocal
from ..db.models import Oferta

logger = logging.getLogger(__name__)


class GraphRAG:
    """Grafo de conhecimento: Emissor --[emitiu]--> Oferta <--[coordenou]-- Coordenador"""

    def __init__(self):
        self._grafo: Dict[str, Dict[str, set]] = {
            "emissores": defaultdict(set),
            "ofertas": defaultdict(dict),
            "emissor_ofertas": defaultdict(set),
            "coordenador_ofertas": defaultdict(set),
            "emissor_coordenadores": defaultdict(set),
            "coordenador_emissores": defaultdict(set),
        }
        self._carregado = False

    def carregar(self):
        if self._carregado:
            return
        session = SessionLocal()
        try:
            ofertas = session.query(Oferta).all()
            for o in ofertas:
                emissor = (o.emissor or "").strip().upper()
                coordenador = (o.coordenador or "").strip().upper()
                codigo = o.codigo or o.id or ""

                if emissor:
                    self._grafo["emissores"][emissor]
                    self._grafo["emissor_ofertas"][emissor].add(codigo)
                    if coordenador:
                        self._grafo["emissor_coordenadores"][emissor].add(coordenador)

                if coordenador:
                    self._grafo["coordenador_ofertas"][coordenador].add(codigo)
                    if emissor:
                        self._grafo["coordenador_emissores"][coordenador].add(emissor)

                if codigo:
                    self._grafo["ofertas"][codigo] = {
                        "codigo": codigo,
                        "emissor": o.emissor or "",
                        "coordenador": o.coordenador or "",
                        "produto": o.produto or "",
                        "indexador": o.indexador or "",
                        "taxa_raw": o.taxa_raw or "",
                        "rating": o.rating or "",
                        "score": o.score_atratividade or 0,
                    }

            self._carregado = True
            logger.info(
                f"[GraphRAG] {len(self._grafo['emissores'])} emissores, "
                f"{len(self._grafo['coordenador_emissores'])} coordenadores, "
                f"{len(self._grafo['ofertas'])} ofertas"
            )
        finally:
            session.close()

    def ofertas_por_emissor(self, emissor: str) -> List[Dict[str, Any]]:
        self.carregar()
        codigos = self._grafo["emissor_ofertas"].get(emissor.upper().strip(), set())
        return [self._grafo["ofertas"].get(c, {}) for c in codigos if c in self._grafo["ofertas"]]

    def ofertas_por_coordenador(self, coordenador: str) -> List[Dict[str, Any]]:
        self.carregar()
        codigos = self._grafo["coordenador_ofertas"].get(coordenador.upper().strip(), set())
        return [self._grafo["ofertas"].get(c, {}) for c in codigos if c in self._grafo["ofertas"]]

    def coordenadores_do_emissor(self, emissor: str) -> List[str]:
        self.carregar()
        return list(self._grafo["emissor_coordenadores"].get(emissor.upper().strip(), set()))

    def emissores_do_coordenador(self, coordenador: str) -> List[str]:
        self.carregar()
        return list(self._grafo["coordenador_emissores"].get(coordenador.upper().strip(), set()))

    def ofertas_similares_por_rating(self, rating: str, limite: int = 10) -> List[Dict[str, Any]]:
        self.carregar()
        r = rating.upper().strip()[0:3]
        candidatas = []
        for codigo, oferta in self._grafo["ofertas"].items():
            if oferta.get("rating", "").upper().startswith(r):
                candidatas.append(oferta)
        candidatas.sort(key=lambda x: x.get("score", 0) or 0, reverse=True)
        return candidatas[:limite]

    def resumo_mercado(self) -> Dict[str, Any]:
        self.carregar()
        return {
            "total_emissores": len(self._grafo["emissores"]),
            "total_coordenadores": len(self._grafo["coordenador_emissores"]),
            "total_ofertas": len(self._grafo["ofertas"]),
            "top_coordenadores": sorted(
                [(k, len(v)) for k, v in self._grafo["coordenador_ofertas"].items()],
                key=lambda x: -x[1],
            )[:10],
            "top_emissores": sorted(
                [(k, len(v)) for k, v in self._grafo["emissor_ofertas"].items()],
                key=lambda x: -x[1],
            )[:10],
        }

    def graph_query(self, pergunta: str) -> str:
        self.carregar()
        q = pergunta.upper().strip()

        palavras_coordenador = ["coordenad", "lider", "banco", "distribuid"]
        palavras_emissor = ["emissor", "empresa", "companhia", "emissao"]
        palavras_rating = ["rating", "classificac"]
        palavras_produto = ["debenture", "cri", "cra", "cdb", "lci", "lca", "fii", "fip"]

        if any(p in q for p in palavras_coordenador):
            for nome in list(self._grafo["coordenador_emissores"].keys()):
                if nome[:min(len(nome), 10)] in q or any(
                    part in nome for part in q.split()
                ):
                    ofertas = self.ofertas_por_coordenador(nome)
                    return (
                        f"O coordenador {nome.title()} liderou "
                        f"{len(ofertas)} ofertas: "
                        + "; ".join(
                            f"{o.get('produto', '?')} de {o.get('emissor', '?')} "
                            f"({o.get('score', 0)} pts)"
                            for o in ofertas[:5]
                        )
                    )

        if any(p in q for p in palavras_emissor):
            for nome in list(self._grafo["emissores"].keys()):
                if nome[:min(len(nome), 10)] in q or any(
                    part in nome for part in q.split()
                ):
                    ofertas = self.ofertas_por_emissor(nome)
                    coords = self.coordenadores_do_emissor(nome)
                    return (
                        f"O emissor {nome.title()} tem {len(ofertas)} ofertas "
                        f"com os coordenadores: {', '.join(c.title() for c in coords)}. "
                        f"Melhor oferta: {ofertas[0].get('produto', '?')} "
                        f"score {ofertas[0].get('score', 0)}"
                        if ofertas
                        else f"O emissor {nome.title()} nao tem ofertas registradas."
                    )

        if any(p in q for p in palavras_rating):
            for r in ["AAA", "AA", "A", "BBB", "BB", "B", "CCC"]:
                if r in q:
                    similar = self.ofertas_similares_por_rating(r, 5)
                    if similar:
                        return (
                            f"Ofertas com rating {r}: "
                            + "; ".join(
                                f"{s.get('produto', '?')} de {s.get('emissor', '?')} "
                                f"coordenado por {s.get('coordenador', '?')} "
                                f"({s.get('score', 0)} pts)"
                                for s in similar
                            )
                        )

        if any(p in q for p in palavras_produto):
            for prod in palavras_produto:
                if prod in q:
                    session = SessionLocal()
                    try:
                        from sqlalchemy import func
                        ofertas = session.query(Oferta).filter(
                            Oferta.produto == prod,
                            Oferta.score_atratividade.isnot(None),
                        ).order_by(Oferta.score_atratividade.desc()).limit(5).all()
                        if ofertas:
                            return (
                                f"Top 5 {prod.upper()}: "
                                + "; ".join(
                                    f"{o.emissor} taxa {o.taxa_raw} "
                                    f"score {o.score_atratividade}"
                                    for o in ofertas
                                )
                            )
                    finally:
                        session.close()

        return self._resumo_generico()

    def _resumo_generico(self) -> str:
        r = self.resumo_mercado()
        return (
            f"Mercado possui {r['total_ofertas']} ofertas de "
            f"{r['total_emissores']} emissores e "
            f"{r['total_coordenadores']} coordenadores. "
            f"Top coordenadores: "
            + ", ".join(f"{n.title()} ({c} ofertas)" for n, c in r["top_coordenadores"][:5])
        )


_graphrag_instance: Optional[GraphRAG] = None


def get_graphrag() -> GraphRAG:
    global _graphrag_instance
    if _graphrag_instance is None:
        _graphrag_instance = GraphRAG()
    return _graphrag_instance
