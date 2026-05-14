from __future__ import annotations
import logging
from datetime import date

from ..state import PipelineState
from ...db.engine import SessionLocal, init_db
from ...db.models import Oferta, Documento, MacroDiaria

logger = logging.getLogger(__name__)


def node_persistir(state: PipelineState) -> PipelineState:
    init_db()
    session = SessionLocal()
    try:
        for o_dict in state["ofertas"]:
            o = Oferta(
                id=o_dict.get("codigo") or o_dict.get("id", ""),
                codigo=o_dict.get("codigo", ""),
                fonte=o_dict.get("fonte", ""),
                produto=o_dict.get("produto", ""),
                emissor=o_dict.get("emissor", ""),
                indexador=o_dict.get("indexador", ""),
                taxa_raw=o_dict.get("taxa_raw", ""),
                vencimento=o_dict.get("vencimento", ""),
                rating=o_dict.get("rating"),
                coordenador=o_dict.get("coordenador"),
                volume_mm=o_dict.get("volume_mm"),
                data_coleta=o_dict.get("data_coleta"),
                url_origem=o_dict.get("url_origem", ""),
                metadata_json=o_dict.get("metadata"),
            )
            session.merge(o)

        for d_dict in state["documentos"]:
            d = Documento(
                id=d_dict.get("id", ""),
                oferta_id=d_dict.get("oferta_id", ""),
                nome_arquivo=d_dict.get("nome_arquivo", ""),
                url=d_dict.get("url", ""),
                caminho_local=d_dict.get("caminho_local"),
                tipo=d_dict.get("tipo", "documento_emissao"),
                emissor=d_dict.get("emissor", ""),
                codigo_oferta=d_dict.get("codigo_oferta", ""),
                data_documento=d_dict.get("data_documento", ""),
                fonte=d_dict.get("fonte", ""),
                metadata_json=d_dict.get("metadata"),
            )
            session.merge(d)

        macro = state.get("macro", {})
        if macro:
            m = MacroDiaria(
                data=state.get("data_fim") or date.today(),
                selic_atual=macro.get("selic_atual"),
                selic_proxima=macro.get("selic_proxima"),
                ipca_12m=macro.get("ipca_12m"),
                ipca_proximo_12m=macro.get("ipca_proximo_12m"),
                igpm_12m=macro.get("igpm_12m"),
                ptax_dolar=macro.get("ptax_dolar"),
                regime_mercado=macro.get("regime_mercado"),
                curva_di=macro.get("curva_di"),
            )
            session.add(m)

        session.commit()
        logger.info(f"[Persistir] {len(state['ofertas'])} ofertas e {len(state['documentos'])} docs persistidos")
    except Exception as e:
        session.rollback()
        logger.error(f"[Persistir] Erro: {e}")
        state.setdefault("erros", []).append(str(e))
    finally:
        session.close()

    return state
