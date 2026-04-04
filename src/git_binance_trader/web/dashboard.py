from __future__ import annotations

import json

from git_binance_trader.core.models import DashboardState


def render_dashboard(state: DashboardState, message: str, report: str) -> str:
    history_payload = json.dumps(
        [
            {
                "timestamp": point.timestamp.isoformat(),
                "equity": point.equity,
                "cash": point.cash,
                "margin_used": point.margin_used,
                "position_value": point.position_value,
            }
            for point in state.equity_history
        ],
        ensure_ascii=False,
    )
    storage_meta = "未启用持久存储监控"
    if state.storage is not None:
        storage_meta = (
            f"持久目录：{state.storage.path} ｜ 总容量：{state.storage.total_mb:.0f}MB ｜ "
            f"可用：{state.storage.free_mb:.0f}MB ｜ 最低阈值：{state.storage.min_free_mb}MB"
        )

    positions_html = "".join(
        f"<tr><td>{position.symbol}</td><td>{position.market_type.value}</td><td>{position.leverage}x</td><td>{position.quantity}</td><td>{position.entry_price:.4f}</td><td>{position.current_price:.4f}</td><td>{position.stop_loss:.4f}</td><td>{position.take_profit:.4f}</td><td>{position.unrealized_pnl:.4f}</td></tr>"
        for position in state.positions
    ) or "<tr><td colspan='9'>当前无持仓</td></tr>"

    trades_html = "".join(
        f"<tr><td>{trade.symbol}</td><td>{trade.market_type.value}</td><td>{trade.leverage}x</td><td>{trade.side.value}</td><td>{trade.quantity}</td><td>{trade.price:.4f}</td><td>{trade.realized_pnl:.4f}</td><td>{trade.note}</td></tr>"
        for trade in state.trades
    ) or "<tr><td colspan='8'>暂无成交</td></tr>"

    watchlist_html = "".join(
        f"<tr><td>{item.symbol}</td><td>{item.market_type.value}</td><td>{item.leverage}x</td><td>{item.data_source}</td><td>{item.price:.4f}</td><td>{item.change_pct_24h:.2f}%</td><td>{item.volume_24h:.0f}</td><td>{item.market_cap_rank}</td></tr>"
        for item in state.watchlist
    )

    return f"""
<!DOCTYPE html>
<html lang='zh-CN'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>git_binance_trader 模拟盘控制台</title>
  <style>
    :root {{
      --bg: #f4efe6;
      --panel: rgba(255,255,255,0.84);
      --ink: #18222c;
      --accent: #b65f3a;
      --good: #0f766e;
      --bad: #b42318;
      --line: rgba(24,34,44,0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: "Segoe UI", "Microsoft YaHei", sans-serif; color: var(--ink); background: radial-gradient(circle at top, #fff7e8 0%, #f4efe6 45%, #e6ded0 100%); }}
    .shell {{ max-width: 1280px; margin: 0 auto; padding: 24px; }}
    .hero {{ display: grid; gap: 16px; grid-template-columns: 1.5fr 1fr; align-items: stretch; }}
    .panel {{ background: var(--panel); backdrop-filter: blur(14px); border: 1px solid var(--line); border-radius: 20px; padding: 20px; box-shadow: 0 12px 40px rgba(24,34,44,0.08); }}
    .headline {{ font-size: 34px; margin: 0 0 8px; }}
    .subline {{ margin: 0; color: rgba(24,34,44,0.72); line-height: 1.6; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-top: 18px; }}
    .metric {{ padding: 18px; border-radius: 18px; background: linear-gradient(180deg, rgba(255,255,255,0.92), rgba(240,201,184,0.32)); border: 1px solid var(--line); }}
    .metric strong {{ display: block; font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: rgba(24,34,44,0.58); }}
    .metric span {{ display: block; margin-top: 10px; font-size: 28px; font-weight: 700; }}
    .observer {{ margin-top: 18px; padding: 12px 14px; border-radius: 12px; border: 1px solid var(--line); background: rgba(255,255,255,0.7); }}
    .meta {{ margin-top: 8px; color: rgba(24,34,44,0.68); font-size: 13px; }}
    .tables {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; }}
    .chart-panel {{ margin-top: 16px; }}
    .chart-header {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }}
    .chart-actions {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .chart-button {{ border: 1px solid var(--line); border-radius: 999px; padding: 10px 14px; cursor: pointer; font-weight: 700; background: rgba(255,255,255,0.78); color: var(--ink); }}
    .chart-button.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
    .chart-surface {{ border-radius: 18px; border: 1px solid var(--line); background: linear-gradient(180deg, rgba(255,255,255,0.95), rgba(240,201,184,0.28)); padding: 12px; }}
    .chart-svg {{ width: 100%; height: 260px; display: block; }}
    .chart-summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 12px; }}
    .chart-summary div {{ padding: 12px; border-radius: 14px; background: rgba(255,255,255,0.7); border: 1px solid var(--line); }}
    .chart-summary strong {{ display: block; font-size: 12px; color: rgba(24,34,44,0.6); }}
    .chart-summary span {{ display: block; margin-top: 8px; font-size: 22px; font-weight: 700; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 10px 8px; border-bottom: 1px solid var(--line); text-align: left; }}
    pre {{ white-space: pre-wrap; background: #fff; padding: 16px; border-radius: 14px; border: 1px solid var(--line); }}
    .status-good {{ color: var(--good); }}
    .status-bad {{ color: var(--bad); }}
    @media (max-width: 960px) {{
      .hero, .tables, .grid, .chart-summary {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class='shell'>
    <section class='hero'>
      <div class='panel'>
        <p style='margin:0;color:rgba(24,34,44,0.58)'>模拟资金 / 风控优先 / 禁止实盘</p>
        <h1 class='headline'>git_binance_trader 控制台</h1>
        <p class='subline'>系统仅运行在模拟盘环境，默认执行现货、永续与 Alpha（币安专门交易分类/新上市机会）统一风控框架。当前前端为观察者模式，仅展示策略结果。</p>
        <div class='observer'>
          <strong>策略洞察：</strong> {state.strategy_insight or '暂无'}
          <div class='meta'>报告时间（UTC）：{state.generated_at.strftime('%Y-%m-%d %H:%M:%S')}</div>
        </div>
      </div>
      <div class='panel'>
        <strong>系统状态</strong>
        <h2 style='margin:10px 0 6px'>{state.account.status.value}</h2>
        <p class='{"status-bad" if state.account.risk_status.breached else "status-good"}'>{state.account.risk_status.message}</p>
        <p>最近事件：{message}</p>
      </div>
    </section>
    <section class='grid'>
      <div class='metric'><strong>账户净值</strong><span>{state.account.equity:.2f}</span></div>
      <div class='metric'><strong>现金余额</strong><span>{state.account.cash:.2f}</span></div>
      <div class='metric'><strong>保证金占用</strong><span>{state.account.margin_used:.2f}</span></div>
      <div class='metric'><strong>持仓市值</strong><span>{state.account.position_value:.2f}</span></div>
      <div class='metric'><strong>现金+持仓校验差</strong><span>{state.account.balance_check_delta:.6f}</span></div>
      <div class='metric'><strong>总收益率</strong><span>{state.account.total_return_pct:.2f}%</span></div>
      <div class='metric'><strong>全程回撤</strong><span>{state.account.drawdown_pct:.2f}%</span></div>
    </section>
    <section class='panel chart-panel'>
      <div class='chart-header'>
        <div>
          <h3 style='margin:0 0 6px'>净值曲线</h3>
          <div class='meta'>支持 1 小时、4 小时、日线、周线切换。{storage_meta}</div>
        </div>
        <div class='chart-actions'>
          <button class='chart-button active' data-window='1h'>1小时</button>
          <button class='chart-button' data-window='4h'>4小时</button>
          <button class='chart-button' data-window='1d'>日线</button>
          <button class='chart-button' data-window='1w'>周线</button>
        </div>
      </div>
      <div class='chart-surface'>
        <svg id='equity-chart' class='chart-svg' viewBox='0 0 960 260' preserveAspectRatio='none'>
          <defs>
            <linearGradient id='equity-fill' x1='0' x2='0' y1='0' y2='1'>
              <stop offset='0%' stop-color='rgba(182,95,58,0.32)' />
              <stop offset='100%' stop-color='rgba(182,95,58,0.02)' />
            </linearGradient>
          </defs>
          <path id='equity-area' fill='url(#equity-fill)' stroke='none'></path>
          <path id='equity-line' fill='none' stroke='#b65f3a' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'></path>
          <g id='equity-grid' stroke='rgba(24,34,44,0.12)' stroke-width='1'></g>
          <text id='equity-empty' x='480' y='130' text-anchor='middle' fill='rgba(24,34,44,0.52)' font-size='18'>等待历史净值累积</text>
        </svg>
        <div class='chart-summary'>
          <div><strong>最新净值</strong><span id='chart-latest'>--</span></div>
          <div><strong>区间涨跌</strong><span id='chart-change'>--</span></div>
          <div><strong>区间最高</strong><span id='chart-high'>--</span></div>
          <div><strong>区间最低</strong><span id='chart-low'>--</span></div>
        </div>
      </div>
    </section>
    <section class='tables'>
      <div class='panel'>
        <h3>持仓</h3>
        <table>
          <thead><tr><th>标的</th><th>市场</th><th>杠杆</th><th>数量</th><th>开仓价</th><th>现价</th><th>止损</th><th>止盈</th><th>浮盈亏</th></tr></thead>
          <tbody>{positions_html}</tbody>
        </table>
      </div>
      <div class='panel'>
        <h3>观察池（前 10）</h3>
        <table>
          <thead><tr><th>标的</th><th>市场</th><th>杠杆</th><th>来源</th><th>价格</th><th>24h</th><th>24h成交额</th><th>排名</th></tr></thead>
          <tbody>{watchlist_html}</tbody>
        </table>
      </div>
      <div class='panel'>
        <h3>成交明细</h3>
        <table>
          <thead><tr><th>标的</th><th>市场</th><th>杠杆</th><th>方向</th><th>数量</th><th>价格</th><th>已实现</th><th>备注</th></tr></thead>
          <tbody>{trades_html}</tbody>
        </table>
      </div>
      <div class='panel'>
        <h3>每小时报告（最新快照）</h3>
        <pre>{report}</pre>
      </div>
    </section>
  </div>
  <script>
    const equityHistory = {history_payload};
    const windowConfig = {{
      '1h': {{ spanMs: 60 * 60 * 1000, bucketMs: 60 * 1000 }},
      '4h': {{ spanMs: 4 * 60 * 60 * 1000, bucketMs: 5 * 60 * 1000 }},
      '1d': {{ spanMs: 24 * 60 * 60 * 1000, bucketMs: 15 * 60 * 1000 }},
      '1w': {{ spanMs: 7 * 24 * 60 * 60 * 1000, bucketMs: 60 * 60 * 1000 }},
    }};

    function formatMetric(value, suffix = '') {{
      if (!Number.isFinite(value)) {{
        return '--';
      }}
      return `${{value.toFixed(2)}}${{suffix}}`;
    }}

    function bucketize(points, spanMs, bucketMs) {{
      if (!points.length) {{
        return [];
      }}
      const newestTs = new Date(points[points.length - 1].timestamp).getTime();
      const startTs = newestTs - spanMs;
      const buckets = new Map();
      for (const point of points) {{
        const ts = new Date(point.timestamp).getTime();
        if (ts < startTs) {{
          continue;
        }}
        const bucketKey = Math.floor(ts / bucketMs) * bucketMs;
        buckets.set(bucketKey, {{ ...point, bucketTs: bucketKey }});
      }}
      const aggregated = Array.from(buckets.values()).sort((left, right) => left.bucketTs - right.bucketTs);
      return aggregated.length ? aggregated : points.slice(-1);
    }}

    function drawChart(windowKey) {{
      const config = windowConfig[windowKey] || windowConfig['1h'];
      const points = bucketize(equityHistory, config.spanMs, config.bucketMs);
      const line = document.getElementById('equity-line');
      const area = document.getElementById('equity-area');
      const grid = document.getElementById('equity-grid');
      const empty = document.getElementById('equity-empty');
      document.getElementById('chart-latest').textContent = '--';
      document.getElementById('chart-change').textContent = '--';
      document.getElementById('chart-high').textContent = '--';
      document.getElementById('chart-low').textContent = '--';
      grid.innerHTML = '';

      if (!points.length) {{
        line.setAttribute('d', '');
        area.setAttribute('d', '');
        empty.style.display = 'block';
        return;
      }}

      empty.style.display = 'none';
      const width = 960;
      const height = 260;
      const padding = 18;
      const minValue = Math.min(...points.map((point) => point.equity));
      const maxValue = Math.max(...points.map((point) => point.equity));
      const range = Math.max(maxValue - minValue, 1);

      for (let index = 0; index < 4; index += 1) {{
        const y = padding + ((height - padding * 2) / 3) * index;
        const xLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        xLine.setAttribute('x1', String(padding));
        xLine.setAttribute('x2', String(width - padding));
        xLine.setAttribute('y1', String(y));
        xLine.setAttribute('y2', String(y));
        grid.appendChild(xLine);
      }}

      const coordinates = points.map((point, index) => {{
        const x = points.length === 1
          ? width / 2
          : padding + ((width - padding * 2) * index) / (points.length - 1);
        const y = height - padding - ((point.equity - minValue) / range) * (height - padding * 2);
        return {{ x, y }};
      }});

      const linePath = coordinates
        .map((coordinate, index) => `${{index === 0 ? 'M' : 'L'}}${{coordinate.x.toFixed(2)}},${{coordinate.y.toFixed(2)}}`)
        .join(' ');
      const areaPath = `${{linePath}} L${{coordinates[coordinates.length - 1].x.toFixed(2)}},${{(height - padding).toFixed(2)}} L${{coordinates[0].x.toFixed(2)}},${{(height - padding).toFixed(2)}} Z`;

      line.setAttribute('d', linePath);
      area.setAttribute('d', areaPath);

      const first = points[0].equity;
      const last = points[points.length - 1].equity;
      const changePct = first === 0 ? 0 : ((last - first) / first) * 100;
      document.getElementById('chart-latest').textContent = formatMetric(last);
      document.getElementById('chart-change').textContent = formatMetric(changePct, '%');
      document.getElementById('chart-high').textContent = formatMetric(maxValue);
      document.getElementById('chart-low').textContent = formatMetric(minValue);
    }}

    const chartButtons = Array.from(document.querySelectorAll('.chart-button'));
    function activateWindow(windowKey) {{
      localStorage.setItem('equity-window', windowKey);
      for (const button of chartButtons) {{
        button.classList.toggle('active', button.dataset.window === windowKey);
      }}
      drawChart(windowKey);
    }}

    for (const button of chartButtons) {{
      button.addEventListener('click', () => activateWindow(button.dataset.window));
    }}

    activateWindow(localStorage.getItem('equity-window') || '1h');
    setTimeout(() => window.location.reload(), 15000);
  </script>
</body>
</html>
"""
