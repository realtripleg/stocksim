from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Stock:
    symbol: str
    name: str
    sector: str
    seed_price: float
    mu: float
    sigma: float
    kind: Literal["stock", "crypto"] = "stock"


STOCKS: tuple[Stock, ...] = (
    Stock("AAPL",  "Apple",                 "tech",       185.00, 0.10, 0.28),
    Stock("MSFT",  "Microsoft",             "tech",       410.00, 0.10, 0.25),
    Stock("GOOGL", "Alphabet",              "tech",       175.00, 0.09, 0.27),
    Stock("AMZN",  "Amazon",                "tech",       180.00, 0.11, 0.32),
    Stock("META",  "Meta Platforms",        "tech",       480.00, 0.12, 0.38),
    Stock("NVDA",  "NVIDIA",                "tech",       850.00, 0.20, 0.55),
    Stock("TSLA",  "Tesla",                 "tech",       220.00, 0.12, 0.60),
    Stock("AMD",   "AMD",                   "tech",       180.00, 0.15, 0.50),

    Stock("JPM",   "JPMorgan Chase",        "finance",    195.00, 0.08, 0.24),
    Stock("BAC",   "Bank of America",        "finance",     38.00, 0.07, 0.28),
    Stock("GS",    "Goldman Sachs",         "finance",    420.00, 0.09, 0.30),
    Stock("V",     "Visa",                  "finance",    275.00, 0.10, 0.22),
    Stock("MA",    "Mastercard",            "finance",    460.00, 0.10, 0.23),

    Stock("WMT",   "Walmart",               "consumer",    60.00, 0.06, 0.16),
    Stock("COST",  "Costco",                "consumer",   720.00, 0.09, 0.20),
    Stock("NKE",   "Nike",                  "consumer",    95.00, 0.07, 0.28),
    Stock("MCD",   "McDonald's",            "consumer",   285.00, 0.07, 0.18),
    Stock("SBUX",  "Starbucks",             "consumer",    92.00, 0.07, 0.26),
    Stock("DIS",   "Disney",                "consumer",   105.00, 0.06, 0.30),

    Stock("JNJ",   "Johnson & Johnson",     "healthcare", 155.00, 0.05, 0.15),
    Stock("PFE",   "Pfizer",                "healthcare",  28.00, 0.04, 0.22),
    Stock("UNH",   "UnitedHealth",          "healthcare", 510.00, 0.08, 0.20),
    Stock("LLY",   "Eli Lilly",             "healthcare", 760.00, 0.14, 0.30),

    Stock("XOM",   "ExxonMobil",            "energy",     115.00, 0.06, 0.28),
    Stock("CVX",   "Chevron",               "energy",     155.00, 0.06, 0.26),
    Stock("COP",   "ConocoPhillips",        "energy",     115.00, 0.07, 0.32),

    Stock("BA",    "Boeing",                "industrial", 195.00, 0.05, 0.35),
    Stock("CAT",   "Caterpillar",           "industrial", 340.00, 0.08, 0.26),
    Stock("GE",    "General Electric",      "industrial", 165.00, 0.09, 0.28),
    Stock("HON",   "Honeywell",             "industrial", 200.00, 0.07, 0.22),
)


CRYPTOS: tuple[Stock, ...] = (
    Stock("BTC",   "Bitcoin",     "crypto", 65_000.00, 0.30, 0.65, kind="crypto"),
    Stock("ETH",   "Ethereum",    "crypto",  3_200.00, 0.30, 0.70, kind="crypto"),
    Stock("SOL",   "Solana",      "crypto",    140.00, 0.25, 0.85, kind="crypto"),
    Stock("DOGE",  "Dogecoin",    "crypto",      0.12, 0.10, 1.00, kind="crypto"),
    Stock("ADA",   "Cardano",     "crypto",      0.45, 0.05, 0.80, kind="crypto"),
    Stock("XRP",   "Ripple",      "crypto",      0.55, 0.05, 0.75, kind="crypto"),
    Stock("AVAX",  "Avalanche",   "crypto",     35.00, 0.15, 0.85, kind="crypto"),
    Stock("MATIC", "Polygon",     "crypto",      0.70, 0.05, 0.85, kind="crypto"),
    Stock("LINK",  "Chainlink",   "crypto",     15.00, 0.15, 0.80, kind="crypto"),
    Stock("LTC",   "Litecoin",    "crypto",     75.00, 0.05, 0.65, kind="crypto"),
)


ALL_ASSETS: tuple[Stock, ...] = STOCKS + CRYPTOS


SECTORS: tuple[str, ...] = (
    "tech", "finance", "consumer", "healthcare", "energy", "industrial", "crypto",
)


SECTOR_RHO: dict[str, float] = {
    "tech":       0.60,
    "finance":    0.55,
    "consumer":   0.40,
    "healthcare": 0.35,
    "energy":     0.65,
    "industrial": 0.45,
    "crypto":     0.75,
}


BY_SYMBOL: dict[str, Stock] = {s.symbol: s for s in ALL_ASSETS}


def get(symbol: str) -> Stock:
    return BY_SYMBOL[symbol]


def seed_prices() -> dict[str, float]:
    return {s.symbol: s.seed_price for s in ALL_ASSETS}


def format_price(price: float) -> str:
    if price < 1.0:
        return f"${price:.4f}"
    return f"${price:,.2f}"
