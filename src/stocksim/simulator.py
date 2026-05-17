
from __future__ import annotations

import math
import random

from .stocks import ALL_ASSETS, SECTOR_RHO, SECTORS

MINUTES_PER_TRADING_DAY: int = 1440
PRICE_FLOOR: float = 0.01
HOT_VOL_MULTIPLIER: float = 3.0


def step(
    prices: dict[str, float],
    dmin: int,
    *,
    rng: random.Random | None = None,
    hot_ticker: str | None = None,
) -> dict[str, float]:
    if dmin <= 0:
        return dict(prices)

    r = rng if rng is not None else random
    dt = dmin / MINUTES_PER_TRADING_DAY
    sqrt_dt = math.sqrt(dt)

    sector_z = {sec: r.gauss(0.0, 1.0) for sec in SECTORS}

    new_prices: dict[str, float] = {}
    for stock in ALL_ASSETS:
        rho = SECTOR_RHO[stock.sector]
        z_idio = r.gauss(0.0, 1.0)
        z = rho * sector_z[stock.sector] + math.sqrt(1.0 - rho * rho) * z_idio
        sigma = stock.sigma * HOT_VOL_MULTIPLIER if stock.symbol == hot_ticker else stock.sigma
        drift = (stock.mu - 0.5 * stock.sigma * stock.sigma) * dt
        diffusion = sigma * sqrt_dt * z
        next_price = prices[stock.symbol] * math.exp(drift + diffusion)
        new_prices[stock.symbol] = max(next_price, PRICE_FLOOR)

    return new_prices
