from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "app" / "main.py"
BACKUPS = ROOT / "backups"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

IMPORT_LINE = "from app.multibot.router import router as multibot_router"
INCLUDE_LINE = "app.include_router(multibot_router)"


def backup(path: Path) -> None:
    if not path.exists():
        return
    BACKUPS.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, BACKUPS / f"{path.name}.{STAMP}.bak")


def patch_main() -> str:
    if not MAIN.exists():
        raise SystemExit(f"Missing {MAIN}. Run this script from the receiver project root.")
    text = MAIN.read_text(encoding="utf-8")
    if IMPORT_LINE in text and INCLUDE_LINE in text:
        return "main.py already patched"

    backup(MAIN)
    if IMPORT_LINE not in text:
        text += f"\n\n# Multi-bot foundation v1.1\n{IMPORT_LINE}\n"
    if INCLUDE_LINE not in text:
        text += f"{INCLUDE_LINE}\n"
    MAIN.write_text(text, encoding="utf-8")
    return "main.py patched"


def migrate_db() -> dict:
    sys.path.insert(0, str(ROOT))
    from app.config import settings
    from app.multibot.db import migrate

    db_path = ROOT / settings.db_path
    if db_path.exists():
        backup(db_path)
    return migrate()


def main() -> None:
    print(patch_main())
    print("migration:", migrate_db())
    print("Done. Restart receiver with: python run.py")
    print("Verify: curl http://localhost:5050/api/multibot/migration/status")
    print("Dashboard: http://localhost:5050/multi-bot-dashboard")


if __name__ == "__main__":
    main()
