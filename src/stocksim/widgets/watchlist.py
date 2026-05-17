from __future__ import annotations

from textual.widgets import DataTable

from ..stocks import STOCKS, Stock, format_price


def _symbol_label(symbol: str, favorites: set[str], hot_ticker: str | None) -> str:
    if symbol in favorites:
        return f"★ {symbol}"
    if hot_ticker is not None and symbol == hot_ticker:
        return f"🔥 {symbol}"
    return symbol


class WatchlistTable(DataTable):
    def __init__(
        self,
        assets: tuple[Stock, ...] = STOCKS,
        *,
        widget_id: str | None = None,
    ) -> None:
        super().__init__(zebra_stripes=True, cursor_type="row", id=widget_id)
        self._assets: tuple[Stock, ...] = assets
        self._index: dict[str, int] = {s.symbol: i for i, s in enumerate(self._assets)}
        self._favorites: set[str] = set()
        self._hot_ticker: str | None = None

    def _sorted_assets(self) -> list[Stock]:
        return sorted(
            self._assets,
            key=lambda s: (0 if s.symbol in self._favorites else 1, self._index[s.symbol]),
        )

    def on_mount(self) -> None:
        self.add_column("Symbol", width=10, key="symbol")
        self.add_column("Price", width=12, key="price")
        self.add_column("Δ%", width=8, key="delta")
        self.add_column("Sector", width=12, key="sector")
        for stock in self._sorted_assets():
            self.add_row(
                _symbol_label(stock.symbol, self._favorites, self._hot_ticker),
                format_price(stock.seed_price),
                "+0.00%",
                stock.sector,
                key=stock.symbol,
            )

    def rebuild(self, favorites: set[str], hot_ticker: str | None) -> None:
        if favorites == self._favorites and hot_ticker == self._hot_ticker:
            return
        prev_symbol = self.selected_symbol
        self._favorites = set(favorites)
        self._hot_ticker = hot_ticker
        self.clear()
        ordered = self._sorted_assets()
        for stock in ordered:
            self.add_row(
                _symbol_label(stock.symbol, self._favorites, self._hot_ticker),
                "",
                "",
                stock.sector,
                key=stock.symbol,
            )
        if prev_symbol is not None:
            for i, s in enumerate(ordered):
                if s.symbol == prev_symbol:
                    self.move_cursor(row=i)
                    break

    def refresh_prices(self, prices: dict[str, float]) -> None:
        for stock in self._assets:
            price = prices.get(stock.symbol, stock.seed_price)
            delta_pct = (price / stock.seed_price - 1.0) * 100.0
            color = "green" if delta_pct >= 0 else "red"
            sign = "+" if delta_pct >= 0 else ""
            self.update_cell(stock.symbol, "price", format_price(price))
            self.update_cell(
                stock.symbol,
                "delta",
                f"[{color}]{sign}{delta_pct:.2f}%[/]",
            )

    @property
    def selected_symbol(self) -> str | None:
        if self.row_count == 0:
            return None
        try:
            row = self.coordinate_to_cell_key(self.cursor_coordinate).row_key.value
        except Exception:
            return None
        return row if isinstance(row, str) else None
