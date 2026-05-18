# StockSim

Console paper-trading game with simulated prices.

## Install

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv tool install git+https://github.com/realtripleg/stocksim            # stable
uv tool install git+https://github.com/realtripleg/stocksim@nightly    # nightly / test features
```

Then run from anywhere:

```sh
stocksim          # play
stocksim --reset  # wipe save and start fresh
```

## Build from source

```sh
git clone https://github.com/realtripleg/stocksim            # default branch (stable)
git clone -b nightly https://github.com/realtripleg/stocksim # nightly branch
cd stocksim
uv sync
uv run stocksim
```
