from __future__ import annotations


def render_dashboard() -> str:
    return """
<!DOCTYPE html>
<html lang='zh-CN'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>AI治理控制台</title>
  <style>
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
    .span-9 { grid-column: span 9; }
    .span-8 { grid-column: span 8; }
    .span-6 { grid-column: span 6; }
    .span-4 { grid-column: span 4; }
    .span-3 { grid-column: span 3; }
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
    .log-box { max-height: 290px; overflow: auto; border: 1px solid var(--line); border-radius: 10px; background: #0b1420; padding: 10px; font-family: var(--mono); font-size: 12px; line-height: 1.5; }
    .details-list { max-height: 420px; overflow: auto; display: grid; gap: 8px; }
    details { border: 1px solid var(--line); border-radius: 10px; background: #0b1420; padding: 8px 10px; }
    summary { cursor: pointer; font-weight: 700; color: #cfe1f7; }
    .detail-meta { color: var(--muted); font-size: 12px; margin-top: 6px; }
    .detail-steps { margin: 8px 0 0; padding-left: 16px; color: #c4d6ee; }
    .kv { display: grid; grid-template-columns: 1fr auto; gap: 6px 10px; font-size: 12px; }
    .kv b { color: var(--muted); font-weight: 600; }
    .kv span { font-family: var(--mono); }
    .tiny { font-size: 11px; color: var(--muted); }
    a { color: var(--accent); }
    .footer { color: var(--muted); font-size: 12px; }
    @media (max-width: 1040px) {
      .grid, .cards, .btns { grid-template-columns: 1fr; }
      .span-12, .span-9, .span-8, .span-6, .span-4, .span-3 { grid-column: 1 / -1; }
      table { min-width: 680px; }
    }
  </style>
</head>
<body>
  <div class='shell'>
    <section class='grid'>
      <div class='panel span-8'>
        <h1 class='headline'>AI治理 + 人类最高权限</h1>
        <p class='sub'>你可以在这里评估 AI 效果：净值、现金、保证金、持仓、成交、手续费、Token 与美元成本、运行日志和任务细节。</p>
      </div>
      <div class='panel span-4'>
        <div class='cards'>
          <div class='card'><b>Token总消耗</b><span id='k-total-tokens'>--</span></div>
          <div class='card'><b>美元总成本</b><span id='k-total-cost'>--</span></div>
          <div class='card'><b>输入Token</b><span id='k-input-tokens'>--</span></div>
          <div class='card'><b>输出Token</b><span id='k-output-tokens'>--</span></div>
        </div>
      </div>

      <div class='panel span-12'>
        <div class='cards'>
          <div class='card'><b>净值</b><span id='m-equity'>--</span></div>
          <div class='card'><b>现金余额</b><span id='m-cash'>--</span></div>
          <div class='card'><b>保证金占用</b><span id='m-margin'>--</span></div>
          <div class='card'><b>持仓市值</b><span id='m-position-value'>--</span></div>
          <div class='card'><b>累计手续费</b><span id='m-fee'>--</span></div>
          <div class='card'><b>已实现盈亏</b><span id='m-realized'>--</span></div>
          <div class='card'><b>未实现盈亏</b><span id='m-unrealized'>--</span></div>
          <div class='card'><b>总收益率</b><span id='m-ret'>--</span></div>
          <div class='card'><b>全程回撤</b><span id='m-dd'>--</span></div>
          <div class='card'><b>当日回撤</b><span id='m-ddd'>--</span></div>
          <div class='card'><b>持仓数</b><span id='m-pos'>--</span></div>
          <div class='card'><b>当前状态</b><span id='m-status'>--</span></div>
        </div>
      </div>

      <div class='panel span-6'>
        <h3 style='margin:0 0 8px'>人类总控</h3>
        <div class='btns'>
          <button class='btn warn' data-act='pause'>全面暂停</button>
          <button class='btn' data-act='resume'>恢复自动交易</button>
          <button class='btn danger' data-act='close'>全面平仓并暂停</button>
          <button class='btn danger' data-act='halt'>全面停止</button>
          <button class='btn danger' data-act='freeze'>全局停止自治</button>
          <button class='btn warn' data-act='rollback'>一键回滚冠军</button>
        </div>
        <div id='action-result' class='status'>等待操作</div>
      </div>

      <div class='panel span-6'>
        <h3 style='margin:0 0 8px'>人类输入框</h3>
        <textarea id='cmd' placeholder='输入你对 AI 的自然语言指令'></textarea>
        <button id='send' class='btn' style='margin-top:8px'>提交指令</button>
        <div id='cmd-result' class='status'>未提交</div>
      </div>

      <div class='panel span-6'>
        <h3 style='margin:0 0 8px'>自治总控与目标红线</h3>
        <div class='kv'>
          <b>自治等级</b><span id='g-level'>--</span>
          <b>结构性改动</b><span id='g-structural'>--</span>
          <b>夜间自治</b><span id='g-night'>--</span>
          <b>日收益目标</b><span id='g-target'>--</span>
          <b>费用上限</b><span id='g-fee-limit'>--</span>
          <b>全程回撤上限</b><span id='g-max-dd'>--</span>
          <b>当日回撤上限</b><span id='g-max-dd-day'>--</span>
          <b>单笔亏损上限</b><span id='g-max-loss'>--</span>
        </div>
      </div>

      <div class='panel span-6'>
        <h3 style='margin:0 0 8px'>灰度发布中心</h3>
        <div class='kv'>
          <b>冠军版本</b><span id='r-champion'>--</span>
          <b>挑战者版本</b><span id='r-challenger'>--</span>
          <b>灰度比例</b><span id='r-ratio'>--</span>
          <b>状态</b><span id='r-status'>--</span>
          <b>最近发布</b><span id='r-last-release'>--</span>
          <b>最近回滚</b><span id='r-last-rollback'>--</span>
        </div>
      </div>

      <div class='panel span-6'>
        <h3 style='margin:0 0 8px'>持仓明细</h3>
        <div class='table-wrap'>
          <table>
            <thead>
              <tr><th>标的</th><th>市场</th><th>方向</th><th>杠杆</th><th>数量</th><th>开仓价</th><th>现价</th><th>止损</th><th>止盈</th><th>浮盈亏</th></tr>
            </thead>
            <tbody id='positions-body'><tr><td colspan='10'>加载中...</td></tr></tbody>
          </table>
        </div>
      </div>

      <div class='panel span-6'>
        <h3 style='margin:0 0 8px'>成交记录</h3>
        <div class='table-wrap'>
          <table>
            <thead>
              <tr><th>时间</th><th>标的</th><th>市场</th><th>方向</th><th>数量</th><th>价格</th><th>手续费</th><th>已实现</th><th>备注</th></tr>
            </thead>
            <tbody id='trades-body'><tr><td colspan='9'>加载中...</td></tr></tbody>
          </table>
        </div>
      </div>

      <div class='panel span-6'>
        <h3 style='margin:0 0 8px'>AI正在做什么（点击标题展开详细步骤）</h3>
        <div id='task-list' class='details-list'><div class='status'>加载中...</div></div>
      </div>

      <div class='panel span-6'>
        <h3 style='margin:0 0 8px'>审批队列（高风险必须人工审批）</h3>
        <div class='table-wrap'>
          <table>
            <thead><tr><th>ID</th><th>动作</th><th>原因</th><th>发起方</th><th>状态</th><th>操作</th></tr></thead>
            <tbody id='approval-body'><tr><td colspan='6'>暂无审批</td></tr></tbody>
          </table>
        </div>
      </div>

      <div class='panel span-12'>
        <h3 style='margin:0 0 8px'>实验与回测中心（候选策略）</h3>
        <div class='table-wrap'>
          <table>
            <thead><tr><th>ID</th><th>候选名</th><th>日收益%</th><th>Sharpe</th><th>MDD%</th><th>费率%</th><th>J评分</th><th>硬约束</th><th>状态</th><th>风险说明</th></tr></thead>
            <tbody id='candidate-body'><tr><td colspan='10'>暂无候选策略</td></tr></tbody>
          </table>
        </div>
      </div>

      <div class='panel span-6'>
        <h3 style='margin:0 0 8px'>运行日志</h3>
        <div id='runtime-log' class='log-box'>加载中...</div>
      </div>

      <div class='panel span-6'>
        <h3 style='margin:0 0 8px'>AI行为记忆</h3>
        <div id='ai-log' class='log-box'>加载中...</div>
      </div>

      <div class='panel span-6'>
        <h3 style='margin:0 0 8px'>人类命令历史</h3>
        <div id='cmd-log' class='log-box'>加载中...</div>
      </div>

      <div class='panel span-6'>
        <h3 style='margin:0 0 8px'>回滚与审计中心</h3>
        <div id='audit-log' class='log-box'>加载中...</div>
      </div>

      <div class='panel span-6'>
        <h3 style='margin:0 0 8px'>日报/小时报告</h3>
        <div id='report-log' class='log-box'>加载中...</div>
      </div>

      <div class='panel span-12 footer'>
        <a id='human-link' target='_blank' rel='noopener'>人类版本</a>
        <span> | </span>
        <a id='ai-link' target='_blank' rel='noopener'>AI版本</a>
        <span id='status' style='margin-left:12px'>状态: --</span>
      </div>
    </section>
  </div>

  <script>
    function n(v, d=2){const x=Number(v);return Number.isFinite(x)?x.toFixed(d):'--'}
    function ts(v){if(!v)return'--'; const d=new Date(v); if(Number.isNaN(d.getTime())) return '--'; return d.toLocaleString('zh-CN',{hour12:false,timeZone:'Asia/Shanghai'})}
    function cls(v){const x=Number(v);if(!Number.isFinite(x))return ''; if(x>0)return 'pos'; if(x<0)return 'neg'; return ''}

    function renderLogRows(data, key){
      if(!data||!data.length){return '暂无记录';}
      return data.map(r=>{
        const title = r.event_type || r.operator || 'event';
        const msg = r[key] || '--';
        return '['+ts(r.timestamp)+'] '+title+' | '+msg;
      }).join('\n');
    }

    function renderPositions(rows){
      const body = document.getElementById('positions-body');
      if(!rows||!rows.length){body.innerHTML = "<tr><td colspan='10'>当前无持仓</td></tr>"; return;}
      body.innerHTML = rows.map(r=>"<tr><td>"+r.symbol+"</td><td>"+r.market_type+"</td><td>"+r.side+"</td><td>"+r.leverage+"x</td><td class='num'>"+n(r.quantity,6)+"</td><td class='num'>"+n(r.entry_price,4)+"</td><td class='num'>"+n(r.current_price,4)+"</td><td class='num'>"+n(r.stop_loss,4)+"</td><td class='num'>"+n(r.take_profit,4)+"</td><td class='num "+cls(r.unrealized_pnl)+"'>"+n(r.unrealized_pnl,4)+"</td></tr>").join('');
    }

    function renderTrades(rows){
      const body = document.getElementById('trades-body');
      if(!rows||!rows.length){body.innerHTML = "<tr><td colspan='9'>暂无成交记录</td></tr>"; return;}
      body.innerHTML = rows.map(r=>"<tr><td>"+ts(r.created_at)+"</td><td>"+r.symbol+"</td><td>"+r.market_type+"</td><td>"+r.side+"</td><td class='num'>"+n(r.quantity,6)+"</td><td class='num'>"+n(r.price,4)+"</td><td class='num'>"+n(r.fee_paid,4)+"</td><td class='num "+cls(r.realized_pnl)+"'>"+n(r.realized_pnl,4)+"</td><td>"+(r.note||'')+"</td></tr>").join('');
    }

    function renderTasks(tasks){
      const box = document.getElementById('task-list');
      if(!tasks||!tasks.length){box.innerHTML = "<div class='status'>暂无任务细节</div>"; return;}
      box.innerHTML = tasks.map(t=>{
        const steps = (t.steps||[]).map(s=>"<li>"+s+"</li>").join('');
        return "<details><summary>"+t.title+" | "+(t.status||'--')+" | "+ts(t.created_at)+"</summary><div class='detail-meta'>摘要："+(t.summary||'--')+"</div><ul class='detail-steps'>"+steps+"</ul></details>";
      }).join('');
    }

    function renderApprovals(rows){
      const body = document.getElementById('approval-body');
      if(!rows||!rows.length){body.innerHTML="<tr><td colspan='6'>暂无审批</td></tr>"; return;}
      body.innerHTML = rows.map(r=>{
        const buttons = r.status==='pending'
          ? "<button class='btn' style='padding:6px 8px' onclick=\"decideApproval('"+r.id+"','approve')\">通过</button> <button class='btn danger' style='padding:6px 8px' onclick=\"decideApproval('"+r.id+"','reject')\">拒绝</button>"
          : "-";
        return "<tr><td>"+r.id+"</td><td>"+r.action+"</td><td>"+r.reason+"</td><td>"+r.requested_by+"</td><td>"+r.status+"</td><td>"+buttons+"</td></tr>";
      }).join('');
    }

    function renderCandidates(rows){
      const body = document.getElementById('candidate-body');
      if(!rows||!rows.length){body.innerHTML="<tr><td colspan='10'>暂无候选策略</td></tr>"; return;}
      body.innerHTML = rows.map(r=>"<tr><td>"+r.id+"</td><td>"+r.name+"</td><td class='num'>"+n(r.day_return_pct,4)+"</td><td class='num'>"+n(r.sharpe,4)+"</td><td class='num'>"+n(r.mdd_pct,4)+"</td><td class='num'>"+n(r.fee_ratio_pct,4)+"</td><td class='num'>"+n(r.score_j,6)+"</td><td>"+(r.hard_constraint_passed?'通过':'拒绝')+"</td><td>"+r.status+"</td><td>"+r.risk_note+"</td></tr>").join('');
    }

    function renderAudit(rows){
      if(!rows||!rows.length){return '暂无审计事件';}
      return rows.map(r=>"["+ts(r.created_at)+"] "+r.category+" | "+r.actor+" | "+r.message+" | "+JSON.stringify(r.detail||{})).join('\n');
    }

    function renderReports(payload){
      const hourly = payload?.hourly || [];
      const daily = payload?.daily || [];
      const lines = [];
      lines.push('=== 小时报告 ===');
      lines.push(...hourly.slice(0,20));
      lines.push('');
      lines.push('=== 日报告 ===');
      lines.push(...daily.slice(0,10));
      return lines.join('\n') || '暂无报告';
    }

    async function load(){
      const r = await fetch('/api/ai/governance',{cache:'no-store'});
      if(!r.ok) throw new Error('load failed');
      const p = await r.json();
      const s = p.system || {};
      const u = p.ai_usage || {};
      const g = p.governance_config || {};
      const risk = g.risk || {};
      const release = p.release_state || {};

      document.getElementById('k-total-tokens').textContent = n(u.total_tokens,0);
      document.getElementById('k-total-cost').textContent = '$'+n(u.total_cost_usd,4);
      document.getElementById('k-input-tokens').textContent = n(u.input_tokens,0);
      document.getElementById('k-output-tokens').textContent = n(u.output_tokens,0);

      document.getElementById('m-equity').textContent = n(s.equity,2);
      document.getElementById('m-cash').textContent = n(s.cash,2);
      document.getElementById('m-margin').textContent = n(s.margin_used,2);
      document.getElementById('m-position-value').textContent = n(s.position_value,2);
      document.getElementById('m-fee').textContent = n(s.fees_paid,4);
      document.getElementById('m-realized').textContent = n(s.realized_pnl,4);
      document.getElementById('m-unrealized').textContent = n(s.unrealized_pnl,4);
      document.getElementById('m-ret').textContent = n(s.total_return_pct,2)+'%';
      document.getElementById('m-dd').textContent = n(s.drawdown_pct,2)+'%';
      document.getElementById('m-ddd').textContent = n(s.daily_drawdown_pct,2)+'%';
      document.getElementById('m-pos').textContent = n(s.positions,0);
      document.getElementById('m-status').textContent = s.status || '--';
      document.getElementById('status').textContent = '状态: '+(s.status||'--')+' | '+(s.ai_message||'--');

      document.getElementById('g-level').textContent = g.autonomy_level || '--';
      document.getElementById('g-structural').textContent = String(g.allow_structural_changes);
      document.getElementById('g-night').textContent = String(g.allow_night_autonomy);
      document.getElementById('g-target').textContent = n(g.objective_daily_return_pct,2)+'%';
      document.getElementById('g-fee-limit').textContent = n(g.max_fee_ratio_pct,2)+'%';
      document.getElementById('g-max-dd').textContent = n(risk.max_drawdown_pct,2)+'%';
      document.getElementById('g-max-dd-day').textContent = n(risk.max_daily_drawdown_pct,2)+'%';
      document.getElementById('g-max-loss').textContent = n(risk.max_trade_loss_pct,2)+'%';

      document.getElementById('r-champion').textContent = release.champion_version || '--';
      document.getElementById('r-challenger').textContent = release.challenger_version || '--';
      document.getElementById('r-ratio').textContent = n(release.gray_ratio_pct,2)+'%';
      document.getElementById('r-status').textContent = release.status || '--';
      document.getElementById('r-last-release').textContent = ts(release.last_release_at);
      document.getElementById('r-last-rollback').textContent = ts(release.last_rollback_at);

      renderPositions(p.positions || []);
      renderTrades(p.trades || []);
      renderTasks(p.ai_tasks || []);
      renderApprovals(p.approvals || []);
      renderCandidates(p.candidates || []);

      const runtimeLogs = (p.runtime_logs || []).join('\n');
      document.getElementById('runtime-log').textContent = runtimeLogs || '暂无运行日志';
      document.getElementById('ai-log').textContent = renderLogRows(p.memory || [], 'message');
      document.getElementById('cmd-log').textContent = renderLogRows(p.commands || [], 'command');
      document.getElementById('audit-log').textContent = renderAudit(p.audit_events || []);
      document.getElementById('report-log').textContent = renderReports(p.reports || {});

      const hu = p.human_version?.dashboard_url || '#';
      const au = p.ai_version?.dashboard_url || '#';
      const hl = document.getElementById('human-link');
      const al = document.getElementById('ai-link');
      hl.href = hu; hl.textContent = '人类版本: '+hu;
      al.href = au; al.textContent = 'AI版本: '+au;
    }

    async function act(name){
      const mp = {
        pause:'/api/actions/pause',
        resume:'/api/actions/resume',
        close:'/api/actions/emergency-close',
        halt:'/api/actions/halt',
        freeze:'/api/actions/freeze-autonomy',
        rollback:'/api/actions/rollback'
      };
      const r = await fetch(mp[name],{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({operator:'human',role:'human_root'})});
      const d = await r.json();
      document.getElementById('action-result').textContent = (d.message||'完成')+' (状态: '+(d.status||'--')+')';
      await load();
    }

    async function decideApproval(id, decision){
      const r = await fetch('/api/governance/approvals/'+id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({operator:'human',role:'human_root',decision})});
      const d = await r.json();
      document.getElementById('action-result').textContent = '审批结果: '+(d.status||'--');
      await load();
    }

    async function sendCmd(){
      const val = document.getElementById('cmd').value.trim();
      if(!val){document.getElementById('cmd-result').textContent='请输入内容';return;}
      const r = await fetch('/api/ai/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command:val,operator:'human'})});
      const d = await r.json();
      document.getElementById('cmd-result').textContent = d.message || '已提交';
      document.getElementById('cmd').value='';
      await load();
    }

    document.querySelectorAll('[data-act]').forEach(b=>b.addEventListener('click',()=>act(b.dataset.act).catch(e=>document.getElementById('action-result').textContent='失败: '+String(e))));
    document.getElementById('send').addEventListener('click',()=>sendCmd().catch(e=>document.getElementById('cmd-result').textContent='失败: '+String(e)));
    load().catch(e=>{document.getElementById('runtime-log').textContent='加载失败: '+String(e);});
    setInterval(()=>load().catch(()=>{}),5000);
  </script>
</body>
</html>
"""
