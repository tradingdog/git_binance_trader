from git_binance_trader.core.models import DashboardState


def render_dashboard(state: DashboardState, message: str, report: str) -> str:
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
      --accent-soft: #f0c9b8;
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
    .actions {{ display: flex; gap: 12px; flex-wrap: wrap; margin-top: 18px; }}
    .observer {{ margin-top: 18px; padding: 12px 14px; border-radius: 12px; border: 1px solid var(--line); background: rgba(255,255,255,0.7); }}
    .meta {{ margin-top: 8px; color: rgba(24,34,44,0.68); font-size: 13px; }}
    button {{ border: 0; border-radius: 999px; padding: 12px 18px; cursor: pointer; font-weight: 700; }}
    .primary {{ background: var(--accent); color: #fff; }}
    .secondary {{ background: #fff; color: var(--ink); border: 1px solid var(--line); }}
    .danger {{ background: var(--bad); color: #fff; }}
    .tables {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 10px 8px; border-bottom: 1px solid var(--line); text-align: left; }}
    pre {{ white-space: pre-wrap; background: #fff; padding: 16px; border-radius: 14px; border: 1px solid var(--line); }}
    .status-good {{ color: var(--good); }}
    .status-bad {{ color: var(--bad); }}
    @media (max-width: 960px) {{
      .hero, .tables, .grid {{ grid-template-columns: 1fr; }}
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
    setTimeout(() => window.location.reload(), 15000);
  </script>
</body>
</html>
"""
