from __future__ import annotations
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..config import settings

logger = logging.getLogger(__name__)

COLECOES: Dict[str, int] = {
    "ofertas": 768,
    "emissores": 768,
    "coordenadores": 768,
}

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("[Qdrant] Carregando modelo BERTimbau...")
        _model = SentenceTransformer("neuralmind/bert-large-portuguese-cased")
    return _model


def _get_client() -> QdrantClient:
    from qdrant_client import QdrantClient
    path = Path(settings.QDRANT_PATH)
    path.mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=str(path))


def _init_colecoes(client):
    from qdrant_client.models import VectorParams, Distance
    for nome, dim in COLECOES.items():
        try:
            client.get_collection(nome)
        except Exception:
            client.create_collection(
                collection_name=nome,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )


def _gerar_embedding(texto: str) -> List[float]:
    if not texto.strip():
        return [0.0] * 768
    model = _get_model()
    vec = model.encode(texto, normalize_embeddings=True)
    return vec.tolist()


def _gerar_embeddings_batch(textos: List[str]) -> List[List[float]]:
    model = _get_model()
    vecs = model.encode(textos, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vecs]


def indexar_oferta(oferta: Dict[str, Any]) -> bool:
    texto = _texto_oferta(oferta)
    if not texto.strip():
        return False

    vec = _gerar_embedding(texto)
    codigo = oferta.get("codigo") or oferta.get("id", "")
    if not codigo:
        return False

    client = _get_client()
    _init_colecoes(client)
    from qdrant_client.models import PointStruct

    payload = {
        "codigo": codigo,
        "emissor": oferta.get("emissor", ""),
        "produto": oferta.get("produto", ""),
        "indexador": oferta.get("indexador", ""),
        "taxa_raw": oferta.get("taxa_raw", ""),
        "rating": oferta.get("rating", ""),
        "coordenador": oferta.get("coordenador", ""),
        "fonte": oferta.get("fonte", ""),
        "score": oferta.get("score_atratividade", 0),
        "vencimento": str(oferta.get("vencimento", "")),
    }

    client.upsert(
        collection_name="ofertas",
        points=[PointStruct(id=hash(codigo) % (2**63), vector=vec, payload=payload)],
    )
    return True


def indexar_ofertas_batch(ofertas: List[Dict[str, Any]]) -> int:
    if not ofertas:
        return 0

    client = _get_client()
    _init_colecoes(client)
    from qdrant_client.models import PointStruct

    textos = [_texto_oferta(o) for o in ofertas]
    vetores = _gerar_embeddings_batch(textos)

    pontos = []
    for i, (oferta, vec) in enumerate(zip(ofertas, vetores)):
        codigo = oferta.get("codigo") or oferta.get("id", f"oferta_{i}")
        if not codigo:
            continue
        pontos.append(PointStruct(
            id=hash(codigo) % (2**63),
            vector=vec,
            payload={
                "codigo": codigo,
                "emissor": oferta.get("emissor", ""),
                "produto": oferta.get("produto", ""),
                "indexador": oferta.get("indexador", ""),
                "taxa_raw": oferta.get("taxa_raw", ""),
                "rating": oferta.get("rating", ""),
                "coordenador": oferta.get("coordenador", ""),
                "fonte": oferta.get("fonte", ""),
                "score": oferta.get("score_atratividade", oferta.get("score_total", 0)),
                "vencimento": str(oferta.get("vencimento", "")),
            },
        ))

    if pontos:
        client.upsert(collection_name="ofertas", points=pontos)
        logger.info(f"[Qdrant] {len(pontos)} ofertas indexadas")

    return len(pontos)


def indexar_emissor(emissor: str, metadata: Optional[Dict] = None) -> bool:
    if not emissor.strip():
        return False
    vec = _gerar_embedding(emissor)
    client = _get_client()
    _init_colecoes(client)
    from qdrant_client.models import PointStruct
    client.upsert(
        collection_name="emissores",
        points=[PointStruct(
            id=hash(emissor) % (2**63),
            vector=vec,
            payload={"nome": emissor, **(metadata or {})},
        )],
    )
    return True


def indexar_coordenador(nome: str, metadata: Optional[Dict] = None) -> bool:
    if not nome.strip():
        return False
    vec = _gerar_embedding(nome)
    client = _get_client()
    _init_colecoes(client)
    from qdrant_client.models import PointStruct
    client.upsert(
        collection_name="coordenadores",
        points=[PointStruct(
            id=hash(nome) % (2**63),
            vector=vec,
            payload={"nome": nome, **(metadata or {})},
        )],
    )
    return True


def buscar_ofertas_similares(
    query: str,
    filtros: Optional[Dict[str, Any]] = None,
    limite: int = 10,
    score_min: float = 0.0,
) -> List[Dict[str, Any]]:
    from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

    client = _get_client()
    vec = _gerar_embedding(query)

    qfilter = None
    if filtros:
        must = []
        for chave, valor in filtros.items():
            if isinstance(valor, str):
                must.append(FieldCondition(key=chave, match=MatchValue(value=valor)))
            elif isinstance(valor, (int, float)):
                must.append(FieldCondition(key=chave, range=Range(gte=valor)))
        if must:
            qfilter = Filter(must=must)

    try:
        resultados = client.search(
            collection_name="ofertas",
            query_vector=vec,
            limit=limite * 2,
            query_filter=qfilter,
            score_threshold=score_min,
        )
    except Exception as e:
        logger.error(f"[Qdrant] Erro na busca: {e}")
        return []

    ofertas = []
    for r in resultados:
        ofertas.append({
            **r.payload,
            "similaridade": round(r.score, 4),
        })

    ofertas.sort(key=lambda x: x.get("score", 0) or 0, reverse=True)
    return ofertas[:limite]


def buscar_por_emissor(emissor: str, limite: int = 10) -> List[Dict[str, Any]]:
    return buscar_ofertas_similares(emissor, {"emissor": emissor}, limite)


def buscar_por_produto(produto: str, score_min: float = 0, limite: int = 20) -> List[Dict[str, Any]]:
    return buscar_ofertas_similares(
        f"oferta de {produto}",
        {"produto": produto},
        limite,
        score_min / 100.0 if score_min > 0 else 0,
    )


def _texto_oferta(oferta: Dict[str, Any]) -> str:
    return (
        f"Oferta de {oferta.get('produto', '')} do emissor "
        f"{oferta.get('emissor', '')} com taxa {oferta.get('taxa_raw', '')} "
        f"indexada a {oferta.get('indexador', '')} "
        f"coordenada por {oferta.get('coordenador', '')} "
        f"rating {oferta.get('rating', '')} "
        f"vencimento {oferta.get('vencimento', '')}"
    )
