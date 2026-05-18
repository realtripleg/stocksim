from __future__ import annotations

import random
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Footer, Header, ListView, RichLog, TabbedContent, TabPane

from . import db, news, simulator
from .clock import SimClock
from .portfolio import Portfolio, TradeError
from .stocks import ALL_ASSETS, CRYPTOS, STOCKS, format_price, seed_prices
from .widgets import CasinoTab, PortfolioPanel, TradeModal, WatchlistTable

TICK_REAL_SECONDS: float = 1.0
TRIM_EVERY_N_TICKS: int = 200
PRICE_HISTORY_KEEP: int = 1440
STOCK_OF_DAY_PROBABILITY: float = 0.4

TAB_STOCKS = "tab-stocks"
TAB_CRYPTO = "tab-crypto"
TAB_CASINO = "tab-casino"
TAB_ORDER = (TAB_STOCKS, TAB_CRYPTO, TAB_CASINO)


class StockSimApp(App):
    CSS_PATH = "styles.tcss"
    TITLE = "StockSim"
    SUB_TITLE = "*** FAKE PRICES — NOT REAL MARKET DATA ***"

    BINDINGS = [
        Binding("b", "buy", "Buy"),
        Binding("s", "sell", "Sell"),
        Binding("f", "toggle_favorite", "Favorite"),
        Binding("t", "switch_tab", "Switch tab"),
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
            with TabbedContent(initial=TAB_STOCKS, id="watchlists"):
                with TabPane("Stocks", id=TAB_STOCKS):
                    yield WatchlistTable(STOCKS, widget_id="watchlist-stocks")
                with TabPane("Crypto", id=TAB_CRYPTO):
                    yield WatchlistTable(CRYPTOS, widget_id="watchlist-crypto")
                with TabPane("Casino", id=TAB_CASINO):
                    yield CasinoTab(widget_id="casino-tab")
            yield PortfolioPanel()
        yield RichLog(id="news-log", max_lines=50, highlight=True, markup=True, wrap=True)
        yield Footer()

    def _active_watchlist(self) -> WatchlistTable:
        tabs = self.query_one(TabbedContent)
        return tabs.active_pane.query_one(WatchlistTable)

    def _all_watchlists(self) -> list[WatchlistTable]:
        return list(self.query(WatchlistTable))

    def on_mount(self) -> None:
        for wl in self._all_watchlists():
            wl.rebuild(self.favorites, self.hot_ticker)
            wl.refresh_prices(self.prices)
        panel = self.query_one(PortfolioPanel)
        panel.refresh_view(self.portfolio, self.prices)
        self._log = self.query_one("#news-log", RichLog)
        self._log.write(
            "[dim]Welcome to StockSim. All prices are simulated. "
            f"Sim time starts at minute {self.clock.sim_minutes}.[/]"
        )
        if self.hot_ticker:
            self._log.write(
                f"[bold yellow]🔥 Today's hot ticker: {self.hot_ticker}[/]"
            )
        self._refresh_subtitle()
        self.set_interval(TICK_REAL_SECONDS, self._tick)
        self.call_after_refresh(self._focus_active_watchlist)

    def _focus_active_watchlist(self) -> None:
        try:
            tabs = self.query_one(TabbedContent)
            if tabs.active == TAB_CASINO:
                self.query_one(CasinoTab).query_one(ListView).focus()
            else:
                self._active_watchlist().focus()
        except Exception:
            pass

    def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        self.call_after_refresh(self._focus_active_watchlist)

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
                [s.symbol for s in ALL_ASSETS],
                keep_last=PRICE_HISTORY_KEEP,
            )

    def _roll_hot_ticker(self, sim_day: int) -> None:
        if self._rng.random() < STOCK_OF_DAY_PROBABILITY:
            new_hot: str | None = self._rng.choice(ALL_ASSETS).symbol
        else:
            new_hot = None
        with db.transaction(self.conn):
            db.set_hot_state(self.conn, sim_day, new_hot)
        self.hot_ticker = new_hot
        if self.is_mounted:
            if new_hot is not None:
                self._log.write(f"[bold yellow]🔥 Today's hot ticker: {new_hot}[/]")
            else:
                self._log.write("[dim]Quiet day — no hot ticker today.[/]")
            try:
                for wl in self._all_watchlists():
                    wl.rebuild(self.favorites, self.hot_ticker)
            except Exception:
                pass

    def watch_prices(self, _old: dict[str, float], new: dict[str, float]) -> None:
        if not new or not self.is_mounted:
            return
        try:
            for wl in self._all_watchlists():
                wl.refresh_prices(new)
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
        self.notify(
            event.headline,
            severity="error" if event.kind == "crash" else "information",
            timeout=5,
        )

    def _log_tip(self, event: news.NewsEvent) -> None:
        self._log.write(f"[yellow italic]🤫 {news.tip_for(event, rng=self._rng)}[/]")

    def action_toggle_pause(self) -> None:
        self.clock.toggle_pause()
        self._refresh_subtitle()

    def action_speed_up(self) -> None:
        self.clock.speed_up()
        self._refresh_subtitle()

    def action_slow_down(self) -> None:
        self.clock.slow_down()
        self._refresh_subtitle()

    def action_switch_tab(self) -> None:
        tabs = self.query_one(TabbedContent)
        idx = TAB_ORDER.index(tabs.active) if tabs.active in TAB_ORDER else 0
        tabs.active = TAB_ORDER[(idx + 1) % len(TAB_ORDER)]

    def _on_casino_tab(self) -> bool:
        try:
            return self.query_one(TabbedContent).active == TAB_CASINO
        except Exception:
            return False

    def action_toggle_favorite(self) -> None:
        if self._on_casino_tab():
            self.notify("Favorites don't apply in the casino.", severity="warning")
            return
        watchlist = self._active_watchlist()
        sym = watchlist.selected_symbol
        if sym is None:
            self.bell()
            return
        with db.transaction(self.conn):
            added = db.toggle_favorite(self.conn, sym)
        self.favorites = db.get_favorites(self.conn)
        for wl in self._all_watchlists():
            wl.rebuild(self.favorites, self.hot_ticker)
            wl.refresh_prices(self.prices)
        if added:
            self._log.write(f"[yellow]★ Pinned {sym}[/]")
        else:
            self._log.write(f"[dim]☆ Unpinned {sym}[/]")

    def action_buy(self) -> None:
        if self._on_casino_tab():
            self._open_casino()
            return
        self._open_trade("buy")

    def action_sell(self) -> None:
        if self._on_casino_tab():
            self._open_casino()
            return
        self._open_trade("sell")

    def on_list_view_selected(self, event) -> None:
        if self._on_casino_tab():
            self._open_casino()

    def _open_casino(self) -> None:
        tab = self.query_one(CasinoTab)
        game = tab.selected_game
        if game is None:
            self.bell()
            return
        cash = self.portfolio.cash()
        if cash <= 0:
            self.notify("You're broke. Go grind some stocks.", severity="warning")
            return

        title = game.title.strip()

        def _on_close(delta: float | None) -> None:
            if delta is None or delta == 0:
                return
            self._apply_casino_delta(delta, title)

        self.push_screen(game.modal_factory(self._rng, cash), _on_close)

    def _apply_casino_delta(self, delta: float, game_title: str) -> None:
        pf = db.get_portfolio(self.conn)
        new_cash = max(0.0, pf.cash + delta)
        with db.transaction(self.conn):
            db.update_portfolio(self.conn, cash=new_cash, sim_minutes=pf.sim_minutes)
        if delta > 0:
            self._log.write(
                f"[bold green]🎲 {game_title}: +${delta:,.2f}[/]"
            )
        else:
            self._log.write(
                f"[bold red]🎲 {game_title}: -${abs(delta):,.2f}[/]"
            )
        self.query_one(PortfolioPanel).refresh_view(self.portfolio, self.prices)

    def _open_trade(self, side: str) -> None:
        watchlist = self._active_watchlist()
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
                        f"[cyan]✓ Bought {r.shares} {r.ticker} @ {format_price(r.price)} "
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
                        f"[magenta]✓ Sold {r.shares} {r.ticker} @ {format_price(r.price)} "
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
