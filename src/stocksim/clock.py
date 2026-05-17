
from __future__ import annotations

MIN_SPEED = 0.25
MAX_SPEED = 60.0


class SimClock:
    def __init__(self, *, sim_minutes: int = 0, speed: float = 1.0) -> None:
        self.sim_minutes: int = sim_minutes
        self.paused: bool = False
        self.speed: float = speed
        self._accumulator: float = 0.0

    def advance(self, real_dt: float) -> int:
        if self.paused or real_dt <= 0:
            return 0
        self._accumulator += real_dt * self.speed
        whole = int(self._accumulator)
        if whole <= 0:
            return 0
        self._accumulator -= whole
        self.sim_minutes += whole
        return whole

    def toggle_pause(self) -> bool:
        self.paused = not self.paused
        return self.paused

    def set_speed(self, speed: float) -> float:
        self.speed = max(MIN_SPEED, min(MAX_SPEED, speed))
        return self.speed

    def speed_up(self, factor: float = 2.0) -> float:
        return self.set_speed(self.speed * factor)

    def slow_down(self, factor: float = 2.0) -> float:
        return self.set_speed(self.speed / factor)
