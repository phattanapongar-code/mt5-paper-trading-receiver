import os
import subprocess
import sys
import time

import uvicorn
from app.config import settings

_IS_LOCAL_TRADER = settings.trade_host in ("127.0.0.1", "localhost", "0.0.0.0")

if __name__ == "__main__":
    trader_proc = None
    if _IS_LOCAL_TRADER:
        if settings.trade_api_key:
            print(f"Starting trader.py on port {settings.trade_port}...")
            env = os.environ.copy()
            trader_proc = subprocess.Popen(
                [sys.executable, "trader.py"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            time.sleep(2)
            if trader_proc.poll() is not None:
                print("WARNING: trader.py exited early — check logs/trader.log")
            else:
                print(f"trader.py running (pid={trader_proc.pid})")
        else:
            print("TRADE_API_KEY not set — trader.py not started")
    else:
        print(f"Trader server remote at {settings.trade_host}:{settings.trade_port} — not spawning locally")

    print(f"Starting receiver on {settings.app_host}:{settings.app_port}")
    print(f"Dashboard: http://localhost:{settings.app_port}/dashboard")
    try:
        uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=False)
    finally:
        if trader_proc and trader_proc.poll() is None:
            print("Shutting down trader.py...")
            trader_proc.terminate()
            trader_proc.wait(timeout=5)
