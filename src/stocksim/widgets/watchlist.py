
from __future__ import annotations

from textual.widgets import DataTable

from ..stocks import STOCKS


class WatchlistTable(DataTable):

    def __init__(self) -> None:
        super().__init__(zebra_stripes=True, cursor_type="row", id="watchlist")
        self._row_keys: dict[str, str] = {}

    def on_mount(self) -> None:
        self.add_column("Symbol", width=7, key="symbol")
        self.add_column("Price", width=11, key="price")
        self.add_column("Δ%", width=8, key="delta")
        self.add_column("Sector", width=12, key="sector")
        for stock in STOCKS:
            key = self.add_row(
                stock.symbol,
                f"${stock.seed_price:,.2f}",
                "+0.00%",
                stock.sector,
                key=stock.symbol,
            )
            self._row_keys[stock.symbol] = str(key)

    def refresh_prices(self, prices: dict[str, float]) -> None:
        for stock in STOCKS:
            price = prices.get(stock.symbol, stock.seed_price)
            delta_pct = (price / stock.seed_price - 1.0) * 100.0
            color = "green" if delta_pct >= 0 else "red"
            sign = "+" if delta_pct >= 0 else ""
            self.update_cell(stock.symbol, "price", f"${price:,.2f}")
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
