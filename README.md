# StockSim

Console paper-trading game with simulated prices.

## Install

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv tool install git+https://github.com/realtripleg/stocksim
```

Then run from anywhere:

```sh
stocksim          # play
stocksim --reset  # wipe save and start fresh
```

## Build from source

```sh
git clone https://github.com/realtripleg/stocksim
cd stocksim
uv sync
uv run stocksim
```
