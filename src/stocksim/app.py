
from __future__ import annotations

import random
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Footer, Header, RichLog

from . import db, news, simulator
from .clock import SimClock
from .portfolio import Portfolio, TradeError
from .stocks import STOCKS, seed_prices
from .widgets import PortfolioPanel, TradeModal, WatchlistTable

TICK_REAL_SECONDS: float = 1.0
TRIM_EVERY_N_TICKS: int = 200
PRICE_HISTORY_KEEP: int = 1440


class StockSimApp(App):
    CSS_PATH = "styles.tcss"
    TITLE = "StockSim"
    SUB_TITLE = "*** FAKE PRICES — NOT REAL MARKET DATA ***"

    BINDINGS = [
        Binding("b", "buy", "Buy"),
        Binding("s", "sell", "Sell"),
        Binding("space", "toggle_pause", "Pause"),
        Binding("plus,equals_sign,equal", "speed_up", "Faster"),
        Binding("minus,underscore", "slow_down", "Slower"),
        Binding("q,ctrl+c", "quit", "Quit"),
    ]

    prices: reactive[dict[str, float]] = reactive({}, layout=False)

    def __init__(self, *, db_path: Path | str) -> None:
        super().__init__()
        self._db_path = db_path
        self.conn = db.connect(db_path)
        db.init_schema(self.conn)
        self.portfolio = Portfolio(self.conn)
        self._rng = random.Random()

        loaded = db.latest_prices(self.conn)
        seeds = seed_prices()
        self.prices = {sym: loaded.get(sym, seeds[sym]) for sym in seeds}
        pf_row = db.get_portfolio(self.conn)
        self.clock = SimClock(sim_minutes=pf_row.sim_minutes)
        self._tick_count = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            yield WatchlistTable()
            yield PortfolioPanel()
        yield RichLog(id="news-log", max_lines=50, highlight=True, markup=True, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        watchlist = self.query_one(WatchlistTable)
        panel = self.query_one(PortfolioPanel)
        watchlist.refresh_prices(self.prices)
        panel.refresh_view(self.portfolio, self.prices)
        self._log = self.query_one("#news-log", RichLog)
        self._log.write(
            "[dim]Welcome to StockSim. All prices are simulated. "
            f"Sim time starts at minute {self.clock.sim_minutes}.[/]"
        )
        self._refresh_subtitle()
        self.set_interval(TICK_REAL_SECONDS, self._tick)

    def _tick(self) -> None:
        dmin = self.clock.advance(TICK_REAL_SECONDS)
        if dmin <= 0:
            return
        new_prices = simulator.step(self.prices, dmin, rng=self._rng)
        event = news.maybe_event(new_prices, dmin=dmin, rng=self._rng)
        if event is not None:
            new_prices = news.apply_event(new_prices, event)
            self._log_event(event)

        self.prices = new_prices

        with db.transaction(self.conn):
            db.insert_prices(self.conn, self.clock.sim_minutes, new_prices)
            db.update_sim_minutes(self.conn, self.clock.sim_minutes)

        self._tick_count += 1
        if self._tick_count % TRIM_EVERY_N_TICKS == 0:
            db.trim_prices(
                self.conn,
                [s.symbol for s in STOCKS],
                keep_last=PRICE_HISTORY_KEEP,
            )

    def watch_prices(self, _old: dict[str, float], new: dict[str, float]) -> None:
        if not new or not self.is_mounted:
            return
        try:
            self.query_one(WatchlistTable).refresh_prices(new)
            self.query_one(PortfolioPanel).refresh_view(self.portfolio, new)
        except Exception:
            pass

    def _refresh_subtitle(self) -> None:
        sim_h = self.clock.sim_minutes // 60
        sim_m = self.clock.sim_minutes % 60
        flag = " [PAUSED]" if self.clock.paused else ""
        self.sub_title = (
            f"FAKE PRICES — sim {sim_h:03d}h{sim_m:02d}m — {self.clock.speed:g}x{flag}"
        )

    def _log_event(self, event: news.NewsEvent) -> None:
        sign = "+" if event.pct_change >= 0 else ""
        color = "green" if event.pct_change >= 0 else "red"
        self._log.write(
            f"[{color}]📰 {event.headline} ({sign}{event.pct_change * 100:.1f}%)[/]"
        )
        self.notify(event.headline, severity="warning", timeout=4)

    def action_toggle_pause(self) -> None:
        paused = self.clock.toggle_pause()
        self._log.write("[yellow]⏸ Paused[/]" if paused else "[yellow]▶ Resumed[/]")
        self._refresh_subtitle()

    def action_speed_up(self) -> None:
        self.clock.speed_up()
        self._refresh_subtitle()

    def action_slow_down(self) -> None:
        self.clock.slow_down()
        self._refresh_subtitle()

    def action_buy(self) -> None:
        self._open_trade("buy")

    def action_sell(self) -> None:
        self._open_trade("sell")

    def _open_trade(self, side: str) -> None:
        watchlist = self.query_one(WatchlistTable)
        symbol = watchlist.selected_symbol
        if symbol is None:
            self.bell()
            return
        price = self.prices.get(symbol)
        if price is None:
            self.bell()
            return
        positions = self.portfolio.positions()
        held = positions[symbol].shares if symbol in positions else 0
        if side == "sell" and held == 0:
            self.notify(f"You don't own any {symbol}.", severity="warning")
            return

        def _on_close(result: tuple[int, str] | None) -> None:
            if result is None:
                return
            shares, _side = result
            price_now = self.prices.get(symbol, price)
            try:
                if _side == "buy":
                    r = self.portfolio.buy(
                        ticker=symbol,
                        shares=shares,
                        price=price_now,
                        sim_ts=self.clock.sim_minutes,
                    )
                    self._log.write(
                        f"[cyan]✓ Bought {r.shares} {r.ticker} @ ${r.price:,.2f} "
                        f"(${r.total:,.2f})[/]"
                    )
                else:
                    r = self.portfolio.sell(
                        ticker=symbol,
                        shares=shares,
                        price=price_now,
                        sim_ts=self.clock.sim_minutes,
                    )
                    self._log.write(
                        f"[magenta]✓ Sold {r.shares} {r.ticker} @ ${r.price:,.2f} "
                        f"(${r.total:,.2f})[/]"
                    )
            except TradeError as exc:
                self.notify(str(exc), severity="error")
                return
            self.query_one(PortfolioPanel).refresh_view(self.portfolio, self.prices)

        self.push_screen(
            TradeModal(
                side=side,
                ticker=symbol,
                price=price,
                cash=self.portfolio.cash(),
                shares_held=held,
            ),
            _on_close,
        )

    def on_unmount(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
