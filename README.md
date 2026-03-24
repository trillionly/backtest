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

Running a backtest also refreshes `data/results/results-index.json`, which the static web UI uses to list and compare saved results.

## Phase 3: Static web reporting

Phase 3 adds a static reporting UI in `web/` for browsing saved backtest result JSON files.

The web layer includes:

1. `web/index.html` for scanning saved result files
2. `web/strategy.html` for a single result detail page
3. `web/compare.html` for comparing multiple saved results
4. `web/app.js` for loading `data/results/results-index.json` and result JSON files
5. `web/styles.css` for the shared layout and visual styling

## Viewing the web UI locally

Because the pages fetch JSON files, open the repository through a local static server instead of opening the HTML files directly with `file://`.

One simple option is:

```powershell
python -m http.server 8000
```

Then open:

```text
http://localhost:8000/web/index.html
```

## Publishing with GitHub Pages

The web UI is static and GitHub Pages-friendly. Publish the repository contents in a way that keeps both `web/` and `data/results/` available in the deployed site.

For a Pages deployment:

1. Publish the repository root or a built artifact that includes both `web/` and `data/results/`
2. Use `web/index.html` as the entry page
3. Make sure `data/results/results-index.json` is deployed together with the saved result JSON files

Without `results-index.json`, the results list and compare page cannot discover saved result files in a static hosting environment.
