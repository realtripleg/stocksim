
from __future__ import annotations

import math
import random

from .stocks import SECTOR_RHO, SECTORS, STOCKS

MINUTES_PER_TRADING_DAY: int = 1440
PRICE_FLOOR: float = 0.01


def step(
    prices: dict[str, float],
    dmin: int,
    *,
    rng: random.Random | None = None,
) -> dict[str, float]:
    if dmin <= 0:
        return dict(prices)

    r = rng if rng is not None else random
    dt = dmin / MINUTES_PER_TRADING_DAY
    sqrt_dt = math.sqrt(dt)

    sector_z = {sec: r.gauss(0.0, 1.0) for sec in SECTORS}

    new_prices: dict[str, float] = {}
    for stock in STOCKS:
        rho = SECTOR_RHO[stock.sector]
        z_idio = r.gauss(0.0, 1.0)
        z = rho * sector_z[stock.sector] + math.sqrt(1.0 - rho * rho) * z_idio
        drift = (stock.mu - 0.5 * stock.sigma * stock.sigma) * dt
        diffusion = stock.sigma * sqrt_dt * z
        next_price = prices[stock.symbol] * math.exp(drift + diffusion)
        new_prices[stock.symbol] = max(next_price, PRICE_FLOOR)

    return new_prices
