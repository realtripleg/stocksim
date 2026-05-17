
from __future__ import annotations

import pytest

from stocksim.app import StockSimApp


@pytest.mark.asyncio
async def test_app_mounts_and_ticks(tmp_path):
    pytest.importorskip("textual.pilot")
    app = StockSimApp(db_path=tmp_path / "smoke.db")
    async with app.run_test() as pilot:
        await pilot.pause()
        assert not app.clock.paused
        assert len(app.prices) == 30
        await pilot.pause(1.2)
        await pilot.press("space")
        await pilot.pause()
        assert app.clock.paused
        await pilot.press("space")
        await pilot.pause()
        assert not app.clock.paused


@pytest.mark.asyncio
async def test_app_buy_via_modal(tmp_path):
    pytest.importorskip("textual.pilot")
    app = StockSimApp(db_path=tmp_path / "smoke.db")
    async with app.run_test() as pilot:
        await pilot.pause()
        starting_cash = app.portfolio.cash()
        await pilot.press("b")
        await pilot.pause()
        await pilot.press("2")
        await pilot.press("enter")
        await pilot.pause()
        pos = app.portfolio.positions()
        assert len(pos) == 1
        assert app.portfolio.cash() < starting_cash


@pytest.mark.asyncio
async def test_state_persists_across_relaunch(tmp_path):
    pytest.importorskip("textual.pilot")
    db_path = tmp_path / "persist.db"

    app1 = StockSimApp(db_path=db_path)
    async with app1.run_test() as pilot:
        await pilot.pause()
        await pilot.press("b")
        await pilot.pause()
        await pilot.press("3")
        await pilot.press("enter")
        await pilot.pause()
        cash_after = app1.portfolio.cash()
        positions_after = app1.portfolio.positions()
        sim_minutes_after = app1.clock.sim_minutes
        await pilot.pause(2.0)
        final_sim_minutes = app1.clock.sim_minutes

    app2 = StockSimApp(db_path=db_path)
    async with app2.run_test() as pilot:
        await pilot.pause()
        assert app2.portfolio.cash() == cash_after
        assert {k: (v.shares, v.avg_cost) for k, v in app2.portfolio.positions().items()} == {
            k: (v.shares, v.avg_cost) for k, v in positions_after.items()
        }
        assert app2.clock.sim_minutes >= sim_minutes_after
        assert app2.clock.sim_minutes >= final_sim_minutes - 1


@pytest.mark.asyncio
async def test_toggle_favorite_pins_to_top(tmp_path):
    pytest.importorskip("textual.pilot")
    from stocksim import db
    from stocksim.widgets.watchlist import WatchlistTable

    app = StockSimApp(db_path=tmp_path / "fav.db")
    async with app.run_test() as pilot:
        await pilot.pause()
        watchlist = app.query_one(WatchlistTable)
        target = "NVDA"
        watchlist.move_cursor(row=5)
        await pilot.pause()
        assert watchlist.selected_symbol == target

        app.action_toggle_favorite()
        await pilot.pause()

        assert target in app.favorites
        first_after = watchlist.coordinate_to_cell_key((0, 0)).row_key.value
        assert first_after == target


@pytest.mark.asyncio
async def test_scheduled_event_fires_after_sim_ts(tmp_path):
    pytest.importorskip("textual.pilot")
    from stocksim import db

    db_path = tmp_path / "sched.db"
    app = StockSimApp(db_path=db_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        target = "AAPL"
        initial_price = app.prices[target]
        scheduled_ts = app.clock.sim_minutes + 1
        with db.transaction(app.conn):
            db.schedule_event(
                app.conn,
                ticker=target,
                headline="scheduled boom",
                pct_change=0.50,
                scheduled_sim_ts=scheduled_ts,
            )
        for _ in range(20):
            app.clock.speed_up()
        await pilot.pause(2.0)

        remaining = db.peek_due_events(app.conn, app.clock.sim_minutes + 10000)
        assert all(r["ticker"] != target or r["headline"] != "scheduled boom" for r in remaining)
        assert app.prices[target] > initial_price * 1.2
