# backtest

This repository is intended to manage ETF close-price data, run multiple backtests from shared source data, store strategy definitions and result snapshots separately, and later present those results through a web interface.

## Phase 1: Price updates

Phase 1 keeps the CSV files in `data/prices/` updated automatically without changing their filenames or locations.

`update_prices.py`:

1. Reads every CSV file in `data/prices/`
2. Maps supported filenames to tickers:
   `qqq.csv` -> `QQQ`
   `qld.csv` -> `QLD`
   `tqqq.csv` -> `TQQQ`
   `soxl.csv` -> `SOXL`
   `schd.csv` -> `SCHD`
3. Validates that each file contains `Date` and `Close`
4. Fetches daily market data using close prices only
5. Appends only newer missing rows
6. Rewrites the file as `Date,Close` with ascending dates and no duplicate dates

The updater does not use adjusted close, dividends, fees, or any derived pricing logic.

## GitHub Actions

The workflow at `.github/workflows/update-prices.yml` supports:

1. A weekday daily scheduled run
2. A manual `workflow_dispatch` run from GitHub Actions

To run it manually:

1. Open the repository on GitHub.
2. Go to the `Actions` tab.
3. Select the `Update ETF Prices` workflow.
4. Click `Run workflow`.

The workflow installs dependencies, runs `update_prices.py`, and commits updated CSV files only when there are actual file changes.

## Planned repository layout

The repository is being kept simple in phase 1, but the structure is intended to grow into:

```text
data/
  prices/
    qqq.csv
    qld.csv
    tqqq.csv
    soxl.csv
    schd.csv
  strategies/
    *.json
  results/
    *.json
```

This allows price data to stay shared and stable while future phases add separate strategy definitions, separate backtest result files, and a web UI that lists, views, and compares results.
