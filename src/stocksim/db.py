
from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

STARTING_CASH: float = 10_000.00


def default_db_path() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return Path(base) / "stocksim" / "stocksim.db"


def connect(path: Path | str) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS portfolio (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            cash        REAL NOT NULL,
            sim_minutes INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS positions (
            ticker   TEXT PRIMARY KEY,
            shares   INTEGER NOT NULL CHECK (shares > 0),
            avg_cost REAL NOT NULL CHECK (avg_cost > 0)
        );
        CREATE TABLE IF NOT EXISTS trades (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            sim_ts INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            side   TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
            shares INTEGER NOT NULL CHECK (shares > 0),
            price  REAL NOT NULL CHECK (price > 0)
        );
        CREATE TABLE IF NOT EXISTS prices (
            ticker TEXT NOT NULL,
            sim_ts INTEGER NOT NULL,
            price  REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_prices_ticker_ts ON prices(ticker, sim_ts DESC);
        CREATE INDEX IF NOT EXISTS idx_trades_ts ON trades(sim_ts DESC);
        CREATE TABLE IF NOT EXISTS favorites (
            ticker TEXT PRIMARY KEY
        );
        CREATE TABLE IF NOT EXISTS hot_state (
            id      INTEGER PRIMARY KEY CHECK (id = 1),
            sim_day INTEGER NOT NULL,
            ticker  TEXT
        );
        CREATE TABLE IF NOT EXISTS scheduled_events (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker           TEXT NOT NULL,
            headline         TEXT NOT NULL,
            pct_change       REAL NOT NULL,
            scheduled_sim_ts INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_scheduled_ts ON scheduled_events(scheduled_sim_ts);
        """
    )
    cur = conn.execute("SELECT 1 FROM portfolio WHERE id = 1")
    if cur.fetchone() is None:
        conn.execute(
            "INSERT INTO portfolio (id, cash, sim_minutes) VALUES (1, ?, 0)",
            (STARTING_CASH,),
        )
    cur = conn.execute("SELECT 1 FROM hot_state WHERE id = 1")
    if cur.fetchone() is None:
        conn.execute(
            "INSERT INTO hot_state (id, sim_day, ticker) VALUES (1, -1, NULL)"
        )


def reset(path: Path | str) -> None:
    path = Path(path)
    for suffix in ("", "-wal", "-shm", "-journal"):
        p = path.with_name(path.name + suffix) if suffix else path
        if p.exists():
            p.unlink()


@contextmanager
def transaction(conn: sqlite3.Connection):
    conn.execute("BEGIN")
    try:
        yield
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


@dataclass(frozen=True)
class PortfolioRow:
    cash: float
    sim_minutes: int


def get_portfolio(conn: sqlite3.Connection) -> PortfolioRow:
    row = conn.execute("SELECT cash, sim_minutes FROM portfolio WHERE id = 1").fetchone()
    return PortfolioRow(cash=row["cash"], sim_minutes=row["sim_minutes"])


def update_portfolio(conn: sqlite3.Connection, *, cash: float, sim_minutes: int) -> None:
    conn.execute(
        "UPDATE portfolio SET cash = ?, sim_minutes = ? WHERE id = 1",
        (cash, sim_minutes),
    )


def update_sim_minutes(conn: sqlite3.Connection, sim_minutes: int) -> None:
    conn.execute("UPDATE portfolio SET sim_minutes = ? WHERE id = 1", (sim_minutes,))


@dataclass(frozen=True)
class PositionRow:
    ticker: str
    shares: int
    avg_cost: float


def get_positions(conn: sqlite3.Connection) -> dict[str, PositionRow]:
    rows = conn.execute("SELECT ticker, shares, avg_cost FROM positions").fetchall()
    return {r["ticker"]: PositionRow(r["ticker"], r["shares"], r["avg_cost"]) for r in rows}


def upsert_position(
    conn: sqlite3.Connection, *, ticker: str, shares: int, avg_cost: float
) -> None:
    conn.execute(
        """
        INSERT INTO positions (ticker, shares, avg_cost) VALUES (?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET shares = excluded.shares, avg_cost = excluded.avg_cost
        """,
        (ticker, shares, avg_cost),
    )


def delete_position(conn: sqlite3.Connection, ticker: str) -> None:
    conn.execute("DELETE FROM positions WHERE ticker = ?", (ticker,))


def record_trade(
    conn: sqlite3.Connection,
    *,
    sim_ts: int,
    ticker: str,
    side: str,
    shares: int,
    price: float,
) -> None:
    conn.execute(
        "INSERT INTO trades (sim_ts, ticker, side, shares, price) VALUES (?, ?, ?, ?, ?)",
        (sim_ts, ticker, side, shares, price),
    )


def insert_prices(
    conn: sqlite3.Connection, sim_ts: int, prices: Mapping[str, float]
) -> None:
    conn.executemany(
        "INSERT INTO prices (ticker, sim_ts, price) VALUES (?, ?, ?)",
        [(ticker, sim_ts, price) for ticker, price in prices.items()],
    )


def latest_prices(conn: sqlite3.Connection) -> dict[str, float]:
    rows = conn.execute(
        """
        SELECT p.ticker, p.price
        FROM prices p
        JOIN (
            SELECT ticker, MAX(sim_ts) AS max_ts FROM prices GROUP BY ticker
        ) latest ON latest.ticker = p.ticker AND latest.max_ts = p.sim_ts
        """
    ).fetchall()
    return {r["ticker"]: r["price"] for r in rows}


def price_history(
    conn: sqlite3.Connection, ticker: str, limit: int = 60
) -> list[tuple[int, float]]:
    rows = conn.execute(
        "SELECT sim_ts, price FROM prices WHERE ticker = ? ORDER BY sim_ts DESC LIMIT ?",
        (ticker, limit),
    ).fetchall()
    return [(r["sim_ts"], r["price"]) for r in reversed(rows)]


def recent_trades(
    conn: sqlite3.Connection, limit: int = 20
) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT sim_ts, ticker, side, shares, price FROM trades ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()


def trim_prices(
    conn: sqlite3.Connection, tickers: Iterable[str], keep_last: int = 1440
) -> None:
    for t in tickers:
        conn.execute(
            """
            DELETE FROM prices
            WHERE ticker = ?
              AND sim_ts < COALESCE(
                  (SELECT MIN(sim_ts) FROM (
                      SELECT sim_ts FROM prices WHERE ticker = ? ORDER BY sim_ts DESC LIMIT ?
                  )),
                  0
              )
            """,
            (t, t, keep_last),
        )


def get_favorites(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT ticker FROM favorites").fetchall()
    return {r["ticker"] for r in rows}


def toggle_favorite(conn: sqlite3.Connection, ticker: str) -> bool:
    row = conn.execute("SELECT 1 FROM favorites WHERE ticker = ?", (ticker,)).fetchone()
    if row is None:
        conn.execute("INSERT INTO favorites (ticker) VALUES (?)", (ticker,))
        return True
    conn.execute("DELETE FROM favorites WHERE ticker = ?", (ticker,))
    return False


@dataclass(frozen=True)
class HotState:
    sim_day: int
    ticker: str | None


def get_hot_state(conn: sqlite3.Connection) -> HotState:
    row = conn.execute("SELECT sim_day, ticker FROM hot_state WHERE id = 1").fetchone()
    return HotState(sim_day=row["sim_day"], ticker=row["ticker"])


def set_hot_state(conn: sqlite3.Connection, sim_day: int, ticker: str | None) -> None:
    conn.execute(
        "UPDATE hot_state SET sim_day = ?, ticker = ? WHERE id = 1",
        (sim_day, ticker),
    )


def schedule_event(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    headline: str,
    pct_change: float,
    scheduled_sim_ts: int,
) -> int:
    cur = conn.execute(
        "INSERT INTO scheduled_events (ticker, headline, pct_change, scheduled_sim_ts) "
        "VALUES (?, ?, ?, ?)",
        (ticker, headline, pct_change, scheduled_sim_ts),
    )
    return cur.lastrowid


def peek_due_events(conn: sqlite3.Connection, sim_ts: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, ticker, headline, pct_change, scheduled_sim_ts FROM scheduled_events "
        "WHERE scheduled_sim_ts <= ? ORDER BY scheduled_sim_ts",
        (sim_ts,),
    ).fetchall()


def delete_event(conn: sqlite3.Connection, event_id: int) -> None:
    conn.execute("DELETE FROM scheduled_events WHERE id = ?", (event_id,))
