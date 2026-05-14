"""Exporta o schema OpenAPI da FastAPI para arquivo JSON."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.app import app

spec = app.openapi()
caminho = Path("data/openapi.json")
caminho.parent.mkdir(parents=True, exist_ok=True)
caminho.write_text(json.dumps(spec, indent=2, ensure_ascii=False))
print(f"[OpenAPI] Schema exportado: {caminho} ({len(json.dumps(spec))} bytes)")
