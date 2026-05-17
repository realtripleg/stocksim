from __future__ import annotations

import pytest

from stocksim.clock import MAX_SPEED, MIN_SPEED, SimClock


def test_starts_at_zero():
    c = SimClock()
    assert c.sim_minutes == 0
    assert not c.paused
    assert c.speed == 1.0


def test_advance_at_default_speed():
    c = SimClock()
    assert c.advance(1.0) == 1
    assert c.sim_minutes == 1


def test_advance_accumulates_fractional():
    c = SimClock()
    assert c.advance(0.4) == 0
    assert c.advance(0.4) == 0
    assert c.advance(0.4) == 1
    assert c.sim_minutes == 1


def test_advance_returns_multiple_when_fast():
    c = SimClock(speed=10.0)
    assert c.advance(1.0) == 10
    assert c.sim_minutes == 10


def test_pause_blocks_advance():
    c = SimClock()
    c.toggle_pause()
    assert c.paused
    assert c.advance(5.0) == 0
    assert c.sim_minutes == 0


def test_resume_after_pause():
    c = SimClock()
    c.toggle_pause()
    c.advance(5.0)
    c.toggle_pause()
    assert c.advance(2.0) == 2


def test_speed_up_and_slow_down():
    c = SimClock()
    c.speed_up()
    assert c.speed == 2.0
    c.speed_up()
    assert c.speed == 4.0
    c.slow_down()
    assert c.speed == 2.0


def test_speed_clamps():
    c = SimClock()
    c.set_speed(1000)
    assert c.speed == MAX_SPEED
    c.set_speed(0.001)
    assert c.speed == MIN_SPEED


def test_zero_real_dt_is_noop():
    c = SimClock()
    assert c.advance(0) == 0
    assert c.advance(-1) == 0
