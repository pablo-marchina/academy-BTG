from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class PerfilInvestidor:
    def __init__(
        self,
        nome: str = "",
        tolerancia_risco: str = "moderado",
        prazo_preferido_meses: int = 24,
        produto_preferido: str = "",
        indexador_preferido: str = "",
        taxa_minima_cdi: float = 0.0,
        taxa_minima_ipca: float = 0.0,
        rating_minimo: str = "",
        restricoes: Optional[List[str]] = None,
        apenas_isento_ir: bool = False,
        volume_maximo_mm: Optional[float] = None,
    ):
        self.nome = nome
        self.tolerancia_risco = tolerancia_risco
        self.prazo_preferido_meses = prazo_preferido_meses
        self.produto_preferido = produto_preferido
        self.indexador_preferido = indexador_preferido
        self.taxa_minima_cdi = taxa_minima_cdi
        self.taxa_minima_ipca = taxa_minima_ipca
        self.rating_minimo = rating_minimo
        self.restricoes = restricoes or []
        self.apenas_isento_ir = apenas_isento_ir
        self.volume_maximo_mm = volume_maximo_mm

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def conservador(cls) -> "PerfilInvestidor":
        return cls(
            nome="Conservador",
            tolerancia_risco="baixo",
            prazo_preferido_meses=12,
            produto_preferido="cdb",
            indexador_preferido="cdi+",
            taxa_minima_cdi=1.0,
            rating_minimo="AA",
            apenas_isento_ir=False,
        )

    @classmethod
    def moderado(cls) -> "PerfilInvestidor":
        return cls(
            nome="Moderado",
            tolerancia_risco="moderado",
            prazo_preferido_meses=24,
            indexador_preferido="ipca+",
            taxa_minima_cdi=1.2,
            taxa_minima_ipca=4.0,
            rating_minimo="A",
            apenas_isento_ir=False,
        )

    @classmethod
    def arrojado(cls) -> "PerfilInvestidor":
        return cls(
            nome="Arrojado",
            tolerancia_risco="alto",
            prazo_preferido_meses=36,
            produto_preferido="debenture",
            indexador_preferido="ipca+",
            taxa_minima_cdi=1.5,
            taxa_minima_ipca=5.0,
            rating_minimo="BBB",
            apenas_isento_ir=False,
        )


RATING_ORDEM = {
    "AAA": 10, "AA+": 9, "AA": 8, "AA-": 7,
    "A+": 6, "A": 5, "A-": 4,
    "BBB+": 3, "BBB": 2, "BBB-": 1,
}


def _rating_num(rating: Optional[str]) -> int:
    if not rating:
        return 0
    r = rating.upper().strip()
    for chave, val in RATING_ORDEM.items():
        if r == chave or r.startswith(chave):
            return val
    return 0


def calcular_match(
    oferta: Dict[str, Any],
    perfil: PerfilInvestidor,
    normalizado: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    score = 100.0
    rejeicoes = []
    avisos = []

    produto = oferta.get("produto", "").lower()
    indexador = oferta.get("indexador", "").lower().strip()
    taxa_raw = oferta.get("taxa_raw", "")
    rating = oferta.get("rating", "")
    vencimento = oferta.get("vencimento", "")

    prazo_meses = 12
    if vencimento and len(str(vencimento)) >= 10:
        try:
            from datetime import datetime, date
            if isinstance(vencimento, date):
                prazo_meses = max((vencimento - date.today()).days // 30, 1)
            else:
                dv = datetime.strptime(str(vencimento)[:10], "%Y-%m-%d")
                prazo_meses = max((dv.date() - date.today()).days // 30, 1)
        except ValueError:
            pass

    if perfil.apenas_isento_ir and produto not in ("lci", "lca", "cri", "cra"):
        rejeicoes.append("Produto nao eh isento de IR")
        score -= 40

    if perfil.produto_preferido and produto != perfil.produto_preferido:
        score -= 10

    if perfil.indexador_preferido:
        if indexador == perfil.indexador_preferido:
            score += 10
        elif indexador.replace("+", "") == perfil.indexador_preferido.replace("+", ""):
            score += 5
        else:
            score -= 5

    if perfil.rating_minimo:
        min_r = _rating_num(perfil.rating_minimo)
        oferta_r = _rating_num(rating)
        if oferta_r < min_r:
            rejeicoes.append(f"Rating {rating} abaixo do minimo {perfil.rating_minimo}")
            score -= 30

    if prazo_meses > perfil.prazo_preferido_meses * 2:
        avisos.append(f"Prazo {prazo_meses}m muito maior que o preferido {perfil.prazo_preferido_meses}m")
        score -= 10
    elif prazo_meses < perfil.prazo_preferido_meses // 2:
        avisos.append(f"Prazo {prazo_meses}m muito menor que o preferido {perfil.prazo_preferido_meses}m")
        score -= 5

    if "CDI" in indexador.upper() and perfil.taxa_minima_cdi > 0:
        try:
            taxa_val = float(taxa_raw.replace(",", ".").replace("%", "").strip())
            if taxa_val < perfil.taxa_minima_cdi:
                avisos.append(f"Taxa CDI+{taxa_val}% abaixo do minimo CDI+{perfil.taxa_minima_cdi}%")
                score -= 15
        except (ValueError, AttributeError):
            pass

    if "IPCA" in indexador.upper() and perfil.taxa_minima_ipca > 0:
        try:
            taxa_val = float(taxa_raw.replace(",", ".").replace("%", "").strip())
            if taxa_val < perfil.taxa_minima_ipca:
                avisos.append(f"Taxa IPCA+{taxa_val}% abaixo do minimo IPCA+{perfil.taxa_minima_ipca}%")
                score -= 15
        except (ValueError, AttributeError):
            pass

    for restricao in perfil.restricoes:
        r = restricao.lower()
        if r == "sem cdb" and produto == "cdb":
            rejeicoes.append("CDB excluido por restricao")
            score -= 50
        if r == "sem debenture" and produto == "debenture":
            rejeicoes.append("Debenture excluida por restricao")
            score -= 50
        if r in produto:
            rejeicoes.append(f"Restricao: {restricao}")
            score -= 50

    score = max(0, min(100, score))

    return {
        "match_score": round(score, 1),
        "match_label": _label_match(score),
        "rejeicoes": rejeicoes,
        "avisos": avisos,
        "perfil": perfil.nome,
        "prazo_meses": prazo_meses,
    }


def _label_match(score: float) -> str:
    if score >= 80: return "excelente"
    if score >= 60: return "boa"
    if score >= 40: return "regular"
    return "ruim"


def rankear_para_perfil(
    ofertas: List[Dict[str, Any]],
    perfil: PerfilInvestidor,
    normalizados: Optional[List[Dict]] = None,
    limite: int = 10,
) -> List[Dict[str, Any]]:
    resultados = []
    for i, oferta in enumerate(ofertas):
        norm = normalizados[i] if normalizados and i < len(normalizados) else None
        match = calcular_match(oferta, perfil, norm)
        resultados.append({
            "oferta": oferta,
            "match": match,
        })

    resultados.sort(key=lambda x: x["match"]["match_score"], reverse=True)
    return resultados[:limite]
