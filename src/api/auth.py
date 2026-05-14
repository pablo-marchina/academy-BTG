from __future__ import annotations
import os
import json
import secrets
from pathlib import Path
from fastapi import Request, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Set

API_KEYS: Set[str] = set()
API_KEYS_FILE = Path("data/api_keys.json")

security = HTTPBearer(auto_error=False)


def _carregar_chaves():
    chaves = set()

    env_keys = os.environ.get("API_KEYS", "")
    for k in env_keys.split(","):
        k = k.strip()
        if k:
            chaves.add(k)

    if API_KEYS_FILE.exists():
        try:
            dados = json.loads(API_KEYS_FILE.read_text())
            if isinstance(dados, list):
                for k in dados:
                    if isinstance(k, str) and k.strip():
                        chaves.add(k.strip())
        except Exception:
            pass

    if not chaves:
        default_key = secrets.token_hex(16)
        chaves.add(default_key)
        API_KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
        API_KEYS_FILE.write_text(json.dumps([default_key], indent=2))
        print(f"[Auth] API Key gerada e salva em {API_KEYS_FILE}: {default_key}")
        print(f"[Auth] Defina API_KEYS no .env ou edite {API_KEYS_FILE} para adicionar chaves")

    return chaves


API_KEYS = _carregar_chaves()


def verificar_api_key(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="API Key obrigatoria. Header: Authorization: Bearer <key>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    if token not in API_KEYS:
        raise HTTPException(status_code=403, detail="API Key invalida")

    return token
