from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List


ROOT_DIR = Path(__file__).resolve().parents[1]
PRICES_DIR = ROOT_DIR / "data" / "prices"
STRATEGIES_DIR = ROOT_DIR / "data" / "strategies"
RESULTS_DIR = ROOT_DIR / "data" / "results"
CSV_COLUMNS = {"date", "close"}
DATE_COLUMN_ALIASES = {"date", "날짜"}
CLOSE_COLUMN_ALIASES = {"close", "종가"}
SUPPORTED_REBALANCE_TYPES = {"none", "monthly", "band"}
CASH_ASSET = "CASH"


@dataclass
class Strategy:
    id: str
    name: str
    description: str
    tags: List[str]
    benchmark_asset: str
    assets: List[str]
    weights: List[float]
    start_date: date
    end_date: date
    initial_cash: float
    monthly_contribution: float
    rebalance_type: str
    rebalance_threshold: float | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ETF backtests from one or more strategy JSON files.")
    parser.add_argument(
        "strategies",
        nargs="*",
        help="Strategy JSON filenames in data/strategies/ or explicit paths to strategy files.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all strategy JSON files in data/strategies/.",
    )
    return parser.parse_args()


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def round_metric(value: float) -> float:
    return round(value, 6)


def normalize_asset_name(asset: str) -> str:
    return asset.strip().upper()


def normalize_column_name(value: str) -> str:
    return value.replace("\ufeff", "").strip().lower()


def load_strategy(strategy_arg: str) -> Strategy:
    strategy_path = Path(strategy_arg)
    if not strategy_path.is_absolute():
        strategy_path = STRATEGIES_DIR / strategy_arg
    if not strategy_path.exists():
        raise FileNotFoundError(f"Strategy file not found: {strategy_path}")

    with strategy_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    required_fields = [
        "id",
        "name",
        "description",
        "assets",
        "weights",
        "start_date",
        "end_date",
        "initial_cash",
        "monthly_contribution",
        "rebalance",
    ]
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        raise ValueError(f"Strategy file is missing required fields: {', '.join(missing_fields)}")

    assets = [normalize_asset_name(asset) for asset in data["assets"]]
    weights = [float(weight) for weight in data["weights"]]
    if len(assets) == 0:
        raise ValueError("Strategy must include at least one asset.")
    if len(assets) != len(weights):
        raise ValueError("assets and weights must have the same length.")
    if len(set(assets)) != len(assets):
        raise ValueError("assets must not contain duplicates.")

    total_weight = sum(weights)
    if not math.isclose(total_weight, 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError(f"weights must sum to 1.0, got {total_weight}")

    rebalance = data["rebalance"]
    if not isinstance(rebalance, dict) or "type" not in rebalance:
        raise ValueError("rebalance.type is required.")
    rebalance_type = str(rebalance["type"]).strip().lower()
    if rebalance_type not in SUPPORTED_REBALANCE_TYPES:
        raise ValueError(
            f"Unsupported rebalance.type '{rebalance_type}'. Supported types: {', '.join(sorted(SUPPORTED_REBALANCE_TYPES))}"
        )

    rebalance_threshold = None
    if rebalance_type == "band":
        if "threshold" not in rebalance:
            raise ValueError("rebalance.threshold is required for band rebalancing.")
        rebalance_threshold = float(rebalance["threshold"])
        if rebalance_threshold <= 0:
            raise ValueError("rebalance.threshold must be greater than 0.")

    start_date = parse_iso_date(data["start_date"])
    end_date = parse_iso_date(data["end_date"])
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date.")

    return Strategy(
        id=str(data["id"]).strip(),
        name=str(data["name"]).strip(),
        description=str(data["description"]).strip(),
        tags=[str(tag).strip() for tag in data.get("tags", []) if str(tag).strip()],
        benchmark_asset=normalize_asset_name(data.get("benchmark_asset", assets[0])),
        assets=assets,
        weights=weights,
        start_date=start_date,
        end_date=end_date,
        initial_cash=float(data["initial_cash"]),
        monthly_contribution=float(data["monthly_contribution"]),
        rebalance_type=rebalance_type,
        rebalance_threshold=rebalance_threshold,
    )


def resolve_strategy_paths(args: argparse.Namespace) -> List[Path]:
    strategy_paths: List[Path] = []

    if args.all:
        strategy_paths.extend(sorted(STRATEGIES_DIR.glob("*.json")))

    for strategy_arg in args.strategies:
        strategy_path = Path(strategy_arg)
        if not strategy_path.is_absolute():
            strategy_path = STRATEGIES_DIR / strategy_arg
        strategy_paths.append(strategy_path)

    if not strategy_paths:
        raise ValueError("Provide at least one strategy file or use --all.")

    unique_paths: List[Path] = []
    seen = set()
    for path in strategy_paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_paths.append(path)

    return unique_paths


def load_price_series(asset: str, start_date: date, end_date: date) -> Dict[date, float]:
    if asset == CASH_ASSET:
        return {}

    csv_path = PRICES_DIR / f"{asset.lower()}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Price CSV not found for asset {asset}: {csv_path}")

    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{csv_path} is empty or missing a header row.")

        normalized_columns = {normalize_column_name(name): name for name in reader.fieldnames}
        date_column = next((normalized_columns[key] for key in DATE_COLUMN_ALIASES if key in normalized_columns), None)
        close_column = next((normalized_columns[key] for key in CLOSE_COLUMN_ALIASES if key in normalized_columns), None)
        if date_column is None or close_column is None:
            raise ValueError(f"{csv_path} must contain Date and Close columns.")

        series: Dict[date, float] = {}
        for row in reader:
            row_date = parse_iso_date((row.get(date_column) or "").strip())
            if row_date < start_date or row_date > end_date:
                continue

            close_value = float((row.get(close_column) or "").strip())
            series[row_date] = close_value

    if not series:
        raise ValueError(f"No price data found for {asset} between {start_date} and {end_date}.")

    return series


def get_common_dates(price_data: Dict[str, Dict[date, float]]) -> List[date]:
    common_dates = set.intersection(*(set(series.keys()) for series in price_data.values()))
    return sorted(common_dates)


def record_trade(
    trade_log: List[Dict[str, object]],
    trade_date: date,
    asset: str,
    action: str,
    shares: float,
    price: float,
    reason: str,
) -> None:
    if shares <= 0:
        return

    amount = shares * price
    trade_log.append(
        {
            "date": trade_date.isoformat(),
            "asset": asset,
            "action": action,
            "shares": round_metric(shares),
            "price": round_metric(price),
            "amount": round_metric(amount),
            "reason": reason,
        }
    )


def invest_by_weights(
    holdings: Dict[str, float],
    prices: Dict[str, float],
    weights: Dict[str, float],
    cash: float,
    trade_date: date,
    reason: str,
    trade_log: List[Dict[str, object]],
) -> float:
    if cash <= 0:
        return cash

    starting_cash = cash
    for asset, weight in weights.items():
        allocation = starting_cash * weight

        if allocation <= 0:
            continue

        if asset == CASH_ASSET:
            cash -= allocation
            continue

        price = prices[asset]
        shares = allocation / price
        holdings[asset] += shares
        record_trade(trade_log, trade_date, asset, "buy", shares, price, reason)
        cash -= allocation

    return max(cash, 0.0)


def compute_portfolio_weights(
    holdings: Dict[str, float],
    prices: Dict[str, float],
    cash: float,
    assets: List[str],
) -> Dict[str, float]:
    total_value = cash + sum(holdings[asset] * prices[asset] for asset in holdings)
    if total_value <= 0:
        return {asset: 0.0 for asset in assets}

    weights = {}
    for asset in assets:
        if asset == CASH_ASSET:
            weights[asset] = cash / total_value
        else:
            weights[asset] = (holdings[asset] * prices[asset]) / total_value
    return weights


def should_band_rebalance(
    holdings: Dict[str, float],
    prices: Dict[str, float],
    weights: Dict[str, float],
    cash: float,
    assets: List[str],
    threshold: float,
) -> bool:
    current_weights = compute_portfolio_weights(holdings, prices, cash, assets)
    return any(abs(current_weights[asset] - weights[asset]) > threshold for asset in assets)


def rebalance_portfolio(
    holdings: Dict[str, float],
    prices: Dict[str, float],
    weights: Dict[str, float],
    cash: float,
    trade_date: date,
    trade_log: List[Dict[str, object]],
) -> float:
    total_value = cash + sum(holdings[asset] * prices[asset] for asset in holdings)
    target_values = {}
    current_values = {}
    for asset, weight in weights.items():
        target_values[asset] = total_value * weight
        current_values[asset] = cash if asset == CASH_ASSET else holdings[asset] * prices[asset]

    for asset in holdings:
        difference = current_values[asset] - target_values[asset]
        if difference <= 0:
            continue

        shares_to_sell = difference / prices[asset]
        holdings[asset] -= shares_to_sell
        cash += shares_to_sell * prices[asset]
        record_trade(trade_log, trade_date, asset, "sell", shares_to_sell, prices[asset], "rebalance")

    for asset in holdings:
        difference = target_values[asset] - holdings[asset] * prices[asset]
        if difference <= 0:
            continue

        buy_amount = min(difference, cash)
        if buy_amount <= 0:
            continue

        shares_to_buy = buy_amount / prices[asset]
        holdings[asset] += shares_to_buy
        cash -= buy_amount
        record_trade(trade_log, trade_date, asset, "buy", shares_to_buy, prices[asset], "rebalance")

    return cash


def compute_equity_value(holdings: Dict[str, float], prices: Dict[str, float], cash: float) -> float:
    return cash + sum(holdings[asset] * prices[asset] for asset in holdings)


def compute_annualized_volatility(daily_returns: List[Dict[str, object]]) -> float:
    returns = [float(entry["return"]) for entry in daily_returns[1:]]
    if len(returns) < 2:
        return 0.0

    mean_return = sum(returns) / len(returns)
    variance = sum((value - mean_return) ** 2 for value in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(252)


def compute_drawdown_details(equity_curve: List[Dict[str, object]]) -> Dict[str, object]:
    peak_value = float(equity_curve[0]["value"])
    peak_date = equity_curve[0]["date"]
    max_drawdown = 0.0
    drawdown_start_date = peak_date
    drawdown_trough_date = peak_date
    recovery_date = None
    active_peak_date = peak_date
    active_drawdown_start = peak_date
    current_drawdown_start = None
    max_drawdown_peak_value = peak_value
    max_drawdown_recovered = False

    for entry in equity_curve:
        value = float(entry["value"])
        entry_date = str(entry["date"])

        if value >= peak_value:
            peak_value = value
            active_peak_date = entry_date
            if not max_drawdown_recovered and current_drawdown_start == drawdown_start_date and value >= max_drawdown_peak_value:
                recovery_date = entry_date
                max_drawdown_recovered = True
            current_drawdown_start = None
            continue

        if current_drawdown_start is None:
            current_drawdown_start = active_peak_date

        drawdown = (value / peak_value) - 1.0
        if drawdown < max_drawdown:
            max_drawdown = drawdown
            drawdown_start_date = current_drawdown_start
            drawdown_trough_date = entry_date
            max_drawdown_peak_value = peak_value
            recovery_date = None
            max_drawdown_recovered = False

    recovery_days = None
    if recovery_date is not None:
        recovery_days = (parse_iso_date(recovery_date) - parse_iso_date(drawdown_start_date)).days

    return {
        "max_drawdown": round_metric(max_drawdown),
        "start_date": drawdown_start_date,
        "trough_date": drawdown_trough_date,
        "recovery_date": recovery_date,
        "recovery_days": recovery_days,
    }


def build_period_analysis(equity_curve: List[Dict[str, object]]) -> Dict[str, Dict[str, object]]:
    analysis: Dict[str, Dict[str, object]] = {}
    curve_dates = [parse_iso_date(str(entry["date"])) for entry in equity_curve]
    curve_values = [float(entry["value"]) for entry in equity_curve]

    periods = [
        ("전체 기간", None),
        ("최근 1년", 365),
        ("최근 3년", 365 * 3),
        ("최근 5년", 365 * 5),
    ]

    end_date = curve_dates[-1]
    end_value = curve_values[-1]

    for label, days in periods:
        if days is None:
            start_index = 0
        else:
            threshold = end_date - timedelta(days=days)
            start_index = bisect.bisect_left(curve_dates, threshold)
            if start_index >= len(curve_dates):
                continue
            if curve_dates[start_index] > threshold and start_index > 0:
                start_index -= 1
            if (end_date - curve_dates[start_index]).days < int(days * 0.8):
                continue

        start_date_value = curve_dates[start_index]
        start_value = curve_values[start_index]
        total_return = 0.0 if start_value <= 0 else (end_value / start_value) - 1.0
        years = max((end_date - start_date_value).days / 365.25, 1 / 365.25)
        cagr = (end_value / start_value) ** (1 / years) - 1.0 if start_value > 0 else 0.0
        analysis[label] = {
            "start_date": start_date_value.isoformat(),
            "end_date": end_date.isoformat(),
            "total_return": round_metric(total_return),
            "cagr": round_metric(cagr),
        }

    return analysis


def build_rolling_return_analysis(equity_curve: List[Dict[str, object]]) -> Dict[str, object]:
    curve_dates = [parse_iso_date(str(entry["date"])) for entry in equity_curve]
    curve_values = [float(entry["value"]) for entry in equity_curve]
    rolling_entries: List[Dict[str, object]] = []

    for index, current_date in enumerate(curve_dates):
        threshold = current_date - timedelta(days=365)
        base_index = bisect.bisect_right(curve_dates, threshold) - 1
        if base_index < 0:
            continue
        if (current_date - curve_dates[base_index]).days < 300:
            continue

        base_value = curve_values[base_index]
        current_value = curve_values[index]
        rolling_return = 0.0 if base_value <= 0 else (current_value / base_value) - 1.0
        rolling_entries.append(
            {
                "date": current_date.isoformat(),
                "return": round_metric(rolling_return),
            }
        )

    if not rolling_entries:
        return {
            "window": "1y",
            "series": [],
            "summary": None,
        }

    returns = [float(entry["return"]) for entry in rolling_entries]
    return {
        "window": "1y",
        "series": rolling_entries,
        "summary": {
            "best": round_metric(max(returns)),
            "worst": round_metric(min(returns)),
            "average": round_metric(sum(returns) / len(returns)),
        },
    }


def build_benchmark_result(
    benchmark_asset: str,
    start_date: date,
    end_date: date,
    initial_cash: float,
    monthly_contribution: float,
) -> Dict[str, object] | None:
    benchmark_prices = load_price_series(benchmark_asset, start_date, end_date)
    benchmark_dates = sorted(benchmark_prices)
    if not benchmark_dates:
        return None

    shares = 0.0
    cash = initial_cash
    equity_curve: List[Dict[str, object]] = []
    last_contribution_month = None

    for index, trading_date in enumerate(benchmark_dates):
        price = benchmark_prices[trading_date]
        if index == 0 and cash > 0:
            shares += cash / price
            cash = 0.0

        month_key = (trading_date.year, trading_date.month)
        if index > 0 and monthly_contribution > 0 and month_key != last_contribution_month:
            cash += monthly_contribution
            shares += cash / price
            cash = 0.0

        value = shares * price + cash
        equity_curve.append({"date": trading_date.isoformat(), "value": round_metric(value)})
        last_contribution_month = month_key

    start_value = float(equity_curve[0]["value"])
    end_value = float(equity_curve[-1]["value"])
    total_return = 0.0 if start_value <= 0 else (end_value / start_value) - 1.0
    years = max((benchmark_dates[-1] - benchmark_dates[0]).days / 365.25, 1 / 365.25)
    cagr = (end_value / start_value) ** (1 / years) - 1.0 if start_value > 0 else 0.0

    return {
        "asset": benchmark_asset,
        "summary": {
            "final_value": round_metric(end_value),
            "total_return": round_metric(total_return),
            "cagr": round_metric(cagr),
        },
        "equity_curve": equity_curve,
    }


def run_backtest(strategy: Strategy) -> Dict[str, object]:
    weights = dict(zip(strategy.assets, strategy.weights))
    investable_assets = [asset for asset in strategy.assets if asset != CASH_ASSET]
    if not investable_assets:
        raise ValueError("Strategy must include at least one non-cash asset.")

    price_data = {
        asset: load_price_series(asset, strategy.start_date, strategy.end_date)
        for asset in investable_assets
    }
    trading_dates = get_common_dates(price_data)
    if not trading_dates:
        raise ValueError("No common trading dates found across the selected assets.")

    holdings = {asset: 0.0 for asset in investable_assets}
    cash = strategy.initial_cash
    trade_log: List[Dict[str, object]] = []
    equity_curve: List[Dict[str, object]] = []
    daily_returns: List[Dict[str, object]] = []
    last_contribution_month = None

    for index, trading_date in enumerate(trading_dates):
        prices = {asset: price_data[asset][trading_date] for asset in investable_assets}
        net_flow = 0.0

        if index == 0 and cash > 0:
            net_flow += cash
            cash = invest_by_weights(holdings, prices, weights, cash, trading_date, "initial_allocation", trade_log)

        month_key = (trading_date.year, trading_date.month)
        if index > 0 and strategy.monthly_contribution > 0 and month_key != last_contribution_month:
            cash += strategy.monthly_contribution
            net_flow += strategy.monthly_contribution
            cash = invest_by_weights(
                holdings,
                prices,
                weights,
                cash,
                trading_date,
                "monthly_contribution",
                trade_log,
            )

        if strategy.rebalance_type == "monthly":
            previous_month_key = None if index == 0 else (trading_dates[index - 1].year, trading_dates[index - 1].month)
            if index == 0 or month_key != previous_month_key:
                cash = rebalance_portfolio(holdings, prices, weights, cash, trading_date, trade_log)
        elif strategy.rebalance_type == "band" and index > 0:
            if should_band_rebalance(
                holdings,
                prices,
                weights,
                cash,
                strategy.assets,
                strategy.rebalance_threshold or 0.0,
            ):
                cash = rebalance_portfolio(holdings, prices, weights, cash, trading_date, trade_log)

        portfolio_value = compute_equity_value(holdings, prices, cash)
        equity_curve.append(
            {
                "date": trading_date.isoformat(),
                "value": round_metric(portfolio_value),
            }
        )

        if index == 0:
            daily_return = 0.0
        else:
            previous_value = equity_curve[index - 1]["value"]
            daily_return = 0.0 if previous_value <= 0 else ((portfolio_value - net_flow) / previous_value) - 1.0

        daily_returns.append(
            {
                "date": trading_date.isoformat(),
                "year": trading_date.year,
                "return": daily_return,
            }
        )
        last_contribution_month = month_key

    cumulative_return = 1.0
    annual_return_factors: Dict[int, float] = {}
    drawdown_peak = 1.0
    max_drawdown = 0.0

    for entry in daily_returns:
        cumulative_return *= 1.0 + entry["return"]
        annual_return_factors.setdefault(entry["year"], 1.0)
        annual_return_factors[entry["year"]] *= 1.0 + entry["return"]
        drawdown_peak = max(drawdown_peak, cumulative_return)
        drawdown = (cumulative_return / drawdown_peak) - 1.0
        max_drawdown = min(max_drawdown, drawdown)

    total_return = cumulative_return - 1.0
    elapsed_days = max((trading_dates[-1] - trading_dates[0]).days, 1)
    elapsed_years = elapsed_days / 365.25
    cagr = 0.0 if elapsed_years <= 0 else (cumulative_return ** (1 / elapsed_years)) - 1.0

    annual_returns = [
        {
            "year": year,
            "return": round_metric(factor - 1.0),
        }
        for year, factor in sorted(annual_return_factors.items())
    ]

    annualized_volatility = compute_annualized_volatility(daily_returns)
    drawdown_details = compute_drawdown_details(equity_curve)
    period_analysis = build_period_analysis(equity_curve)
    rolling_returns = build_rolling_return_analysis(equity_curve)
    benchmark = build_benchmark_result(
        strategy.benchmark_asset,
        trading_dates[0],
        trading_dates[-1],
        strategy.initial_cash,
        strategy.monthly_contribution,
    )
    calmar_like = 0.0 if abs(max_drawdown) <= 1e-12 else cagr / abs(max_drawdown)

    return {
        "strategy_id": strategy.id,
        "strategy_name": strategy.name,
        "description": strategy.description,
        "tags": strategy.tags,
        "assets": strategy.assets,
        "weights": strategy.weights,
        "period": {
            "start_date": trading_dates[0].isoformat(),
            "end_date": trading_dates[-1].isoformat(),
        },
        "rebalance": {
            "type": strategy.rebalance_type,
            "threshold": strategy.rebalance_threshold,
        },
        "benchmark_asset": strategy.benchmark_asset,
        "summary": {
            "final_value": round_metric(equity_curve[-1]["value"]),
            "total_return": round_metric(total_return),
            "cagr": round_metric(cagr),
            "mdd": round_metric(max_drawdown),
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "analysis": {
            "periods": period_analysis,
            "drawdown": drawdown_details,
            "rolling_returns": rolling_returns,
            "risk": {
                "annualized_volatility": round_metric(annualized_volatility),
                "return_to_drawdown": round_metric(calmar_like),
            },
            "benchmark": {
                "asset": benchmark["asset"] if benchmark else None,
                "summary": benchmark["summary"] if benchmark else None,
                "outperformance": {
                    "final_value": round_metric(equity_curve[-1]["value"] - benchmark["summary"]["final_value"]) if benchmark else None,
                    "total_return": round_metric(total_return - benchmark["summary"]["total_return"]) if benchmark else None,
                    "cagr": round_metric(cagr - benchmark["summary"]["cagr"]) if benchmark else None,
                } if benchmark else None,
            },
        },
        "equity_curve": equity_curve,
        "annual_returns": annual_returns,
        "trade_log": trade_log,
        "benchmark_curve": benchmark["equity_curve"] if benchmark else [],
    }


def build_results_index() -> Dict[str, object]:
    results: List[Dict[str, object]] = []
    for result_path in sorted(RESULTS_DIR.glob("*.json")):
        if result_path.name == "results-index.json":
            continue

        with result_path.open("r", encoding="utf-8") as handle:
            result = json.load(handle)

        period = result.get("period") or {}
        summary = result.get("summary") or {}
        results.append(
            {
                "file": result_path.name,
                "strategy_id": result.get("strategy_id", ""),
                "strategy_name": result.get("strategy_name", result.get("strategy_id", "")),
                "description": result.get("description", ""),
                "tags": result.get("tags", []),
                "created_at": result.get("created_at", datetime.fromtimestamp(result_path.stat().st_mtime, tz=timezone.utc).isoformat()),
                "period": {
                    "start_date": period.get("start_date"),
                    "end_date": period.get("end_date"),
                },
                "summary": {
                    "final_value": summary.get("final_value"),
                    "total_return": summary.get("total_return"),
                    "cagr": summary.get("cagr"),
                    "mdd": summary.get("mdd"),
                },
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }


def write_results_index() -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    index_path = RESULTS_DIR / "results-index.json"
    with index_path.open("w", encoding="utf-8") as handle:
        json.dump(build_results_index(), handle, indent=2)
        handle.write("\n")
    return index_path


def save_result(strategy: Strategy, result: Dict[str, object]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{strategy.id}_{strategy.start_date.isoformat()}_{strategy.end_date.isoformat()}.json"
    result_path = RESULTS_DIR / filename
    with result_path.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    return result_path


def main() -> None:
    args = parse_args()
    strategy_paths = resolve_strategy_paths(args)

    for strategy_path in strategy_paths:
        strategy = load_strategy(str(strategy_path))
        result = run_backtest(strategy)
        result_path = save_result(strategy, result)

        print(f"Strategy: {strategy.id}")
        print(f"Result file: {result_path}")
        print(f"Final value: {result['summary']['final_value']}")
        print(f"Total return: {result['summary']['total_return']}")
        print(f"CAGR: {result['summary']['cagr']}")
        print(f"MDD: {result['summary']['mdd']}")
        print("")

    index_path = write_results_index()
    print(f"Results index: {index_path}")


if __name__ == "__main__":
    main()
