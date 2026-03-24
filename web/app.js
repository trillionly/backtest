const RESULTS_INDEX_PATH = "../data/results/results-index.json";
const RESULTS_BASE_PATH = "../data/results";

const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
});

const percentFormatter = new Intl.NumberFormat("en-US", {
  style: "percent",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const chartInstances = [];

function formatCurrency(value) {
  return value == null ? "-" : currencyFormatter.format(Number(value));
}

function formatPercent(value) {
  return value == null ? "-" : percentFormatter.format(Number(value));
}

function formatPeriod(period) {
  if (!period || !period.start_date || !period.end_date) {
    return "기간 정보 없음";
  }
  return `${period.start_date} ~ ${period.end_date}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Failed to load ${path}`);
  }
  return response.json();
}

async function loadResultsIndex() {
  const index = await fetchJson(RESULTS_INDEX_PATH);
  return Array.isArray(index.results) ? index.results : [];
}

function getQueryParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

function showState(id, message) {
  const element = document.getElementById(id);
  if (!element) {
    return;
  }
  element.textContent = message;
  element.classList.remove("hidden");
}

function hideState(id) {
  const element = document.getElementById(id);
  if (!element) {
    return;
  }
  element.classList.add("hidden");
}

function destroyCharts() {
  while (chartInstances.length > 0) {
    chartInstances.pop().destroy();
  }
}

function buildLineChart(canvasId, datasets) {
  destroyCharts();
  const canvas = document.getElementById(canvasId);
  if (!canvas || typeof Chart === "undefined") {
    return;
  }

  const chart = new Chart(canvas, {
    type: "line",
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          type: "category",
          ticks: { maxTicksLimit: 10, color: "#665b52" },
          grid: { display: false },
        },
        y: {
          ticks: { color: "#665b52" },
          grid: { color: "rgba(80, 58, 32, 0.08)" },
        },
      },
      plugins: {
        legend: {
          labels: {
            usePointStyle: true,
            color: "#1f1a17",
            font: { family: "IBM Plex Sans" },
          },
        },
      },
    },
  });

  chartInstances.push(chart);
}

function cardMarkup(result) {
  return `
    <article class="result-card">
      <div>
        <p class="section-label">저장된 결과</p>
        <h3 class="strategy-name">${escapeHtml(result.strategy_name || result.strategy_id || result.file)}</h3>
        <p class="strategy-id">${escapeHtml(result.strategy_id || "-")}</p>
      </div>
      <div class="metric-pair-grid">
        <div class="metric-chip">
          <p class="section-label">최종 평가금액</p>
          <p class="metric-value">${escapeHtml(formatCurrency(result.summary?.final_value))}</p>
        </div>
        <div class="metric-chip">
          <p class="section-label">총수익률</p>
          <p class="metric-value">${escapeHtml(formatPercent(result.summary?.total_return))}</p>
        </div>
        <div class="metric-chip">
          <p class="section-label">CAGR</p>
          <p class="metric-value">${escapeHtml(formatPercent(result.summary?.cagr))}</p>
        </div>
        <div class="metric-chip negative">
          <p class="section-label">MDD</p>
          <p class="metric-value">${escapeHtml(formatPercent(result.summary?.mdd))}</p>
        </div>
      </div>
      <div class="card-footer">
        <p class="period-text">${escapeHtml(formatPeriod(result.period))}</p>
        <div>
          <a class="button-link secondary" href="compare.html?files=${encodeURIComponent(result.file)}">비교하기</a>
          <a class="button-link" href="strategy.html?file=${encodeURIComponent(result.file)}">상세 보기</a>
        </div>
      </div>
    </article>
  `;
}

async function renderIndexPage() {
  try {
    const results = await loadResultsIndex();
    document.getElementById("result-count").textContent = `저장된 결과 ${results.length}개`;
    if (results.length === 0) {
      showState("index-state", "저장된 백테스트 결과가 아직 없습니다. `scripts/run_backtest.py`를 실행해 결과 JSON을 생성하세요.");
      return;
    }

    hideState("index-state");
    document.getElementById("index-grid").innerHTML = results.map(cardMarkup).join("");
  } catch (error) {
    document.getElementById("result-count").textContent = "불러오기 실패";
    showState("index-state", "결과 인덱스를 불러오지 못했습니다. 로컬 정적 서버나 GitHub Pages에서 사이트를 열어 JSON 파일을 가져오세요.");
  }
}

function metricCard(label, value, tone = "") {
  return `
    <article class="metric-card">
      <p class="section-label">${escapeHtml(label)}</p>
      <h3>${escapeHtml(label)}</h3>
      <p class="${tone}">${escapeHtml(value)}</p>
    </article>
  `;
}

async function renderStrategyPage() {
  const file = getQueryParam("file");
  if (!file) {
    showState("strategy-state", "선택된 결과 파일이 없습니다. 결과 목록에서 상세 페이지를 열어주세요.");
    return;
  }

  try {
    const result = await fetchJson(`${RESULTS_BASE_PATH}/${file}`);
    document.getElementById("strategy-title").textContent = result.strategy_name || result.strategy_id || file;
    document.getElementById("strategy-subtitle").textContent = result.description
      ? `전략 ID: ${result.strategy_id} · ${result.description}`
      : `전략 ID: ${result.strategy_id} · ${formatPeriod(result.period)}`;

    document.getElementById("strategy-metrics").innerHTML = [
      metricCard("최종 평가금액", formatCurrency(result.summary?.final_value)),
      metricCard("총수익률", formatPercent(result.summary?.total_return), Number(result.summary?.total_return) < 0 ? "negative-text" : "positive-text"),
      metricCard("CAGR", formatPercent(result.summary?.cagr), Number(result.summary?.cagr) < 0 ? "negative-text" : "positive-text"),
      metricCard("MDD", formatPercent(result.summary?.mdd), "negative-text"),
    ].join("");

    const annualBody = document.getElementById("annual-returns-body");
    const annualReturns = result.annual_returns || [];
    annualBody.innerHTML = annualReturns.length
      ? annualReturns
          .map(
            (entry) => `
              <tr>
                <td>${escapeHtml(entry.year)}</td>
                <td class="${Number(entry.return) < 0 ? "negative-text" : "positive-text"}">${escapeHtml(formatPercent(entry.return))}</td>
              </tr>
            `
          )
          .join("")
      : '<tr><td colspan="2">연도별 수익률 데이터가 없습니다.</td></tr>';

    const tradeBody = document.getElementById("trade-log-body");
    const trades = result.trade_log || [];
    tradeBody.innerHTML = trades.length
      ? trades
          .map(
            (trade) => `
              <tr>
                <td>${escapeHtml(trade.date)}</td>
                <td>${escapeHtml(trade.asset)}</td>
                <td>${escapeHtml(trade.action)}</td>
                <td>${escapeHtml(Number(trade.shares).toFixed(4))}</td>
                <td>${escapeHtml(formatCurrency(trade.price))}</td>
                <td>${escapeHtml(formatCurrency(trade.amount))}</td>
                <td>${escapeHtml(trade.reason)}</td>
              </tr>
            `
          )
          .join("")
      : '<tr><td colspan="7">이 결과 파일에는 매매 내역이 없습니다.</td></tr>';

    buildLineChart("strategy-chart", [
      {
        label: result.strategy_name || result.strategy_id || file,
        data: (result.equity_curve || []).map((point) => ({ x: point.date, y: point.value })),
        borderColor: "#1f6b57",
        backgroundColor: "rgba(31, 107, 87, 0.15)",
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.2,
      },
    ]);
  } catch (error) {
    showState("strategy-state", "선택한 결과 파일을 불러오지 못했습니다. JSON 파일 존재 여부와 HTTP 환경에서의 정적 제공 여부를 확인하세요.");
  }
}

function updateCompareQuery(selectedFiles) {
  const url = new URL(window.location.href);
  if (selectedFiles.length === 0) {
    url.searchParams.delete("files");
  } else {
    url.searchParams.set("files", selectedFiles.join(","));
  }
  window.history.replaceState({}, "", url);
}

async function renderCompareResults(selectedFiles) {
  const summaryBody = document.getElementById("compare-summary-body");
  if (selectedFiles.length < 2) {
    destroyCharts();
    summaryBody.innerHTML = "";
    showState("compare-state", "비교 화면을 보려면 결과 파일을 두 개 이상 선택하세요.");
    return;
  }

  hideState("compare-state");
  const results = await Promise.all(selectedFiles.map((file) => fetchJson(`${RESULTS_BASE_PATH}/${file}`)));
  const colors = ["#1f6b57", "#bf7b38", "#5c5a9e", "#9f4b42", "#3a7ea1"];

  summaryBody.innerHTML = results
    .map(
      (result) => `
        <tr>
          <td>${escapeHtml(result.strategy_name || result.strategy_id)}</td>
          <td>${escapeHtml(result.strategy_id)}</td>
          <td>${escapeHtml(formatCurrency(result.summary?.final_value))}</td>
          <td class="${Number(result.summary?.total_return) < 0 ? "negative-text" : "positive-text"}">${escapeHtml(formatPercent(result.summary?.total_return))}</td>
          <td class="${Number(result.summary?.cagr) < 0 ? "negative-text" : "positive-text"}">${escapeHtml(formatPercent(result.summary?.cagr))}</td>
          <td class="negative-text">${escapeHtml(formatPercent(result.summary?.mdd))}</td>
          <td>${escapeHtml(formatPeriod(result.period))}</td>
        </tr>
      `
    )
    .join("");

  buildLineChart(
    "compare-chart",
    results.map((result, index) => ({
      label: result.strategy_name || result.strategy_id,
      data: (result.equity_curve || []).map((point) => ({ x: point.date, y: point.value })),
      borderColor: colors[index % colors.length],
      backgroundColor: `${colors[index % colors.length]}20`,
      borderWidth: 2,
      pointRadius: 0,
      tension: 0.2,
    }))
  );
}

async function renderComparePage() {
  try {
    const results = await loadResultsIndex();
    if (results.length === 0) {
      showState("compare-state", "저장된 결과 파일이 아직 없습니다. 비교 화면을 사용하기 전에 백테스트 결과를 먼저 생성하세요.");
      return;
    }

    const selector = document.getElementById("compare-selector");
    const initialFiles = (getQueryParam("files") || "")
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);

    selector.innerHTML = results
      .map(
        (result) => `
          <article class="selection-card">
            <label>
              <input type="checkbox" value="${escapeHtml(result.file)}" ${initialFiles.includes(result.file) ? "checked" : ""} />
              <span>
                <p class="selection-title">${escapeHtml(result.strategy_name || result.file)}</p>
                <p class="selection-meta">${escapeHtml(result.strategy_id || "-")}</p>
                <p class="selection-meta">${escapeHtml(formatPeriod(result.period))}</p>
              </span>
            </label>
          </article>
        `
      )
      .join("");

    const sync = async () => {
      const selectedFiles = Array.from(selector.querySelectorAll("input:checked")).map((input) => input.value);
      updateCompareQuery(selectedFiles);
      await renderCompareResults(selectedFiles);
    };

    selector.querySelectorAll("input").forEach((input) => {
      input.addEventListener("change", sync);
    });

    await renderCompareResults(initialFiles);
  } catch (error) {
    showState("compare-state", "결과 인덱스를 불러오지 못했습니다. 로컬 정적 서버나 GitHub Pages에서 사이트를 열어 JSON 요청이 가능하도록 하세요.");
  }
}

async function main() {
  const page = document.body.dataset.page;
  if (page === "index") {
    await renderIndexPage();
  } else if (page === "strategy") {
    await renderStrategyPage();
  } else if (page === "compare") {
    await renderComparePage();
  }
}

main();
