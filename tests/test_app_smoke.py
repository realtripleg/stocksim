
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
