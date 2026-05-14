"""
Pipeline de coleta.
Orquestra a execução paralela de todos os coletores via asyncio.gather.
Retorna (ofertas, documentos, macro_context) consolidados e deduplicados.
"""
import asyncio
import logging
from datetime import date, timedelta
from typing import List, Tuple, Dict

from .anbima import ANBIMACollector
from .bcb_collector import BCBCollector
from .cvm import CVMCollector
from .platforms import PlatformCollector
from ..models.raw import RawOffer, RawDocument
from ..config import settings

logger = logging.getLogger(__name__)

# Prioridade de fonte para deduplicação (menor = mais confiável)
PRIORIDADE_FONTE = {
    "anbima":      1,
    "cvm":         2,
    "btg_api":     3,
    "xp_api":      3,
    "genial_api":  3,
    "btg_html":    4,
    "xp_html":     4,
    "genial_html": 4,
}


class CollectionPipeline:
    """
    Orquestra a coleta paralela de todos os coletores.
    Ponto de entrada do sistema de inteligência.
    """

    def __init__(self):
        self.anbima    = ANBIMACollector()
        self.bcb       = BCBCollector()
        self.cvm       = CVMCollector()
        self.platforms = PlatformCollector()

    async def run(
        self,
        data_inicio: date = None,
        data_fim: date = None,
        baixar_pdfs: bool = True,
    ) -> Tuple[List[RawOffer], List[RawDocument], Dict]:
        """
        Executa pipeline completo de coleta em paralelo.

        Returns:
            ofertas:        lista de RawOffer deduplicada
            documentos:     lista de RawDocument (PDFs baixados se baixar_pdfs=True)
            macro_context:  dict com SELIC, IPCA, Focus, curva DI, regime
        """
        if not data_inicio:
            data_inicio = date.today() - timedelta(days=settings.DATE_LOOKBACK_DAYS)
        if not data_fim:
            data_fim = date.today()

        logger.info(
            f"[Pipeline] Iniciando coleta paralela: "
            f"{data_inicio.isoformat()} → {data_fim.isoformat()}"
        )

        # ---------------------------------------------------------- #
        # Execução paralela                                            #
        # ---------------------------------------------------------- #
        resultados = await asyncio.gather(
            self._run_anbima(data_inicio, data_fim),
            self._run_cvm(data_inicio),
            self._run_platforms(),
            self._run_macro(data_inicio, data_fim),
            return_exceptions=True,
        )

        fontes = ["anbima", "cvm", "platforms", "macro"]

        # ---------------------------------------------------------- #
        # Consolidação                                                 #
        # ---------------------------------------------------------- #
        todas_ofertas:   List[RawOffer]    = []
        todos_docs:      List[RawDocument] = []
        macro_context:   Dict              = {}
        erros:           List[str]         = []

        for fonte, resultado in zip(fontes, resultados):
            if isinstance(resultado, Exception):
                erros.append(f"{fonte}: {resultado}")
                logger.error(f"[Pipeline] Falha em '{fonte}': {resultado}")
                continue

            if fonte == "macro":
                macro_context = resultado
            else:
                ofertas, docs = resultado
                todas_ofertas.extend(ofertas)
                todos_docs.extend(docs)

        # ---------------------------------------------------------- #
        # Download de PDFs (sequential com semaphore para não sobrecarregar)
        # ---------------------------------------------------------- #
        if baixar_pdfs and todos_docs:
            logger.info(f"[Pipeline] Baixando {len(todos_docs)} PDFs...")
            async with self.cvm:
                todos_docs = await self.cvm.download_todos(todos_docs, max_concurrent=3)
            todos_docs = [d for d in todos_docs if d.get("caminho_local")]

        # ---------------------------------------------------------- #
        # Deduplicação                                                 #
        # ---------------------------------------------------------- #
        todas_ofertas = self._deduplicar(todas_ofertas)

        logger.info(
            f"[Pipeline] Concluído: {len(todas_ofertas)} ofertas únicas, "
            f"{len(todos_docs)} PDFs, {len(erros)} erros"
        )

        if erros:
            logger.warning(f"[Pipeline] Erros: {erros}")

        return todas_ofertas, todos_docs, macro_context

    # ------------------------------------------------------------------ #
    # Runners individuais com tratamento de contexto                      #
    # ------------------------------------------------------------------ #

    async def _run_anbima(self, data_inicio: date, data_fim: date):
        async with self.anbima:
            return await self.anbima.collect(
                data_inicio=data_inicio,
                data_fim=data_fim,
            )

    async def _run_cvm(self, data_inicio: date):
        # Não usa context manager aqui pois download_todos usa separado
        return await self.cvm.collect(data_inicio=data_inicio)

    async def _run_platforms(self):
        return await self.platforms.collect_all()

    async def _run_macro(self, data_inicio: date, data_fim: date):
        return await self.bcb.collect_macro(
            data_inicio=data_inicio,
            data_fim=data_fim,
        )

    # ------------------------------------------------------------------ #
    # Deduplicação                                                         #
    # ------------------------------------------------------------------ #

    def _deduplicar(self, ofertas: List[RawOffer]) -> List[RawOffer]:
        """
        Remove duplicatas mantendo a oferta da fonte mais confiável.
        Ofertas sem ISIN são mantidas separadamente (ainda não confirmadas).
        """
        com_codigo:  Dict[str, RawOffer] = {}
        sem_codigo:  List[RawOffer]      = []

        for oferta in ofertas:
            codigo = (oferta.get("codigo") or "").strip()

            if not codigo:
                sem_codigo.append(oferta)
                continue

            if codigo not in com_codigo:
                com_codigo[codigo] = oferta
            else:
                # Mantém a oferta da fonte mais confiável
                p_nova   = PRIORIDADE_FONTE.get(oferta["fonte"], 99)
                p_atual  = PRIORIDADE_FONTE.get(com_codigo[codigo]["fonte"], 99)
                if p_nova < p_atual:
                    com_codigo[codigo] = oferta

        resultado = list(com_codigo.values()) + sem_codigo

        logger.debug(
            f"[Dedup] {len(ofertas)} → {len(resultado)} "
            f"({len(com_codigo)} com ISIN, {len(sem_codigo)} sem ISIN)"
        )
        return resultado

    # ------------------------------------------------------------------ #
    # Coleta de curvas ANBIMA (chamada separada para normalização)        #
    # ------------------------------------------------------------------ #

    async def fetch_curvas(self) -> dict:
        """Busca curvas de referência ANBIMA (DI x PRÉ e NTN-B/ETTJ)."""
        async with self.anbima:
            return await self.anbima.fetch_curvas()
