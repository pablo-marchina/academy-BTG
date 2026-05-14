from __future__ import annotations
import subprocess
import sys
from pathlib import Path
from datetime import datetime


def backup_sqlite():
    db_path = Path("data/btg_intelligence.db")
    if not db_path.exists():
        print("[Backup] Banco SQLite nao encontrado")
        return False

    backup_dir = Path("data/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"btg_intelligence_{ts}.db"

    try:
        subprocess.run(
            [sys.executable, "-c", f"""
import sqlite3
con = sqlite3.connect(r"{db_path.resolve()}")
bck = sqlite3.connect(r"{backup_path.resolve()}")
con.backup(bck)
bck.close()
con.close()
print("[Backup] Banco copiado com sucesso")
"""],
            check=True, capture_output=True, text=True, timeout=30,
        )
        print(f"[Backup] {db_path} -> {backup_path}")
        return True
    except Exception as e:
        print(f"[Backup] Erro: {e}")
        return False


if __name__ == "__main__":
    backup_sqlite()
