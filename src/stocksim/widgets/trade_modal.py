
from __future__ import annotations

from typing import Literal

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static


class TradeModal(ModalScreen[tuple[int, str] | None]):

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        *,
        side: Literal["buy", "sell"],
        ticker: str,
        price: float,
        cash: float,
        shares_held: int = 0,
    ) -> None:
        super().__init__()
        self.side = side
        self.ticker = ticker
        self.price = price
        self.cash = cash
        self.shares_held = shares_held

    def compose(self) -> ComposeResult:
        verb = "Buy" if self.side == "buy" else "Sell"
        max_affordable = int(self.cash // self.price) if self.side == "buy" else self.shares_held
        with Vertical(id="trade-modal"):
            yield Static(f"[b]{verb} {self.ticker}[/]", id="trade-title")
            yield Static(f"Price: [b]${self.price:,.2f}[/]")
            if self.side == "buy":
                yield Static(
                    f"Cash: ${self.cash:,.2f}    Max: {max_affordable} sh"
                )
            else:
                yield Static(f"Holding: {self.shares_held} sh")
            yield Input(placeholder="shares", id="shares-input", restrict=r"[0-9]*")
            yield Static("", id="estimate")
            with Horizontal(id="trade-buttons"):
                yield Button(verb, id="confirm", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_input_changed(self, event: Input.Changed) -> None:
        est = self.query_one("#estimate", Static)
        try:
            n = int(event.value) if event.value else 0
        except ValueError:
            est.update("")
            return
        if n <= 0:
            est.update("")
            return
        total = n * self.price
        if self.side == "buy":
            after = self.cash - total
            color = "green" if after >= 0 else "red"
            est.update(
                f"Total: [b]${total:,.2f}[/]    Cash after: [{color}]${after:,.2f}[/]"
            )
        else:
            if n > self.shares_held:
                est.update(f"[red]Only have {self.shares_held} sh[/]")
            else:
                est.update(f"Proceeds: [b]${total:,.2f}[/]")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self._submit()
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _submit(self) -> None:
        inp = self.query_one("#shares-input", Input)
        try:
            n = int(inp.value)
        except ValueError:
            self.app.bell()
            return
        if n <= 0:
            self.app.bell()
            return
        if self.side == "buy" and n * self.price > self.cash:
            self.app.bell()
            return
        if self.side == "sell" and n > self.shares_held:
            self.app.bell()
            return
        self.dismiss((n, self.side))
