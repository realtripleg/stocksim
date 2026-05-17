
from __future__ import annotations

import argparse

from . import db


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="stocksim",
        description="Terminal paper-trading game with FAKE simulated prices.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Wipe saved portfolio and start fresh",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Override database file path",
    )
    args = parser.parse_args()

    path = args.db if args.db else db.default_db_path()
    if args.reset:
        db.reset(path)

    from .app import StockSimApp

    StockSimApp(db_path=path).run()
