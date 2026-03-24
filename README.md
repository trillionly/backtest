# backtest

이 저장소는 ETF 종가 CSV를 자동으로 갱신하고, 전략 파일과 백테스트 결과 파일을 분리해서 관리하며, 저장된 결과를 정적 웹 UI로 확인하기 위한 용도입니다.

## 내가 이 저장소를 쓰는 흐름

1. `update_prices.py` 또는 GitHub Actions로 `data/prices/` 종가 CSV를 최신 상태로 유지합니다.
2. 새 전략 아이디어가 생기면 `data/strategies/` 아래에 전략 JSON 파일을 추가하거나 수정합니다.
3. `scripts/run_backtest.py`로 하나 또는 여러 전략을 실행합니다.
4. 결과 JSON은 `data/results/`에 저장되고 `results-index.json`도 함께 갱신됩니다.
5. `web/` 페이지 또는 GitHub Pages에서 저장된 결과를 확인합니다.

## 전략 파일 규칙

- 위치: `data/strategies/*.json`
- 권장 파일명: `{strategy_id}.json`
- `strategy_id`는 결과 파일명에도 그대로 쓰이므로 짧고 일관되게 유지하는 편이 좋습니다.
- 현재 전략 파일은 `id`, `name`, `description`, `assets`, `weights`, `start_date`, `end_date`, `initial_cash`, `monthly_contribution`, `rebalance.type`를 사용합니다.

## 백테스트 실행

단일 전략 실행:

```powershell
python scripts/run_backtest.py sample_qqq_tqqq_monthly.json
```

여러 전략 실행:

```powershell
python scripts/run_backtest.py sample_qqq_tqqq_monthly.json another_strategy.json
```

모든 전략 실행:

```powershell
python scripts/run_backtest.py --all
```

결과 파일명 규칙:

```text
{strategy_id}_{start_date}_{end_date}.json
```

실행이 끝나면 `data/results/results-index.json`도 자동 갱신되어 웹 UI가 결과 목록을 바로 읽을 수 있습니다.

## 한국어 웹 UI 구조

- `web/index.html`: 저장된 결과 목록
- `web/strategy.html`: 단일 전략 상세 화면
- `web/compare.html`: 여러 결과 비교 화면
- `web/app.js`: 결과 JSON과 `results-index.json` 로딩
- `web/styles.css`: 공통 스타일

사용자에게 보이는 메뉴, 버튼, 표 헤더, 요약 카드, 빈 상태 메시지는 모두 한국어로 표시되며, 내부 코드와 JSON 키는 유지했습니다.

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

## Phase 4: GitHub Pages deployment

The repository now includes a root landing page at `index.html` so GitHub Pages has a clean default entry page. That landing page links to:

1. `web/index.html`
2. `web/strategy.html`
3. `web/compare.html`

The web pages use relative paths so they continue to work when the site is hosted under a repository path such as:

```text
https://username.github.io/repository-name/
```

### How to enable GitHub Pages

In your GitHub repository:

1. Open `Settings`
2. Open `Pages` in the left sidebar
3. Under `Build and deployment`, choose `Deploy from a branch`
4. Under `Branch`, select your publishing branch, typically `main`
5. Under folder, select `/ (root)`
6. Click `Save`

After GitHub finishes publishing, open the site URL shown on the Pages settings screen.

### Which page to open first

Open the root landing page first:

```text
https://username.github.io/repository-name/
```

From there:

1. Open the strategy list at `web/index.html`
2. Open detail pages from the list
3. Open `web/compare.html` to compare multiple saved results

### Local file opening limitation

Opening the HTML files directly from disk with `file://` is not reliable because the browser blocks JSON fetch requests in that mode.

Use either:

1. GitHub Pages hosting
2. A local static server such as `python -m http.server 8000`
