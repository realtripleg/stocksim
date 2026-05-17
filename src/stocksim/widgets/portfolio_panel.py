
from __future__ import annotations

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from ..db import STARTING_CASH
from ..portfolio import Portfolio


class PortfolioPanel(Vertical):

    def __init__(self) -> None:
        super().__init__(id="portfolio")
        self._summary = Static("", id="summary")
        self._positions = Static("", id="positions")

    def compose(self) -> ComposeResult:
        yield Static("[b]Portfolio[/]", classes="panel-title")
        yield self._summary
        yield Static("[b]Positions[/]", classes="panel-title")
        yield self._positions

    def refresh_view(self, portfolio: Portfolio, prices: dict[str, float]) -> None:
        cash = portfolio.cash()
        positions = portfolio.positions()
        holdings_value = sum(
            p.shares * prices.get(p.ticker, p.avg_cost) for p in positions.values()
        )
        total = cash + holdings_value
        pnl = total - STARTING_CASH
        pnl_pct = (total / STARTING_CASH - 1.0) * 100.0

        pnl_color = "green" if pnl >= 0 else "red"
        pnl_sign = "+" if pnl >= 0 else ""
        summary = Text.from_markup(
            f"[b]Cash:[/]      ${cash:,.2f}\n"
            f"[b]Holdings:[/]  ${holdings_value:,.2f}\n"
            f"[b]Total:[/]     ${total:,.2f}\n"
            f"[b]P&L:[/]       [{pnl_color}]{pnl_sign}${pnl:,.2f} ({pnl_sign}{pnl_pct:.2f}%)[/]"
        )
        self._summary.update(summary)

        if not positions:
            self._positions.update("[dim italic]No positions yet — press [b]b[/] to buy.[/]")
            return

        tbl = Table(show_header=True, header_style="bold", expand=True, box=None)
        tbl.add_column("Sym", width=6)
        tbl.add_column("Sh", justify="right", width=5)
        tbl.add_column("Avg", justify="right", width=10)
        tbl.add_column("Now", justify="right", width=10)
        tbl.add_column("P&L", justify="right", width=12)
        for pos in sorted(positions.values(), key=lambda p: p.ticker):
            now = prices.get(pos.ticker, pos.avg_cost)
            pos_pnl = (now - pos.avg_cost) * pos.shares
            color = "green" if pos_pnl >= 0 else "red"
            sign = "+" if pos_pnl >= 0 else ""
            tbl.add_row(
                pos.ticker,
                str(pos.shares),
                f"${pos.avg_cost:,.2f}",
                f"${now:,.2f}",
                f"[{color}]{sign}${pos_pnl:,.2f}[/]",
            )
        self._positions.update(tbl)
