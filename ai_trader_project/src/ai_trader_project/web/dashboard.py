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
      --bg: #0b0f14;
      --panel: #131a23;
      --line: #2b3a4d;
      --text: #e5edf8;
      --muted: #89a0bc;
      --warn: #f0b90b;
      --danger: #ff6464;
      --ok: #2bc97f;
      --accent: #39a8ff;
      --mono: "JetBrains Mono", Consolas, monospace;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--text);
      font-family: "HarmonyOS Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
      background:
        radial-gradient(1000px 500px at -10% -20%, rgba(57,168,255,0.2), transparent 70%),
        radial-gradient(800px 420px at 110% -12%, rgba(240,185,11,0.16), transparent 65%),
        var(--bg);
      min-height: 100vh;
    }
    .shell { width: min(1460px, calc(100vw - 24px)); margin: 0 auto; padding: 18px 0 24px; }
    .grid { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 12px; }
    .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 14px; }
    .span-12 { grid-column: span 12; }
    .span-8 { grid-column: span 8; }
    .span-6 { grid-column: span 6; }
    .span-4 { grid-column: span 4; }
    h1 { margin: 0; font-size: clamp(28px, 2.8vw, 40px); }
    .sub { color: var(--muted); margin: 8px 0 0; }
    .metrics { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
    .metric { border: 1px solid var(--line); border-radius: 10px; padding: 10px; }
    .metric b { display: block; font-size: 12px; color: var(--muted); }
    .metric span { display: block; font-size: 28px; margin-top: 6px; font-family: var(--mono); }
    .controls { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
    .btn { border: 1px solid var(--line); border-radius: 10px; padding: 12px; background: #182233; color: var(--text); cursor: pointer; font-weight: 700; }
    .btn.warn { border-color: #7b6515; background: #2d2612; color: #ffd76b; }
    .btn.danger { border-color: #7b3333; background: #2c1717; color: #ff9d9d; }
    textarea { width: 100%; min-height: 120px; border-radius: 10px; border: 1px solid var(--line); background: #0d141d; color: var(--text); padding: 10px; font-family: var(--mono); }
    .log { height: 380px; overflow: auto; border: 1px solid var(--line); border-radius: 10px; background: #0d141d; padding: 10px; font-family: var(--mono); font-size: 12px; line-height: 1.5; }
    .entry { border-bottom: 1px dashed #25354b; padding: 8px 0; }
    .muted { color: var(--muted); }
    a { color: var(--accent); }
    @media (max-width: 960px) {
      .grid, .controls, .metrics { grid-template-columns: 1fr; }
      .span-12, .span-8, .span-6, .span-4 { grid-column: 1 / -1; }
    }
  </style>
</head>
<body>
  <div class='shell'>
    <section class='grid'>
      <div class='panel span-8'>
        <h1>AI治理 + 人类最高权限</h1>
        <p class='sub'>独立AI项目控制台。这里展示AI实时动作、记忆、人工命令与应急控制入口。</p>
      </div>
      <div class='panel span-4'>
        <div class='metrics'>
          <div class='metric'><b>净值</b><span id='m-equity'>--</span></div>
          <div class='metric'><b>全程回撤</b><span id='m-dd'>--</span></div>
          <div class='metric'><b>当日回撤</b><span id='m-ddd'>--</span></div>
          <div class='metric'><b>持仓数</b><span id='m-pos'>--</span></div>
        </div>
      </div>

      <div class='panel span-6'>
        <h3 style='margin:0 0 10px'>人类总控</h3>
        <div class='controls'>
          <button class='btn warn' data-act='pause'>全面暂停</button>
          <button class='btn' data-act='resume'>恢复自动交易</button>
          <button class='btn danger' data-act='close'>全面平仓并暂停</button>
          <button class='btn danger' data-act='halt'>全面停止</button>
        </div>
        <p id='action-result' class='muted'>等待操作</p>
      </div>

      <div class='panel span-6'>
        <h3 style='margin:0 0 10px'>人类输入框</h3>
        <textarea id='cmd' placeholder='输入给AI治理层的文字指令'></textarea>
        <button id='send' class='btn' style='margin-top:10px'>提交指令</button>
        <p id='cmd-result' class='muted'>未提交</p>
      </div>

      <div class='panel span-6'>
        <h3 style='margin:0 0 10px'>AI正在做什么</h3>
        <div class='log' id='ai-log'>加载中...</div>
      </div>
      <div class='panel span-6'>
        <h3 style='margin:0 0 10px'>人类命令历史</h3>
        <div class='log' id='cmd-log'>加载中...</div>
      </div>

      <div class='panel span-12'>
        <a id='human-link' target='_blank' rel='noopener'>人类版本</a>
        <span class='muted'> | </span>
        <a id='ai-link' target='_blank' rel='noopener'>AI版本</a>
        <span id='status' class='muted' style='margin-left:12px'>状态: --</span>
      </div>
    </section>
  </div>

  <script>
    function n(v, d=2){const x=Number(v);return Number.isFinite(x)?x.toFixed(d):'--'}
    function ts(v){if(!v)return'--'; const d=new Date(v); if(Number.isNaN(d.getTime())) return '--'; return d.toLocaleString('zh-CN',{hour12:false,timeZone:'Asia/Shanghai'})}
    function rows(data, keyMsg){
      if(!data||!data.length){return "<div class='entry muted'>暂无记录</div>"}
      return data.map(r=>"<div class='entry'><div><b>"+(r.event_type||r.operator||'event')+"</b> <span class='muted'>"+ts(r.timestamp)+"</span></div><div>"+(r[keyMsg]||'--')+"</div></div>").join('')
    }

    async function load(){
      const r = await fetch('/api/ai/governance',{cache:'no-store'});
      if(!r.ok) throw new Error('load failed');
      const p = await r.json();
      const s = p.system || {};
      document.getElementById('m-equity').textContent = n(s.equity,2);
      document.getElementById('m-dd').textContent = n(s.drawdown_pct,2)+'%';
      document.getElementById('m-ddd').textContent = n(s.daily_drawdown_pct,2)+'%';
      document.getElementById('m-pos').textContent = n(s.positions,0);
      document.getElementById('status').textContent = '状态: '+(s.status||'--')+' | '+(s.ai_message||'--');
      document.getElementById('ai-log').innerHTML = rows(p.memory,'message');
      document.getElementById('cmd-log').innerHTML = rows(p.commands,'command');
      const hu = p.human_version?.dashboard_url || '#';
      const au = p.ai_version?.dashboard_url || '#';
      const hl = document.getElementById('human-link');
      const al = document.getElementById('ai-link');
      hl.href = hu; hl.textContent = '人类版本: '+hu;
      al.href = au; al.textContent = 'AI版本: '+au;
    }

    async function act(name){
      const mp = {pause:'/api/actions/pause',resume:'/api/actions/resume',close:'/api/actions/emergency-close',halt:'/api/actions/halt'};
      const r = await fetch(mp[name],{method:'POST'});
      const d = await r.json();
      document.getElementById('action-result').textContent = (d.message||'完成')+' (状态: '+(d.status||'--')+')';
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
    load().catch(e=>{document.getElementById('ai-log').textContent='加载失败: '+String(e);document.getElementById('cmd-log').textContent='加载失败: '+String(e)});
    setInterval(()=>load().catch(()=>{}),5000);
  </script>
</body>
</html>
"""
