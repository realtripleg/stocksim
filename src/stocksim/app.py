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
STOCK_OF_DAY_PROBABILITY: float = 0.4


class StockSimApp(App):
    CSS_PATH = "styles.tcss"
    TITLE = "StockSim"
    SUB_TITLE = "*** FAKE PRICES — NOT REAL MARKET DATA ***"

    BINDINGS = [
        Binding("b", "buy", "Buy"),
        Binding("s", "sell", "Sell"),
        Binding("f", "toggle_favorite", "Favorite"),
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

        self.favorites: set[str] = db.get_favorites(self.conn)
        hot = db.get_hot_state(self.conn)
        self.hot_ticker: str | None = hot.ticker
        self._last_sim_day: int = hot.sim_day

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
        watchlist.rebuild(self.favorites, self.hot_ticker)
        watchlist.refresh_prices(self.prices)
        panel.refresh_view(self.portfolio, self.prices)
        self._log = self.query_one("#news-log", RichLog)
        self._log.write(
            "[dim]Welcome to StockSim. All prices are simulated. "
            f"Sim time starts at minute {self.clock.sim_minutes}.[/]"
        )
        if self.hot_ticker:
            self._log.write(
                f"[bold yellow]🔥 Today's hot stock: {self.hot_ticker}[/]"
            )
        self._refresh_subtitle()
        self.set_interval(TICK_REAL_SECONDS, self._tick)

    def _tick(self) -> None:
        dmin = self.clock.advance(TICK_REAL_SECONDS)
        if dmin <= 0:
            return

        current_day = self.clock.sim_minutes // simulator.MINUTES_PER_TRADING_DAY
        if current_day != self._last_sim_day:
            self._roll_hot_ticker(current_day)
            self._last_sim_day = current_day

        new_prices = simulator.step(
            self.prices, dmin, rng=self._rng, hot_ticker=self.hot_ticker
        )

        event = news.maybe_event(
            new_prices, dmin=dmin, rng=self._rng, hot_ticker=self.hot_ticker
        )
        if event is not None:
            new_prices = news.apply_event(new_prices, event)
            self._log_event(event)

        mevent = news.maybe_market_event(dmin=dmin, rng=self._rng)
        if mevent is not None:
            new_prices = news.apply_market_event(new_prices, mevent)
            self._log_market_event(mevent)

        tip = news.maybe_schedule_tip(
            new_prices,
            current_sim_ts=self.clock.sim_minutes,
            dmin=dmin,
            rng=self._rng,
            hot_ticker=self.hot_ticker,
        )

        with db.transaction(self.conn):
            if tip is not None:
                tip_event, scheduled_ts = tip
                db.schedule_event(
                    self.conn,
                    ticker=tip_event.ticker,
                    headline=tip_event.headline,
                    pct_change=tip_event.pct_change,
                    scheduled_sim_ts=scheduled_ts,
                )
                self._log_tip(tip_event)

            for row in db.peek_due_events(self.conn, self.clock.sim_minutes):
                ev = news.NewsEvent(
                    ticker=row["ticker"],
                    headline=row["headline"],
                    pct_change=row["pct_change"],
                )
                new_prices = news.apply_event(new_prices, ev)
                self._log_event(ev)
                db.delete_event(self.conn, row["id"])

            db.insert_prices(self.conn, self.clock.sim_minutes, new_prices)
            db.update_sim_minutes(self.conn, self.clock.sim_minutes)

        self.prices = new_prices

        self._tick_count += 1
        if self._tick_count % TRIM_EVERY_N_TICKS == 0:
            db.trim_prices(
                self.conn,
                [s.symbol for s in STOCKS],
                keep_last=PRICE_HISTORY_KEEP,
            )

    def _roll_hot_ticker(self, sim_day: int) -> None:
        if self._rng.random() < STOCK_OF_DAY_PROBABILITY:
            new_hot: str | None = self._rng.choice(STOCKS).symbol
        else:
            new_hot = None
        with db.transaction(self.conn):
            db.set_hot_state(self.conn, sim_day, new_hot)
        self.hot_ticker = new_hot
        if self.is_mounted:
            if new_hot is not None:
                self._log.write(f"[bold yellow]🔥 Today's hot stock: {new_hot}[/]")
            else:
                self._log.write("[dim]Quiet day — no hot stock today.[/]")
            try:
                self.query_one(WatchlistTable).rebuild(self.favorites, self.hot_ticker)
            except Exception:
                pass

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

    def _log_market_event(self, event: news.MarketEvent) -> None:
        color = "bold red" if event.kind == "crash" else "bold green"
        sign = "+" if event.pct_change >= 0 else ""
        self._log.write(
            f"[{color}]💥 {event.headline} ({sign}{event.pct_change * 100:.1f}%)[/]"
        )
        self.notify(event.headline, severity="error" if event.kind == "crash" else "information", timeout=5)

    def _log_tip(self, event: news.NewsEvent) -> None:
        self._log.write(f"[yellow italic]🤫 {news.tip_for(event, rng=self._rng)}[/]")

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

    def action_toggle_favorite(self) -> None:
        watchlist = self.query_one(WatchlistTable)
        sym = watchlist.selected_symbol
        if sym is None:
            self.bell()
            return
        with db.transaction(self.conn):
            added = db.toggle_favorite(self.conn, sym)
        self.favorites = db.get_favorites(self.conn)
        watchlist.rebuild(self.favorites, self.hot_ticker)
        watchlist.refresh_prices(self.prices)
        if added:
            self._log.write(f"[yellow]★ Pinned {sym}[/]")
        else:
            self._log.write(f"[dim]☆ Unpinned {sym}[/]")

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
