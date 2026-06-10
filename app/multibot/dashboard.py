HTML = r'''<!doctype html>
<html lang="th"><head><meta charset="utf-8"><title>Multi-Bot Dashboard</title>
<style>body{font-family:Arial;background:#111;color:#eee;margin:24px}table{width:100%;border-collapse:collapse;margin-top:12px}th,td{border:1px solid #444;padding:8px;text-align:left}button{padding:7px 10px;margin-right:4px}.card{background:#1b1b1b;padding:16px;border-radius:10px;margin-bottom:16px}.green{color:#8f8}</style></head>
<body><h1>MT5 Multi-Bot Foundation v1.1</h1><div class="card" id="summary">Loading...</div>
<div class="card"><h2>Profiles</h2><table><thead><tr><th>ID</th><th>Name</th><th>Enabled</th><th>Bots</th><th>Balance</th><th>PnL</th></tr></thead><tbody id="profiles"></tbody></table></div>
<div class="card"><h2>Bots</h2><table><thead><tr><th>ID</th><th>Profile</th><th>Bot</th><th>Strategy</th><th>Enabled</th><th>Balance</th><th>PnL</th><th>Action</th></tr></thead><tbody id="bots"></tbody></table></div>
<script>
async function json(url,opts){const r=await fetch(url,opts); return await r.json()}
async function toggle(id,on){await json(`/api/bots/${id}/${on?'disable':'enable'}`,{method:'POST'});await load()}
async function load(){const [m,p,b]=await Promise.all([json('/api/multibot/migration/status'),json('/api/profiles'),json('/api/bots')]);summary.innerHTML=`Schema <span class="green">${m.schema_version}</span> | Profiles ${m.profiles} | Bots ${m.bots} | Wallets ${m.wallets}`;profiles.innerHTML=p.map(x=>`<tr><td>${x.id}</td><td>${x.name}</td><td>${x.enabled}</td><td>${x.bot_count}</td><td>${Number(x.total_balance).toFixed(2)}</td><td>${Number(x.total_realized_pnl).toFixed(2)}</td></tr>`).join('');bots.innerHTML=b.map(x=>`<tr><td>${x.id}</td><td>${x.profile_name}</td><td>${x.name}</td><td>${x.strategy_type} ${x.strategy_version}</td><td>${x.enabled}</td><td>${Number(x.balance).toFixed(2)}</td><td>${Number(x.realized_pnl).toFixed(2)}</td><td><button onclick="toggle(${x.id},${x.enabled})">${x.enabled?'Disable':'Enable'}</button></td></tr>`).join('')}
load();setInterval(load,3000);
</script></body></html>'''
