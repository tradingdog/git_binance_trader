from __future__ import annotations

import json
from zoneinfo import ZoneInfo

from git_binance_trader.core.models import DashboardState


def render_dashboard(state: DashboardState, message: str, report: str, strategy_meta: dict[str, object] | None = None) -> str:
    generated_at_iso = state.generated_at.isoformat()
    generated_at_local = state.generated_at.astimezone(ZoneInfo("Asia/Shanghai"))
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
    strategy_payload = json.dumps(strategy_meta or {}, ensure_ascii=False)
    storage_meta = "未启用持久存储监控"
    if state.storage is not None:
        storage_meta = (
            f"持久目录：{state.storage.path} ｜ 总容量：{state.storage.total_mb:.0f}MB ｜ "
            f"可用：{state.storage.free_mb:.0f}MB ｜ 最低阈值：{state.storage.min_free_mb}MB"
        )

    def pnl_class(value: float) -> str:
      if value > 0:
        return "value-positive"
      if value < 0:
        return "value-negative"
      return "value-neutral"

    positions_html = "".join(
      (
        f"<tr>"
        f"<td class='cell-text cell-symbol'>{position.symbol}</td>"
        f"<td class='cell-text'>{position.market_type.value}</td>"
        f"<td class='cell-text'>{position.side.value}</td>"
        f"<td class='cell-text'>{position.leverage}x</td>"
        f"<td class='cell-num'>{position.quantity:.6f}</td>"
        f"<td class='cell-num'>{position.entry_price:.4f}</td>"
        f"<td class='cell-num'>{position.current_price:.4f}</td>"
        f"<td class='cell-num'>{position.stop_loss:.4f}</td>"
        f"<td class='cell-num'>{position.take_profit:.4f}</td>"
        f"<td class='cell-num {pnl_class(position.unrealized_pnl)}'>{position.unrealized_pnl:.4f}</td>"
        f"</tr>"
      )
      for position in state.positions
    ) or "<tr><td colspan='10' class='table-empty'>当前无持仓</td></tr>"

    watchlist_html = "".join(
      (
        f"<tr>"
        f"<td class='cell-text cell-symbol'>{item.symbol}</td>"
        f"<td class='cell-text'>{item.market_type.value}</td>"
        f"<td class='cell-text'>{item.leverage}x</td>"
        f"<td class='cell-text cell-source'>{item.data_source}</td>"
        f"<td class='cell-num'>{item.price:.4f}</td>"
        f"<td class='cell-num {pnl_class(item.change_pct_24h)}'>{item.change_pct_24h:.2f}%</td>"
        f"<td class='cell-num'>{item.volume_24h:.0f}</td>"
        f"<td class='cell-num'>{item.market_cap_rank}</td>"
        f"</tr>"
      )
      for item in state.watchlist
    ) or "<tr><td colspan='8' class='table-empty'>观察池为空</td></tr>"

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
    html {{ overflow-y: scroll; scrollbar-gutter: stable; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: "Segoe UI", "Microsoft YaHei", sans-serif; color: var(--ink); background: radial-gradient(circle at top, #fff7e8 0%, #f4efe6 45%, #e6ded0 100%); }}
    .shell {{ width: min(1440px, calc(100vw - 32px)); margin: 0 auto; padding: 24px 0 32px; }}
    .hero {{ display: grid; gap: 16px; grid-template-columns: repeat(12, minmax(0, 1fr)); align-items: stretch; }}
    .panel {{ background: var(--panel); backdrop-filter: blur(14px); border: 1px solid var(--line); border-radius: 20px; padding: 20px; box-shadow: 0 12px 40px rgba(24,34,44,0.08); }}
    .panel, .metric, .chart-panel {{ min-width: 0; }}
    .span-12 {{ grid-column: span 12; }}
    .span-8 {{ grid-column: span 8; }}
    .span-7 {{ grid-column: span 7; }}
    .span-6 {{ grid-column: span 6; }}
    .span-5 {{ grid-column: span 5; }}
    .span-4 {{ grid-column: span 4; }}
    .span-3 {{ grid-column: span 3; }}
    .headline {{ font-size: 34px; margin: 0 0 8px; }}
    .subline {{ margin: 0; color: rgba(24,34,44,0.72); line-height: 1.6; }}
    .metrics-grid {{ display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 16px; margin-top: 18px; }}
    .metric {{ padding: 18px; border-radius: 18px; background: linear-gradient(180deg, rgba(255,255,255,0.92), rgba(240,201,184,0.32)); border: 1px solid var(--line); }}
    .metric strong {{ display: block; font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: rgba(24,34,44,0.58); }}
    .metric span {{ display: block; margin-top: 10px; font-size: 28px; font-weight: 700; }}
    .observer {{ margin-top: 18px; padding: 12px 14px; border-radius: 12px; border: 1px solid var(--line); background: rgba(255,255,255,0.7); }}
    .meta {{ margin-top: 8px; color: rgba(24,34,44,0.68); font-size: 13px; }}
    .panel-tools {{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; justify-content: space-between; }}
    .panel-title {{ margin: 0; font-size: 20px; }}
    .panel-note {{ margin-left: auto; font-size: 12px; color: rgba(24,34,44,0.62); }}
    .select {{ border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; background: #fff; }}
    .btn {{ border: 1px solid var(--line); border-radius: 10px; padding: 8px 12px; background: #fff; cursor: pointer; font-weight: 600; }}
    .controls {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
    .tables {{ display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 16px; margin-top: 16px; align-items: start; }}
    .chart-panel {{ margin-top: 16px; }}
    .chart-header {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }}
    .chart-actions {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .chart-button {{ border: 1px solid var(--line); border-radius: 999px; padding: 10px 14px; cursor: pointer; font-weight: 700; background: rgba(255,255,255,0.78); color: var(--ink); }}
    .chart-button.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
    .chart-surface {{ position: relative; border-radius: 18px; border: 1px solid var(--line); background: linear-gradient(180deg, rgba(255,255,255,0.95), rgba(240,201,184,0.28)); padding: 12px; }}
    .chart-surface.dragging {{ cursor: grabbing; user-select: none; -webkit-user-select: none; }}
    body.chart-no-select, body.chart-no-select * {{ user-select: none !important; -webkit-user-select: none !important; }}
    .chart-svg {{ width: 100%; height: 300px; display: block; }}
    .chart-tooltip {{ position: absolute; pointer-events: none; display: none; background: #fff; border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; box-shadow: 0 8px 20px rgba(0,0,0,0.12); font-size: 12px; }}
    .chart-summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 12px; }}
    .chart-summary div {{ padding: 12px; border-radius: 14px; background: rgba(255,255,255,0.7); border: 1px solid var(--line); }}
    .chart-summary strong {{ display: block; font-size: 12px; color: rgba(24,34,44,0.6); }}
    .chart-summary span {{ display: block; margin-top: 8px; font-size: 22px; font-weight: 700; }}
    .scroll-box {{ max-height: 540px; overflow-x: auto; overflow-y: auto; border: 1px solid var(--line); border-radius: 16px; background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(250,246,241,0.98)); }}
    .scroll-box tbody tr.highlight {{ background: rgba(182,95,58,0.12); }}
    .log-box {{ max-height: 540px; overflow-y: auto; border: 1px solid var(--line); border-radius: 12px; background: #fff; padding: 12px; font-family: Consolas, monospace; font-size: 12px; white-space: pre-wrap; line-height: 1.5; }}
    .dashboard-table {{ width: 100%; border-collapse: collapse; border-spacing: 0; font-size: 13px; table-layout: auto; min-width: 100%; }}
    .positions-table {{ min-width: 1040px; }}
    .watchlist-table {{ min-width: 780px; }}
    .trades-table {{ min-width: 1220px; }}
    .dashboard-table thead th {{ position: sticky; top: 0; z-index: 1; background: #f7f3ed; font-size: 12px; letter-spacing: 0.04em; color: rgba(24,34,44,0.66); text-transform: uppercase; }}
    .dashboard-table th, .dashboard-table td {{ padding: 12px 10px; border-bottom: 1px solid rgba(24,34,44,0.08); text-align: center; vertical-align: middle; }}
    .dashboard-table tbody tr:hover {{ background: rgba(182,95,58,0.06); }}
    .cell-text {{ white-space: nowrap; text-align: center; }}
    .cell-source {{ color: rgba(24,34,44,0.72); }}
    .cell-num {{ text-align: center; white-space: nowrap; font-variant-numeric: tabular-nums; font-family: Consolas, "SFMono-Regular", monospace; }}
    .cell-symbol {{ font-weight: 700; letter-spacing: 0.01em; }}
    .cell-note {{ min-width: 240px; max-width: 320px; white-space: normal; line-height: 1.45; color: rgba(24,34,44,0.78); text-align: center; }}
    .table-empty {{ text-align: center; color: rgba(24,34,44,0.58); padding: 36px 12px; }}
    .value-positive {{ color: var(--good); }}
    .value-negative {{ color: var(--bad); }}
    .value-neutral {{ color: rgba(24,34,44,0.72); }}
    pre {{ white-space: pre-wrap; background: #fff; padding: 16px; border-radius: 14px; border: 1px solid var(--line); max-width: 100%; overflow: auto; }}
    .status-good {{ color: var(--good); }}
    .status-bad {{ color: var(--bad); }}
    .report-box {{ height: 100%; }}
    .report-box pre {{ min-height: 540px; margin: 0; }}
    .strategy-panel {{ margin-top: 16px; }}
    .strategy-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 10px; margin-bottom: 12px; }}
    .strategy-card {{ border: 1px solid var(--line); border-radius: 12px; background: rgba(255,255,255,0.78); padding: 12px; min-height: 120px; }}
    .strategy-card h4 {{ margin: 0 0 8px; font-size: 14px; }}
    .strategy-card ul {{ margin: 0; padding-left: 16px; }}
    .strategy-card li {{ margin: 4px 0; font-size: 12px; color: rgba(24,34,44,0.84); }}
    .kv {{ display: grid; grid-template-columns: 1fr auto; gap: 6px 10px; font-size: 12px; }}
    .kv b {{ color: rgba(24,34,44,0.72); font-weight: 600; }}
    .kv span {{ font-family: Consolas, "SFMono-Regular", monospace; }}
    .strategy-candidates-table {{ min-width: 1150px; }}
    .history-list {{ display: grid; gap: 10px; margin-top: 12px; }}
    .history-item {{ border: 1px solid var(--line); border-radius: 12px; background: rgba(255,255,255,0.72); padding: 12px; }}
    .history-item-head {{ display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; font-size: 12px; color: rgba(24,34,44,0.7); margin-bottom: 8px; }}
    .history-item-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px 12px; font-size: 12px; }}
    .history-item-grid b {{ color: rgba(24,34,44,0.72); font-weight: 600; }}
    @media (max-width: 960px) {{
      .shell {{ width: min(100vw - 20px, 100%); padding: 16px 0 24px; }}
      .hero, .tables, .metrics-grid, .chart-summary {{ grid-template-columns: 1fr; }}
      .strategy-grid {{ grid-template-columns: 1fr; }}
      .history-item-grid {{ grid-template-columns: 1fr; }}
      .span-12, .span-8, .span-7, .span-6, .span-5, .span-4, .span-3 {{ grid-column: 1 / -1; }}
      .report-box pre {{ min-height: 320px; }}
      .panel-tools {{ align-items: flex-start; }}
      .panel-note {{ margin-left: 0; width: 100%; }}
    }}
  </style>
</head>
<body>
  <div class='shell'>
    <section class='hero'>
      <div class='panel span-8'>
        <p style='margin:0;color:rgba(24,34,44,0.58)'>模拟资金 / 风控优先 / 禁止实盘</p>
        <h1 class='headline'>git_binance_trader 控制台</h1>
        <p class='subline'>系统仅运行在模拟盘环境，默认执行现货、永续与 Alpha（币安专门交易分类/新上市机会）统一风控框架。当前前端为观察者模式，仅展示策略结果。</p>
        <div class='observer'>
          <strong>策略洞察：</strong> <span id='strategy-insight'>{state.strategy_insight or '暂无'}</span>
          <div class='meta'>报告时间（北京时间）：<span id='report-time'>{generated_at_local.strftime('%Y-%m-%d %H:%M:%S')}</span></div>
        </div>
      </div>
      <div class='panel span-4'>
        <strong>系统状态</strong>
        <h2 id='account-status' style='margin:10px 0 6px'>{state.account.status.value}</h2>
        <p id='risk-status' class='{{"status-bad" if state.account.risk_status.breached else "status-good"}}'>{state.account.risk_status.message}</p>
        <p>最近事件：<span id='cycle-message'>{message}</span></p>
        <p class='meta' id='last-updated-label' style='margin:4px 0 0'>正在运行</p>
      </div>
    </section>
    <section class='metrics-grid'>
      <div class='metric span-3'><strong>账户净值</strong><span id='metric-equity'>{state.account.equity:.2f}</span></div>
      <div class='metric span-3'><strong>现金余额</strong><span id='metric-cash'>{state.account.cash:.2f}</span></div>
      <div class='metric span-3'><strong>保证金占用</strong><span id='metric-margin'>{state.account.margin_used:.2f}</span></div>
      <div class='metric span-3'><strong>持仓市值</strong><span id='metric-position-val'>{state.account.position_value:.2f}</span></div>
      <div class='metric span-3'><strong>现金+持仓校验差</strong><span id='metric-balance-delta'>{state.account.balance_check_delta:.6f}</span></div>
      <div class='metric span-3'><strong>累计手续费</strong><span id='metric-fees-paid'>{state.account.fees_paid:.4f}</span></div>
      <div class='metric span-3'><strong>总收益率</strong><span id='metric-total-return'>{state.account.total_return_pct:.2f}%</span></div>
      <div class='metric span-3'><strong>全程回撤</strong><span id='metric-drawdown'>{state.account.drawdown_pct:.2f}%</span></div>
    </section>

    <section class='panel chart-panel span-12'>
      <div class='chart-header'>
        <div>
          <h3 style='margin:0 0 6px'>净值曲线</h3>
          <div class='meta'>支持 1 小时、4 小时、日线、周线切换。图表时间按北京时间显示，净值按基金口径标准化（起点 1.0000），支持拖拽回看和滚轮缩放。{storage_meta}</div>
          <div id='chart-range-meta' class='meta'>当前窗口：--</div>
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

    <section class='panel span-12 strategy-panel'>
      <div class='panel-tools'>
        <h3 class='panel-title'>策略逻辑看板</h3>
        <span id='strategy-updated' class='panel-note'>等待策略数据...</span>
      </div>
      <div class='strategy-grid'>
        <div class='strategy-card'>
          <h4>热点因子定义</h4>
          <ul id='factor-def-list'><li>加载中...</li></ul>
        </div>
        <div class='strategy-card'>
          <h4>小时级自适应参数（当前）</h4>
          <div id='adaptive-param-list' class='kv'><b>加载中</b><span>--</span></div>
        </div>
        <div class='strategy-card'>
          <h4>近 1 小时调参依据</h4>
          <div id='adaptive-metric-list' class='kv'><b>加载中</b><span>--</span></div>
        </div>
      </div>
      <div class='scroll-box'>
        <table class='dashboard-table strategy-candidates-table'>
          <thead>
            <tr>
              <th>标的</th><th>市场</th><th>总分</th><th>24h涨跌</th><th>24h成交额</th>
              <th>放量</th><th>波动挤压突破</th><th>跨市场强弱</th><th>社交热度代理</th><th>新币行为</th>
            </tr>
          </thead>
          <tbody id='strategy-candidates-body'><tr><td colspan='10' class='table-empty'>加载中...</td></tr></tbody>
        </table>
      </div>
      <div style='margin-top:12px;'>
        <h4 style='margin:0 0 10px;'>调参历史记录</h4>
        <div id='adaptation-history-list' class='history-list'><div class='history-item'>加载中...</div></div>
      </div>
    </section>

    <section class='tables'>
      <div class='panel table-panel span-12'>
        <h3 class='panel-title'>持仓</h3>
        <div class='scroll-box'>
          <table class='dashboard-table positions-table'>
            <thead><tr><th>标的</th><th>市场</th><th>方向</th><th>杠杆</th><th>数量</th><th>开仓价</th><th>现价</th><th>止损</th><th>止盈</th><th>浮盈亏</th></tr></thead>
            <tbody id='positions-body'>{positions_html}</tbody>
          </table>
        </div>
      </div>
      <div class='panel table-panel span-12'>
        <h3 class='panel-title'>观察池（前 10）</h3>
        <div class='scroll-box'>
          <table class='dashboard-table watchlist-table'>
            <thead><tr><th>标的</th><th>市场</th><th>杠杆</th><th>来源</th><th>价格</th><th>24h</th><th>24h成交额</th><th>排名</th></tr></thead>
            <tbody id='watchlist-body'>{watchlist_html}</tbody>
          </table>
        </div>
      </div>
      <div class='panel trade-panel span-12'>
        <div class='panel-tools'>
          <h3 class='panel-title'>成交明细</h3>
          <div class='controls'>
            <label>条数
              <select id='trades-limit' class='select'>
                <option value='500' selected>500</option>
                <option value='1000'>1000</option>
                <option value='2000'>2000</option>
                <option value='5000'>5000</option>
              </select>
            </label>
          </div>
          <span id='trades-status' class='panel-note'>等待刷新</span>
        </div>
        <div class='scroll-box'>
          <table class='dashboard-table trades-table'>
            <thead><tr><th>时间</th><th>标的</th><th>市场</th><th>杠杆</th><th>方向</th><th>下单类型</th><th>数量</th><th>价格</th><th>手续费</th><th>已实现</th><th>备注</th></tr></thead>
            <tbody id='trades-body'><tr><td colspan='11'>加载中...</td></tr></tbody>
          </table>
        </div>
      </div>
      <div class='panel report-box span-12'>
        <h3 class='panel-title'>每小时报告（最新快照）</h3>
        <pre>{report}</pre>
      </div>
    </section>

    <section class='panel span-12' style='margin-top:16px;'>
      <div class='panel-tools'>
        <h3 class='panel-title'>运行日志</h3>
        <div class='controls'>
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
        <span id='logs-status' class='panel-note'>等待刷新</span>
      </div>
      <div id='log-box' class='log-box'>加载中...</div>
    </section>
  </div>

  <script>
    const equityHistory = {history_payload};
    const strategyMetaInitial = {strategy_payload};
    let serverNowMs = new Date('{generated_at_iso}').getTime();
    const displayOffsetMs = 8 * 60 * 60 * 1000;
    const windowConfig = {{
      '1h': {{ bucketMs: 60 * 60 * 1000, visibleBuckets: 5 }},
      '4h': {{ bucketMs: 4 * 60 * 60 * 1000, visibleBuckets: 6 }},
      '1d': {{ bucketMs: 24 * 60 * 60 * 1000, visibleBuckets: 7 }},
      '1w': {{ bucketMs: 7 * 24 * 60 * 60 * 1000, visibleBuckets: 8 }},
    }};
    const sortedHistory = equityHistory
      .map((point) => ({{ ...point, tsMs: new Date(point.timestamp).getTime() }}))
      .filter((point) => Number.isFinite(point.tsMs))
      .sort((a, b) => a.tsMs - b.tsMs);
    let historyMinTs = sortedHistory.length ? sortedHistory[0].tsMs : serverNowMs;
    let historyMaxTs = sortedHistory.length ? sortedHistory[sortedHistory.length - 1].tsMs : serverNowMs;
    const viewportEndByWindow = {{
      '1h': Math.max(serverNowMs, historyMaxTs),
      '4h': Math.max(serverNowMs, historyMaxTs),
      '1d': Math.max(serverNowMs, historyMaxTs),
      '1w': Math.max(serverNowMs, historyMaxTs),
    }};
    const viewportSpanBucketsByWindow = {{
      '1h': windowConfig['1h'].visibleBuckets,
      '4h': windowConfig['4h'].visibleBuckets,
      '1d': windowConfig['1d'].visibleBuckets,
      '1w': windowConfig['1w'].visibleBuckets,
    }};
    let activeWindowKey = '1h';

    function formatMetric(value, suffix = '') {{
      if (!Number.isFinite(value)) return '--';
      return `${{value.toFixed(2)}}${{suffix}}`;
    }}

    function formatNav(value) {{
      if (!Number.isFinite(value)) return '--';
      return value.toFixed(4);
    }}

    const displayTimeZone = 'Asia/Shanghai';

    function getTimeParts(ts) {{
      const parts = new Intl.DateTimeFormat('zh-CN', {{
        timeZone: displayTimeZone,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      }}).formatToParts(new Date(ts));
      return Object.fromEntries(parts.filter((part) => part.type !== 'literal').map((part) => [part.type, part.value]));
    }}

    function formatTime(ts, windowKey) {{
      const parts = getTimeParts(ts);
      if (windowKey === '1w' || windowKey === '1d') {{
        return `${{parts.month}}-${{parts.day}} ${{parts.hour}}:${{parts.minute}}`;
      }}
      return `${{parts.hour}}:${{parts.minute}}:${{parts.second}}`;
    }}

    function formatDateTime(ts) {{
      const parts = getTimeParts(ts);
      return `${{parts.year}}-${{parts.month}}-${{parts.day}} ${{parts.hour}}:${{parts.minute}}:${{parts.second}}`;
    }}

    function formatRange(startMs, endMs) {{
      const fmt = (ms) => `${{formatDateTime(ms)}} 北京时间`;
      return `${{fmt(startMs)}} 至 ${{fmt(endMs)}}`;
    }}

    function alignToPeriodEnd(windowKey, ts) {{
      const shifted = new Date(ts + displayOffsetMs);
      shifted.setUTCMilliseconds(0);
      shifted.setUTCSeconds(0);

      if (windowKey === '1h') {{
        shifted.setUTCMinutes(0);
      }} else if (windowKey === '4h') {{
        shifted.setUTCMinutes(0);
        shifted.setUTCHours(Math.floor(shifted.getUTCHours() / 4) * 4);
      }} else if (windowKey === '1d') {{
        shifted.setUTCMinutes(0);
        shifted.setUTCHours(0, 0, 0, 0);
      }} else if (windowKey === '1w') {{
        shifted.setUTCMinutes(0);
        shifted.setUTCHours(0, 0, 0, 0);
        const day = shifted.getUTCDay();
        const diffToMonday = day === 0 ? 6 : day - 1;
        shifted.setUTCDate(shifted.getUTCDate() - diffToMonday);
      }}

      return shifted.getTime() - displayOffsetMs;
    }}

    function spanBucketsForWindow(windowKey) {{
      const fallback = windowConfig[windowKey].visibleBuckets;
      const raw = viewportSpanBucketsByWindow[windowKey] ?? fallback;
      return Math.max(3, Math.round(raw));
    }}

    function clampSpanBuckets(windowKey, spanBuckets) {{
      const config = windowConfig[windowKey];
      const minBuckets = 3;
      const alignedMin = alignToPeriodEnd(windowKey, historyMinTs);
      const alignedMax = alignToPeriodEnd(windowKey, Math.max(serverNowMs, historyMaxTs));
      const maxBucketsByHistory = Math.max(
        config.visibleBuckets,
        Math.floor((alignedMax - alignedMin) / config.bucketMs) + 1,
      );
      return Math.min(maxBucketsByHistory, Math.max(minBuckets, Math.round(spanBuckets)));
    }}

    function clampViewport(windowKey, endMs, spanBuckets) {{
      const config = windowConfig[windowKey];
      const clampedSpan = clampSpanBuckets(windowKey, spanBuckets ?? spanBucketsForWindow(windowKey));
      const maxEnd = alignToPeriodEnd(windowKey, Math.max(serverNowMs, historyMaxTs));
      const minEnd = alignToPeriodEnd(windowKey, historyMinTs) + (clampedSpan - 1) * config.bucketMs;
      if (minEnd >= maxEnd) {{
        return maxEnd;
      }}
      const snappedEnd = alignToPeriodEnd(windowKey, endMs);
      return Math.min(maxEnd, Math.max(minEnd, snappedEnd));
    }}

    function seriesForWindow(windowKey) {{
      const config = windowConfig[windowKey];
      const spanBuckets = clampSpanBuckets(windowKey, spanBucketsForWindow(windowKey));
      viewportSpanBucketsByWindow[windowKey] = spanBuckets;
      const defaultEndMs = alignToPeriodEnd(windowKey, Math.max(serverNowMs, historyMaxTs));
      const endMs = clampViewport(windowKey, viewportEndByWindow[windowKey] ?? defaultEndMs, spanBuckets);
      viewportEndByWindow[windowKey] = endMs;
      const startMs = endMs - (spanBuckets - 1) * config.bucketMs;
      if (!sortedHistory.length) {{
        return {{ points: [], startMs, endMs, bucketMs: config.bucketMs, spanBuckets }};
      }}

      const points = [];
      let cursor = 0;
      let lastKnown = null;
      while (cursor < sortedHistory.length && sortedHistory[cursor].tsMs <= startMs) {{
        lastKnown = sortedHistory[cursor];
        cursor += 1;
      }}

      for (let bucketTs = startMs; bucketTs <= endMs; bucketTs += config.bucketMs) {{
        while (cursor < sortedHistory.length && sortedHistory[cursor].tsMs <= bucketTs) {{
          lastKnown = sortedHistory[cursor];
          cursor += 1;
        }}
        if (lastKnown) {{
          points.push({{ ...lastKnown, bucketTs, synthetic: lastKnown.tsMs !== bucketTs }});
        }}
      }}

      return {{ points, startMs, endMs, bucketMs: config.bucketMs, spanBuckets }};
    }}

    function drawChart(windowKey) {{
      const result = seriesForWindow(windowKey);
      const points = result.points;
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
      const rangeMeta = document.getElementById('chart-range-meta');

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
        rangeMeta.textContent = '当前窗口：无可用数据';
        return;
      }}
      empty.style.display = 'none';
      rangeMeta.textContent = `当前窗口：${{formatRange(result.startMs, result.endMs)}} ｜ 缩放：${{result.spanBuckets}}格`;

      const navBaseCandidate = sortedHistory.length ? sortedHistory[0].equity : points[0].equity;
      const navBase = Math.abs(navBaseCandidate) > 1e-12 ? navBaseCandidate : 1;
      const navPoints = points.map((point) => ({{ ...point, nav: point.equity / navBase }}));

      const minValue = Math.min(...navPoints.map((point) => point.nav));
      const maxValue = Math.max(...navPoints.map((point) => point.nav));
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
        xText.textContent = formatTime(points[idx].bucketTs || points[idx].timestamp, windowKey);
        xLabels.appendChild(xText);
      }}

      const coordinates = navPoints.map((point, index) => {{
        const x = xAt(index);
        const y = yAt(point.nav);
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
          const hoverTs = item.point.bucketTs || item.point.tsMs;
          tooltip.innerHTML = `周期: ${{formatDateTime(hoverTs)}}<br>净值: ${{formatNav(item.point.nav)}}`;
          crosshair.style.display = 'block';
          crosshair.setAttribute('x1', String(item.x));
          crosshair.setAttribute('x2', String(item.x));
          highlightTradeRows(hoverTs, result.bucketMs);
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
          highlightTradeRows(null, result.bucketMs);
        }});

        pointsLayer.appendChild(dot);
      }}

      const first = navPoints[0].nav;
      const last = navPoints[navPoints.length - 1].nav;
      const changePct = first === 0 ? 0 : ((last - first) / first) * 100;
      document.getElementById('chart-latest').textContent = formatNav(last);
      document.getElementById('chart-change').textContent = formatMetric(changePct, '%');
      document.getElementById('chart-high').textContent = formatNav(maxValue);
      document.getElementById('chart-low').textContent = formatNav(minValue);
    }}

    function highlightTradeRows(centerMs, bucketMs) {{
      const rows = Array.from(document.querySelectorAll('#trades-body tr[data-ts]'));
      for (const row of rows) {{
        row.classList.remove('highlight');
      }}
      if (!Number.isFinite(centerMs)) {{
        return;
      }}
      const range = Math.max(bucketMs / 2, 60 * 1000);
      for (const row of rows) {{
        const ts = Number(row.dataset.ts);
        if (Number.isFinite(ts) && Math.abs(ts - centerMs) <= range) {{
          row.classList.add('highlight');
        }}
      }}
    }}

    let tradesRequestSeq = 0;
    let logsRequestSeq = 0;
    let tradesHasData = false;
    let logsHasData = false;

    function setStatusText(id, text) {{
      const el = document.getElementById(id);
      if (el) el.textContent = text;
    }}

    function toNum(v, digits = 4) {{
      const n = Number(v);
      return Number.isFinite(n) ? n.toFixed(digits) : '--';
    }}

    const adaptiveParamLabels = {{
      max_positions: '最大持仓数',
      max_exposure_pct: '最大总仓位暴露比例',
      target_margin_utilization_pct: '目标保证金利用率',
      entry_score_threshold: '开仓评分阈值',
      rotation_exit_score: '轮动退出阈值',
      position_budget_pct: '单仓预算比例',
      min_quote_volume: '最低24h成交额',
      perpetual_leverage: '永续默认杠杆',
    }};

    function paramLabel(key) {{
      return adaptiveParamLabels[key] || key;
    }}

    function renderStrategyMeta(meta) {{
      const strategyUpdated = document.getElementById('strategy-updated');
      const defsEl = document.getElementById('factor-def-list');
      const paramsEl = document.getElementById('adaptive-param-list');
      const metricEl = document.getElementById('adaptive-metric-list');
      const candidatesEl = document.getElementById('strategy-candidates-body');
      const historyEl = document.getElementById('adaptation-history-list');

      const payload = meta && typeof meta === 'object' ? meta : {{}};
      const factors = Array.isArray(payload.factors) ? payload.factors : [];
      defsEl.innerHTML = factors.length
        ? factors.map((item) => `<li><b>${{item.label}}</b>：${{item.desc}}</li>`).join('')
        : '<li>暂无热点因子说明</li>';

      const params = payload.adaptive_params && typeof payload.adaptive_params === 'object' ? payload.adaptive_params : {{}};
      const paramKeys = ['max_positions', 'max_exposure_pct', 'target_margin_utilization_pct', 'entry_score_threshold', 'rotation_exit_score', 'position_budget_pct', 'min_quote_volume'];
      paramsEl.innerHTML = paramKeys.map((k) => `<b>${{paramLabel(k)}}</b><span>${{toNum(params[k], k === 'min_quote_volume' ? 0 : 4)}}${{k === 'target_margin_utilization_pct' ? '%' : ''}}</span>`).join('') || '<b>暂无</b><span>--</span>';

      const latest = payload.latest_adaptation && typeof payload.latest_adaptation === 'object' ? payload.latest_adaptation : null;
      const metrics = latest && latest.metrics && typeof latest.metrics === 'object' ? latest.metrics : null;
      const before = latest && latest.before && typeof latest.before === 'object' ? latest.before : null;
      const after = latest && latest.after && typeof latest.after === 'object' ? latest.after : null;
      if (metrics) {{
        metricEl.innerHTML = [
          `<b>平仓笔数</b><span>${{toNum(metrics.closed_trades, 0)}}</span>`,
          `<b>胜率</b><span>${{toNum(Number(metrics.win_rate) * 100, 2)}}%</span>`,
          `<b>平均已实现盈亏</b><span>${{toNum(metrics.avg_realized_pnl, 6)}}</span>`,
          `<b>已实现盈亏合计</b><span>${{toNum(metrics.realized_sum, 6)}}</span>`,
          `<b>手续费合计</b><span>${{toNum(metrics.fee_sum, 6)}}</span>`,
          `<b>开仓评分阈值变化</b><span>${{before && after ? `${{toNum(before.entry_score_threshold)}} -> ${{toNum(after.entry_score_threshold)}}` : '--'}}</span>`,
        ].join('');
      }} else {{
        metricEl.innerHTML = '<b>暂无调参事件</b><span>最近1小时尚未形成新事件</span>';
      }}

      const historyRows = Array.isArray(payload.adaptation_history) ? payload.adaptation_history : [];
      if (!historyRows.length) {{
        historyEl.innerHTML = "<div class='history-item'>暂无调参历史</div>";
      }} else {{
        historyEl.innerHTML = historyRows.map((row) => {{
          const event = row.event || {{}};
          const metricsRow = event.metrics || {{}};
          const beforeRow = event.before || {{}};
          const afterRow = event.after || {{}};
          return `
            <div class='history-item'>
              <div class='history-item-head'>
                <span>时间：${{event.timestamp ? formatDateTime(event.timestamp) : '--'}}</span>
                <span>收益率：${{toNum(row.total_return_pct, 4)}}%</span>
                <span>手续费：${{toNum(row.fees_paid, 4)}}</span>
              </div>
              <div class='history-item-grid'>
                <div><b>胜率</b> ${{toNum(Number(metricsRow.win_rate) * 100, 2)}}%</div>
                <div><b>已实现盈亏</b> ${{toNum(metricsRow.realized_sum, 6)}}</div>
                <div><b>手续费合计</b> ${{toNum(metricsRow.fee_sum, 6)}}</div>
                <div><b>${{paramLabel('max_exposure_pct')}}</b> ${{toNum(beforeRow.max_exposure_pct, 4)}} -> ${{toNum(afterRow.max_exposure_pct, 4)}}</div>
                <div><b>${{paramLabel('target_margin_utilization_pct')}}</b> ${{toNum(beforeRow.target_margin_utilization_pct, 4)}}% -> ${{toNum(afterRow.target_margin_utilization_pct, 4)}}%</div>
                <div><b>${{paramLabel('position_budget_pct')}}</b> ${{toNum(beforeRow.position_budget_pct, 4)}} -> ${{toNum(afterRow.position_budget_pct, 4)}}</div>
                <div><b>${{paramLabel('entry_score_threshold')}}</b> ${{toNum(beforeRow.entry_score_threshold, 4)}} -> ${{toNum(afterRow.entry_score_threshold, 4)}}</div>
              </div>
            </div>
          `;
        }}).join('');
      }}

      const rows = Array.isArray(payload.hot_candidates) ? payload.hot_candidates : [];
      if (!rows.length) {{
        candidatesEl.innerHTML = "<tr><td colspan='10' class='table-empty'>暂无可解释候选</td></tr>";
      }} else {{
        candidatesEl.innerHTML = rows.map((row) => {{
          const f = row.factors || {{}};
          const change = Number(row.change_pct_24h);
          const changeClass = change > 0 ? 'value-positive' : change < 0 ? 'value-negative' : 'value-neutral';
          return `
            <tr>
              <td class='cell-text cell-symbol'>${{row.symbol || '--'}}</td>
              <td class='cell-text'>${{row.market_type || '--'}}</td>
              <td class='cell-num'>${{toNum(row.score, 4)}}</td>
              <td class='cell-num ${{changeClass}}'>${{toNum(row.change_pct_24h, 2)}}%</td>
              <td class='cell-num'>${{toNum(row.volume_24h, 0)}}</td>
              <td class='cell-num'>${{toNum(f.volume_surge, 4)}}</td>
              <td class='cell-num'>${{toNum(f.volatility_breakout, 4)}}</td>
              <td class='cell-num'>${{toNum(f.cross_market_strength, 4)}}</td>
              <td class='cell-num'>${{toNum(f.social_heat, 4)}}</td>
              <td class='cell-num'>${{toNum(f.new_coin_behavior, 4)}}</td>
            </tr>
          `;
        }}).join('');
      }}

      strategyUpdated.textContent = payload.generated_at
        ? `策略数据更新时间：${{formatDateTime(payload.generated_at)}}`
        : '策略数据更新时间：--';
    }}

    async function loadTrades(limit, options = {{}}) {{
      const silent = Boolean(options.silent);
      const body = document.getElementById('trades-body');
      const requestId = ++tradesRequestSeq;
      if (!silent && !tradesHasData) {{
        body.innerHTML = `<tr><td colspan='11'>加载中...</td></tr>`;
      }}
      setStatusText('trades-status', '成交更新中...');
      try {{
        const response = await fetch(`/api/trades?limit=${{limit}}`, {{ cache: 'no-store' }});
        if (!response.ok) {{
          throw new Error('trades request failed');
        }}
        const payload = await response.json();
        if (requestId !== tradesRequestSeq) {{
          return;
        }}
        if (!payload.items || !payload.items.length) {{
          body.innerHTML = `<tr><td colspan='11' class='table-empty'>暂无成交</td></tr>`;
          tradesHasData = false;
          setStatusText('trades-status', '暂无成交（已同步）');
          return;
        }}
        body.innerHTML = payload.items.map((trade) => `
          <tr data-ts="${{new Date(trade.created_at).getTime()}}">
            <td class='cell-text cell-time'>${{formatDateTime(trade.created_at)}}</td>
            <td class='cell-text cell-symbol'>${{trade.symbol}}</td>
            <td class='cell-text'>${{trade.market_type}}</td>
            <td class='cell-text'>${{trade.leverage}}x</td>
            <td class='cell-text'>${{trade.side}}</td>
            <td class='cell-text'>${{trade.liquidity_type || 'auto'}}</td>
            <td class='cell-num'>${{Number(trade.quantity).toFixed(6)}}</td>
            <td class='cell-num'>${{Number(trade.price).toFixed(4)}}</td>
            <td class='cell-num'>${{Number(trade.fee_paid || 0).toFixed(4)}}</td>
            <td class='cell-num ${{Number(trade.realized_pnl) > 0 ? 'value-positive' : Number(trade.realized_pnl) < 0 ? 'value-negative' : 'value-neutral'}}'>${{Number(trade.realized_pnl).toFixed(4)}}</td>
            <td class='cell-note'>${{trade.note || ''}}</td>
          </tr>
        `).join('');
        tradesHasData = true;
        setStatusText('trades-status', `成交已更新（${{payload.items.length}}条）`);
      }} catch (_) {{
        if (requestId !== tradesRequestSeq) {{
          return;
        }}
        if (!tradesHasData) {{
          body.innerHTML = `<tr><td colspan='11' class='table-empty'>成交明细加载失败</td></tr>`;
        }}
        setStatusText('trades-status', '成交刷新失败，已保留上次数据');
      }}
    }}

    async function loadLogs(limit, options = {{}}) {{
      const silent = Boolean(options.silent);
      const box = document.getElementById('log-box');
      const requestId = ++logsRequestSeq;
      if (!silent && !logsHasData) {{
        box.textContent = '加载中...';
      }}
      setStatusText('logs-status', '日志更新中...');
      try {{
        const response = await fetch(`/api/logs/tail?lines=${{limit}}`, {{ cache: 'no-store' }});
        if (!response.ok) {{
          throw new Error('logs request failed');
        }}
        const text = await response.text();
        if (requestId !== logsRequestSeq) {{
          return;
        }}
        box.textContent = text;
        logsHasData = true;
        setStatusText('logs-status', '日志已更新');
      }} catch (_) {{
        if (requestId !== logsRequestSeq) {{
          return;
        }}
        if (!logsHasData) {{
          box.textContent = '日志加载失败';
        }}
        setStatusText('logs-status', '日志刷新失败，已保留上次数据');
      }}
    }}

    const chartButtons = Array.from(document.querySelectorAll('.chart-button'));
    function activateWindow(windowKey) {{
      activeWindowKey = windowKey;
      localStorage.setItem('equity-window', windowKey);
      for (const button of chartButtons) {{
        button.classList.toggle('active', button.dataset.window === windowKey);
      }}
      drawChart(windowKey);
    }}

    for (const button of chartButtons) {{
      button.addEventListener('click', () => activateWindow(button.dataset.window));
    }}

    (function enableChartDragging() {{
      const chartSurface = document.getElementById('chart-surface');
      let dragging = false;
      let dragStartX = 0;
      let dragStartEndMs = 0;
      let dragStartSpanBuckets = 0;

      function setSelectionLock(locked) {{
        document.body.classList.toggle('chart-no-select', locked);
      }}

      chartSurface.addEventListener('pointerdown', (event) => {{
        if (event.button !== 0) return;
        event.preventDefault();
        dragging = true;
        dragStartX = event.clientX;
        dragStartSpanBuckets = spanBucketsForWindow(activeWindowKey);
        dragStartEndMs = clampViewport(
          activeWindowKey,
          viewportEndByWindow[activeWindowKey] ?? Math.max(serverNowMs, historyMaxTs),
          dragStartSpanBuckets,
        );
        chartSurface.classList.add('dragging');
        setSelectionLock(true);
        chartSurface.setPointerCapture(event.pointerId);
      }});

      chartSurface.addEventListener('pointermove', (event) => {{
        if (!dragging) return;
        event.preventDefault();
        const width = Math.max(200, chartSurface.clientWidth - 78);
        const deltaX = event.clientX - dragStartX;
        const spanMs = (dragStartSpanBuckets - 1) * windowConfig[activeWindowKey].bucketMs;
        const shiftMs = (-deltaX / width) * spanMs;
        viewportEndByWindow[activeWindowKey] = clampViewport(activeWindowKey, dragStartEndMs + shiftMs, dragStartSpanBuckets);
        drawChart(activeWindowKey);
      }});

      chartSurface.addEventListener('pointerup', (event) => {{
        dragging = false;
        chartSurface.classList.remove('dragging');
        setSelectionLock(false);
        chartSurface.releasePointerCapture(event.pointerId);
      }});

      chartSurface.addEventListener('pointercancel', () => {{
        dragging = false;
        chartSurface.classList.remove('dragging');
        setSelectionLock(false);
      }});

      chartSurface.addEventListener('lostpointercapture', () => {{
        dragging = false;
        chartSurface.classList.remove('dragging');
        setSelectionLock(false);
      }});

      chartSurface.addEventListener('dragstart', (event) => {{
        event.preventDefault();
      }});

      chartSurface.addEventListener('wheel', (event) => {{
        event.preventDefault();
        const config = windowConfig[activeWindowKey];
        const currentSpanBuckets = spanBucketsForWindow(activeWindowKey);
        const zoomStep = event.shiftKey ? 2 : 1;
        const targetSpanBuckets = clampSpanBuckets(
          activeWindowKey,
          currentSpanBuckets + (event.deltaY > 0 ? zoomStep : -zoomStep),
        );
        if (targetSpanBuckets === currentSpanBuckets) return;

        const rect = chartSurface.getBoundingClientRect();
        const ratio = Math.min(1, Math.max(0, (event.clientX - rect.left) / Math.max(rect.width, 1)));
        const currentEnd = clampViewport(
          activeWindowKey,
          viewportEndByWindow[activeWindowKey] ?? Math.max(serverNowMs, historyMaxTs),
          currentSpanBuckets,
        );
        const currentStart = currentEnd - (currentSpanBuckets - 1) * config.bucketMs;
        const anchorTs = currentStart + ratio * (currentSpanBuckets - 1) * config.bucketMs;
        const nextEnd = anchorTs + (1 - ratio) * (targetSpanBuckets - 1) * config.bucketMs;

        viewportSpanBucketsByWindow[activeWindowKey] = targetSpanBuckets;
        viewportEndByWindow[activeWindowKey] = clampViewport(activeWindowKey, nextEnd, targetSpanBuckets);
        drawChart(activeWindowKey);
      }}, {{ passive: false }});
    }})();

    const tradesLimitSelect = document.getElementById('trades-limit');
    tradesLimitSelect.addEventListener('change', () => loadTrades(tradesLimitSelect.value, {{ silent: false }}));

    const logsLimitSelect = document.getElementById('logs-limit');
    logsLimitSelect.addEventListener('change', () => loadLogs(logsLimitSelect.value, {{ silent: false }}));

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
    renderStrategyMeta(strategyMetaInitial);
    loadTrades(500, {{ silent: false }});
    loadLogs(500, {{ silent: false }});

    let lastUpdatedAt = Date.now();

    function updateLastUpdated() {{
      const el = document.getElementById('last-updated-label');
      if (!el) return;
      const secs = Math.round((Date.now() - lastUpdatedAt) / 1000);
      el.textContent = secs < 60
        ? `数据更新于 ${{secs}} 秒前`
        : `数据更新于 ${{Math.floor(secs / 60)}} 分钟前`;
    }}

    function renderPositionRow(p) {{
      const pnl = ((p.current_price - p.entry_price) * p.quantity).toFixed(4);
      const pnlClass = Number(pnl) > 0 ? 'value-positive' : Number(pnl) < 0 ? 'value-negative' : 'value-neutral';
      return `<tr>` +
        `<td class='cell-text cell-symbol'>${{p.symbol}}</td>` +
        `<td class='cell-text'>${{p.market_type}}</td>` +
        `<td class='cell-text'>${{p.side}}</td>` +
        `<td class='cell-text'>${{p.leverage}}x</td>` +
        `<td class='cell-num'>${{Number(p.quantity).toFixed(6)}}</td>` +
        `<td class='cell-num'>${{Number(p.entry_price).toFixed(4)}}</td>` +
        `<td class='cell-num'>${{Number(p.current_price).toFixed(4)}}</td>` +
        `<td class='cell-num'>${{Number(p.stop_loss).toFixed(4)}}</td>` +
        `<td class='cell-num'>${{Number(p.take_profit).toFixed(4)}}</td>` +
        `<td class='cell-num ${{pnlClass}}'>${{pnl}}</td>` +
        `</tr>`;
    }}

    function renderWatchlistRow(w) {{
      const changeClass = Number(w.change_pct_24h) > 0 ? 'value-positive' : Number(w.change_pct_24h) < 0 ? 'value-negative' : 'value-neutral';
      return `<tr>` +
        `<td class='cell-text cell-symbol'>${{w.symbol}}</td>` +
        `<td class='cell-text'>${{w.market_type}}</td>` +
        `<td class='cell-text'>${{w.leverage}}x</td>` +
        `<td class='cell-text cell-source'>${{w.data_source}}</td>` +
        `<td class='cell-num'>${{Number(w.price).toFixed(4)}}</td>` +
        `<td class='cell-num ${{changeClass}}'>${{Number(w.change_pct_24h).toFixed(2)}}%</td>` +
        `<td class='cell-num'>${{Number(w.volume_24h).toFixed(0)}}</td>` +
        `<td class='cell-num'>${{w.market_cap_rank}}</td>` +
        `</tr>`;
    }}

    async function softRefresh() {{
      try {{
        const resp = await fetch('/api/dashboard');
        if (!resp.ok) return;
        const data = await resp.json();
        const state = data.state;
        const acc = state.account;

        document.getElementById('metric-equity').textContent = Number(acc.equity).toFixed(2);
        document.getElementById('metric-cash').textContent = Number(acc.cash).toFixed(2);
        document.getElementById('metric-margin').textContent = Number(acc.margin_used).toFixed(2);
        document.getElementById('metric-position-val').textContent = Number(acc.position_value).toFixed(2);
        document.getElementById('metric-balance-delta').textContent = Number(acc.balance_check_delta).toFixed(6);
        document.getElementById('metric-fees-paid').textContent = Number(acc.fees_paid || 0).toFixed(4);
        document.getElementById('metric-total-return').textContent = Number(acc.total_return_pct).toFixed(2) + '%';
        document.getElementById('metric-drawdown').textContent = Number(acc.drawdown_pct).toFixed(2) + '%';

        document.getElementById('account-status').textContent = acc.status;
        const riskEl = document.getElementById('risk-status');
        riskEl.className = acc.risk_status.breached ? 'status-bad' : 'status-good';
        riskEl.textContent = acc.risk_status.message;
        document.getElementById('cycle-message').textContent = data.message || '--';

        document.getElementById('strategy-insight').textContent = state.strategy_insight || '暂无';
        const genAt = new Date(state.generated_at);
        document.getElementById('report-time').textContent = formatDateTime(genAt);

        document.getElementById('positions-body').innerHTML = state.positions && state.positions.length
          ? state.positions.map(renderPositionRow).join('')
          : "<tr><td colspan='10'>当前无持仓</td></tr>";

        document.getElementById('watchlist-body').innerHTML = state.watchlist && state.watchlist.length
          ? state.watchlist.map(renderWatchlistRow).join('')
          : "<tr><td colspan='8'>观察池为空</td></tr>";

        renderStrategyMeta(data.strategy_meta || {{}});

        if (state.equity_history && state.equity_history.length) {{
          const prevMaxTs = historyMaxTs;
          const newHistory = state.equity_history
            .map((p) => ({{ ...p, tsMs: new Date(p.timestamp).getTime() }}))
            .filter((p) => Number.isFinite(p.tsMs))
            .sort((a, b) => a.tsMs - b.tsMs);
          sortedHistory.splice(0, sortedHistory.length, ...newHistory);
          historyMinTs = sortedHistory[0].tsMs;
          historyMaxTs = sortedHistory[sortedHistory.length - 1].tsMs;
          serverNowMs = new Date(state.generated_at).getTime();
          for (const wk of Object.keys(viewportEndByWindow)) {{
            viewportSpanBucketsByWindow[wk] = clampSpanBuckets(wk, spanBucketsForWindow(wk));
            const currentAlignedMax = alignToPeriodEnd(wk, prevMaxTs);
            if (Math.abs(viewportEndByWindow[wk] - currentAlignedMax) < windowConfig[wk].bucketMs) {{
              viewportEndByWindow[wk] = alignToPeriodEnd(wk, Math.max(serverNowMs, historyMaxTs));
            }}
            viewportEndByWindow[wk] = clampViewport(wk, viewportEndByWindow[wk], viewportSpanBucketsByWindow[wk]);
          }}
          drawChart(activeWindowKey);
        }}

        loadTrades(parseInt(tradesLimitSelect.value), {{ silent: true }});
        loadLogs(parseInt(logsLimitSelect.value), {{ silent: true }});
        lastUpdatedAt = Date.now();
      }} catch (_) {{
        // 静默忽略刷新错误
      }}
    }}

    setInterval(updateLastUpdated, 5000);
    setInterval(softRefresh, 5000);
  </script>
</body>
</html>
"""
