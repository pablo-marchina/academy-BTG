from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class RawOffer(BaseModel):
    id: str = ""
    fonte: str = ""
    produto: str = ""
    codigo: str = ""
    emissor: str = ""
    indexador: str = ""
    taxa_raw: str = ""
    vencimento: str = ""
    rating: Optional[str] = None
    coordenador: Optional[str] = None
    volume_mm: Optional[float] = None
    data_coleta: Optional[datetime] = None
    url_origem: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def get(self, key: str, default=None):
        return getattr(self, key, default)

    def __getitem__(self, key: str):
        return getattr(self, key)

    def __setitem__(self, key: str, value):
        setattr(self, key, value)


class RawDocument(BaseModel):
    id: str = ""
    oferta_id: str = ""
    nome_arquivo: str = ""
    url: str = ""
    caminho_local: Optional[str] = None
    tipo: str = "documento_emissao"
    emissor: str = ""
    codigo_oferta: str = ""
    data_documento: str = ""
    fonte: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def get(self, key: str, default=None):
        return getattr(self, key, default)

    def __getitem__(self, key: str):
        return getattr(self, key)

    def __setitem__(self, key: str, value):
        setattr(self, key, value)
