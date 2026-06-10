from __future__ import annotations

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "app" / "main.py"
BACKUPS = ROOT / "backups"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

ROUTER_IMPORT = "from app.multibot.router import router as multibot_router"
ROUTER_INCLUDE = "app.include_router(multibot_router)"
MIDDLEWARE_IMPORT = "from app.multibot.middleware import MultiBotTickMiddleware"
MIDDLEWARE_ADD = "app.add_middleware(MultiBotTickMiddleware)"


def backup(path: Path) -> None:
    if not path.exists():
        return
    BACKUPS.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, BACKUPS / f"{path.name}.{STAMP}.bak")


def patch_main() -> str:
    if not MAIN.exists():
        raise SystemExit(f"Missing {MAIN}. Run installer inside receiver project root.")
    text = MAIN.read_text(encoding="utf-8")
    original = text
    backup(MAIN)

    # Free /dashboard for the unified router while keeping legacy UI reachable.
    # Exact replacements keep the installer idempotent: rerunning it never creates
    # /dashboard-legacy-legacy.
    text = text.replace('@app.get("/dashboard")', '@app.get("/dashboard-legacy")')
    text = text.replace('@app.get("/dashboard",', '@app.get("/dashboard-legacy",')

    block = []
    if ROUTER_IMPORT not in text:
        block.append(ROUTER_IMPORT)
    if MIDDLEWARE_IMPORT not in text:
        block.append(MIDDLEWARE_IMPORT)
    if MIDDLEWARE_ADD not in text:
        block.append(MIDDLEWARE_ADD)
    if ROUTER_INCLUDE not in text:
        block.append(ROUTER_INCLUDE)

    if block:
        text += "\n\n# Multi-bot runtime fan-out v1.2\n" + "\n".join(block) + "\n"
    MAIN.write_text(text, encoding="utf-8")
    return "main.py patched" if text != original else "main.py already patched"


def migrate_db() -> dict:
    sys.path.insert(0, str(ROOT))
    from app.multibot.db import DB_PATH, migrate
    db_path = ROOT / DB_PATH
    if db_path.exists():
        backup(db_path)
    return migrate()


def main() -> None:
    print(patch_main())
    print("migration:", migrate_db())
    print("Done. Restart receiver with: python run.py")
    print("Verify: curl http://localhost:5050/api/multibot/migration/status")
    print("Runtime: curl http://localhost:5050/api/multibot/runtime/status")
    print("Dashboard: http://localhost:5050/dashboard")


if __name__ == "__main__":
    main()
