from __future__ import annotations

import os
import sqlite3
import tempfile


def setup_db(path: str) -> None:
    conn = sqlite3.connect(path)
    conn.executescript('''
    CREATE TABLE candles (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      symbol TEXT,timeframe TEXT,open_time INTEGER,close_time INTEGER,
      open REAL,high REAL,low REAL,close REAL,tick_count INTEGER,is_closed INTEGER,updated_at INTEGER
    );
    CREATE TABLE order_blocks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      symbol TEXT,timeframe TEXT,side TEXT,break_open_time INTEGER,ob_open_time INTEGER,
      ob_low REAL,ob_high REAL,status TEXT,score INTEGER,is_strong INTEGER
    );
    CREATE TABLE paper_account (id INTEGER PRIMARY KEY,balance REAL,realized_pnl REAL);
    INSERT INTO paper_account VALUES(1,500,0);
    ''')
    for i in range(320):
        close = 500.0 - i
        conn.execute('INSERT INTO candles(symbol,timeframe,open_time,close_time,open,high,low,close,tick_count,is_closed,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                     ('XAUUSD','M15',i*900,(i+1)*900,close+1,close+2,close-2,close,10,1,i*900))
    conn.execute("INSERT INTO order_blocks(symbol,timeframe,side,break_open_time,ob_open_time,ob_low,ob_high,status,score,is_strong) VALUES(?,?,?,?,?,?,?,?,?,?)",
                 ('XAUUSD','M15','bearish',999999,999000,100.0,110.0,'active',8,1))
    conn.commit(); conn.close()


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, 'test.sqlite3')
        setup_db(db)
        os.environ['DB_PATH'] = db
        from app import storage
        from app.multibot import db as mdb
        from app.multibot import service
        from app.multibot.runtime import process_tick_sync
        result = mdb.migrate()
        assert result['schema_version'] == '2.5', f"expected 2.5 got {result['schema_version']}"
        bots = service.list_bots()
        assert len(bots) == 1 and bots[0]['name'] == 'Paper Trading', f"expected Paper Trading got {bots[0]['name']}"
        bot_id = bots[0]['id']
        service.set_bot_enabled(bot_id, True)
        # zone touch but bid below midpoint -> create pending
        process_tick_sync({'symbol':'XAUUSD','bid':104.0,'ask':104.2,'type':'tick'})
        state = service.bot_state(bot_id)
        assert state and state['pending'] and state['pending']['status'] == 'pending'
        # crosses midpoint for sell -> fill
        process_tick_sync({'symbol':'XAUUSD','bid':105.1,'ask':105.3,'type':'tick'})
        state = service.bot_state(bot_id)
        assert state and state['position'] and state['position']['status'] == 'open'
        # move down to TP -> close with gain
        process_tick_sync({'symbol':'XAUUSD','bid':80.0,'ask':80.2,'type':'tick'})
        state = service.bot_state(bot_id)
        assert state and state['position'] is None
        wallet = service.get_wallet(bot_id)
        assert wallet and wallet['balance'] > 500
        clone = service.clone_bot(bot_id, 'trend-ob-strict')
        assert clone['id'] != bot_id
        assert len(service.list_bots()) == 2
        storage._conn.close()
        print('v2.5 smoke test passed')

if __name__ == '__main__':
    main()
