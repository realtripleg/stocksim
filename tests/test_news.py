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


def test_market_event_crash_rate_matches_lambda():
    rng = random.Random(7)
    n = 200_000
    dmin = 1
    expected_p = (
        news.CRASH_LAMBDA_PER_SIM_DAY + news.RALLY_LAMBDA_PER_SIM_DAY
    ) * dmin / news.MINUTES_PER_SIM_DAY
    fires = sum(1 for _ in range(n) if news.maybe_market_event(dmin=dmin, rng=rng))
    sample_p = fires / n
    se = (expected_p * (1 - expected_p) / n) ** 0.5
    assert abs(sample_p - expected_p) < 6 * se


def test_market_event_crash_has_negative_shock():
    rng = random.Random(0)
    crashes = 0
    for _ in range(5000):
        e = news.maybe_market_event(dmin=500, rng=rng)
        if e is not None and e.kind == "crash":
            crashes += 1
            assert -news.CRASH_MAX <= e.pct_change <= -news.CRASH_MIN
    assert crashes > 0


def test_market_event_rally_has_positive_shock():
    rng = random.Random(1)
    rallies = 0
    for _ in range(5000):
        e = news.maybe_market_event(dmin=500, rng=rng)
        if e is not None and e.kind == "rally":
            rallies += 1
            assert news.RALLY_MIN <= e.pct_change <= news.RALLY_MAX
    assert rallies > 0


def test_apply_market_event_shocks_every_ticker():
    prices = {"AAPL": 100.0, "MSFT": 200.0, "TSLA": 50.0}
    e = news.MarketEvent(headline="x", pct_change=-0.15, kind="crash")
    out = news.apply_market_event(prices, e)
    assert out["AAPL"] == pytest.approx(85.0)
    assert out["MSFT"] == pytest.approx(170.0)
    assert out["TSLA"] == pytest.approx(42.5)
    assert out is not prices


def test_apply_market_event_floors():
    prices = {"AAPL": 0.05, "MSFT": 200.0}
    e = news.MarketEvent(headline="x", pct_change=-0.99, kind="crash")
    out = news.apply_market_event(prices, e)
    assert out["AAPL"] >= 0.01
    assert out["MSFT"] >= 0.01


def test_pick_ticker_weighted_uniform():
    rng = random.Random(123)
    counts: dict[str, int] = {}
    n_total = len(news.ALL_ASSETS)
    n_iter = 60_000
    for _ in range(n_iter):
        s = news.pick_ticker_weighted(rng)
        counts[s.symbol] = counts.get(s.symbol, 0) + 1
    avg = n_iter / n_total
    for sym, n in counts.items():
        assert 0.65 * avg < n < 1.35 * avg, (sym, n)


def test_pick_ticker_weighted_favors_hot():
    rng = random.Random(99)
    counts: dict[str, int] = {}
    n = 30_000
    for _ in range(n):
        s = news.pick_ticker_weighted(rng, hot_ticker="AAPL")
        counts[s.symbol] = counts.get(s.symbol, 0) + 1
    others = len(news.ALL_ASSETS) - 1
    expected_p_hot = news.HOT_WEIGHT / (news.HOT_WEIGHT + others)
    sample_p_hot = counts["AAPL"] / n
    se = (expected_p_hot * (1 - expected_p_hot) / n) ** 0.5
    assert abs(sample_p_hot - expected_p_hot) < 6 * se


def test_maybe_schedule_tip_returns_event_and_future_ts():
    rng = random.Random(0)
    prices = seed_prices()
    for _ in range(10_000):
        result = news.maybe_schedule_tip(
            prices, current_sim_ts=500, dmin=10_000, rng=rng
        )
        if result is None:
            continue
        event, scheduled_ts = result
        assert event.ticker in prices
        assert 500 + news.TIP_DELAY_MIN <= scheduled_ts <= 500 + news.TIP_DELAY_MAX
        assert news.MIN_SHOCK <= abs(event.pct_change) <= news.MAX_SHOCK


def test_tip_for_is_vague():
    e = news.NewsEvent("AAPL", "AAPL beats earnings", 0.07)
    text = news.tip_for(e, rng=random.Random(0))
    assert "AAPL" in text
    assert "0.07" not in text
    assert "+" not in text
    assert "%" not in text
    assert "beats" not in text


def test_zero_dmin_no_market_or_tip():
    prices = seed_prices()
    assert news.maybe_market_event(dmin=0, rng=random.Random(0)) is None
    assert news.maybe_schedule_tip(prices, current_sim_ts=0, dmin=0, rng=random.Random(0)) is None


def test_crypto_uses_crypto_templates():
    from stocksim.stocks import BY_SYMBOL
    btc = BY_SYMBOL["BTC"]
    rng = random.Random(1)
    forbidden = ("earnings", "buyback", "executive", "lawsuit", "Analyst", "guidance")
    for _ in range(500):
        event = news._build_news_event(rng, btc)
        for word in forbidden:
            assert word not in event.headline, event.headline


def test_stock_uses_stock_templates():
    from stocksim.stocks import BY_SYMBOL
    aapl = BY_SYMBOL["AAPL"]
    rng = random.Random(2)
    forbidden = ("Whale", "on-chain", "Smart-contract", "ETF", "exchange")
    for _ in range(500):
        event = news._build_news_event(rng, aapl)
        for word in forbidden:
            assert word not in event.headline, event.headline
