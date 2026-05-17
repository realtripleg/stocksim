from __future__ import annotations

import sqlite3

import pytest

from stocksim import db


@pytest.fixture()
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_schema(c)
    yield c
    c.close()


def test_init_seeds_portfolio_with_starting_cash(conn):
    p = db.get_portfolio(conn)
    assert p.cash == db.STARTING_CASH
    assert p.sim_minutes == 0


def test_init_is_idempotent(tmp_path):
    path = tmp_path / "t.db"
    c1 = db.connect(path)
    db.init_schema(c1)
    db.update_portfolio(c1, cash=5_000.0, sim_minutes=42)
    c1.close()

    c2 = db.connect(path)
    db.init_schema(c2)
    p = db.get_portfolio(c2)
    assert p.cash == 5_000.0
    assert p.sim_minutes == 42
    c2.close()


def test_upsert_position_then_get(conn):
    db.upsert_position(conn, ticker="AAPL", shares=10, avg_cost=185.0)
    db.upsert_position(conn, ticker="MSFT", shares=5, avg_cost=410.0)
    pos = db.get_positions(conn)
    assert set(pos) == {"AAPL", "MSFT"}
    assert pos["AAPL"].shares == 10
    assert pos["AAPL"].avg_cost == 185.0


def test_upsert_position_replaces(conn):
    db.upsert_position(conn, ticker="AAPL", shares=10, avg_cost=185.0)
    db.upsert_position(conn, ticker="AAPL", shares=15, avg_cost=190.0)
    pos = db.get_positions(conn)
    assert pos["AAPL"].shares == 15
    assert pos["AAPL"].avg_cost == 190.0


def test_delete_position(conn):
    db.upsert_position(conn, ticker="AAPL", shares=10, avg_cost=185.0)
    db.delete_position(conn, "AAPL")
    assert db.get_positions(conn) == {}


def test_position_check_rejects_zero_shares(conn):
    with pytest.raises(sqlite3.IntegrityError):
        db.upsert_position(conn, ticker="AAPL", shares=0, avg_cost=185.0)


def test_record_and_recent_trades(conn):
    db.record_trade(conn, sim_ts=10, ticker="AAPL", side="buy", shares=5, price=185.0)
    db.record_trade(conn, sim_ts=11, ticker="AAPL", side="sell", shares=2, price=190.0)
    trades = db.recent_trades(conn, limit=10)
    assert [t["side"] for t in trades] == ["sell", "buy"]
    assert trades[0]["shares"] == 2


def test_insert_and_latest_prices(conn):
    db.insert_prices(conn, sim_ts=1, prices={"AAPL": 185.0, "MSFT": 410.0})
    db.insert_prices(conn, sim_ts=2, prices={"AAPL": 186.5, "MSFT": 411.0})
    latest = db.latest_prices(conn)
    assert latest == {"AAPL": 186.5, "MSFT": 411.0}


def test_price_history_in_chronological_order(conn):
    for ts, p in [(1, 100.0), (2, 101.0), (3, 99.0), (4, 102.0)]:
        db.insert_prices(conn, sim_ts=ts, prices={"AAPL": p})
    hist = db.price_history(conn, "AAPL", limit=3)
    assert hist == [(2, 101.0), (3, 99.0), (4, 102.0)]


def test_trim_prices_keeps_last_n(conn):
    for ts in range(100):
        db.insert_prices(conn, sim_ts=ts, prices={"AAPL": float(ts)})
    db.trim_prices(conn, ["AAPL"], keep_last=10)
    rows = conn.execute("SELECT COUNT(*) AS n FROM prices WHERE ticker = 'AAPL'").fetchone()
    assert rows["n"] == 10


def test_reset_removes_db(tmp_path):
    path = tmp_path / "x.db"
    c = db.connect(path)
    db.init_schema(c)
    c.close()
    assert path.exists()
    db.reset(path)
    assert not path.exists()
