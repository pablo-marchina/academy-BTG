from __future__ import annotations
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db.engine import SessionLocal, init_db
from src.db.models import MacroDiaria


def health_check() -> dict:
    result = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "checks": {},
    }

    try:
        init_db()
        session = SessionLocal()
        count_ofertas = session.query(MacroDiaria).count()
        session.close()
        result["checks"]["database"] = {"status": "ok", "count": count_ofertas}
    except Exception as e:
        result["checks"]["database"] = {"status": "erro", "detail": str(e)}
        result["status"] = "erro"

    env_keys = ["GROQ_API_KEY", "TELEGRAM_BOT_TOKEN", "ANBIMA_CLIENT_ID"]
    for k in env_keys:
        result["checks"][f"env_{k}"] = {
            "status": "ok" if os.environ.get(k) or open(Path(__file__).resolve().parent.parent / ".env").read().find(k + "=") >= 0 else "ausente",
        }

    return result


if __name__ == "__main__":
    import json
    r = health_check()
    print(json.dumps(r, indent=2, ensure_ascii=False))
    sys.exit(0 if r["status"] == "ok" else 1)
