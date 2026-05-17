from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

from .simulator import PRICE_FLOOR
from .stocks import STOCKS, Stock

MINUTES_PER_SIM_DAY: int = 1440
DEFAULT_LAMBDA_PER_SIM_DAY: float = 0.5
MIN_SHOCK: float = 0.03
MAX_SHOCK: float = 0.10

CRASH_LAMBDA_PER_SIM_DAY: float = 0.2
RALLY_LAMBDA_PER_SIM_DAY: float = 0.1
CRASH_MIN: float = 0.10
CRASH_MAX: float = 0.20
RALLY_MIN: float = 0.03
RALLY_MAX: float = 0.08

TIP_LAMBDA_PER_SIM_DAY: float = 0.2
TIP_DELAY_MIN: int = 30
TIP_DELAY_MAX: int = 60

HOT_WEIGHT: float = 3.0


POSITIVE_TEMPLATES: tuple[str, ...] = (
    "{ticker} beats earnings expectations",
    "Analyst upgrade lifts {ticker}",
    "{ticker} announces record buyback",
    "{ticker} unveils breakthrough product",
    "{ticker} wins major contract",
    "{ticker} raises full-year guidance",
)

NEGATIVE_TEMPLATES: tuple[str, ...] = (
    "{ticker} misses on earnings",
    "Regulator opens probe into {ticker}",
    "{ticker} cuts forward guidance",
    "Key executive departs {ticker}",
    "{ticker} hit with class-action lawsuit",
    "Downgrade weighs on {ticker}",
)

CRASH_TEMPLATES: tuple[str, ...] = (
    "Markets in free-fall — broad sell-off",
    "Flash crash sweeps the tape",
    "Risk-off rout: every sector in the red",
    "Liquidation cascade hits global markets",
)

RALLY_TEMPLATES: tuple[str, ...] = (
    "Surprise rally lifts every sector",
    "Risk-on bid drives a broad melt-up",
    "Markets rip higher on positive sentiment",
)

TIP_TEMPLATES: tuple[str, ...] = (
    "Whispers around {ticker} — something coming in the next hour",
    "Trading desks are watching {ticker} closely",
    "Unverified chatter points to {ticker}",
    "Insider buzz: keep an eye on {ticker}",
)


@dataclass(frozen=True)
class NewsEvent:
    ticker: str
    headline: str
    pct_change: float


@dataclass(frozen=True)
class MarketEvent:
    headline: str
    pct_change: float
    kind: Literal["crash", "rally"]


def pick_ticker_weighted(
    rng: random.Random,
    *,
    hot_ticker: str | None = None,
) -> Stock:
    if hot_ticker is None:
        return rng.choice(STOCKS)
    weights = [HOT_WEIGHT if s.symbol == hot_ticker else 1.0 for s in STOCKS]
    return rng.choices(STOCKS, weights=weights, k=1)[0]


def _build_news_event(rng: random.Random, stock: Stock) -> NewsEvent:
    magnitude = rng.uniform(MIN_SHOCK, MAX_SHOCK)
    positive = rng.random() < 0.5
    pct = magnitude if positive else -magnitude
    template = rng.choice(POSITIVE_TEMPLATES if positive else NEGATIVE_TEMPLATES)
    return NewsEvent(
        ticker=stock.symbol,
        headline=template.format(ticker=stock.symbol),
        pct_change=pct,
    )


def maybe_event(
    prices: dict[str, float],
    *,
    dmin: int = 1,
    lambda_per_sim_day: float = DEFAULT_LAMBDA_PER_SIM_DAY,
    rng: random.Random | None = None,
    hot_ticker: str | None = None,
) -> NewsEvent | None:
    if dmin <= 0:
        return None
    r = rng if rng is not None else random
    p_event = lambda_per_sim_day * dmin / MINUTES_PER_SIM_DAY
    if r.random() >= p_event:
        return None
    stock = pick_ticker_weighted(r, hot_ticker=hot_ticker)
    if stock.symbol not in prices:
        return None
    return _build_news_event(r, stock)


def apply_event(prices: dict[str, float], event: NewsEvent) -> dict[str, float]:
    new = dict(prices)
    if event.ticker in new:
        shocked = new[event.ticker] * (1.0 + event.pct_change)
        new[event.ticker] = max(shocked, PRICE_FLOOR)
    return new


def maybe_market_event(
    *,
    dmin: int = 1,
    rng: random.Random | None = None,
) -> MarketEvent | None:
    if dmin <= 0:
        return None
    r = rng if rng is not None else random
    p_crash = CRASH_LAMBDA_PER_SIM_DAY * dmin / MINUTES_PER_SIM_DAY
    if r.random() < p_crash:
        pct = -r.uniform(CRASH_MIN, CRASH_MAX)
        return MarketEvent(
            headline=r.choice(CRASH_TEMPLATES),
            pct_change=pct,
            kind="crash",
        )
    p_rally = RALLY_LAMBDA_PER_SIM_DAY * dmin / MINUTES_PER_SIM_DAY
    if r.random() < p_rally:
        pct = r.uniform(RALLY_MIN, RALLY_MAX)
        return MarketEvent(
            headline=r.choice(RALLY_TEMPLATES),
            pct_change=pct,
            kind="rally",
        )
    return None


def apply_market_event(
    prices: dict[str, float], event: MarketEvent
) -> dict[str, float]:
    factor = 1.0 + event.pct_change
    return {t: max(p * factor, PRICE_FLOOR) for t, p in prices.items()}


def maybe_schedule_tip(
    prices: dict[str, float],
    *,
    current_sim_ts: int,
    dmin: int = 1,
    rng: random.Random | None = None,
    hot_ticker: str | None = None,
) -> tuple[NewsEvent, int] | None:
    if dmin <= 0:
        return None
    r = rng if rng is not None else random
    p = TIP_LAMBDA_PER_SIM_DAY * dmin / MINUTES_PER_SIM_DAY
    if r.random() >= p:
        return None
    stock = pick_ticker_weighted(r, hot_ticker=hot_ticker)
    if stock.symbol not in prices:
        return None
    event = _build_news_event(r, stock)
    delay = r.randint(TIP_DELAY_MIN, TIP_DELAY_MAX)
    return event, current_sim_ts + delay


def tip_for(event: NewsEvent, rng: random.Random | None = None) -> str:
    r = rng if rng is not None else random
    return r.choice(TIP_TEMPLATES).format(ticker=event.ticker)
