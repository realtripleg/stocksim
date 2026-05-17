
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Mapping

from . import db


class TradeError(ValueError):
    pass


@dataclass(frozen=True)
class TradeResult:
    ticker: str
    side: str
    shares: int
    price: float
    total: float
    new_cash: float


class Portfolio:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def cash(self) -> float:
        return db.get_portfolio(self.conn).cash

    def positions(self) -> dict[str, db.PositionRow]:
        return db.get_positions(self.conn)

    def value(self, prices: Mapping[str, float]) -> float:
        total = self.cash()
        for pos in self.positions().values():
            if pos.ticker in prices:
                total += pos.shares * prices[pos.ticker]
        return total

    def pnl(self, prices: Mapping[str, float]) -> float:
        return self.value(prices) - db.STARTING_CASH

    def buy(self, *, ticker: str, shares: int, price: float, sim_ts: int) -> TradeResult:
        if shares <= 0:
            raise TradeError("shares must be positive")
        if price <= 0:
            raise TradeError("price must be positive")

        total = shares * price
        pf = db.get_portfolio(self.conn)
        if pf.cash < total:
            raise TradeError(
                f"insufficient cash: need ${total:,.2f}, have ${pf.cash:,.2f}"
            )

        positions = db.get_positions(self.conn)
        existing = positions.get(ticker)
        if existing is None:
            new_shares = shares
            new_avg = price
        else:
            new_shares = existing.shares + shares
            new_avg = (existing.shares * existing.avg_cost + shares * price) / new_shares

        new_cash = pf.cash - total
        with db.transaction(self.conn):
            db.update_portfolio(self.conn, cash=new_cash, sim_minutes=pf.sim_minutes)
            db.upsert_position(self.conn, ticker=ticker, shares=new_shares, avg_cost=new_avg)
            db.record_trade(
                self.conn,
                sim_ts=sim_ts,
                ticker=ticker,
                side="buy",
                shares=shares,
                price=price,
            )

        return TradeResult(ticker, "buy", shares, price, total, new_cash)

    def sell(self, *, ticker: str, shares: int, price: float, sim_ts: int) -> TradeResult:
        if shares <= 0:
            raise TradeError("shares must be positive")
        if price <= 0:
            raise TradeError("price must be positive")

        positions = db.get_positions(self.conn)
        existing = positions.get(ticker)
        if existing is None or existing.shares < shares:
            held = 0 if existing is None else existing.shares
            raise TradeError(f"cannot sell {shares} {ticker}; hold {held}")

        total = shares * price
        pf = db.get_portfolio(self.conn)
        new_cash = pf.cash + total
        remaining = existing.shares - shares

        with db.transaction(self.conn):
            db.update_portfolio(self.conn, cash=new_cash, sim_minutes=pf.sim_minutes)
            if remaining == 0:
                db.delete_position(self.conn, ticker)
            else:
                db.upsert_position(
                    self.conn,
                    ticker=ticker,
                    shares=remaining,
                    avg_cost=existing.avg_cost,
                )
            db.record_trade(
                self.conn,
                sim_ts=sim_ts,
                ticker=ticker,
                side="sell",
                shares=shares,
                price=price,
            )

        return TradeResult(ticker, "sell", shares, price, total, new_cash)
