HTML = r'''<!doctype html>
<html lang="th"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MT5 Multi-Bot Dashboard</title>
<style>
:root{color-scheme:dark}body{font-family:Arial,sans-serif;background:#0e1116;color:#e8edf2;margin:0;padding:20px}h1{margin:0 0 6px}.muted{color:#9aa7b3}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:16px 0}.card{background:#171d24;border:1px solid #28323d;border-radius:12px;padding:14px}.value{font-size:24px;font-weight:700}.ok{color:#86efac}.bad{color:#fca5a5}.warn{color:#fde68a}table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:9px;border-bottom:1px solid #293440;text-align:left}button{border:0;border-radius:8px;padding:7px 10px;cursor:pointer;margin:2px;background:#334155;color:#fff}button.primary{background:#2563eb}button.danger{background:#b91c1c}.section{margin-top:16px}.toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.pill{padding:3px 8px;border-radius:999px;background:#293440;font-size:12px}pre{white-space:pre-wrap;max-height:260px;overflow:auto;background:#0b0f14;padding:10px;border-radius:8px}.tabs button{background:#1f2937}.tabs button.active{background:#2563eb}.hidden{display:none}
</style></head>
<body>
<h1>MT5 Multi-Bot Dashboard <span class="pill">v1.2</span></h1><div class="muted">Tick กลางชุดเดียว → Bot หลายตัว → Wallet / Pending / Position / PnL แยกกัน</div>
<div class="grid">
 <div class="card"><div class="muted">Runtime</div><div id="runtime" class="value">...</div></div>
 <div class="card"><div class="muted">WebSocket</div><div id="ws" class="value">connecting</div></div>
 <div class="card"><div class="muted">Sender</div><div id="sender" class="value">...</div><div id="tickAge" class="muted">-</div></div>
 <div class="card"><div class="muted">XAUUSD Bid</div><div id="bid" class="value">-</div></div>
 <div class="card"><div class="muted">XAUUSD Ask</div><div id="ask" class="value">-</div></div>
 <div class="card"><div class="muted">Mid</div><div id="mid" class="value">-</div></div>
 <div class="card"><div class="muted">Spread</div><div id="spread" class="value">-</div></div>
 <div class="card"><div class="muted">Bots</div><div id="botCount" class="value">0</div></div>
 <div class="card"><div class="muted">Total Balance</div><div id="balance" class="value">0.00</div></div>
 <div class="card"><div class="muted">Total PnL</div><div id="pnl" class="value">0.00</div></div>
</div>
<div class="tabs toolbar"><button class="active" onclick="show('bots',this)">Bots</button><button onclick="show('profiles',this)">Profiles</button><button onclick="show('compare',this)">Compare</button><button onclick="show('detail',this)">Bot Detail</button></div>
<div id="bots" class="section card"><h2>Bots</h2><table><thead><tr><th>ID</th><th>Profile</th><th>Bot</th><th>Strategy</th><th>Enabled</th><th>Trend</th><th>Balance</th><th>PnL</th><th>Pending</th><th>Position</th><th>Action</th></tr></thead><tbody id="botRows"></tbody></table></div>
<div id="profiles" class="section card hidden"><h2>Profiles</h2><table><thead><tr><th>ID</th><th>Name</th><th>Enabled</th><th>Bots</th><th>Balance</th><th>PnL</th></tr></thead><tbody id="profileRows"></tbody></table></div>
<div id="compare" class="section card hidden"><h2>Compare</h2><table><thead><tr><th>Bot</th><th>Balance</th><th>Net PnL</th><th>Trades</th><th>Wins</th><th>Win Rate</th><th>Max DD</th><th>Pending</th><th>Open</th></tr></thead><tbody id="compareRows"></tbody></table></div>
<div id="detail" class="section card hidden"><h2>Bot Detail</h2><div class="toolbar"><select id="botSelect" onchange="loadDetail()"></select><button onclick="loadDetail()">Refresh</button></div><pre id="detailText">เลือก Bot</pre></div>
<script>
let bots=[]; let socket; let heartbeat;
async function j(url,opts){const r=await fetch(url,opts); if(!r.ok)throw new Error(await r.text()); return await r.json()}
function n(v){return Number(v||0).toFixed(2)}
function cls(v){return Number(v)>=0?'ok':'bad'}
async function toggle(id,on){await j(`/api/bots/${id}/${on?'disable':'enable'}`,{method:'POST'}); await load()}
function show(id,btn){document.querySelectorAll('.section').forEach(x=>x.classList.add('hidden'));document.getElementById(id).classList.remove('hidden');document.querySelectorAll('.tabs button').forEach(x=>x.classList.remove('active'));btn.classList.add('active')}
async function load(){const [r,p,b,c,s]=await Promise.all([j('/api/multibot/runtime/status'),j('/api/profiles'),j('/api/bots'),j('/api/compare'),j('/api/state')]);bots=b;runtime.textContent=r.running?'RUNNING':'IDLE';runtime.className='value '+(r.running?'ok':'warn');const h=s.health||{};const t=s.latest_tick||{};sender.textContent=h.sender_online?'ONLINE':'OFFLINE';sender.className='value '+(h.sender_online?'ok':'bad');tickAge.textContent=h.seconds_since_last_message==null?'ยังไม่มี Tick':`ล่าสุด ${h.seconds_since_last_message}s ก่อน`;bid.textContent=t.bid==null?'-':Number(t.bid).toFixed(2);ask.textContent=t.ask==null?'-':Number(t.ask).toFixed(2);mid.textContent=t.mid==null?'-':Number(t.mid).toFixed(2);spread.textContent=t.spread==null?'-':Number(t.spread).toFixed(3);botCount.textContent=b.length;balance.textContent=n(c.reduce((a,x)=>a+Number(x.balance||0),0));pnl.textContent=n(c.reduce((a,x)=>a+Number(x.net_pnl||0),0));profileRows.innerHTML=p.map(x=>`<tr><td>${x.id}</td><td>${x.name}</td><td>${x.enabled}</td><td>${x.bot_count}</td><td>${n(x.total_balance)}</td><td class="${cls(x.total_realized_pnl)}">${n(x.total_realized_pnl)}</td></tr>`).join('');botRows.innerHTML=b.map(x=>`<tr><td>${x.id}</td><td>${x.profile_name}</td><td>${x.name}</td><td>${x.strategy_type} ${x.strategy_version}</td><td>${x.enabled}</td><td>${x.latest_trend||'-'}</td><td>${n(x.balance)}</td><td class="${cls(x.realized_pnl)}">${n(x.realized_pnl)}</td><td>${x.pending_count}</td><td>${x.open_position_count}</td><td><button onclick="toggle(${x.id},${x.enabled})">${x.enabled?'Disable':'Enable'}</button><button onclick="selectBot(${x.id})">Detail</button></td></tr>`).join('');compareRows.innerHTML=c.map(x=>`<tr><td>${x.name}</td><td>${n(x.balance)}</td><td class="${cls(x.net_pnl)}">${n(x.net_pnl)}</td><td>${x.closed_trades}</td><td>${x.wins}</td><td>${n(x.win_rate)}%</td><td>${n(x.max_drawdown*100)}%</td><td>${x.pending_orders}</td><td>${x.open_positions}</td></tr>`).join('');const current=botSelect.value;botSelect.innerHTML=b.map(x=>`<option value="${x.id}">${x.id} - ${x.name}</option>`).join('');if(current)botSelect.value=current}
function selectBot(id){botSelect.value=id;document.querySelectorAll('.section').forEach(x=>x.classList.add('hidden'));detail.classList.remove('hidden');loadDetail()}
async function loadDetail(){if(!botSelect.value)return;detailText.textContent=JSON.stringify(await j(`/api/bots/${botSelect.value}/state`),null,2)}
function connect(){socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws/multibot`);socket.onopen=()=>{ws.textContent='CONNECTED';ws.className='value ok';heartbeat=setInterval(()=>socket.readyState===1&&socket.send('ping'),10000)};socket.onmessage=()=>load();socket.onclose=()=>{ws.textContent='RECONNECTING';ws.className='value warn';clearInterval(heartbeat);setTimeout(connect,1500)};socket.onerror=()=>socket.close()}
load();setInterval(load,5000);connect();
</script></body></html>'''
