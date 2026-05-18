from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal


SLOT_SYMBOLS: tuple[str, ...] = ("🍒", "🍋", "🍊", "🔔", "💎", "7️⃣")
SLOT_TRIPLE_PAYOUTS: dict[str, float] = {
    "🍒": 10.0,
    "🍋": 20.0,
    "🍊": 30.0,
    "🔔": 50.0,
    "💎": 100.0,
    "7️⃣": 500.0,
}
SLOT_PAIR_PAYOUT: float = 1.5

COIN_PAYOUT: float = 1.9

DICE_OVER_UNDER_PAYOUT: float = 1.9
DICE_SEVEN_PAYOUT: float = 5.0

ROULETTE_REDS: frozenset[int] = frozenset({
    1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36
})
ROULETTE_EVEN_PAYOUT: float = 1.9
ROULETTE_DOZEN_PAYOUT: float = 2.9

CRASH_HOUSE_EDGE: float = 0.05
CRASH_MIN_MULTIPLIER: float = 1.10


@dataclass(frozen=True)
class SlotsResult:
    reels: tuple[str, str, str]
    multiplier: float


@dataclass(frozen=True)
class CoinResult:
    landed: Literal["heads", "tails"]
    multiplier: float


@dataclass(frozen=True)
class DiceResult:
    rolls: tuple[int, int]
    total: int
    multiplier: float


@dataclass(frozen=True)
class RouletteResult:
    number: int
    color: Literal["red", "black", "green"]
    multiplier: float


def play_slots(rng: random.Random) -> SlotsResult:
    reels = (
        rng.choice(SLOT_SYMBOLS),
        rng.choice(SLOT_SYMBOLS),
        rng.choice(SLOT_SYMBOLS),
    )
    if reels[0] == reels[1] == reels[2]:
        mult = SLOT_TRIPLE_PAYOUTS[reels[0]]
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        mult = SLOT_PAIR_PAYOUT
    else:
        mult = 0.0
    return SlotsResult(reels=reels, multiplier=mult)


def play_coin(
    rng: random.Random, guess: Literal["heads", "tails"]
) -> CoinResult:
    landed: Literal["heads", "tails"] = rng.choice(("heads", "tails"))
    mult = COIN_PAYOUT if landed == guess else 0.0
    return CoinResult(landed=landed, multiplier=mult)


def play_dice(
    rng: random.Random, bet: Literal["over", "under", "seven"]
) -> DiceResult:
    a = rng.randint(1, 6)
    b = rng.randint(1, 6)
    total = a + b
    if bet == "seven":
        mult = DICE_SEVEN_PAYOUT if total == 7 else 0.0
    elif bet == "over":
        mult = DICE_OVER_UNDER_PAYOUT if total > 7 else 0.0
    elif bet == "under":
        mult = DICE_OVER_UNDER_PAYOUT if total < 7 else 0.0
    else:
        mult = 0.0
    return DiceResult(rolls=(a, b), total=total, multiplier=mult)


def roulette_color(n: int) -> Literal["red", "black", "green"]:
    if n == 0:
        return "green"
    if n in ROULETTE_REDS:
        return "red"
    return "black"


def play_roulette(
    rng: random.Random,
    bet: Literal["red", "black", "even", "odd", "dozen1", "dozen2", "dozen3"],
) -> RouletteResult:
    n = rng.randint(0, 36)
    color = roulette_color(n)
    even_win = False
    dozen_win = False
    if bet == "red" and color == "red":
        even_win = True
    elif bet == "black" and color == "black":
        even_win = True
    elif bet == "even" and n != 0 and n % 2 == 0:
        even_win = True
    elif bet == "odd" and n % 2 == 1:
        even_win = True
    elif bet == "dozen1" and 1 <= n <= 12:
        dozen_win = True
    elif bet == "dozen2" and 13 <= n <= 24:
        dozen_win = True
    elif bet == "dozen3" and 25 <= n <= 36:
        dozen_win = True
    if even_win:
        mult = ROULETTE_EVEN_PAYOUT
    elif dozen_win:
        mult = ROULETTE_DOZEN_PAYOUT
    else:
        mult = 0.0
    return RouletteResult(number=n, color=color, multiplier=mult)


def sample_crash_point(rng: random.Random) -> float:
    u = rng.random()
    if u >= 1.0:
        u = 0.999
    return CRASH_MIN_MULTIPLIER + (1.0 - CRASH_HOUSE_EDGE) * u / (1.0 - u)
