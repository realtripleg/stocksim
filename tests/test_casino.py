from __future__ import annotations

import random
import statistics

import pytest

from stocksim import casino


def test_slots_reels_are_valid_symbols():
    rng = random.Random(0)
    for _ in range(2000):
        r = casino.play_slots(rng)
        for s in r.reels:
            assert s in casino.SLOT_SYMBOLS


def test_slots_triple_pays_per_table():
    rng = random.Random(1)
    triples = 0
    for _ in range(50_000):
        r = casino.play_slots(rng)
        if r.reels[0] == r.reels[1] == r.reels[2]:
            triples += 1
            assert r.multiplier == casino.SLOT_TRIPLE_PAYOUTS[r.reels[0]]
    assert triples > 0


def test_slots_pair_pays_pair_payout():
    rng = random.Random(2)
    pairs = 0
    for _ in range(10_000):
        r = casino.play_slots(rng)
        if r.reels[0] == r.reels[1] == r.reels[2]:
            continue
        if (
            r.reels[0] == r.reels[1]
            or r.reels[1] == r.reels[2]
            or r.reels[0] == r.reels[2]
        ):
            pairs += 1
            assert r.multiplier == casino.SLOT_PAIR_PAYOUT
    assert pairs > 0


def test_slots_no_match_pays_zero():
    rng = random.Random(3)
    losses = 0
    for _ in range(5000):
        r = casino.play_slots(rng)
        if (
            r.reels[0] != r.reels[1]
            and r.reels[1] != r.reels[2]
            and r.reels[0] != r.reels[2]
        ):
            losses += 1
            assert r.multiplier == 0.0
    assert losses > 0


def test_coin_wins_on_correct_guess():
    rng = random.Random(0)
    wins = losses = 0
    for _ in range(5000):
        r = casino.play_coin(rng, "heads")
        if r.landed == "heads":
            assert r.multiplier == casino.COIN_PAYOUT
            wins += 1
        else:
            assert r.multiplier == 0.0
            losses += 1
    assert 0.4 < wins / (wins + losses) < 0.6


def test_dice_rolls_in_range_and_total_matches():
    rng = random.Random(0)
    for _ in range(2000):
        r = casino.play_dice(rng, "over")
        assert 1 <= r.rolls[0] <= 6
        assert 1 <= r.rolls[1] <= 6
        assert r.total == r.rolls[0] + r.rolls[1]


def test_dice_over_pays_only_above_seven():
    rng = random.Random(11)
    overs = 0
    for _ in range(5000):
        r = casino.play_dice(rng, "over")
        if r.total > 7:
            assert r.multiplier == casino.DICE_OVER_UNDER_PAYOUT
            overs += 1
        else:
            assert r.multiplier == 0.0
    assert overs > 0


def test_dice_seven_pays_only_on_seven():
    rng = random.Random(22)
    sevens = 0
    for _ in range(5000):
        r = casino.play_dice(rng, "seven")
        if r.total == 7:
            assert r.multiplier == casino.DICE_SEVEN_PAYOUT
            sevens += 1
        else:
            assert r.multiplier == 0.0
    assert sevens > 0


def test_roulette_number_in_range():
    rng = random.Random(0)
    for _ in range(2000):
        r = casino.play_roulette(rng, "red")
        assert 0 <= r.number <= 36


def test_roulette_color_consistent():
    for n in range(37):
        c = casino.roulette_color(n)
        if n == 0:
            assert c == "green"
        elif n in casino.ROULETTE_REDS:
            assert c == "red"
        else:
            assert c == "black"


def test_roulette_red_wins_when_red():
    rng = random.Random(7)
    reds = 0
    for _ in range(5000):
        r = casino.play_roulette(rng, "red")
        if r.color == "red":
            assert r.multiplier == casino.ROULETTE_EVEN_PAYOUT
            reds += 1
        else:
            assert r.multiplier == 0.0
    assert reds > 0


def test_roulette_even_does_not_pay_on_zero():
    rng = random.Random(0)
    saw_zero = False
    for _ in range(20_000):
        r = casino.play_roulette(rng, "even")
        if r.number == 0:
            saw_zero = True
            assert r.multiplier == 0.0
    assert saw_zero


def test_roulette_dozen1_pays_on_1_to_12():
    rng = random.Random(33)
    wins = losses = 0
    for _ in range(10_000):
        r = casino.play_roulette(rng, "dozen1")
        if 1 <= r.number <= 12:
            assert r.multiplier == casino.ROULETTE_DOZEN_PAYOUT
            wins += 1
        else:
            assert r.multiplier == 0.0
            losses += 1
    assert wins > 0 and losses > 0


def test_roulette_dozen2_pays_on_13_to_24():
    rng = random.Random(44)
    for _ in range(5_000):
        r = casino.play_roulette(rng, "dozen2")
        if 13 <= r.number <= 24:
            assert r.multiplier == casino.ROULETTE_DOZEN_PAYOUT
        else:
            assert r.multiplier == 0.0


def test_roulette_dozen3_pays_on_25_to_36():
    rng = random.Random(55)
    for _ in range(5_000):
        r = casino.play_roulette(rng, "dozen3")
        if 25 <= r.number <= 36:
            assert r.multiplier == casino.ROULETTE_DOZEN_PAYOUT
        else:
            assert r.multiplier == 0.0


def test_crash_point_at_least_minimum():
    rng = random.Random(0)
    for _ in range(10_000):
        c = casino.sample_crash_point(rng)
        assert c >= casino.CRASH_MIN_MULTIPLIER


def test_crash_min_multiplier_is_above_one():
    assert casino.CRASH_MIN_MULTIPLIER > 1.0


def test_crash_long_tail_has_house_edge():
    rng = random.Random(42)
    n = 30_000
    cash_out = 10.0
    payouts = [
        cash_out if casino.sample_crash_point(rng) >= cash_out else 0.0
        for _ in range(n)
    ]
    ev = statistics.fmean(payouts)
    assert ev < 1.0, f"expected house edge at high cash-out but EV={ev}"


def test_crash_distribution_has_high_outliers():
    rng = random.Random(99)
    samples = [casino.sample_crash_point(rng) for _ in range(20_000)]
    assert max(samples) > 5.0
    assert sum(1 for s in samples if s > 2.0) > 0
