"""
自选股持久化模块 - SQLite3
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "watchlist.db")


def _conn():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            market  TEXT NOT NULL,
            symbol  TEXT NOT NULL,
            name    TEXT DEFAULT '',
            note    TEXT DEFAULT '',
            created TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(market, symbol)
        )
    """)
    con.commit()
    return con


def get_watchlist(market: str) -> list:
    """获取某市场的自选股列表，返回 [{"symbol":..,"name":..,"note":..}]"""
    with _conn() as con:
        rows = con.execute(
            "SELECT symbol, name, note FROM watchlist WHERE market=? ORDER BY id",
            (market,)
        ).fetchall()
    return [{"symbol": r[0], "name": r[1], "note": r[2]} for r in rows]


def add_symbol(market: str, symbol: str, name: str = "", note: str = "") -> bool:
    """添加自选股，已存在返回 False"""
    try:
        with _conn() as con:
            con.execute(
                "INSERT INTO watchlist(market, symbol, name, note) VALUES(?,?,?,?)",
                (market, symbol.upper(), name, note)
            )
        return True
    except sqlite3.IntegrityError:
        return False


def remove_symbol(market: str, symbol: str):
    """删除自选股"""
    with _conn() as con:
        con.execute(
            "DELETE FROM watchlist WHERE market=? AND symbol=?",
            (market, symbol.upper())
        )


def update_note(market: str, symbol: str, note: str):
    """更新备注"""
    with _conn() as con:
        con.execute(
            "UPDATE watchlist SET note=? WHERE market=? AND symbol=?",
            (note, market, symbol.upper())
        )


def get_symbols(market: str) -> list:
    """只返回代码列表"""
    return [r["symbol"] for r in get_watchlist(market)]
