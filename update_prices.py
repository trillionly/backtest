from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

import yfinance as yf


PRICE_FILES: Dict[str, str] = {
    "qqq.csv": "QQQ",
    "qld.csv": "QLD",
    "tqqq.csv": "TQQQ",
    "soxl.csv": "SOXL",
    "schd.csv": "SCHD",
}

PRICES_DIR = Path("data/prices")
CSV_COLUMNS = ["Date", "Close"]


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def format_close(value: float) -> str:
    return f"{value:.10f}".rstrip("0").rstrip(".")


def load_existing_rows(csv_path: Path) -> Tuple[List[Dict[str, str]], date | None]:
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{csv_path} is empty or missing a header row.")

        normalized_columns = {name.lower(): name for name in reader.fieldnames}
        if "date" not in normalized_columns or "close" not in normalized_columns:
            raise ValueError(f"{csv_path} must contain Date and Close columns.")

        date_column = normalized_columns["date"]
        close_column = normalized_columns["close"]

        rows_by_date: Dict[str, Dict[str, str]] = {}
        for raw_row in reader:
            raw_date = (raw_row.get(date_column) or "").strip()
            raw_close = (raw_row.get(close_column) or "").strip()
            if not raw_date or not raw_close:
                continue

            normalized_date = parse_iso_date(raw_date).isoformat()
            rows_by_date[normalized_date] = {
                "Date": normalized_date,
                "Close": raw_close,
            }

    rows = [rows_by_date[key] for key in sorted(rows_by_date)]
    last_existing_date = parse_iso_date(rows[-1]["Date"]) if rows else None
    return rows, last_existing_date


def fetch_new_rows(ticker: str, last_existing_date: date | None) -> List[Dict[str, str]]:
    if last_existing_date is None:
        history = yf.download(
            ticker,
            period="max",
            interval="1d",
            auto_adjust=False,
            progress=False,
            actions=False,
            multi_level_index=False,
        )
    else:
        history = yf.download(
            ticker,
            start=(last_existing_date - timedelta(days=5)).isoformat(),
            interval="1d",
            auto_adjust=False,
            progress=False,
            actions=False,
            multi_level_index=False,
        )

    if history.empty:
        return []

    if "Close" not in history.columns:
        raise ValueError(f"Downloaded data for {ticker} does not contain a Close column.")

    close_history = history[["Close"]].dropna()
    if close_history.empty:
        return []

    new_rows: List[Dict[str, str]] = []
    for index, row in close_history.iterrows():
        row_date = index.date()
        if last_existing_date is not None and row_date <= last_existing_date:
            continue

        new_rows.append(
            {
                "Date": row_date.isoformat(),
                "Close": format_close(float(row["Close"])),
            }
        )

    return new_rows


def write_rows(csv_path: Path, rows: List[Dict[str, str]]) -> None:
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def update_price_file(csv_path: Path, ticker: str) -> None:
    existing_rows, last_existing_date = load_existing_rows(csv_path)
    existing_label = last_existing_date.isoformat() if last_existing_date else "none"
    print(f"[{ticker}] last existing date: {existing_label}")

    new_rows = fetch_new_rows(ticker, last_existing_date)
    if not new_rows:
        write_rows(csv_path, existing_rows)
        print(f"[{ticker}] appended: no")
        print(f"[{ticker}] rows appended: 0")
        return

    rows_by_date = {row["Date"]: row for row in existing_rows}
    for row in new_rows:
        rows_by_date[row["Date"]] = row

    merged_rows = [rows_by_date[key] for key in sorted(rows_by_date)]
    appended_count = len(new_rows)
    write_rows(csv_path, merged_rows)

    print(f"[{ticker}] appended: yes")
    print(f"[{ticker}] rows appended: {appended_count}")


def main() -> None:
    for filename, ticker in PRICE_FILES.items():
        csv_path = PRICES_DIR / filename
        if not csv_path.exists():
            raise FileNotFoundError(f"Missing expected file: {csv_path}")
        update_price_file(csv_path, ticker)


if __name__ == "__main__":
    main()
