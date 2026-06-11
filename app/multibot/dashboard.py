HTML = r'''<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MT5 Multi-Bot Dashboard</title>
<style>
:root{color-scheme:dark;--bg:#0e1116;--card:#171d24;--line:#28323d;--muted:#9aa7b3;--ok:#86efac;--bad:#fca5a5;--warn:#fde68a;--accent:#60a5fa}
*{box-sizing:border-box}body{font-family:Arial,sans-serif;background:var(--bg);color:#e8edf2;margin:0;padding:20px}h1,h2,h3{margin:0 0 10px}.muted{color:var(--muted)}.small{font-size:12px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:16px 0}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}.value{font-size:24px;font-weight:700}.ok{color:var(--ok)}.bad{color:var(--bad)}.warn{color:var(--warn)}.accent{color:var(--accent)}table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:9px;border-bottom:1px solid #293440;text-align:left;vertical-align:top}th{color:#cbd5e1;background:#141a21;position:sticky;top:0}button,select{border:1px solid #334155;border-radius:8px;padding:8px 10px;cursor:pointer;background:#1f2937;color:#fff}button.primary{background:#2563eb}button.danger{background:#b91c1c}.section{margin-top:16px}.toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.pill{padding:3px 8px;border-radius:999px;background:#293440;font-size:12px}.tabs button.active{background:#2563eb}.hidden{display:none}.table-wrap{overflow:auto;max-height:560px}.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}.kpi{background:#10161d;border:1px solid #26313d;border-radius:10px;padding:12px}.kpi .label{color:var(--muted);font-size:12px}.kpi .num{font-size:22px;font-weight:700;margin-top:5px}.section-title{display:flex;justify-content:space-between;gap:8px;align-items:center;flex-wrap:wrap}.badge{display:inline-block;padding:2px 7px;border-radius:999px;font-size:11px;background:#27313c}.baseline{background:#1e3a5f}.delta{font-weight:700}.delta.up{color:var(--ok)}.delta.down{color:var(--bad)}.delta.flat{color:var(--muted)}pre{white-space:pre-wrap;max-height:320px;overflow:auto;background:#0b0f14;padding:10px;border-radius:8px}.empty{text-align:center;color:var(--muted);padding:18px}.note{border-left:3px solid #3b82f6;padding-left:10px;color:#cbd5e1}.nowrap{white-space:nowrap}
</style>
</head>
<body>
<h1>MT5 Multi-Bot Dashboard <span class="pill">v1.2.2</span></h1>
<div class="muted">ดูราคาทองสด เปรียบเทียบบอทกับ baseline และตรวจประวัติการเทรดรายไม้ในหน้าเดียว</div>

<div class="grid">
 <div class="card"><div class="muted">Runtime</div><div id="runtime" class="value">...</div></div>
 <div class="card"><div class="muted">WebSocket</div><div id="ws" class="value">connecting</div></div>
 <div class="card"><div class="muted">Sender</div><div id="sender" class="value">...</div><div id="tickAge" class="muted small">-</div></div>
 <div class="card"><div class="muted">XAUUSD Bid</div><div id="bid" class="value">-</div></div>
 <div class="card"><div class="muted">XAUUSD Ask</div><div id="ask" class="value">-</div></div>
 <div class="card"><div class="muted">Spread</div><div id="spread" class="value">-</div></div>
 <div class="card"><div class="muted">Bots</div><div id="botCount" class="value">0</div></div>
 <div class="card"><div class="muted">Total Balance</div><div id="balance" class="value">0.00</div></div>
 <div class="card"><div class="muted">Total PnL</div><div id="pnl" class="value">0.00</div></div>
</div>

<div class="tabs toolbar">
 <button class="active" onclick="show('overview',this)">ภาพรวม</button>
 <button onclick="show('compare',this)">เทียบ Baseline</button>
 <button onclick="show('trades',this)">ประวัติการเทรด</button>
 <button onclick="show('signals',this)">Signal Logs</button>
 <button onclick="show('bots',this)">จัดการ Bots</button>
 <button onclick="show('profiles',this)">Profiles</button>
</div>

<div id="overview" class="section card">
 <div class="section-title"><h2>ภาพรวมผลลัพธ์</h2><div class="muted small">Baseline ใช้เป็นตัวอ้างอิงหลัก</div></div>
 <div id="baselineSummary" class="kpi-grid"></div>
 <div class="note section">คำตอบที่ควรดู: Bot ไหนเข้าเทรดน้อยลง, Win rate ดีขึ้น, Drawdown ลดลง และกำไรรวมดีกว่า baseline หรือไม่</div>
 <div class="table-wrap section"><table><thead><tr><th>Bot</th><th>สถานะ</th><th>Balance</th><th>Net PnL</th><th>จำนวนไม้</th><th>ชนะ</th><th>Win rate</th><th>Max DD</th><th>Pending</th><th>Open</th></tr></thead><tbody id="overviewRows"></tbody></table></div>
</div>

<div id="compare" class="section card hidden">
 <div class="section-title"><h2>เปรียบเทียบกับ trend-ob-baseline</h2><button onclick="load()">Refresh</button></div>
 <div class="table-wrap"><table><thead><tr><th>Bot</th><th>Trades</th><th>เทียบจำนวนไม้</th><th>Win rate</th><th>เทียบ Win rate</th><th>Max DD</th><th>เทียบ DD</th><th>Net PnL</th><th>เทียบกำไร</th></tr></thead><tbody id="compareRows"></tbody></table></div>
</div>

<div id="trades" class="section card hidden">
 <div class="section-title"><h2>ประวัติการเทรดรายไม้</h2><div class="toolbar"><select id="tradeBotSelect" onchange="loadTrades()"></select><button onclick="loadTrades()">Refresh</button></div></div>
 <div id="tradeStatus" class="section note">กำลังโหลดสถานะ...</div>
 <div id="tradeSummary" class="kpi-grid section"></div>
 <div class="table-wrap section"><table><thead><tr><th>ID</th><th>เวลาเปิด</th><th>เวลาออก</th><th>Side</th><th>Lot</th><th>Entry</th><th>SL</th><th>TP</th><th>Exit</th><th>PnL</th><th>R</th><th>สถานะ</th><th>เหตุผลปิด</th></tr></thead><tbody id="tradeRows"></tbody></table></div>
</div>

<div id="signals" class="section card hidden">
 <div class="section-title"><h2>Signal Logs</h2><div class="toolbar"><select id="signalBotSelect" onchange="loadSignals()"></select><button onclick="loadSignals()">Refresh</button></div></div>
 <div class="table-wrap"><table><thead><tr><th>เวลา</th><th>Event</th><th>Message</th><th>Payload</th></tr></thead><tbody id="signalRows"></tbody></table></div>
</div>

<div id="bots" class="section card hidden">
 <h2>จัดการ Bots</h2>
 <div class="table-wrap"><table><thead><tr><th>ID</th><th>Profile</th><th>Bot</th><th>Strategy</th><th>Enabled</th><th>Trend</th><th>Balance</th><th>PnL</th><th>Pending</th><th>Position</th><th>Action</th></tr></thead><tbody id="botRows"></tbody></table></div>
</div>

<div id="profiles" class="section card hidden">
 <h2>Profiles</h2>
 <div class="table-wrap"><table><thead><tr><th>ID</th><th>Name</th><th>Enabled</th><th>Bots</th><th>Balance</th><th>PnL</th></tr></thead><tbody id="profileRows"></tbody></table></div>
</div>

<script>
let bots=[], compares=[], profiles=[], socket, heartbeat;
async function j(url,opts){const r=await fetch(url,opts);if(!r.ok)throw new Error(await r.text());return await r.json()}
function n(v,d=2){return Number(v||0).toFixed(d)}
function pct(v){return `${n(v,2)}%`}
function cls(v){return Number(v)>=0?'ok':'bad'}
function dt(ts){if(!ts)return '-';return new Date(Number(ts)*1000).toLocaleString('th-TH',{hour12:false})}
function delta(v,base,inverse=false,suffix=''){const d=Number(v||0)-Number(base||0);const good=inverse?d<0:d>0;const bad=inverse?d>0:d<0;const c=good?'up':bad?'down':'flat';const sign=d>0?'+':'';return `<span class="delta ${c}">${sign}${n(d,2)}${suffix}</span>`}
function baseline(){return compares.find(x=>x.name==='trend-ob-baseline')||compares[0]||{closed_trades:0,win_rate:0,max_drawdown:0,net_pnl:0,balance:0,wins:0}}
function isBaseline(x){return x.name==='trend-ob-baseline'}
function badge(x){return isBaseline(x)?'<span class="badge baseline">baseline</span>':''}
function empty(cols,text='ยังไม่มีข้อมูล'){return `<tr><td colspan="${cols}" class="empty">${text}</td></tr>`}
function show(id,btn){document.querySelectorAll('.section').forEach(x=>x.classList.add('hidden'));document.getElementById(id).classList.remove('hidden');document.querySelectorAll('.tabs button').forEach(x=>x.classList.remove('active'));btn.classList.add('active');if(id==='trades')loadTrades();if(id==='signals')loadSignals()}
async function toggle(id,on){await j(`/api/bots/${id}/${on?'disable':'enable'}`,{method:'POST'});await load()}
function updateSelect(id){const el=document.getElementById(id),cur=el.value;el.innerHTML=bots.map(x=>`<option value="${x.id}">${x.name}</option>`).join('');if(cur&&bots.some(x=>String(x.id)===String(cur)))el.value=cur}
async function load(){
 const [r,p,b,c,s]=await Promise.all([j('/api/multibot/runtime/status'),j('/api/profiles'),j('/api/bots'),j('/api/compare'),j('/api/state')]);
 profiles=p;bots=b;compares=c;const h=s.health||{},t=s.latest_tick||{};
 runtime.textContent=r.running?'RUNNING':'IDLE';runtime.className='value '+(r.running?'ok':'warn');sender.textContent=h.sender_online?'ONLINE':'OFFLINE';sender.className='value '+(h.sender_online?'ok':'bad');tickAge.textContent=h.seconds_since_last_message==null?'ยังไม่มี Tick':`ล่าสุด ${h.seconds_since_last_message}s ก่อน`;bid.textContent=t.bid==null?'-':n(t.bid);ask.textContent=t.ask==null?'-':n(t.ask);spread.textContent=t.spread==null?'-':n(t.spread,3);botCount.textContent=b.length;balance.textContent=n(c.reduce((a,x)=>a+Number(x.balance||0),0));pnl.textContent=n(c.reduce((a,x)=>a+Number(x.net_pnl||0),0));
 const base=baseline();baselineSummary.innerHTML=[['Baseline trades',base.closed_trades],['Baseline wins',base.wins],['Baseline win rate',pct(base.win_rate)],['Baseline max DD',pct(Number(base.max_drawdown||0)*100)],['Baseline net PnL',n(base.net_pnl)],['Baseline balance',n(base.balance)]].map(x=>`<div class="kpi"><div class="label">${x[0]}</div><div class="num">${x[1]}</div></div>`).join('');
 overviewRows.innerHTML=c.length?c.map(x=>`<tr><td>${x.name} ${badge(x)}</td><td>${bots.find(b=>b.id===x.bot_id)?.enabled?'ON':'OFF'}</td><td>${n(x.balance)}</td><td class="${cls(x.net_pnl)}">${n(x.net_pnl)}</td><td>${x.closed_trades}</td><td>${x.wins}</td><td>${pct(x.win_rate)}</td><td>${pct(Number(x.max_drawdown||0)*100)}</td><td>${x.pending_orders}</td><td>${x.open_positions}</td></tr>`).join(''):empty(10);
 compareRows.innerHTML=c.length?c.map(x=>`<tr><td>${x.name} ${badge(x)}</td><td>${x.closed_trades}</td><td>${isBaseline(x)?'-':delta(x.closed_trades,base.closed_trades,false,'')}</td><td>${pct(x.win_rate)}</td><td>${isBaseline(x)?'-':delta(x.win_rate,base.win_rate,false,'%')}</td><td>${pct(Number(x.max_drawdown||0)*100)}</td><td>${isBaseline(x)?'-':delta(Number(x.max_drawdown||0)*100,Number(base.max_drawdown||0)*100,true,'%')}</td><td class="${cls(x.net_pnl)}">${n(x.net_pnl)}</td><td>${isBaseline(x)?'-':delta(x.net_pnl,base.net_pnl,false)}</td></tr>`).join(''):empty(9);
 profileRows.innerHTML=p.length?p.map(x=>`<tr><td>${x.id}</td><td>${x.name}</td><td>${x.enabled?'ON':'OFF'}</td><td>${x.bot_count}</td><td>${n(x.total_balance)}</td><td class="${cls(x.total_realized_pnl)}">${n(x.total_realized_pnl)}</td></tr>`).join(''):empty(6);
 botRows.innerHTML=b.length?b.map(x=>`<tr><td>${x.id}</td><td>${x.profile_name}</td><td>${x.name}</td><td>${x.strategy_type} ${x.strategy_version}</td><td>${x.enabled?'ON':'OFF'}</td><td>${x.latest_trend||'-'}</td><td>${n(x.balance)}</td><td class="${cls(x.realized_pnl)}">${n(x.realized_pnl)}</td><td>${x.pending_count}</td><td>${x.open_position_count}</td><td><button onclick="toggle(${x.id},${x.enabled})">${x.enabled?'Disable':'Enable'}</button></td></tr>`).join(''):empty(11);
 updateSelect('tradeBotSelect');updateSelect('signalBotSelect');
}
async function loadTrades(){const id=tradeBotSelect.value;if(!id)return;const rows=await j(`/api/bots/${id}/trades?limit=200`);const stat=compares.find(x=>String(x.bot_id)===String(id))||{};const bot=bots.find(x=>String(x.id)===String(id))||{};tradeSummary.innerHTML=[['จำนวนไม้',stat.closed_trades||0],['ชนะ',stat.wins||0],['Win rate',pct(stat.win_rate||0)],['Max DD',pct(Number(stat.max_drawdown||0)*100)],['Net PnL',n(stat.net_pnl||0)],['Balance',n(stat.balance||0)]].map(x=>`<div class="kpi"><div class="label">${x[0]}</div><div class="num">${x[1]}</div></div>`).join('');if(rows.length){tradeStatus.className='section note';tradeStatus.textContent=`แสดงประวัติการเทรด ${rows.length} รายการล่าสุดของ ${bot.name||'Bot นี้'}`;}else if(Number(bot.open_position_count||0)>0){tradeStatus.className='section note warn';tradeStatus.textContent='กำลังถือ Position อยู่ — เมื่อปิดด้วย TP, SL หรือเงื่อนไขออก รายการจะปรากฏในตารางนี้';}else if(Number(bot.pending_count||0)>0){tradeStatus.className='section note warn';tradeStatus.textContent='กำลังรอราคาเข้า Entry — ยังไม่มีประวัติรายไม้จนกว่า Pending จะถูก Fill และ Position ถูกปิด';}else if(bot.enabled){tradeStatus.className='section note';tradeStatus.textContent='Bot เปิดใช้งานอยู่ แต่ยังไม่มีประวัติการเทรด — ระบบกำลังรอ Strong OB, Trend และราคา Retest ให้ครบเงื่อนไข';}else{tradeStatus.className='section note';tradeStatus.textContent='Bot ยังปิดอยู่ และยังไม่มีประวัติการเทรด — เปิด Bot ก่อนเพื่อเริ่มเก็บผล';}tradeRows.innerHTML=rows.length?rows.map(x=>`<tr><td>${x.id}</td><td class="nowrap">${dt(x.opened_at)}</td><td class="nowrap">${dt(x.closed_at)}</td><td>${String(x.side||'').toUpperCase()}</td><td>${n(x.lot,2)}</td><td>${n(x.entry)}</td><td>${x.stop_loss==null?'-':n(x.stop_loss)}</td><td>${x.take_profit==null?'-':n(x.take_profit)}</td><td>${x.exit_price==null?'-':n(x.exit_price)}</td><td class="${cls(x.pnl)}">${x.pnl==null?'-':n(x.pnl)}</td><td>${x.r_multiple==null?'-':n(x.r_multiple)+'R'}</td><td>${x.status}</td><td>${x.exit_reason||'-'}</td></tr>`).join(''):empty(13,'ยังไม่มีประวัติการเทรดรายไม้สำหรับ Bot นี้')}
async function loadSignals(){const id=signalBotSelect.value;if(!id)return;const rows=await j(`/api/bots/${id}/signals?limit=200`);signalRows.innerHTML=rows.length?rows.map(x=>`<tr><td class="nowrap">${dt(x.created_at)}</td><td>${x.event_type}</td><td>${x.message}</td><td><pre>${x.payload_json||'-'}</pre></td></tr>`).join(''):empty(4,'Bot นี้ยังไม่มี Signal Logs')}
function connect(){socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws/multibot`);socket.onopen=()=>{ws.textContent='CONNECTED';ws.className='value ok';heartbeat=setInterval(()=>socket.readyState===1&&socket.send('ping'),10000)};socket.onmessage=()=>load();socket.onclose=()=>{ws.textContent='RECONNECTING';ws.className='value warn';clearInterval(heartbeat);setTimeout(connect,1500)};socket.onerror=()=>socket.close()}
load();setInterval(load,5000);connect();
</script>
</body></html>'''
