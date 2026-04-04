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
    .panel-tools {{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; }}
    .select {{ border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; background: #fff; }}
    .btn {{ border: 1px solid var(--line); border-radius: 10px; padding: 8px 12px; background: #fff; cursor: pointer; font-weight: 600; }}
    .tables {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; }}
    .chart-panel {{ margin-top: 16px; }}
    .chart-header {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }}
    .chart-actions {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .chart-button {{ border: 1px solid var(--line); border-radius: 999px; padding: 10px 14px; cursor: pointer; font-weight: 700; background: rgba(255,255,255,0.78); color: var(--ink); }}
    .chart-button.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
    .chart-surface {{ position: relative; border-radius: 18px; border: 1px solid var(--line); background: linear-gradient(180deg, rgba(255,255,255,0.95), rgba(240,201,184,0.28)); padding: 12px; }}
    .chart-svg {{ width: 100%; height: 300px; display: block; }}
    .chart-tooltip {{ position: absolute; pointer-events: none; display: none; background: #fff; border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; box-shadow: 0 8px 20px rgba(0,0,0,0.12); font-size: 12px; }}
    .chart-summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 12px; }}
    .chart-summary div {{ padding: 12px; border-radius: 14px; background: rgba(255,255,255,0.7); border: 1px solid var(--line); }}
    .chart-summary strong {{ display: block; font-size: 12px; color: rgba(24,34,44,0.6); }}
    .chart-summary span {{ display: block; margin-top: 8px; font-size: 22px; font-weight: 700; }}
    .scroll-box {{ max-height: 540px; overflow-y: auto; border: 1px solid var(--line); border-radius: 12px; background: #fff; }}
    .log-box {{ max-height: 540px; overflow-y: auto; border: 1px solid var(--line); border-radius: 12px; background: #fff; padding: 12px; font-family: Consolas, monospace; font-size: 12px; white-space: pre-wrap; line-height: 1.5; }}
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
      <div class='chart-surface' id='chart-surface'>
        <svg id='equity-chart' class='chart-svg' viewBox='0 0 980 300' preserveAspectRatio='none'>
          <defs>
            <linearGradient id='equity-fill' x1='0' x2='0' y1='0' y2='1'>
              <stop offset='0%' stop-color='rgba(182,95,58,0.32)' />
              <stop offset='100%' stop-color='rgba(182,95,58,0.02)' />
            </linearGradient>
          </defs>
          <g id='equity-grid' stroke='rgba(24,34,44,0.14)' stroke-width='1'></g>
          <g id='equity-y-labels' fill='rgba(24,34,44,0.72)' font-size='11'></g>
          <g id='equity-x-labels' fill='rgba(24,34,44,0.72)' font-size='11'></g>
          <line id='equity-crosshair' x1='0' x2='0' y1='20' y2='260' stroke='rgba(182,95,58,0.45)' stroke-dasharray='4 3' style='display:none'></line>
          <path id='equity-area' fill='url(#equity-fill)' stroke='none'></path>
          <path id='equity-line' fill='none' stroke='#b65f3a' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'></path>
          <g id='equity-points'></g>
          <text id='equity-empty' x='490' y='150' text-anchor='middle' fill='rgba(24,34,44,0.52)' font-size='18'>等待历史净值累积</text>
        </svg>
        <div id='chart-tooltip' class='chart-tooltip'></div>
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
        <div class='panel-tools'>
          <h3 style='margin:0'>成交明细</h3>
          <label>条数
            <select id='trades-limit' class='select'>
              <option value='500' selected>500</option>
              <option value='1000'>1000</option>
              <option value='2000'>2000</option>
              <option value='5000'>5000</option>
            </select>
          </label>
        </div>
        <div class='scroll-box'>
          <table>
            <thead><tr><th>时间</th><th>标的</th><th>市场</th><th>杠杆</th><th>方向</th><th>数量</th><th>价格</th><th>已实现</th><th>备注</th></tr></thead>
            <tbody id='trades-body'><tr><td colspan='9'>加载中...</td></tr></tbody>
          </table>
        </div>
      </div>
      <div class='panel'>
        <h3>每小时报告（最新快照）</h3>
        <pre>{report}</pre>
      </div>
    </section>

    <section class='panel' style='margin-top:16px;'>
      <div class='panel-tools'>
        <h3 style='margin:0'>运行日志</h3>
        <label>条数
          <select id='logs-limit' class='select'>
            <option value='500' selected>500</option>
            <option value='1000'>1000</option>
            <option value='2000'>2000</option>
            <option value='5000'>5000</option>
          </select>
        </label>
        <button id='copy-logs' class='btn'>一键复制日志</button>
      </div>
      <div id='log-box' class='log-box'>加载中...</div>
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
      if (!Number.isFinite(value)) return '--';
      return `${{value.toFixed(2)}}${{suffix}}`;
    }}

    function formatTime(ts, windowKey) {{
      const d = new Date(ts);
      if (windowKey === '1w' || windowKey === '1d') {{
        return `${{d.getUTCMonth()+1}}-${{d.getUTCDate()}} ${{String(d.getUTCHours()).padStart(2,'0')}}:${{String(d.getUTCMinutes()).padStart(2,'0')}}`;
      }}
      return `${{String(d.getUTCHours()).padStart(2,'0')}}:${{String(d.getUTCMinutes()).padStart(2,'0')}}:${{String(d.getUTCSeconds()).padStart(2,'0')}}`;
    }}

    function bucketize(points, spanMs, bucketMs) {{
      if (!points.length) return [];
      const newestTs = new Date(points[points.length - 1].timestamp).getTime();
      const startTs = newestTs - spanMs;
      const buckets = new Map();
      for (const point of points) {{
        const ts = new Date(point.timestamp).getTime();
        if (ts < startTs) continue;
        const bucketKey = Math.floor(ts / bucketMs) * bucketMs;
        buckets.set(bucketKey, {{ ...point, bucketTs: bucketKey }});
      }}
      const aggregated = Array.from(buckets.values()).sort((left, right) => left.bucketTs - right.bucketTs);
      return aggregated.length ? aggregated : points.slice(-1);
    }}

    function drawChart(windowKey) {{
      const config = windowConfig[windowKey] || windowConfig['1h'];
      const points = bucketize(equityHistory, config.spanMs, config.bucketMs);
      const width = 980;
      const height = 300;
      const left = 58;
      const right = 20;
      const top = 20;
      const bottom = 40;

      const line = document.getElementById('equity-line');
      const area = document.getElementById('equity-area');
      const grid = document.getElementById('equity-grid');
      const yLabels = document.getElementById('equity-y-labels');
      const xLabels = document.getElementById('equity-x-labels');
      const pointsLayer = document.getElementById('equity-points');
      const empty = document.getElementById('equity-empty');
      const tooltip = document.getElementById('chart-tooltip');
      const chartSurface = document.getElementById('chart-surface');
      const crosshair = document.getElementById('equity-crosshair');

      grid.innerHTML = '';
      yLabels.innerHTML = '';
      xLabels.innerHTML = '';
      pointsLayer.innerHTML = '';
      tooltip.style.display = 'none';
      crosshair.style.display = 'none';

      document.getElementById('chart-latest').textContent = '--';
      document.getElementById('chart-change').textContent = '--';
      document.getElementById('chart-high').textContent = '--';
      document.getElementById('chart-low').textContent = '--';

      if (!points.length) {{
        line.setAttribute('d', '');
        area.setAttribute('d', '');
        empty.style.display = 'block';
        return;
      }}
      empty.style.display = 'none';

      const minValue = Math.min(...points.map((point) => point.equity));
      const maxValue = Math.max(...points.map((point) => point.equity));
      const range = Math.max(maxValue - minValue, 1);
      const plotWidth = width - left - right;
      const plotHeight = height - top - bottom;

      function xAt(index) {{
        if (points.length === 1) return left + plotWidth / 2;
        return left + (plotWidth * index) / (points.length - 1);
      }}

      function yAt(value) {{
        return top + (maxValue - value) / range * plotHeight;
      }}

      for (let i = 0; i < 4; i += 1) {{
        const y = top + (plotHeight * i) / 3;
        const gridLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        gridLine.setAttribute('x1', String(left));
        gridLine.setAttribute('x2', String(width - right));
        gridLine.setAttribute('y1', String(y));
        gridLine.setAttribute('y2', String(y));
        grid.appendChild(gridLine);

        const value = maxValue - (range * i) / 3;
        const yText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        yText.setAttribute('x', '6');
        yText.setAttribute('y', String(y + 4));
        yText.textContent = value.toFixed(2);
        yLabels.appendChild(yText);
      }}

      const xTickIdx = [0, Math.floor((points.length - 1) / 2), points.length - 1].filter((v, i, arr) => arr.indexOf(v) === i);
      for (const idx of xTickIdx) {{
        const x = xAt(idx);
        const xText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        xText.setAttribute('x', String(x));
        xText.setAttribute('y', String(height - 10));
        xText.setAttribute('text-anchor', 'middle');
        xText.textContent = formatTime(points[idx].timestamp, windowKey);
        xLabels.appendChild(xText);
      }}

      const coordinates = points.map((point, index) => {{
        const x = xAt(index);
        const y = yAt(point.equity);
        return {{ x, y, point }};
      }});

      const linePath = coordinates
        .map((coordinate, index) => `${{index === 0 ? 'M' : 'L'}}${{coordinate.x.toFixed(2)}},${{coordinate.y.toFixed(2)}}`)
        .join(' ');
      const areaPath = `${{linePath}} L${{coordinates[coordinates.length - 1].x.toFixed(2)}},${{(top + plotHeight).toFixed(2)}} L${{coordinates[0].x.toFixed(2)}},${{(top + plotHeight).toFixed(2)}} Z`;
      line.setAttribute('d', linePath);
      area.setAttribute('d', areaPath);

      for (const item of coordinates) {{
        const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        dot.setAttribute('cx', String(item.x));
        dot.setAttribute('cy', String(item.y));
        dot.setAttribute('r', '3.4');
        dot.setAttribute('fill', '#b65f3a');
        dot.setAttribute('opacity', '0.86');

        dot.addEventListener('mouseenter', () => {{
          tooltip.style.display = 'block';
          tooltip.innerHTML = `时间: ${{formatTime(item.point.timestamp, windowKey)}}<br>净值: ${{item.point.equity.toFixed(2)}}`;
          crosshair.style.display = 'block';
          crosshair.setAttribute('x1', String(item.x));
          crosshair.setAttribute('x2', String(item.x));
        }});
        dot.addEventListener('mousemove', (event) => {{
          const rect = chartSurface.getBoundingClientRect();
          const leftPos = Math.min(rect.width - 140, Math.max(12, event.clientX - rect.left + 12));
          const topPos = Math.max(12, event.clientY - rect.top - 46);
          tooltip.style.left = `${{leftPos}}px`;
          tooltip.style.top = `${{topPos}}px`;
        }});
        dot.addEventListener('mouseleave', () => {{
          tooltip.style.display = 'none';
          crosshair.style.display = 'none';
        }});

        pointsLayer.appendChild(dot);
      }}

      const first = points[0].equity;
      const last = points[points.length - 1].equity;
      const changePct = first === 0 ? 0 : ((last - first) / first) * 100;
      document.getElementById('chart-latest').textContent = formatMetric(last);
      document.getElementById('chart-change').textContent = formatMetric(changePct, '%');
      document.getElementById('chart-high').textContent = formatMetric(maxValue);
      document.getElementById('chart-low').textContent = formatMetric(minValue);
    }}

    async function loadTrades(limit) {{
      const body = document.getElementById('trades-body');
      body.innerHTML = `<tr><td colspan='9'>加载中...</td></tr>`;
      try {{
        const response = await fetch(`/api/trades?limit=${{limit}}`);
        const payload = await response.json();
        if (!payload.items || !payload.items.length) {{
          body.innerHTML = `<tr><td colspan='9'>暂无成交</td></tr>`;
          return;
        }}
        body.innerHTML = payload.items.map((trade) => `
          <tr>
            <td>${{new Date(trade.created_at).toISOString().replace('T', ' ').replace('Z', ' UTC')}}</td>
            <td>${{trade.symbol}}</td>
            <td>${{trade.market_type}}</td>
            <td>${{trade.leverage}}x</td>
            <td>${{trade.side}}</td>
            <td>${{Number(trade.quantity).toFixed(6)}}</td>
            <td>${{Number(trade.price).toFixed(4)}}</td>
            <td>${{Number(trade.realized_pnl).toFixed(4)}}</td>
            <td>${{trade.note || ''}}</td>
          </tr>
        `).join('');
      }} catch (_) {{
        body.innerHTML = `<tr><td colspan='9'>成交明细加载失败</td></tr>`;
      }}
    }}

    async function loadLogs(limit) {{
      const box = document.getElementById('log-box');
      box.textContent = '加载中...';
      try {{
        const response = await fetch(`/api/logs/tail?lines=${{limit}}`);
        box.textContent = await response.text();
      }} catch (_) {{
        box.textContent = '日志加载失败';
      }}
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

    const tradesLimitSelect = document.getElementById('trades-limit');
    tradesLimitSelect.addEventListener('change', () => loadTrades(tradesLimitSelect.value));

    const logsLimitSelect = document.getElementById('logs-limit');
    logsLimitSelect.addEventListener('change', () => loadLogs(logsLimitSelect.value));

    document.getElementById('copy-logs').addEventListener('click', async () => {{
      const content = document.getElementById('log-box').textContent || '';
      try {{
        await navigator.clipboard.writeText(content);
        alert('日志已复制到剪贴板');
      }} catch (_) {{
        alert('复制失败，请手动复制');
      }}
    }});

    activateWindow(localStorage.getItem('equity-window') || '1h');
    loadTrades(500);
    loadLogs(500);
    setTimeout(() => window.location.reload(), 30000);
  </script>
</body>
</html>
"""
