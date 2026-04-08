from __future__ import annotations

import json
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

CN_TZ = ZoneInfo("Asia/Shanghai")

STYLE = """
:root {
  --bg: #09111b;
  --panel: #0f1b2a;
  --panel-soft: #122238;
  --line: #27405f;
  --text: #e7effa;
  --muted: #91a7c1;
  --warn: #f0b90b;
  --danger: #ff6565;
  --ok: #29cc87;
  --accent: #43a8ff;
  --mono: "JetBrains Mono", Consolas, monospace;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  color: var(--text);
  font-family: "HarmonyOS Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  background:
    radial-gradient(1100px 540px at -8% -18%, rgba(67,168,255,0.22), transparent 70%),
    radial-gradient(860px 430px at 110% -10%, rgba(240,185,11,0.15), transparent 66%),
    var(--bg);
  min-height: 100vh;
}
.shell { width: min(1600px, calc(100vw - 20px)); margin: 0 auto; padding: 16px 0 24px; }
.grid { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 10px; }
.panel { background: linear-gradient(180deg, var(--panel), #0d1928); border: 1px solid var(--line); border-radius: 12px; padding: 12px; min-width: 0; }
.span-12 { grid-column: span 12; }
.span-8 { grid-column: span 8; }
.span-6 { grid-column: span 6; }
.span-4 { grid-column: span 4; }
.headline { margin: 0; font-size: clamp(30px, 2.2vw, 44px); }
.sub { margin: 6px 0 0; color: var(--muted); }
.cards { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.card { border: 1px solid var(--line); border-radius: 10px; padding: 10px; background: var(--panel-soft); }
.card b { display: block; font-size: 12px; color: var(--muted); }
.card span { display: block; margin-top: 6px; font-family: var(--mono); font-size: 24px; }
.btns { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.btn { border: 1px solid var(--line); border-radius: 10px; padding: 11px; background: #16283d; color: var(--text); font-weight: 700; cursor: pointer; }
.btn.warn { border-color: #856f1c; background: #30290f; color: #ffd86d; }
.btn.danger { border-color: #8a3c3c; background: #321919; color: #ff9d9d; }
.status { margin-top: 8px; color: var(--muted); }
textarea { width: 100%; min-height: 112px; border-radius: 10px; border: 1px solid var(--line); background: #0b1420; color: var(--text); padding: 10px; font-family: var(--mono); }
.table-wrap { overflow: auto; border: 1px solid var(--line); border-radius: 10px; background: #0b1420; }
table { width: 100%; border-collapse: collapse; min-width: 860px; }
th, td { padding: 9px 8px; border-bottom: 1px solid #203650; text-align: center; font-size: 12px; }
th { color: #9cb4cf; background: #112034; position: sticky; top: 0; }
.num { font-family: var(--mono); white-space: nowrap; }
.pos { color: var(--ok); }
.neg { color: var(--danger); }
.log-box { white-space: pre-wrap; max-height: 290px; overflow: auto; border: 1px solid var(--line); border-radius: 10px; background: #0b1420; padding: 10px; font-family: var(--mono); font-size: 12px; line-height: 1.5; }
.details-list { max-height: 420px; overflow: auto; display: grid; gap: 8px; }
details { border: 1px solid var(--line); border-radius: 10px; background: #0b1420; padding: 8px 10px; }
summary { cursor: pointer; font-weight: 700; color: #cfe1f7; }
.detail-meta { color: var(--muted); font-size: 12px; margin-top: 6px; }
.detail-steps { margin: 8px 0 0; padding-left: 16px; color: #c4d6ee; }
.kv { display: grid; grid-template-columns: 1fr auto; gap: 6px 10px; font-size: 12px; }
.kv b { color: var(--muted); font-weight: 600; }
.kv span { font-family: var(--mono); }
a { color: var(--accent); }
.footer { color: var(--muted); font-size: 12px; }
@media (max-width: 1040px) {
  .grid, .cards, .btns { grid-template-columns: 1fr; }
  .span-12, .span-8, .span-6, .span-4 { grid-column: 1 / -1; }
  table { min-width: 680px; }
}
"""

SCRIPT = """
function n(v, d = 2) { const x = Number(v); return Number.isFinite(x) ? x.toFixed(d) : '--'; }
function ts(v) {
  if (!v) return '--';
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return '--';
  return d.toLocaleString('zh-CN', { hour12: false, timeZone: 'Asia/Shanghai' });
}
function cls(v) { const x = Number(v); if (!Number.isFinite(x)) return ''; if (x > 0) return 'pos'; if (x < 0) return 'neg'; return ''; }
function esc(v) { return String(v ?? '--').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;'); }

function renderLogRows(data, key) {
  if (!data || !data.length) return '暂无记录';
  return data.map((r) => `[${ts(r.timestamp)}] ${r.event_type || r.operator || 'event'} | ${r[key] || '--'}`).join('\n');
}

function renderPositions(rows) {
  const body = document.getElementById('positions-body');
  if (!rows || !rows.length) {
    body.innerHTML = "<tr><td colspan='10'>当前无持仓</td></tr>";
    return;
  }
  body.innerHTML = rows.map((r) => `<tr><td>${esc(r.symbol)}</td><td>${esc(r.market_type)}</td><td>${esc(r.side)}</td><td>${esc(r.leverage)}x</td><td class='num'>${n(r.quantity, 6)}</td><td class='num'>${n(r.entry_price, 4)}</td><td class='num'>${n(r.current_price, 4)}</td><td class='num'>${n(r.stop_loss, 4)}</td><td class='num'>${n(r.take_profit, 4)}</td><td class='num ${cls(r.unrealized_pnl)}'>${n(r.unrealized_pnl, 4)}</td></tr>`).join('');
}

function renderTrades(rows) {
  const body = document.getElementById('trades-body');
  if (!rows || !rows.length) {
    body.innerHTML = "<tr><td colspan='9'>暂无成交记录</td></tr>";
    return;
  }
  body.innerHTML = rows.map((r) => `<tr><td>${ts(r.created_at)}</td><td>${esc(r.symbol)}</td><td>${esc(r.market_type)}</td><td>${esc(r.side)}</td><td class='num'>${n(r.quantity, 6)}</td><td class='num'>${n(r.price, 4)}</td><td class='num'>${n(r.fee_paid, 4)}</td><td class='num ${cls(r.realized_pnl)}'>${n(r.realized_pnl, 4)}</td><td>${esc(r.note || '')}</td></tr>`).join('');
}

function renderTasks(tasks) {
  const box = document.getElementById('task-list');
  if (!tasks || !tasks.length) {
    box.innerHTML = "<div class='status'>暂无任务细节</div>";
    return;
  }
  box.innerHTML = tasks.map((t) => {
    const steps = (t.steps || []).map((s) => `<li>${esc(s)}</li>`).join('');
    return `<details><summary>${esc(t.title)} | ${esc(t.status)} | ${ts(t.created_at)}</summary><div class='detail-meta'>摘要：${esc(t.summary || '--')}</div><ul class='detail-steps'>${steps}</ul><div style='margin-top:8px'><button class='btn task-action' style='padding:6px 8px' data-task-id='${esc(t.id)}' data-task-action='pause'>暂停</button> <button class='btn warn task-action' style='padding:6px 8px' data-task-id='${esc(t.id)}' data-task-action='retry'>重试</button> <button class='btn danger task-action' style='padding:6px 8px' data-task-id='${esc(t.id)}' data-task-action='terminate'>终止</button></div></details>`;
  }).join('');
  bindDynamicActions();
}

function renderApprovals(rows) {
  const body = document.getElementById('approval-body');
  if (!rows || !rows.length) {
    body.innerHTML = "<tr><td colspan='6'>暂无审批</td></tr>";
    return;
  }
  body.innerHTML = rows.map((r) => {
    const buttons = r.status === 'pending'
      ? `<button class='btn approval-action' style='padding:6px 8px' data-approval-id='${esc(r.id)}' data-decision='approve'>通过</button> <button class='btn danger approval-action' style='padding:6px 8px' data-approval-id='${esc(r.id)}' data-decision='reject'>拒绝</button>`
      : '-';
    return `<tr><td>${esc(r.id)}</td><td>${esc(r.action)}</td><td>${esc(r.reason)}</td><td>${esc(r.requested_by)}</td><td>${esc(r.status)}</td><td>${buttons}</td></tr>`;
  }).join('');
  bindDynamicActions();
}

function renderCandidates(rows) {
  const body = document.getElementById('candidate-body');
  if (!rows || !rows.length) {
    body.innerHTML = "<tr><td colspan='10'>暂无候选策略</td></tr>";
    return;
  }
  body.innerHTML = rows.map((r) => `<tr><td>${esc(r.id)}</td><td>${esc(r.name)}</td><td class='num'>${n(r.day_return_pct, 4)}</td><td class='num'>${n(r.sharpe, 4)}</td><td class='num'>${n(r.mdd_pct, 4)}</td><td class='num'>${n(r.fee_ratio_pct, 4)}</td><td class='num'>${n(r.score_j, 6)}</td><td>${r.hard_constraint_passed ? '通过' : '拒绝'}</td><td>${esc(r.status)}</td><td>${esc(r.risk_note)}</td></tr>`).join('');
}

function renderAudit(rows) {
  if (!rows || !rows.length) return '暂无审计事件';
  return rows.map((r) => `[${ts(r.created_at)}] ${r.category} | ${r.actor} | ${r.message} | ${JSON.stringify(r.detail || {})}`).join('\n');
}

function renderReports(payload) {
  const hourly = payload?.hourly || [];
  const daily = payload?.daily || [];
  const weekly = payload?.weekly || [];
  return ['=== 小时报告 ===', ...hourly.slice(0, 20), '', '=== 日报告 ===', ...daily.slice(0, 10), '', '=== 周报告 ===', ...weekly.slice(0, 6)].join('\n') || '暂无报告';
}

function renderReliability(p) {
  if (!p) return '暂无可靠性信息';
  return [`幂等缓存: ${p.idempotency_cache_size ?? '--'}`, `重试次数: ${p.retry_count ?? '--'}`, `超时次数: ${p.timeout_count ?? '--'}`, `补偿次数: ${p.compensation_count ?? '--'}`, `上下文恢复次数: ${p.context_continuity_count ?? '--'}`, '', '告警:', ...((p.alarms || []).slice(0, 15))].join('\n');
}

function renderPayload(p) {
  const s = p.system || {};
  const u = p.ai_usage || {};
  const g = p.governance_config || {};
  const risk = g.risk || {};
  const release = p.release_state || {};
  document.getElementById('k-total-tokens').textContent = n(u.total_tokens, 0);
  document.getElementById('k-total-cost').textContent = '$' + n(u.total_cost_usd, 4);
  document.getElementById('k-input-tokens').textContent = n(u.input_tokens, 0);
  document.getElementById('k-output-tokens').textContent = n(u.output_tokens, 0);
  document.getElementById('m-equity').textContent = n(s.equity, 2);
  document.getElementById('m-cash').textContent = n(s.cash, 2);
  document.getElementById('m-margin').textContent = n(s.margin_used, 2);
  document.getElementById('m-position-value').textContent = n(s.position_value, 2);
  document.getElementById('m-fee').textContent = n(s.fees_paid, 4);
  document.getElementById('m-realized').textContent = n(s.realized_pnl, 4);
  document.getElementById('m-unrealized').textContent = n(s.unrealized_pnl, 4);
  document.getElementById('m-ret').textContent = n(s.total_return_pct, 2) + '%';
  document.getElementById('m-dd').textContent = n(s.drawdown_pct, 2) + '%';
  document.getElementById('m-ddd').textContent = n(s.daily_drawdown_pct, 2) + '%';
  document.getElementById('m-pos').textContent = n(s.positions, 0);
  document.getElementById('m-status').textContent = s.status || '--';
  document.getElementById('status').textContent = '状态: ' + (s.status || '--') + ' | ' + (s.ai_message || '--');
  document.getElementById('g-level').textContent = g.autonomy_level || '--';
  document.getElementById('g-structural').textContent = String(g.allow_structural_changes);
  document.getElementById('g-night').textContent = String(g.allow_night_autonomy);
  document.getElementById('g-target').textContent = n(g.objective_daily_return_pct, 2) + '%';
  document.getElementById('g-fee-limit').textContent = n(g.max_fee_ratio_pct, 2) + '%';
  document.getElementById('g-max-dd').textContent = n(risk.max_drawdown_pct, 2) + '%';
  document.getElementById('g-max-dd-day').textContent = n(risk.max_daily_drawdown_pct, 2) + '%';
  document.getElementById('g-max-loss').textContent = n(risk.max_trade_loss_pct, 2) + '%';
  document.getElementById('r-champion').textContent = release.champion_version || '--';
  document.getElementById('r-challenger').textContent = release.challenger_version || '--';
  document.getElementById('r-ratio').textContent = n(release.gray_ratio_pct, 2) + '%';
  document.getElementById('r-status').textContent = release.status || '--';
  document.getElementById('r-last-release').textContent = ts(release.last_release_at);
  document.getElementById('r-last-rollback').textContent = ts(release.last_rollback_at);
  renderPositions(p.positions || []);
  renderTrades(p.trades || []);
  renderTasks(p.ai_tasks || []);
  renderApprovals(p.approvals || []);
  renderCandidates(p.candidates || []);
  document.getElementById('runtime-log').textContent = (p.runtime_logs || []).join('\n') || '暂无运行日志';
  document.getElementById('ai-log').textContent = renderLogRows(p.memory || [], 'message');
  document.getElementById('cmd-log').textContent = renderLogRows(p.commands || [], 'command');
  document.getElementById('audit-log').textContent = renderAudit(p.audit_events || []);
  document.getElementById('report-log').textContent = renderReports(p.reports || {});
  document.getElementById('reliability-log').textContent = renderReliability(p.reliability || {});
  const humanUrl = p.human_version?.dashboard_url || '#';
  const aiUrl = p.ai_version?.dashboard_url || '#';
  const humanLink = document.getElementById('human-link');
  const aiLink = document.getElementById('ai-link');
  humanLink.href = humanUrl;
  humanLink.textContent = '人类版本: ' + humanUrl;
  aiLink.href = aiUrl;
  aiLink.textContent = 'AI版本: ' + aiUrl;
}

async function load() {
  const response = await fetch('/api/ai/governance', { cache: 'no-store' });
  if (!response.ok) throw new Error('load failed');
  renderPayload(await response.json());
}

async function act(name) {
  const mapping = {
    pause: '/api/actions/pause',
    resume: '/api/actions/resume',
    close: '/api/actions/emergency-close',
    halt: '/api/actions/halt',
    freeze: '/api/actions/freeze-autonomy',
    rollback: '/api/actions/rollback'
  };
  const response = await fetch(mapping[name], {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator: 'human', role: 'human_root' })
  });
  const payload = await response.json();
  document.getElementById('action-result').textContent = (payload.message || '完成') + ' (状态: ' + (payload.status || '--') + ')';
  await load();
}

async function decideApproval(id, decision) {
  const response = await fetch('/api/governance/approvals/' + id, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator: 'human', role: 'human_root', decision })
  });
  const payload = await response.json();
  document.getElementById('action-result').textContent = '审批结果: ' + (payload.status || '--');
  await load();
}

async function sendCmd() {
  const value = document.getElementById('cmd').value.trim();
  if (!value) {
    document.getElementById('cmd-result').textContent = '请输入内容';
    return;
  }
  const response = await fetch('/api/ai/command', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ command: value, operator: 'human' })
  });
  const payload = await response.json();
  document.getElementById('cmd-result').textContent = payload.message || '已提交';
  document.getElementById('cmd').value = '';
  await load();
}

async function sendStructuredCmd() {
  const value = document.getElementById('scmd').value.trim();
  if (!value) {
    document.getElementById('scmd-result').textContent = '请输入内容';
    return;
  }
  const selected = document.querySelector('[data-priority].active') || document.querySelector("[data-priority='medium']");
  const priority = selected?.dataset?.priority || 'medium';
  const response = await fetch('/api/ai/command/structured', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      command: value,
      operator: 'human',
      priority,
      scope: 'next_cycle',
      objective_weights: { w1_day_return: 1.1, w3_mdd: 1.0 },
      deadline: 'T+1h',
      rollback_condition: '回撤连续2轮放大',
      idempotency_key: 'ui-' + Date.now()
    })
  });
  const payload = await response.json();
  document.getElementById('scmd-result').textContent = payload.message || payload.status || '已提交';
  document.getElementById('scmd').value = '';
  await load();
}

async function controlTask(taskId, action) {
  const response = await fetch('/api/tasks/' + taskId + '/control', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator: 'human', role: 'human_root', action })
  });
  const payload = await response.json();
  document.getElementById('action-result').textContent = '任务控制: ' + (payload.status || '--');
  await load();
}

function bindDynamicActions() {
  document.querySelectorAll('.approval-action').forEach((btn) => {
    btn.onclick = () => decideApproval(btn.dataset.approvalId, btn.dataset.decision).catch((e) => {
      document.getElementById('action-result').textContent = '失败: ' + String(e);
    });
  });
  document.querySelectorAll('.task-action').forEach((btn) => {
    btn.onclick = () => controlTask(btn.dataset.taskId, btn.dataset.taskAction).catch((e) => {
      document.getElementById('action-result').textContent = '失败: ' + String(e);
    });
  });
}

document.querySelectorAll('[data-act]').forEach((btn) => btn.addEventListener('click', () => act(btn.dataset.act).catch((e) => {
  document.getElementById('action-result').textContent = '失败: ' + String(e);
})));
document.querySelectorAll('[data-priority]').forEach((btn) => btn.addEventListener('click', () => {
  document.querySelectorAll('[data-priority]').forEach((item) => item.classList.remove('active'));
  btn.classList.add('active');
}));
document.querySelector("[data-priority='medium']")?.classList.add('active');
document.getElementById('send').addEventListener('click', () => sendCmd().catch((e) => {
  document.getElementById('cmd-result').textContent = '失败: ' + String(e);
}));
document.getElementById('send-structured').addEventListener('click', () => sendStructuredCmd().catch((e) => {
  document.getElementById('scmd-result').textContent = '失败: ' + String(e);
}));

const bootstrap = JSON.parse(document.getElementById('bootstrap-data').textContent || '{}');
renderPayload(bootstrap);
bindDynamicActions();
load().catch((e) => {
  document.getElementById('runtime-log').textContent = '加载失败: ' + String(e);
});
setInterval(() => load().catch(() => {}), 5000);
"""


def _num(value: object, digits: int = 2, suffix: str = "") -> str:
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return "--"
    return f"{number:.{digits}f}{suffix}"


def _ts(value: object) -> str:
    if not value:
        return "--"
    try:
        if isinstance(value, datetime):
            dt = value
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return dt.astimezone(CN_TZ).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return escape(str(value))


def _text(value: object) -> str:
    if value is None:
        return "--"
    return escape(str(value))


def _cls(value: object) -> str:
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return ""
    if number > 0:
        return "pos"
    if number < 0:
        return "neg"
    return ""


def _mapping(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    return {}


def _rows(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, object]] = []
    for item in value:
        if isinstance(item, dict):
            rows.append({str(key): field for key, field in item.items()})
    return rows


def _items(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    return []


def _lines(value: object) -> list[str]:
    return [str(item) for item in _items(value)]


def _render_positions(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "<tr><td colspan='10'>当前无持仓</td></tr>"
    return "".join(
        "<tr>"
        f"<td>{_text(row.get('symbol'))}</td>"
        f"<td>{_text(row.get('market_type'))}</td>"
        f"<td>{_text(row.get('side'))}</td>"
        f"<td>{_text(row.get('leverage'))}x</td>"
        f"<td class='num'>{_num(row.get('quantity'), 6)}</td>"
        f"<td class='num'>{_num(row.get('entry_price'), 4)}</td>"
        f"<td class='num'>{_num(row.get('current_price'), 4)}</td>"
        f"<td class='num'>{_num(row.get('stop_loss'), 4)}</td>"
        f"<td class='num'>{_num(row.get('take_profit'), 4)}</td>"
        f"<td class='num {_cls(row.get('unrealized_pnl'))}'>{_num(row.get('unrealized_pnl'), 4)}</td>"
        "</tr>"
        for row in rows
    )


def _render_trades(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "<tr><td colspan='9'>暂无成交记录</td></tr>"
    return "".join(
        "<tr>"
        f"<td>{_ts(row.get('created_at'))}</td>"
        f"<td>{_text(row.get('symbol'))}</td>"
        f"<td>{_text(row.get('market_type'))}</td>"
        f"<td>{_text(row.get('side'))}</td>"
        f"<td class='num'>{_num(row.get('quantity'), 6)}</td>"
        f"<td class='num'>{_num(row.get('price'), 4)}</td>"
        f"<td class='num'>{_num(row.get('fee_paid'), 4)}</td>"
        f"<td class='num {_cls(row.get('realized_pnl'))}'>{_num(row.get('realized_pnl'), 4)}</td>"
        f"<td>{_text(row.get('note'))}</td>"
        "</tr>"
        for row in rows[:120]
    )


def _render_tasks(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "<div class='status'>暂无任务细节</div>"
    parts: list[str] = []
    for row in rows[:60]:
        steps = "".join(f"<li>{_text(step)}</li>" for step in _items(row.get("steps")))
        task_id = _text(row.get("id"))
        parts.append(
            "<details>"
            f"<summary>{_text(row.get('title'))} | {_text(row.get('status'))} | {_ts(row.get('created_at'))}</summary>"
            f"<div class='detail-meta'>摘要：{_text(row.get('summary'))}</div>"
            f"<ul class='detail-steps'>{steps}</ul>"
            "<div style='margin-top:8px'>"
            f"<button class='btn task-action' style='padding:6px 8px' data-task-id='{task_id}' data-task-action='pause'>暂停</button> "
            f"<button class='btn warn task-action' style='padding:6px 8px' data-task-id='{task_id}' data-task-action='retry'>重试</button> "
            f"<button class='btn danger task-action' style='padding:6px 8px' data-task-id='{task_id}' data-task-action='terminate'>终止</button>"
            "</div>"
            "</details>"
        )
    return "".join(parts)


def _render_approvals(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "<tr><td colspan='6'>暂无审批</td></tr>"
    parts: list[str] = []
    for row in rows[:80]:
        buttons = "-"
        if row.get("status") == "pending":
            approval_id = _text(row.get("id"))
            buttons = (
                f"<button class='btn approval-action' style='padding:6px 8px' data-approval-id='{approval_id}' data-decision='approve'>通过</button> "
                f"<button class='btn danger approval-action' style='padding:6px 8px' data-approval-id='{approval_id}' data-decision='reject'>拒绝</button>"
            )
        parts.append(
            "<tr>"
            f"<td>{_text(row.get('id'))}</td>"
            f"<td>{_text(row.get('action'))}</td>"
            f"<td>{_text(row.get('reason'))}</td>"
            f"<td>{_text(row.get('requested_by'))}</td>"
            f"<td>{_text(row.get('status'))}</td>"
            f"<td>{buttons}</td>"
            "</tr>"
        )
    return "".join(parts)


def _render_candidates(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "<tr><td colspan='10'>暂无候选策略</td></tr>"
    return "".join(
        "<tr>"
        f"<td>{_text(row.get('id'))}</td>"
        f"<td>{_text(row.get('name'))}</td>"
        f"<td class='num'>{_num(row.get('day_return_pct'), 4)}</td>"
        f"<td class='num'>{_num(row.get('sharpe'), 4)}</td>"
        f"<td class='num'>{_num(row.get('mdd_pct'), 4)}</td>"
        f"<td class='num'>{_num(row.get('fee_ratio_pct'), 4)}</td>"
        f"<td class='num'>{_num(row.get('score_j'), 6)}</td>"
        f"<td>{'通过' if row.get('hard_constraint_passed') else '拒绝'}</td>"
        f"<td>{_text(row.get('status'))}</td>"
        f"<td>{_text(row.get('risk_note'))}</td>"
        "</tr>"
        for row in rows[:80]
    )


def _render_log_lines(rows: list[dict[str, object]], message_key: str) -> str:
    if not rows:
        return "暂无记录"
    return "\n".join(
        f"[{_ts(row.get('timestamp'))}] {_text(row.get('event_type') or row.get('operator') or 'event')} | {_text(row.get(message_key))}"
        for row in rows
    )


def _render_audit(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "暂无审计事件"
    return "\n".join(
        f"[{_ts(row.get('created_at'))}] {_text(row.get('category'))} | {_text(row.get('actor'))} | {_text(row.get('message'))} | {_text(json.dumps(row.get('detail') or {}, ensure_ascii=False))}"
        for row in rows[:120]
    )


def _render_reports(payload: dict[str, object]) -> str:
    hourly = _lines(payload.get("hourly"))[:20]
    daily = _lines(payload.get("daily"))[:10]
    weekly = _lines(payload.get("weekly"))[:6]
    lines = ["=== 小时报告 ===", *hourly, "", "=== 日报告 ===", *daily, "", "=== 周报告 ===", *weekly]
    return "\n".join(lines).strip() or "暂无报告"


def _render_reliability(payload: dict[str, object]) -> str:
    if not payload:
        return "暂无可靠性信息"
    lines = [
        f"幂等缓存: {payload.get('idempotency_cache_size', '--')}",
        f"重试次数: {payload.get('retry_count', '--')}",
        f"超时次数: {payload.get('timeout_count', '--')}",
        f"补偿次数: {payload.get('compensation_count', '--')}",
        f"上下文恢复次数: {payload.get('context_continuity_count', '--')}",
        "",
        "告警:",
        *_lines(payload.get("alarms"))[:15],
    ]
    return "\n".join(lines)


def render_dashboard(payload: dict[str, object] | None = None) -> str:
    payload = payload or {}
    system = _mapping(payload.get("system"))
    ai_usage = _mapping(payload.get("ai_usage"))
    governance = _mapping(payload.get("governance_config"))
    risk = _mapping(governance.get("risk"))
    release = _mapping(payload.get("release_state"))
    positions = _rows(payload.get("positions"))
    trades = _rows(payload.get("trades"))
    tasks = _rows(payload.get("ai_tasks"))
    approvals = _rows(payload.get("approvals"))
    candidates = _rows(payload.get("candidates"))
    memory = _rows(payload.get("memory"))
    commands = _rows(payload.get("commands"))
    audit_events = _rows(payload.get("audit_events"))
    reports = _mapping(payload.get("reports"))
    reliability = _mapping(payload.get("reliability"))
    human_version = _mapping(payload.get("human_version"))
    ai_version = _mapping(payload.get("ai_version"))
    runtime_logs = _lines(payload.get("runtime_logs"))[:200]
    bootstrap_json = json.dumps(payload, ensure_ascii=False).replace("</script>", "<\\/script>")

    return f"""
<!DOCTYPE html>
<html lang='zh-CN'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>AI治理控制台</title>
  <style>{STYLE}</style>
</head>
<body>
  <div class='shell'>
    <section class='grid'>
      <div class='panel span-8'>
        <h1 class='headline'>AI治理 + 人类最高权限</h1>
        <p class='sub'>你可以在这里直接看到真实数据。即使浏览器脚本失败，刷新后也不会再是空白页。</p>
      </div>
      <div class='panel span-4'>
        <div class='cards'>
          <div class='card'><b>Token总消耗</b><span id='k-total-tokens'>{_num(ai_usage.get('total_tokens'), 0)}</span></div>
          <div class='card'><b>美元总成本</b><span id='k-total-cost'>${_num(ai_usage.get('total_cost_usd'), 4)}</span></div>
          <div class='card'><b>输入Token</b><span id='k-input-tokens'>{_num(ai_usage.get('input_tokens'), 0)}</span></div>
          <div class='card'><b>输出Token</b><span id='k-output-tokens'>{_num(ai_usage.get('output_tokens'), 0)}</span></div>
        </div>
      </div>
      <div class='panel span-12'>
        <div class='cards'>
          <div class='card'><b>净值</b><span id='m-equity'>{_num(system.get('equity'), 2)}</span></div>
          <div class='card'><b>现金余额</b><span id='m-cash'>{_num(system.get('cash'), 2)}</span></div>
          <div class='card'><b>保证金占用</b><span id='m-margin'>{_num(system.get('margin_used'), 2)}</span></div>
          <div class='card'><b>持仓市值</b><span id='m-position-value'>{_num(system.get('position_value'), 2)}</span></div>
          <div class='card'><b>累计手续费</b><span id='m-fee'>{_num(system.get('fees_paid'), 4)}</span></div>
          <div class='card'><b>已实现盈亏</b><span id='m-realized'>{_num(system.get('realized_pnl'), 4)}</span></div>
          <div class='card'><b>未实现盈亏</b><span id='m-unrealized'>{_num(system.get('unrealized_pnl'), 4)}</span></div>
          <div class='card'><b>总收益率</b><span id='m-ret'>{_num(system.get('total_return_pct'), 2, '%')}</span></div>
          <div class='card'><b>全程回撤</b><span id='m-dd'>{_num(system.get('drawdown_pct'), 2, '%')}</span></div>
          <div class='card'><b>当日回撤</b><span id='m-ddd'>{_num(system.get('daily_drawdown_pct'), 2, '%')}</span></div>
          <div class='card'><b>持仓数</b><span id='m-pos'>{_num(system.get('positions'), 0)}</span></div>
          <div class='card'><b>当前状态</b><span id='m-status'>{_text(system.get('status'))}</span></div>
        </div>
      </div>
      <div class='panel span-6'><h3 style='margin:0 0 8px'>人类总控</h3><div class='btns'><button class='btn warn' data-act='pause'>全面暂停</button><button class='btn' data-act='resume'>恢复自动交易</button><button class='btn danger' data-act='close'>全面平仓并暂停</button><button class='btn danger' data-act='halt'>全面停止</button><button class='btn danger' data-act='freeze'>全局停止自治</button><button class='btn warn' data-act='rollback'>一键回滚冠军</button></div><div id='action-result' class='status'>等待操作</div></div>
      <div class='panel span-6'><h3 style='margin:0 0 8px'>人类输入框</h3><textarea id='cmd' placeholder='输入你对 AI 的自然语言指令'></textarea><button id='send' class='btn' style='margin-top:8px'>提交指令</button><div id='cmd-result' class='status'>未提交</div></div>
      <div class='panel span-6'><h3 style='margin:0 0 8px'>结构化指令中心</h3><textarea id='scmd' placeholder='结构化指令描述'></textarea><div class='btns' style='margin-top:8px'><button class='btn' data-priority='low'>低优先级</button><button class='btn warn' data-priority='medium'>中优先级</button><button class='btn danger' data-priority='high'>高优先级</button></div><button id='send-structured' class='btn' style='margin-top:8px'>提交结构化指令</button><div id='scmd-result' class='status'>未提交</div></div>
      <div class='panel span-6'><h3 style='margin:0 0 8px'>自治总控与目标红线</h3><div class='kv'><b>自治等级</b><span id='g-level'>{_text(governance.get('autonomy_level'))}</span><b>结构性改动</b><span id='g-structural'>{_text(governance.get('allow_structural_changes'))}</span><b>夜间自治</b><span id='g-night'>{_text(governance.get('allow_night_autonomy'))}</span><b>日收益目标</b><span id='g-target'>{_num(governance.get('objective_daily_return_pct'), 2, '%')}</span><b>费用上限</b><span id='g-fee-limit'>{_num(governance.get('max_fee_ratio_pct'), 2, '%')}</span><b>全程回撤上限</b><span id='g-max-dd'>{_num(risk.get('max_drawdown_pct'), 2, '%')}</span><b>当日回撤上限</b><span id='g-max-dd-day'>{_num(risk.get('max_daily_drawdown_pct'), 2, '%')}</span><b>单笔亏损上限</b><span id='g-max-loss'>{_num(risk.get('max_trade_loss_pct'), 2, '%')}</span></div></div>
      <div class='panel span-6'><h3 style='margin:0 0 8px'>灰度发布中心</h3><div class='kv'><b>冠军版本</b><span id='r-champion'>{_text(release.get('champion_version'))}</span><b>挑战者版本</b><span id='r-challenger'>{_text(release.get('challenger_version'))}</span><b>灰度比例</b><span id='r-ratio'>{_num(release.get('gray_ratio_pct'), 2, '%')}</span><b>状态</b><span id='r-status'>{_text(release.get('status'))}</span><b>最近发布</b><span id='r-last-release'>{_ts(release.get('last_release_at'))}</span><b>最近回滚</b><span id='r-last-rollback'>{_ts(release.get('last_rollback_at'))}</span></div></div>
      <div class='panel span-6'><h3 style='margin:0 0 8px'>持仓明细</h3><div class='table-wrap'><table><thead><tr><th>标的</th><th>市场</th><th>方向</th><th>杠杆</th><th>数量</th><th>开仓价</th><th>现价</th><th>止损</th><th>止盈</th><th>浮盈亏</th></tr></thead><tbody id='positions-body'>{_render_positions(positions)}</tbody></table></div></div>
      <div class='panel span-6'><h3 style='margin:0 0 8px'>成交记录</h3><div class='table-wrap'><table><thead><tr><th>时间</th><th>标的</th><th>市场</th><th>方向</th><th>数量</th><th>价格</th><th>手续费</th><th>已实现</th><th>备注</th></tr></thead><tbody id='trades-body'>{_render_trades(trades)}</tbody></table></div></div>
      <div class='panel span-6'><h3 style='margin:0 0 8px'>AI正在做什么（点击标题展开详细步骤）</h3><div id='task-list' class='details-list'>{_render_tasks(tasks)}</div></div>
      <div class='panel span-6'><h3 style='margin:0 0 8px'>审批队列（高风险必须人工审批）</h3><div class='table-wrap'><table><thead><tr><th>ID</th><th>动作</th><th>原因</th><th>发起方</th><th>状态</th><th>操作</th></tr></thead><tbody id='approval-body'>{_render_approvals(approvals)}</tbody></table></div></div>
      <div class='panel span-12'><h3 style='margin:0 0 8px'>实验与回测中心（候选策略）</h3><div class='table-wrap'><table><thead><tr><th>ID</th><th>候选名</th><th>日收益%</th><th>Sharpe</th><th>MDD%</th><th>费率%</th><th>J评分</th><th>硬约束</th><th>状态</th><th>风险说明</th></tr></thead><tbody id='candidate-body'>{_render_candidates(candidates)}</tbody></table></div></div>
      <div class='panel span-6'><h3 style='margin:0 0 8px'>运行日志</h3><div id='runtime-log' class='log-box'>{escape(chr(10).join(runtime_logs)) or '暂无运行日志'}</div></div>
      <div class='panel span-6'><h3 style='margin:0 0 8px'>AI行为记忆</h3><div id='ai-log' class='log-box'>{escape(_render_log_lines(memory, 'message'))}</div></div>
      <div class='panel span-6'><h3 style='margin:0 0 8px'>人类命令历史</h3><div id='cmd-log' class='log-box'>{escape(_render_log_lines(commands, 'command'))}</div></div>
      <div class='panel span-6'><h3 style='margin:0 0 8px'>回滚与审计中心</h3><div id='audit-log' class='log-box'>{escape(_render_audit(audit_events))}</div></div>
      <div class='panel span-6'><h3 style='margin:0 0 8px'>日报/小时报告</h3><div id='report-log' class='log-box'>{escape(_render_reports(reports))}</div></div>
      <div class='panel span-6'><h3 style='margin:0 0 8px'>可靠性状态</h3><div id='reliability-log' class='log-box'>{escape(_render_reliability(reliability))}</div></div>
      <div class='panel span-12 footer'><a id='human-link' href='{_text(human_version.get('dashboard_url') or '#')}' target='_blank' rel='noopener'>人类版本: {_text(human_version.get('dashboard_url') or '#')}</a><span> | </span><a id='ai-link' href='{_text(ai_version.get('dashboard_url') or '#')}' target='_blank' rel='noopener'>AI版本: {_text(ai_version.get('dashboard_url') or '#')}</a><span id='status' style='margin-left:12px'>状态: {_text(system.get('status'))} | {_text(system.get('ai_message'))}</span></div>
    </section>
  </div>
  <script id='bootstrap-data' type='application/json'>{bootstrap_json}</script>
  <script>{SCRIPT}</script>
</body>
</html>
"""
