"""
Coletor CVM corrigido.
Fix: descobre dinamicamente os arquivos disponíveis no diretório
     em vez de assumir nome fixo que pode não existir.
"""
from __future__ import annotations
from typing import List, Tuple, Optional
from datetime import date, datetime, timedelta
import hashlib, io, logging, re
from pathlib import Path

import httpx
import pandas as pd

from ..models.raw import RawOffer, RawDocument
from ..config import settings

logger = logging.getLogger(__name__)

ASSUNTOS_EMISSAO = [
    "emissão de debêntures", "emissão de cri", "emissão de cra",
    "emissão de nota", "oferta pública", "prospecto definitivo",
    "prospecto preliminar", "captação de recursos", "emissão de título",
]

IPE_DIR = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


class CVMCollector:
    name = "cvm"

    def __init__(self):
        self.pdf_dir = Path(settings.PDF_STORAGE_PATH)
        self.client  = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=15.0),
            headers=HEADERS,
            follow_redirects=True,
        )

    async def collect(
        self,
        data_inicio: Optional[date] = None,
        **kwargs,
    ) -> Tuple[List[RawOffer], List[RawDocument]]:
        if not data_inicio:
            data_inicio = date.today() - timedelta(days=settings.DATE_LOOKBACK_DAYS)

        # Descobre quais arquivos existem no diretório
        arquivos = await self._listar_arquivos_ipe()
        if not arquivos:
            logger.warning("[CVM] Não foi possível listar arquivos IPE")
            return [], []

        documentos: List[RawDocument] = []
        anos_necessarios = {date.today().year}
        if data_inicio.year < date.today().year:
            anos_necessarios.add(data_inicio.year)

        for ano in sorted(anos_necessarios):
            # Tenta todos os arquivos do ano encontrados no diretório
            arqs_ano = [a for a in arquivos if str(ano) in a]
            if not arqs_ano:
                # Fallback: ano anterior
                ano_ant = ano - 1
                arqs_ano = [a for a in arquivos if str(ano_ant) in a]
                if arqs_ano:
                    logger.info(f"[CVM] Ano {ano} sem arquivo — usando {ano_ant}")

            for nome_arq in arqs_ano:
                docs = await self._fetch_ipe_csv(nome_arq, data_inicio)
                documentos.extend(docs)

        logger.info(f"[CVM] {len(documentos)} documentos de emissão encontrados")
        return [], documentos

    # ------------------------------------------------------------------ #
    # Descoberta de arquivos                                               #
    # ------------------------------------------------------------------ #

    async def _listar_arquivos_ipe(self) -> List[str]:
        """Faz fetch do índice do diretório e extrai nomes de arquivos CSV."""
        try:
            resp = await self.client.get(IPE_DIR)
            if resp.status_code == 200:
                nomes = re.findall(r'href="(ipe_cia_aberta[^"]+\.csv)"', resp.text)
                if nomes:
                    logger.debug(f"[CVM] Arquivos disponíveis: {nomes}")
                    return nomes
            # Fallback: tenta nomes convencionais dos últimos 2 anos
            logger.warning(f"[CVM] Diretório retornou {resp.status_code} — usando nomes padrão")
        except Exception as e:
            logger.warning(f"[CVM] Falha ao listar diretório: {e} — usando nomes padrão")

        ano = date.today().year
        return [
            f"ipe_cia_aberta_{ano}.csv",
            f"ipe_cia_aberta_{ano - 1}.csv",
        ]

    # ------------------------------------------------------------------ #
    # Leitura do CSV                                                       #
    # ------------------------------------------------------------------ #

    async def _fetch_ipe_csv(
        self, nome_arquivo: str, data_inicio: date
    ) -> List[RawDocument]:
        url = IPE_DIR + nome_arquivo
        documentos = []

        try:
            resp = await self.client.get(url)
            if resp.status_code == 404:
                logger.debug(f"[CVM] {nome_arquivo} não encontrado (404)")
                return []
            resp.raise_for_status()

            df = pd.read_csv(
                io.StringIO(resp.text),
                sep=";", encoding="latin-1",
                dtype=str, on_bad_lines="skip",
            )
            df.columns = [c.strip().upper() for c in df.columns]

            if "DT_RECEP" in df.columns:
                df["DT_RECEP"] = pd.to_datetime(
                    df["DT_RECEP"], errors="coerce", dayfirst=True
                )
                df = df[df["DT_RECEP"] >= pd.Timestamp(data_inicio)]

            if "DS_ASSUNTO" not in df.columns:
                return []

            mask = df["DS_ASSUNTO"].str.lower().str.contains(
                "|".join(ASSUNTOS_EMISSAO), na=False
            )
            df_f = df[mask]
            logger.info(f"[CVM] {nome_arquivo}: {len(df_f)} docs de emissão (de {len(df)} total)")

            for _, row in df_f.iterrows():
                url_doc = str(row.get("LINK_DOC", "") or "").strip()
                emissor  = str(row.get("DENOM_CIA", "") or "").strip()
                if not url_doc or not emissor:
                    continue
                dt = row.get("DT_RECEP")
                documentos.append(RawDocument(
                    url           = url_doc,
                    caminho_local = None,
                    tipo          = self._tipo(str(row.get("DS_ASSUNTO", ""))),
                    emissor       = emissor,
                    codigo_oferta = str(row.get("CNPJ_CIA", "") or ""),
                    data_documento= dt.strftime("%Y-%m-%d") if pd.notna(dt) else "",
                    fonte         = "cvm",
                    metadata      = row.to_dict(),
                ))

        except httpx.HTTPStatusError as e:
            logger.warning(f"[CVM] {nome_arquivo}: HTTP {e.response.status_code}")
        except Exception as e:
            logger.error(f"[CVM] Erro em {nome_arquivo}: {e}")

        return documentos

    # ------------------------------------------------------------------ #
    # Download de PDFs                                                     #
    # ------------------------------------------------------------------ #

    async def download_prospecto(self, doc: RawDocument) -> Optional[str]:
        url = doc.get("url", "")
        if not url:
            return None

        h = hashlib.md5(url.encode(), usedforsecurity=False).hexdigest()[:12]
        slug = "".join(c if c.isalnum() else "_" for c in
                       (doc.get("emissor") or "doc").lower())[:30]
        caminho = self.pdf_dir / f"{slug}_{h}.pdf"

        if caminho.exists():
            return str(caminho)

        try:
            resp = await self.client.get(url, timeout=90.0)
            resp.raise_for_status()
            if "pdf" not in resp.headers.get("content-type", "").lower():
                return None
            self.pdf_dir.mkdir(parents=True, exist_ok=True)
            caminho.write_bytes(resp.content)
            logger.info(f"[CVM] PDF: {caminho.name} ({len(resp.content)//1024} KB)")
            return str(caminho)
        except Exception as e:
            logger.debug(f"[CVM] Falha ao baixar {url}: {e}")
            return None

    async def download_todos(
        self, docs: List[RawDocument], max_concurrent: int = 3
    ) -> List[RawDocument]:
        import asyncio
        sem = asyncio.Semaphore(max_concurrent)
        async def _baixar(d):
            async with sem:
                d["caminho_local"] = await self.download_prospecto(d)
            return d
        return list(await asyncio.gather(*[_baixar(d) for d in docs]))

    def _tipo(self, assunto: str) -> str:
        a = assunto.lower()
        if "definitivo" in a: return "prospecto_definitivo"
        if "preliminar" in a: return "prospecto_preliminar"
        if "fato relevante" in a: return "fato_relevante"
        return "documento_emissao"

    async def __aenter__(self): return self
    async def __aexit__(self, *a): await self.client.aclose()
