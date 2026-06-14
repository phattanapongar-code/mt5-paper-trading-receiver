from __future__ import annotations

import os
import tempfile
from pathlib import Path


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DB_PATH"] = str(Path(tmp) / "receiver.sqlite3")
        from app import storage
        from app.multibot import db, service

        first = db.migrate()
        assert first["schema_version"] == "2.5", f"expected 2.5 got {first['schema_version']}"
        profiles = service.list_profiles()
        assert profiles[0]["name"] == "default"
        bots = service.list_bots()
        assert bots[0]["name"] == "Paper Trading", f"expected Paper Trading got {bots[0]['name']}"
        assert bots[0]["balance"] == 500.0
        cloned = service.clone_bot(bots[0]["id"], "trend-ob-strict")
        assert cloned["name"] == "trend-ob-strict"
        assert cloned["balance"] == 500.0
        compare = service.compare()
        assert len(compare) == 2
        second = db.migrate()
        assert second["profiles"] == 1
        assert second["bots"] == 2
        if storage._conn:
            storage._conn.close()
    print("multi-bot smoke test passed")


if __name__ == "__main__":
    main()
