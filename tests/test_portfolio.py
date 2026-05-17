from __future__ import annotations

import pytest

from stocksim import db
from stocksim.portfolio import Portfolio, TradeError


@pytest.fixture()
def pf(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.init_schema(conn)
    yield Portfolio(conn)
    conn.close()


def test_initial_state(pf):
    assert pf.cash() == db.STARTING_CASH
    assert pf.positions() == {}


def test_buy_deducts_cash_and_creates_position(pf):
    r = pf.buy(ticker="AAPL", shares=10, price=100.0, sim_ts=1)
    assert r.total == 1000.0
    assert r.new_cash == db.STARTING_CASH - 1000.0
    assert pf.cash() == db.STARTING_CASH - 1000.0
    pos = pf.positions()["AAPL"]
    assert pos.shares == 10
    assert pos.avg_cost == 100.0


def test_second_buy_uses_weighted_avg_cost(pf):
    pf.buy(ticker="AAPL", shares=10, price=100.0, sim_ts=1)
    pf.buy(ticker="AAPL", shares=10, price=120.0, sim_ts=2)
    pos = pf.positions()["AAPL"]
    assert pos.shares == 20
    assert pos.avg_cost == pytest.approx(110.0)


def test_buy_insufficient_cash_raises(pf):
    with pytest.raises(TradeError, match="insufficient cash"):
        pf.buy(ticker="AAPL", shares=1, price=db.STARTING_CASH + 1, sim_ts=1)
    assert pf.cash() == db.STARTING_CASH
    assert pf.positions() == {}


def test_buy_zero_or_negative_shares_raises(pf):
    with pytest.raises(TradeError):
        pf.buy(ticker="AAPL", shares=0, price=100.0, sim_ts=1)
    with pytest.raises(TradeError):
        pf.buy(ticker="AAPL", shares=-1, price=100.0, sim_ts=1)


def test_sell_partial(pf):
    pf.buy(ticker="AAPL", shares=10, price=100.0, sim_ts=1)
    r = pf.sell(ticker="AAPL", shares=4, price=120.0, sim_ts=2)
    assert r.total == 480.0
    assert pf.cash() == pytest.approx(db.STARTING_CASH - 1000.0 + 480.0)
    pos = pf.positions()["AAPL"]
    assert pos.shares == 6
    assert pos.avg_cost == 100.0


def test_sell_all_removes_position(pf):
    pf.buy(ticker="AAPL", shares=5, price=100.0, sim_ts=1)
    pf.sell(ticker="AAPL", shares=5, price=110.0, sim_ts=2)
    assert "AAPL" not in pf.positions()


def test_oversell_raises(pf):
    pf.buy(ticker="AAPL", shares=3, price=100.0, sim_ts=1)
    with pytest.raises(TradeError, match="cannot sell"):
        pf.sell(ticker="AAPL", shares=10, price=110.0, sim_ts=2)
    assert pf.positions()["AAPL"].shares == 3


def test_sell_unowned_raises(pf):
    with pytest.raises(TradeError):
        pf.sell(ticker="AAPL", shares=1, price=100.0, sim_ts=1)


def test_value_includes_holdings_at_current_prices(pf):
    pf.buy(ticker="AAPL", shares=10, price=100.0, sim_ts=1)
    pf.buy(ticker="MSFT", shares=5, price=200.0, sim_ts=2)
    prices = {"AAPL": 110.0, "MSFT": 210.0}
    expected = (db.STARTING_CASH - 1000.0 - 1000.0) + 10 * 110 + 5 * 210
    assert pf.value(prices) == pytest.approx(expected)


def test_pnl_against_starting_cash(pf):
    pf.buy(ticker="AAPL", shares=10, price=100.0, sim_ts=1)
    prices = {"AAPL": 150.0}
    assert pf.pnl(prices) == pytest.approx(500.0)


def test_buy_transaction_atomicity_on_failure(pf, monkeypatch):
    import stocksim.db as dbmod

    real = dbmod.record_trade
    calls = {"n": 0}

    def boom(*a, **kw):
        calls["n"] += 1
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(dbmod, "record_trade", boom)
    with pytest.raises(RuntimeError):
        pf.buy(ticker="AAPL", shares=10, price=100.0, sim_ts=1)

    monkeypatch.setattr(dbmod, "record_trade", real)
    assert pf.cash() == db.STARTING_CASH
    assert pf.positions() == {}
