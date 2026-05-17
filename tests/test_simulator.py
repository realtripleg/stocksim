from __future__ import annotations

import math
import random
import statistics

from stocksim import simulator
from stocksim.stocks import STOCKS, seed_prices


def test_step_returns_new_dict():
    prices = seed_prices()
    out = simulator.step(prices, dmin=1, rng=random.Random(42))
    assert out is not prices
    assert set(out) == set(prices)


def test_zero_dmin_is_identity():
    prices = seed_prices()
    out = simulator.step(prices, dmin=0, rng=random.Random(1))
    assert out == prices


def test_deterministic_with_seed():
    prices = seed_prices()
    a = simulator.step(prices, dmin=5, rng=random.Random(123))
    b = simulator.step(prices, dmin=5, rng=random.Random(123))
    assert a == b


def test_prices_never_negative_over_long_run():
    prices = seed_prices()
    rng = random.Random(7)
    for _ in range(10_000):
        prices = simulator.step(prices, dmin=1, rng=rng)
        assert all(p > 0 for p in prices.values()), prices


def test_price_floor_protects_extreme_shocks():
    rng = random.Random(0)
    prices = {s.symbol: 0.02 for s in STOCKS}
    for _ in range(1000):
        prices = simulator.step(prices, dmin=1, rng=rng)
        assert all(p >= simulator.PRICE_FLOOR for p in prices.values())


def test_mean_log_return_close_to_drift():
    rng = random.Random(2025)
    n_trials = 4000
    start = seed_prices()
    target = "AAPL"
    stock = next(s for s in STOCKS if s.symbol == target)
    dmin = 1
    dt = dmin / simulator.MINUTES_PER_TRADING_DAY
    expected = (stock.mu - 0.5 * stock.sigma ** 2) * dt

    log_returns = []
    for _ in range(n_trials):
        out = simulator.step(start, dmin=dmin, rng=rng)
        log_returns.append(math.log(out[target] / start[target]))

    sample_mean = statistics.fmean(log_returns)
    se = stock.sigma * math.sqrt(dt) / math.sqrt(n_trials)
    assert abs(sample_mean - expected) < 5 * se


def test_sample_variance_close_to_sigma_squared_dt():
    rng = random.Random(99)
    n_trials = 4000
    start = seed_prices()
    target = "MSFT"
    stock = next(s for s in STOCKS if s.symbol == target)
    dmin = 1
    dt = dmin / simulator.MINUTES_PER_TRADING_DAY

    log_returns = []
    for _ in range(n_trials):
        out = simulator.step(start, dmin=dmin, rng=rng)
        log_returns.append(math.log(out[target] / start[target]))

    sample_var = statistics.variance(log_returns)
    expected_var = stock.sigma ** 2 * dt
    assert 0.5 * expected_var < sample_var < 1.5 * expected_var


def test_within_sector_correlation_is_positive():
    rng = random.Random(31337)
    n = 1500
    start = seed_prices()
    aapl_rets = []
    msft_rets = []
    xom_rets = []
    for _ in range(n):
        out = simulator.step(start, dmin=1, rng=rng)
        aapl_rets.append(math.log(out["AAPL"] / start["AAPL"]))
        msft_rets.append(math.log(out["MSFT"] / start["MSFT"]))
        xom_rets.append(math.log(out["XOM"] / start["XOM"]))

    def corr(xs, ys):
        mx, my = statistics.fmean(xs), statistics.fmean(ys)
        cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / len(xs)
        sx = statistics.pstdev(xs)
        sy = statistics.pstdev(ys)
        return cov / (sx * sy)

    tech_corr = corr(aapl_rets, msft_rets)
    cross_corr = corr(aapl_rets, xom_rets)
    assert tech_corr > 0.2
    assert tech_corr > cross_corr
