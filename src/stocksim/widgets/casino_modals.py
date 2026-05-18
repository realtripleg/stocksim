from __future__ import annotations

import random
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from .. import casino


class _BaseCasinoModal(ModalScreen[float]):
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "close", "Close"),
    ]

    TITLE: ClassVar[str] = ""
    SUBTITLE: ClassVar[str] = ""

    def __init__(self, rng: random.Random, cash: float) -> None:
        super().__init__()
        self.rng = rng
        self._initial_cash = cash
        self.cash = cash
        self._timer = None

    def _refresh_cash(self) -> None:
        try:
            self.query_one("#casino-cash", Static).update(
                f"Cash: [b]${self.cash:,.2f}[/]"
            )
        except Exception:
            pass

    def _parse_bet(self) -> int | None:
        try:
            raw = self.query_one("#bet-input", Input).value
            bet = int(raw)
        except (ValueError, TypeError, Exception):
            return None
        if bet <= 0 or bet > self.cash:
            return None
        return bet

    def _focus_bet(self) -> None:
        try:
            self.query_one("#bet-input", Input).focus()
        except Exception:
            pass

    def action_close(self) -> None:
        if self._timer is not None:
            try:
                self._timer.stop()
            except Exception:
                pass
        self.dismiss(self.cash - self._initial_cash)


class SlotsModal(_BaseCasinoModal):
    TITLE = "🎰 Slots"
    SUBTITLE = "Match 3 symbols — up to 500×"
    SPIN_TICK: ClassVar[float] = 0.07
    STOP_TICKS: ClassVar[tuple[int, int, int]] = (18, 26, 34)

    def __init__(self, rng: random.Random, cash: float) -> None:
        super().__init__(rng, cash)
        self.bet = 0
        self.reels = ["🎰", "🎰", "🎰"]
        self._spinning = False
        self._tick = 0
        self._final: casino.SlotsResult | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="casino-modal"):
            yield Static(f"[b]{self.TITLE}[/]", id="casino-title")
            yield Static(f"[dim]{self.SUBTITLE}[/]", id="casino-subtitle")
            yield Static("Cash: ...", id="casino-cash")
            yield Static(self._reel_str(), id="reels", classes="big-display")
            yield Static("", id="result")
            with Horizontal(classes="casino-controls"):
                yield Input(placeholder="bet $", id="bet-input", restrict=r"[0-9]*")
                yield Button("Spin", id="spin", variant="primary")
                yield Button("Close", id="close")

    def on_mount(self) -> None:
        self._refresh_cash()
        self._focus_bet()

    def _reel_str(self) -> str:
        return "  ".join(f"[ {r} ]" for r in self.reels)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "spin":
            self._start_spin()
        elif event.button.id == "close":
            self.action_close()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._start_spin()

    def _start_spin(self) -> None:
        if self._spinning:
            return
        bet = self._parse_bet()
        if bet is None:
            self.app.bell()
            return
        self.bet = bet
        self.cash -= bet
        self._refresh_cash()
        self.query_one("#result", Static).update("[dim italic]Spinning...[/]")
        self._spinning = True
        self._tick = 0
        self._final = None
        self._timer = self.set_interval(self.SPIN_TICK, self._tick_reels)

    def _tick_reels(self) -> None:
        if not self._spinning:
            return
        self._tick += 1
        for i in range(3):
            if self._tick < self.STOP_TICKS[i]:
                self.reels[i] = self.rng.choice(casino.SLOT_SYMBOLS)
        if self._tick >= self.STOP_TICKS[2]:
            self._final = casino.play_slots(self.rng)
            self.reels = list(self._final.reels)
            try:
                self._timer.stop()
            except Exception:
                pass
            self._spinning = False
            self._show_result()
        self.query_one("#reels", Static).update(self._reel_str())

    def _show_result(self) -> None:
        assert self._final is not None
        payout = self.bet * self._final.multiplier
        self.cash += payout
        net = payout - self.bet
        self._refresh_cash()
        result = self.query_one("#result", Static)
        if payout > 0:
            result.update(
                f"[bold green]+${net:,.2f}[/]  ([b]{self._final.multiplier:g}×[/])"
            )
        else:
            result.update(f"[bold red]-${self.bet:,.2f}[/]")
        self._focus_bet()


class CoinFlipModal(_BaseCasinoModal):
    TITLE = "🪙 Coin Flip"
    SUBTITLE = "Heads or tails — 1.9× payout"
    FLIP_TICK: ClassVar[float] = 0.06
    FLIP_DURATION_TICKS: ClassVar[int] = 22

    def __init__(self, rng: random.Random, cash: float) -> None:
        super().__init__(rng, cash)
        self.bet = 0
        self.guess: str = "heads"
        self.face: str = "?"
        self._tick = 0
        self._flipping = False
        self._final: casino.CoinResult | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="casino-modal"):
            yield Static(f"[b]{self.TITLE}[/]", id="casino-title")
            yield Static(f"[dim]{self.SUBTITLE}[/]", id="casino-subtitle")
            yield Static("Cash: ...", id="casino-cash")
            yield Static(self._face_str(), id="coin", classes="big-display")
            yield Static("", id="result")
            with Horizontal(classes="casino-controls"):
                yield Input(placeholder="bet", id="bet-input", restrict=r"[0-9]*")
                yield Button("Heads", id="heads", variant="primary")
                yield Button("Tails", id="tails", variant="primary")
                yield Button("Close", id="close")

    def on_mount(self) -> None:
        self._refresh_cash()
        self._focus_bet()

    def _face_str(self) -> str:
        return f"[b]  {self.face}  [/]"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "heads":
            self.guess = "heads"
            self._start_flip()
        elif event.button.id == "tails":
            self.guess = "tails"
            self._start_flip()
        elif event.button.id == "close":
            self.action_close()

    def _start_flip(self) -> None:
        if self._flipping:
            return
        bet = self._parse_bet()
        if bet is None:
            self.app.bell()
            return
        self.bet = bet
        self.cash -= bet
        self._refresh_cash()
        self.query_one("#result", Static).update(
            f"[dim italic]Flipping... guessed {self.guess}[/]"
        )
        self._tick = 0
        self._flipping = True
        self._final = None
        self._timer = self.set_interval(self.FLIP_TICK, self._tick_flip)

    def _tick_flip(self) -> None:
        if not self._flipping:
            return
        self._tick += 1
        if self._tick < self.FLIP_DURATION_TICKS:
            self.face = self.rng.choice(("H", "T", "•"))
            self.query_one("#coin", Static).update(self._face_str())
            return
        self._final = casino.play_coin(self.rng, self.guess)
        self.face = "H" if self._final.landed == "heads" else "T"
        self.query_one("#coin", Static).update(self._face_str())
        try:
            self._timer.stop()
        except Exception:
            pass
        self._flipping = False
        self._show_result()

    def _show_result(self) -> None:
        assert self._final is not None
        payout = self.bet * self._final.multiplier
        self.cash += payout
        net = payout - self.bet
        self._refresh_cash()
        result = self.query_one("#result", Static)
        if payout > 0:
            result.update(f"[bold green]+${net:,.2f}[/]  ([b]{self._final.landed}[/])")
        else:
            result.update(
                f"[bold red]-${self.bet:,.2f}[/]  ([b]{self._final.landed}[/])"
            )
        self._focus_bet()


_PIPS_BLANK = "   "
_PIPS_DOT = " ● "
_DICE_PIPS: dict[int, tuple[str, str, str, str, str, str, str, str, str]] = {
    1: (_PIPS_BLANK, _PIPS_BLANK, _PIPS_BLANK,
        _PIPS_BLANK, _PIPS_DOT,   _PIPS_BLANK,
        _PIPS_BLANK, _PIPS_BLANK, _PIPS_BLANK),
    2: (_PIPS_DOT,   _PIPS_BLANK, _PIPS_BLANK,
        _PIPS_BLANK, _PIPS_BLANK, _PIPS_BLANK,
        _PIPS_BLANK, _PIPS_BLANK, _PIPS_DOT),
    3: (_PIPS_DOT,   _PIPS_BLANK, _PIPS_BLANK,
        _PIPS_BLANK, _PIPS_DOT,   _PIPS_BLANK,
        _PIPS_BLANK, _PIPS_BLANK, _PIPS_DOT),
    4: (_PIPS_DOT,   _PIPS_BLANK, _PIPS_DOT,
        _PIPS_BLANK, _PIPS_BLANK, _PIPS_BLANK,
        _PIPS_DOT,   _PIPS_BLANK, _PIPS_DOT),
    5: (_PIPS_DOT,   _PIPS_BLANK, _PIPS_DOT,
        _PIPS_BLANK, _PIPS_DOT,   _PIPS_BLANK,
        _PIPS_DOT,   _PIPS_BLANK, _PIPS_DOT),
    6: (_PIPS_DOT,   _PIPS_BLANK, _PIPS_DOT,
        _PIPS_DOT,   _PIPS_BLANK, _PIPS_DOT,
        _PIPS_DOT,   _PIPS_BLANK, _PIPS_DOT),
}


def _render_die(face: int) -> list[str]:
    pips = _DICE_PIPS[face]
    return [
        "┌─────────┐",
        "│" + pips[0] + pips[1] + pips[2] + "│",
        "│" + pips[3] + pips[4] + pips[5] + "│",
        "│" + pips[6] + pips[7] + pips[8] + "│",
        "└─────────┘",
    ]


def _render_dice_pair(a: int, b: int) -> str:
    left = _render_die(a)
    right = _render_die(b)
    return "\n".join(f"{l}   {r}" for l, r in zip(left, right))


class DiceModal(_BaseCasinoModal):
    TITLE = "🎲 Dice"
    SUBTITLE = "Bet over/under 7 (1.9×) or exactly 7 (5×)"
    ROLL_TICK: ClassVar[float] = 0.06
    ROLL_DURATION_TICKS: ClassVar[int] = 20

    def __init__(self, rng: random.Random, cash: float) -> None:
        super().__init__(rng, cash)
        self.bet = 0
        self.guess: str = "over"
        self.rolls: tuple[int, int] = (1, 1)
        self._tick = 0
        self._rolling = False
        self._final: casino.DiceResult | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="casino-modal"):
            yield Static(f"[b]{self.TITLE}[/]", id="casino-title")
            yield Static(f"[dim]{self.SUBTITLE}[/]", id="casino-subtitle")
            yield Static("Cash: ...", id="casino-cash")
            yield Static(self._dice_str(), id="dice", classes="dice-display")
            yield Static(f"sum: [b]{sum(self.rolls)}[/]", id="dice-sum")
            yield Static("", id="result")
            with Horizontal(classes="casino-controls"):
                yield Input(placeholder="bet", id="bet-input", restrict=r"[0-9]*")
                yield Button("Under 7", id="under", variant="primary")
                yield Button("Exactly 7", id="seven", variant="warning")
                yield Button("Over 7", id="over", variant="primary")
                yield Button("Close", id="close")

    def on_mount(self) -> None:
        self._refresh_cash()
        self._focus_bet()

    def _dice_str(self) -> str:
        return _render_dice_pair(self.rolls[0], self.rolls[1])

    def _sum_str(self) -> str:
        return f"sum: [b]{sum(self.rolls)}[/]"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in ("under", "over", "seven"):
            self.guess = event.button.id
            self._start_roll()
        elif event.button.id == "close":
            self.action_close()

    def _start_roll(self) -> None:
        if self._rolling:
            return
        bet = self._parse_bet()
        if bet is None:
            self.app.bell()
            return
        self.bet = bet
        self.cash -= bet
        self._refresh_cash()
        self.query_one("#result", Static).update(
            f"[dim italic]Rolling... ({self.guess})[/]"
        )
        self._tick = 0
        self._rolling = True
        self._final = None
        self._timer = self.set_interval(self.ROLL_TICK, self._tick_roll)

    def _tick_roll(self) -> None:
        if not self._rolling:
            return
        self._tick += 1
        if self._tick < self.ROLL_DURATION_TICKS:
            self.rolls = (self.rng.randint(1, 6), self.rng.randint(1, 6))
            self.query_one("#dice", Static).update(self._dice_str())
            self.query_one("#dice-sum", Static).update(self._sum_str())
            return
        self._final = casino.play_dice(self.rng, self.guess)
        self.rolls = self._final.rolls
        self.query_one("#dice", Static).update(self._dice_str())
        self.query_one("#dice-sum", Static).update(self._sum_str())
        try:
            self._timer.stop()
        except Exception:
            pass
        self._rolling = False
        self._show_result()

    def _show_result(self) -> None:
        assert self._final is not None
        payout = self.bet * self._final.multiplier
        self.cash += payout
        net = payout - self.bet
        self._refresh_cash()
        result = self.query_one("#result", Static)
        if payout > 0:
            result.update(
                f"[bold green]+${net:,.2f}[/]  ([b]total {self._final.total}[/], {self._final.multiplier:g}×)"
            )
        else:
            result.update(
                f"[bold red]-${self.bet:,.2f}[/]  ([b]total {self._final.total}[/])"
            )
        self._focus_bet()


def _roulette_board(landed: int | None = None) -> str:
    def cell(n: int) -> str:
        color = casino.roulette_color(n)
        if color == "red":
            bg = "white on red"
        elif color == "green":
            bg = "white on green"
        else:
            bg = "white on grey15"
        marker = "*" if n == landed else " "
        return f"[{bg}]{marker}{n:>2}[/]"

    top_row = [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36]
    mid_row = [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35]
    bot_row = [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34]

    pad = "    "
    line1 = pad + " ".join(cell(n) for n in top_row)
    line2 = cell(0) + " " + " ".join(cell(n) for n in mid_row)
    line3 = pad + " ".join(cell(n) for n in bot_row)
    dozens = pad + "[dim] └─ 1st 12 ─┘ └─ 2nd 12 ─┘ └─ 3rd 12 ─┘[/]"
    return f"{line1}\n{line2}\n{line3}\n{dozens}"


class RouletteModal(_BaseCasinoModal):
    TITLE = "🎡 Roulette"
    SUBTITLE = "R / B / E / O — 1.9×    1-12 / 13-24 / 25-36 — 2.9×"
    SPIN_TICK: ClassVar[float] = 0.05
    SPIN_DURATION_TICKS: ClassVar[int] = 35

    def __init__(self, rng: random.Random, cash: float) -> None:
        super().__init__(rng, cash)
        self.bet = 0
        self.guess: str = "red"
        self.number = 0
        self._tick = 0
        self._spinning = False
        self._final: casino.RouletteResult | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="casino-modal", classes="roulette"):
            yield Static(f"[b]{self.TITLE}[/]", id="casino-title")
            yield Static(f"[dim]{self.SUBTITLE}[/]", id="casino-subtitle")
            yield Static("Cash: ...", id="casino-cash")
            yield Static(_roulette_board(None), id="wheel", classes="roulette-board")
            yield Static(self._latest_str(), id="latest")
            yield Static("", id="result")
            with Horizontal(classes="casino-controls"):
                yield Input(placeholder="bet", id="bet-input", restrict=r"[0-9]*")
                yield Button("Red", id="red", variant="error")
                yield Button("Black", id="black", variant="default")
                yield Button("Even", id="even", variant="primary")
                yield Button("Odd", id="odd", variant="primary")
            with Horizontal(classes="casino-controls"):
                yield Button("1-12", id="dozen1", variant="success")
                yield Button("13-24", id="dozen2", variant="success")
                yield Button("25-36", id="dozen3", variant="success")
                yield Button("Close", id="close")

    def on_mount(self) -> None:
        self._refresh_cash()
        self._focus_bet()

    def _latest_str(self) -> str:
        color = casino.roulette_color(self.number)
        return f"latest: [b]{self.number} ({color})[/]"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid in ("red", "black", "even", "odd", "dozen1", "dozen2", "dozen3"):
            self.guess = bid
            self._start_spin()
        elif bid == "close":
            self.action_close()

    def _start_spin(self) -> None:
        if self._spinning:
            return
        bet = self._parse_bet()
        if bet is None:
            self.app.bell()
            return
        self.bet = bet
        self.cash -= bet
        self._refresh_cash()
        self.query_one("#result", Static).update(
            f"[dim italic]Spinning... ({self.guess})[/]"
        )
        self._tick = 0
        self._spinning = True
        self._final = None
        self._timer = self.set_interval(self.SPIN_TICK, self._tick_spin)

    def _tick_spin(self) -> None:
        if not self._spinning:
            return
        self._tick += 1
        if self._tick < self.SPIN_DURATION_TICKS:
            self.number = self.rng.randint(0, 36)
            self.query_one("#wheel", Static).update(_roulette_board(self.number))
            self.query_one("#latest", Static).update(self._latest_str())
            return
        self._final = casino.play_roulette(self.rng, self.guess)
        self.number = self._final.number
        self.query_one("#wheel", Static).update(_roulette_board(self.number))
        self.query_one("#latest", Static).update(self._latest_str())
        try:
            self._timer.stop()
        except Exception:
            pass
        self._spinning = False
        self._show_result()

    def _show_result(self) -> None:
        assert self._final is not None
        payout = self.bet * self._final.multiplier
        self.cash += payout
        net = payout - self.bet
        self._refresh_cash()
        result = self.query_one("#result", Static)
        landed = f"{self._final.number} {self._final.color}"
        if payout > 0:
            result.update(
                f"[bold green]+${net:,.2f}[/]  ([b]{landed}[/], {self._final.multiplier:g}×)"
            )
        else:
            result.update(f"[bold red]-${self.bet:,.2f}[/]  ([b]{landed}[/])")
        self._focus_bet()


class CrashModal(_BaseCasinoModal):
    TITLE = "💥 Crash"
    SUBTITLE = "Press space (or Cash Out) before it crashes"
    TICK: ClassVar[float] = 0.05
    GROWTH: ClassVar[float] = 1.008

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("space", "cash_out", "Cash out"),
        Binding("escape", "close", "Close"),
    ]

    def __init__(self, rng: random.Random, cash: float) -> None:
        super().__init__(rng, cash)
        self.bet = 0
        self._crash_at = 0.0
        self._multiplier = 1.0
        self._running = False
        self._cashed_out = False

    def compose(self) -> ComposeResult:
        with Vertical(id="casino-modal"):
            yield Static(f"[b]{self.TITLE}[/]", id="casino-title")
            yield Static(f"[dim]{self.SUBTITLE}[/]", id="casino-subtitle")
            yield Static("Cash: ...", id="casino-cash")
            yield Static("1.00×", id="crash-display", classes="big-display")
            yield Static("", id="result")
            with Horizontal(classes="casino-controls", id="bet-controls"):
                yield Input(placeholder="bet", id="bet-input", restrict=r"[0-9]*")
                yield Button("Go", id="go", variant="primary")
                yield Button("Close", id="close")
            with Horizontal(classes="casino-controls hidden", id="cashout-controls"):
                yield Button(
                    "Cash Out  (space)",
                    id="cash-out",
                    variant="success",
                )

    def on_mount(self) -> None:
        self._refresh_cash()
        self._focus_bet()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "go":
            self._start()
        elif event.button.id == "cash-out":
            self.action_cash_out()
        elif event.button.id == "close":
            self.action_close()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._start()

    def _show_bet_controls(self) -> None:
        try:
            self.query_one("#bet-controls").remove_class("hidden")
            self.query_one("#cashout-controls").add_class("hidden")
        except Exception:
            pass

    def _show_cashout_controls(self) -> None:
        try:
            self.query_one("#bet-controls").add_class("hidden")
            self.query_one("#cashout-controls").remove_class("hidden")
            self.query_one("#cash-out", Button).focus()
        except Exception:
            pass

    def _start(self) -> None:
        if self._running:
            return
        bet = self._parse_bet()
        if bet is None:
            self.app.bell()
            return
        self.bet = bet
        self.cash -= bet
        self._refresh_cash()
        self._crash_at = casino.sample_crash_point(self.rng)
        self._multiplier = 1.0
        self._running = True
        self._cashed_out = False
        self.query_one("#result", Static).update(
            "[yellow]Press [b]space[/] to cash out![/]"
        )
        self._show_cashout_controls()
        self._timer = self.set_interval(self.TICK, self._tick)

    def _tick(self) -> None:
        if not self._running:
            return
        self._multiplier *= self.GROWTH
        if self._multiplier >= self._crash_at:
            try:
                self._timer.stop()
            except Exception:
                pass
            self._running = False
            self.query_one("#crash-display", Static).update(
                f"[bold red]💥 CRASHED @ {self._crash_at:.2f}×[/]"
            )
            self.query_one("#result", Static).update(
                f"[bold red]-${self.bet:,.2f}[/]"
            )
            self._show_bet_controls()
            self._focus_bet()
            return
        color = self._color_for(self._multiplier)
        self.query_one("#crash-display", Static).update(
            f"[bold {color}]{self._multiplier:.2f}×[/]"
        )

    def _color_for(self, m: float) -> str:
        if m < 2:
            return "white"
        if m < 5:
            return "yellow"
        if m < 10:
            return "orange1"
        return "red"

    def action_cash_out(self) -> None:
        if not self._running or self._cashed_out:
            return
        self._cashed_out = True
        self._running = False
        try:
            self._timer.stop()
        except Exception:
            pass
        payout = self.bet * self._multiplier
        self.cash += payout
        net = payout - self.bet
        self._refresh_cash()
        self.query_one("#crash-display", Static).update(
            f"[bold green]✓ {self._multiplier:.2f}×[/]"
        )
        sign = "+" if net >= 0 else ""
        self.query_one("#result", Static).update(
            f"[bold green]{sign}${net:,.2f}[/]"
        )
        self._show_bet_controls()
        self._focus_bet()
