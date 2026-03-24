# backtest

This repository stores ETF close-price CSV data used for backtesting and keeps those price files current with a simple automated updater.

## Price updater

`update_prices.py` reads the CSV files in `data/prices/`, validates that each file has `Date` and `Close` columns, fetches recent daily market data for `QQQ`, `QLD`, `TQQQ`, `SOXL`, and `SCHD`, and appends only newer missing close-price rows. The script keeps the files in ascending date order, writes only `Date,Close`, normalizes dates to `YYYY-MM-DD`, and avoids duplicate dates.

## GitHub Actions

The workflow at `.github/workflows/update-prices.yml` supports both scheduled daily runs and manual runs through GitHub Actions.

To run it manually:

1. Open the repository on GitHub.
2. Go to the `Actions` tab.
3. Select the `Update ETF Prices` workflow.
4. Click `Run workflow`.
