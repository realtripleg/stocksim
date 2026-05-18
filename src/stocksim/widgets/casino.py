from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import ListItem, ListView, Static

from .casino_modals import (
    CoinFlipModal,
    CrashModal,
    DiceModal,
    RouletteModal,
    SlotsModal,
)


@dataclass(frozen=True)
class GameEntry:
    key: str
    title: str
    blurb: str
    modal_factory: Callable


GAMES: tuple[GameEntry, ...] = (
    GameEntry("slots",    "🎰  Slots",     "Match 3 symbols — up to 500×",       SlotsModal),
    GameEntry("coin",     "🪙  Coin Flip", "Heads or tails — 1.9×",              CoinFlipModal),
    GameEntry("dice",     "🎲  Dice",      "Bet over/under 7 (1.9×) or seven (5×)", DiceModal),
    GameEntry("roulette", "🎡  Roulette",  "Red/black/even/odd — 1.9×",          RouletteModal),
    GameEntry("crash",    "💥  Crash",     "Cash out before it crashes",         CrashModal),
)

BY_KEY: dict[str, GameEntry] = {g.key: g for g in GAMES}


class CasinoTab(Vertical):
    def __init__(self, *, widget_id: str | None = None) -> None:
        super().__init__(id=widget_id)

    def compose(self) -> ComposeResult:
        yield Static("[b yellow]🎰 Casino[/]", id="casino-header")
        yield Static(
            "[dim]Spend your sim cash. House always wins (in the long run).[/]",
            id="casino-subheader",
        )
        with ListView(id="casino-list"):
            for g in GAMES:
                yield ListItem(
                    Static(f"[b]{g.title}[/]\n  [dim]{g.blurb}[/]"),
                    id=f"game-{g.key}",
                )

    @property
    def selected_game(self) -> GameEntry | None:
        try:
            lv = self.query_one(ListView)
            item = lv.highlighted_child
            if item is None or item.id is None:
                return None
            key = item.id.removeprefix("game-")
            return BY_KEY.get(key)
        except Exception:
            return None
