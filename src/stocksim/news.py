
from __future__ import annotations

import random
from dataclasses import dataclass

from .simulator import PRICE_FLOOR
from .stocks import STOCKS

MINUTES_PER_SIM_DAY: int = 1440
DEFAULT_LAMBDA_PER_SIM_DAY: float = 0.5
MIN_SHOCK: float = 0.03
MAX_SHOCK: float = 0.10


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


@dataclass(frozen=True)
class NewsEvent:
    ticker: str
    headline: str
    pct_change: float


def maybe_event(
    prices: dict[str, float],
    *,
    dmin: int = 1,
    lambda_per_sim_day: float = DEFAULT_LAMBDA_PER_SIM_DAY,
    rng: random.Random | None = None,
) -> NewsEvent | None:
    if dmin <= 0:
        return None
    r = rng if rng is not None else random
    p_event = lambda_per_sim_day * dmin / MINUTES_PER_SIM_DAY
    if r.random() >= p_event:
        return None

    stock = r.choice(STOCKS)
    if stock.symbol not in prices:
        return None
    magnitude = r.uniform(MIN_SHOCK, MAX_SHOCK)
    positive = r.random() < 0.5
    pct = magnitude if positive else -magnitude
    template = r.choice(POSITIVE_TEMPLATES if positive else NEGATIVE_TEMPLATES)
    return NewsEvent(
        ticker=stock.symbol,
        headline=template.format(ticker=stock.symbol),
        pct_change=pct,
    )


def apply_event(prices: dict[str, float], event: NewsEvent) -> dict[str, float]:
    new = dict(prices)
    if event.ticker in new:
        shocked = new[event.ticker] * (1.0 + event.pct_change)
        new[event.ticker] = max(shocked, PRICE_FLOOR)
    return new
