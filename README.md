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

## Phase 2: Backtest engine foundation

Phase 2 adds a simple file-based backtest workflow:

1. Strategy definitions live in `data/strategies/*.json`
2. Price inputs are read from the existing `data/prices/*.csv`
3. Backtest results are saved to `data/results/*.json`

Each strategy JSON currently supports these fields:

- `id`
- `name`
- `description`
- `assets`
- `weights`
- `start_date`
- `end_date`
- `initial_cash`
- `monthly_contribution`
- `rebalance.type`

Supported `rebalance.type` values in phase 2:

- `none`
- `monthly`

The runner reads close prices only, does not use adjusted close, and does not add dividends or fees.

## Running a backtest

Run the sample strategy with:

```powershell
python scripts/run_backtest.py sample_qqq_tqqq_monthly.json
```

You can also pass an explicit path to a strategy file under `data/strategies/`.

Result files are written to `data/results/` using this pattern:

```text
{strategy_id}_{start_date}_{end_date}.json
```
