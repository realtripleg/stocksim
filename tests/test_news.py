from __future__ import annotations

import random

import pytest

from stocksim import news
from stocksim.stocks import seed_prices


def test_zero_dmin_never_fires():
    prices = seed_prices()
    assert news.maybe_event(prices, dmin=0, rng=random.Random(1)) is None


def test_event_rate_matches_lambda():
    rng = random.Random(42)
    prices = seed_prices()
    n = 100_000
    lam = 0.5
    dmin = 1
    expected_p = lam * dmin / news.MINUTES_PER_SIM_DAY
    fires = sum(
        1 for _ in range(n) if news.maybe_event(prices, dmin=dmin, lambda_per_sim_day=lam, rng=rng)
    )
    sample_p = fires / n
    se = (expected_p * (1 - expected_p) / n) ** 0.5
    assert abs(sample_p - expected_p) < 6 * se, (sample_p, expected_p)


def test_event_ticker_is_in_universe():
    rng = random.Random(0)
    prices = seed_prices()
    for _ in range(2000):
        e = news.maybe_event(prices, dmin=10_000, rng=rng)
        if e is not None:
            assert e.ticker in prices


def test_event_pct_change_in_range():
    rng = random.Random(0)
    prices = seed_prices()
    for _ in range(2000):
        e = news.maybe_event(prices, dmin=10_000, rng=rng)
        if e is not None:
            assert news.MIN_SHOCK <= abs(e.pct_change) <= news.MAX_SHOCK


def test_apply_event_shocks_price():
    prices = {"AAPL": 100.0, "MSFT": 200.0}
    e = news.NewsEvent("AAPL", "test", 0.10)
    out = news.apply_event(prices, e)
    assert out["AAPL"] == pytest.approx(110.0)
    assert out["MSFT"] == 200.0
    assert out is not prices


def test_apply_event_negative_shock():
    prices = {"AAPL": 100.0}
    e = news.NewsEvent("AAPL", "test", -0.05)
    out = news.apply_event(prices, e)
    assert out["AAPL"] == pytest.approx(95.0)


def test_apply_event_floors_at_min_price():
    prices = {"AAPL": 0.05}
    e = news.NewsEvent("AAPL", "test", -0.99)
    out = news.apply_event(prices, e)
    assert out["AAPL"] >= 0.01


def test_apply_event_unknown_ticker_is_noop():
    prices = {"AAPL": 100.0}
    e = news.NewsEvent("ZZZZ", "test", 0.10)
    out = news.apply_event(prices, e)
    assert out == prices
