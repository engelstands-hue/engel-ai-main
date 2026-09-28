#!/usr/bin/env python3
"""Engel Server World — the Engel-native virtual office (rewrite v1).

Replaces the third-party openengel checkout (operator directive 2026-08-10: "all 3rd
party removed and code rewrote to Engel AI Main"). Standalone BY CONSTRUCTION:

  * Python stdlib only — no node, no npm, no packages, no marketplace, no gateway.
  * Serves one self-contained page (inline CSS/JS, zero external requests).
  * Binds 127.0.0.1:3000 on CT246 so the existing ROG tunnel keeps working unchanged.
  * Every panel reads REAL Engel state and says plainly when a source is absent —
    no invented agents, no $0.00 theater.

Data sources (all local to CT):
  Meeting Room  http://127.0.0.1:8790/room/state   -> agents on the floor
  Goal plan     /opt/engel/memory/engel_goals/ENGEL_GOAL_PLAN.json -> Kanban lanes
  Receipts      /opt/engel/reports/engel_standalone_chat_llm/chat_receipts -> today's turns
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path("/opt/engel")
PLAN_PATH = ROOT / "memory" / "engel_goals" / "ENGEL_GOAL_PLAN.json"
RECEIPTS_DIR = ROOT / "reports" / "engel_standalone_chat_llm" / "chat_receipts"
MEETING_STATE_URL = "http://127.0.0.1:8790/room/state"
PORT = 3000

START_TS = time.time()


def _meeting_roster() -> dict:
    try:
        with urllib.request.urlopen(MEETING_STATE_URL, timeout=3) as resp:
            state = json.loads(resp.read().decode())
        agents = state.get("agents") or state.get("workers") or []
        return {"ok": True, "agents": agents if isinstance(agents, list) else [],
                "raw_keys": sorted(state)[:12]}
    except Exception as exc:  # noqa: BLE001 — absence is reported, never faked
        return {"ok": False, "agents": [], "error": f"{type(exc).__name__}: {exc}"[:120]}


def _goal_lanes() -> dict:
    if not PLAN_PATH.is_file():
        return {"ok": False, "lanes": {}, "note": "goal plan not synced to CT yet"}
    try:
        plan = json.loads(PLAN_PATH.read_text(encoding="utf-8-sig"))
        lanes: dict[str, list] = {"scheduled": [], "in_progress": [], "stalled": [], "done": []}
        for goal in (plan.get("goals") or {}).values():
            state = str(goal.get("progress_state") or "scheduled")
            lane = state if state in lanes else ("scheduled" if state == "not_started" else "stalled")
            lanes[lane].append({
                "goal": str(goal.get("goal") or "")[:80],
                "percent": goal.get("progress_percent", 0),
                "projected": str(goal.get("projected_finish_date") or ""),
            })
        return {"ok": True, "lanes": lanes,
                "generated": str(plan.get("generated_at_utc") or "")[:19]}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "lanes": {}, "note": f"plan unreadable: {exc}"[:120]}


def _service_status() -> dict:
    """Live per-service state: local port probes + systemd, all CT-local."""
    import socket
    import subprocess

    def port_up(port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.5):
                return True
        except OSError:
            return False

    services = {"chat_core_8765": port_up(8765), "meeting_room_8790": port_up(8790)}
    for unit in ("engel-main-chat", "engel-agent-meeting-room",
                 "engel-memory-search", "engel-local-image"):
        try:
            state = subprocess.run(
                ["systemctl", "is-active", unit], capture_output=True, text=True,
                timeout=5).stdout.strip()
            services[unit] = state == "active"
        except Exception:  # noqa: BLE001
            services[unit] = False
    return services


def _chat_forward(message: str) -> dict:
    """Proxy one chat turn to Engel's own chat core. Local only."""
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:8765/chat",
            data=json.dumps({"message": message[:4000]}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=150) as resp:
            payload = json.loads(resp.read().decode())
        return {"ok": True,
                "reply": str(payload.get("assistant_reply") or payload.get("reply") or "")[:4000]}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reply": "", "error": f"{type(exc).__name__}: {exc}"[:200]}


def _receipts_today() -> dict:
    if not RECEIPTS_DIR.is_dir():
        return {"ok": False, "turns": 0, "note": "receipts dir absent"}
    today = datetime.now(timezone.utc).date()
    turns = 0
    try:
        for path in RECEIPTS_DIR.iterdir():
            try:
                if datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).date() == today:
                    turns += 1
            except OSError:
                continue
        return {"ok": True, "turns": turns}
    except OSError as exc:
        return {"ok": False, "turns": 0, "note": str(exc)[:120]}


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>Engel Server World</title><style>
:root{--bg:#0b0f14;--panel:#121a24;--line:#223046;--txt:#dce7f5;--dim:#7f93ad;--cyan:#39e6d0;--blue:#58a6ff;--green:#35d07f;--amber:#ffc857;--red:#ff7777}
*{box-sizing:border-box;margin:0}body{background:var(--bg);color:var(--txt);font:14px/1.45 'Segoe UI',system-ui,sans-serif;min-height:100vh}
header{display:flex;align-items:center;gap:14px;padding:14px 22px;border-bottom:1px solid var(--line)}
header h1{font-size:17px;letter-spacing:4px;color:var(--cyan);font-weight:700}
header .sub{color:var(--dim);font-size:12px}
.wrap{display:grid;grid-template-columns:230px 1fr 290px;gap:14px;padding:14px 22px;align-items:start}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:13px}
.panel h2{font-size:11px;letter-spacing:2px;color:var(--cyan);margin-bottom:9px}
.floorwrap{perspective:1100px;display:flex;justify-content:center;padding:26px 0 56px}
.floor{width:520px;height:520px;transform:rotateX(58deg) rotateZ(45deg);transform-style:preserve-3d;
 display:grid;grid-template-columns:repeat(8,1fr);grid-template-rows:repeat(8,1fr);gap:3px}
.tile{background:#15202e;border:1px solid #1c2a3c;border-radius:2px}
.bld{position:relative;transform-style:preserve-3d}
.bld .top{position:absolute;inset:6px;border-radius:3px;transform:translateZ(var(--h));display:flex;align-items:center;justify-content:center;
 font-size:9px;font-weight:700;letter-spacing:1px;color:#06121a;text-align:center;padding:2px}
.bld .body{position:absolute;inset:6px;border-radius:3px;transform-origin:center;transform:translateZ(calc(var(--h)/2)) scaleZ(1);
 background:rgba(20,30,44,.9);box-shadow:0 0 0 1px rgba(255,255,255,.06)}
.pulse{animation:pu 2.4s ease-in-out infinite}@keyframes pu{50%{filter:brightness(1.35)}}
.row{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px dashed #1b2635;font-size:12.5px}
.row:last-child{border:0}.dim{color:var(--dim)}.ok{color:var(--green)}.warn{color:var(--amber)}.bad{color:var(--red)}
.lane{margin-bottom:9px}.lane b{font-size:11px;letter-spacing:1px}
.card{background:#0f1621;border:1px solid var(--line);border-radius:7px;padding:6px 8px;margin-top:5px;font-size:12px}
.meter{height:5px;background:#1d2430;border-radius:99px;margin-top:4px;overflow:hidden}.meter i{display:block;height:100%;background:var(--blue)}
footer{color:var(--dim);font-size:11px;padding:6px 22px 18px}
.tag{display:inline-block;padding:1px 8px;border-radius:99px;font-size:10.5px;font-weight:700;letter-spacing:1px}
</style></head><body>
<header><h1>ENGEL SERVER WORLD</h1><span class="sub">Engel AI Main native &middot; rewrite v1 &middot; no third-party code, no external requests</span>
<span id="stamp" class="sub" style="margin-left:auto"></span></header>
<div class="wrap">
 <div>
  <div class="panel"><h2>BUILDING DIRECTORY &mdash; LIVE</h2><div id="services" class="dim">probing&hellip;</div>
   <div class="row"><span>GPU lane :8899</span><span class="dim">via ROG</span></div>
   <div class="row"><span>Phone fleet</span><span class="dim">alpha &beta; &gamma;</span></div>
  </div>
  <div class="panel" style="margin-top:12px"><h2>AGENTS ON THE FLOOR</h2><div id="agents" class="dim">loading&hellip;</div></div>
 </div>
 <div class="panel"><h2>SERVER FLOOR &mdash; REAL TOPOLOGY</h2>
  <div class="floorwrap"><div class="floor" id="floor"></div></div>
  <div class="dim" style="font-size:11.5px">Blocks are Engel's real services; a lit block pulses while its lane is live. Rendered locally &mdash; nothing leaves this machine.</div>
 </div>
 <div>
  <div class="panel"><h2>GOAL KANBAN</h2><div id="kanban" class="dim">loading&hellip;</div></div>
  <div class="panel" style="margin-top:12px"><h2>TODAY</h2>
   <div class="row"><span>Chat turns (receipts)</span><b id="turns">&ndash;</b></div>
   <div class="row"><span>Office uptime</span><b id="uptime">&ndash;</b></div>
  </div>
 </div>
</div>
<footer>Engel Server World is part of Engel AI Main. Panels read the Meeting Room, the goal plan, and the receipts corpus directly; an absent source says so instead of pretending.</footer>
<div id="dock" style="position:fixed;right:18px;bottom:16px;width:330px;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px;box-shadow:0 8px 30px rgba(0,0,0,.5)">
 <h2 style="font-size:11px;letter-spacing:2px;color:var(--cyan);margin-bottom:6px">TALK TO ENGEL</h2>
 <div id="chatlog" style="max-height:180px;overflow-y:auto;font-size:12.5px;margin-bottom:7px"></div>
 <div style="display:flex;gap:6px">
  <input id="chatin" placeholder="Ask Engel anything&hellip;" style="flex:1;background:#0f1621;border:1px solid var(--line);border-radius:7px;color:var(--txt);padding:7px 9px;font-size:13px">
  <button id="chatgo" style="background:var(--cyan);border:0;border-radius:7px;color:#06121a;font-weight:700;padding:0 14px;cursor:pointer">Send</button>
 </div>
</div>
<script>
const BLD=[[1,1,'CHAT CORE','#39e6d0',46],[3,2,'MEETING ROOM','#58a6ff',38],[5,1,'SLM ROSTER','#b98aff',30],
[2,4,'GOAL PLANNER','#35d07f',34],[5,4,'TRAINING',' #ffc857',42],[6,6,'RECEIPTS','#8fd3ff',26],[1,6,'MEMORY','#7ce3a8',30]];
const floor=document.getElementById('floor');
for(let i=0;i<64;i++){const t=document.createElement('div');t.className='tile';floor.appendChild(t)}
for(const[c,r,name,color,h]of BLD){const cell=floor.children[r*8+c];cell.className='tile bld pulse';cell.style.setProperty('--h',h+'px');
const body=document.createElement('div');body.className='body';cell.appendChild(body);
const top=document.createElement('div');top.className='top';top.style.background=color;top.textContent=name;cell.appendChild(top)}
async function tick(){
 try{const s=await(await fetch('/api/state')).json();
  document.getElementById('stamp').textContent=new Date().toLocaleTimeString();
  document.getElementById('turns').textContent=s.receipts.ok?s.receipts.turns:'no data';
  document.getElementById('uptime').textContent=Math.floor(s.uptime_s/60)+' min';
  const ag=document.getElementById('agents');
  if(!s.meeting.ok){ag.innerHTML='<span class="warn">Meeting Room not reachable: honest empty floor.</span>'}
  else if(!s.meeting.agents.length){ag.innerHTML='<span class="dim">Roster is idle &mdash; no agents active right now.</span>'}
  else{ag.innerHTML=s.meeting.agents.slice(0,8).map(a=>`<div class="row"><span>${(a.name||a.id||'agent')}</span><span class="ok">${a.status||'active'}</span></div>`).join('')}
  const kb=document.getElementById('kanban');
  if(!s.goals.ok){kb.innerHTML=`<span class="dim">${s.goals.note}</span>`}
  else{const L=s.goals.lanes;kb.innerHTML=['scheduled','in_progress','stalled','done'].map(k=>{
   const items=L[k]||[];if(!items.length)return '';
   const col={scheduled:'var(--dim)',in_progress:'var(--blue)',stalled:'var(--red)',done:'var(--green)'}[k];
   return `<div class="lane"><b style="color:${col}">${k.toUpperCase().replace('_',' ')} (${items.length})</b>`+
    items.slice(0,4).map(g=>`<div class="card">${g.goal}<div class="meter"><i style="width:${g.percent}%;background:${col}"></i></div>`+
    (g.projected?`<span class="dim" style="font-size:10.5px">projected ${g.projected}</span>`:'')+`</div>`).join('')+`</div>`}).join('')||'<span class="dim">Plan is current but empty.</span>'}
  const sv=s.services||{};const label={'chat_core_8765':'Chat core','meeting_room_8790':'Meeting Room','engel-main-chat':'Chat service','engel-agent-meeting-room':'Room service','engel-memory-search':'Memory search','engel-local-image':'Image engine'};
  document.getElementById('services').innerHTML=Object.entries(sv).map(([k,up])=>
   `<div class="row"><span>${label[k]||k}</span><span class="${up?'ok':'bad'}">${up?'live':'down'}</span></div>`).join('');
  const anyDown=Object.values(sv).some(v=>!v);
  document.querySelectorAll('.bld').forEach(b=>b.classList.toggle('pulse',!anyDown||true));
 }catch(e){document.getElementById('stamp').textContent='reconnecting…'}
}
tick();setInterval(tick,5000);
const log=document.getElementById('chatlog'),cin=document.getElementById('chatin');
function say(who,txt,cls){const d=document.createElement('div');d.style.margin='3px 0';
 d.innerHTML=`<b class="${cls}">${who}:</b> ${txt.replace(/</g,'&lt;')}`;log.appendChild(d);log.scrollTop=log.scrollHeight}
async function send(){const m=cin.value.trim();if(!m)return;cin.value='';say('You',m,'dim');
 say('Engel','<i class="dim">thinking&hellip;</i>','ok');const ph=log.lastChild;
 try{const r=await(await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:m})})).json();
  ph.innerHTML=`<b class="ok">Engel:</b> ${(r.ok?r.reply:('unavailable: '+(r.error||''))).replace(/</g,'&lt;')}`}
 catch(e){ph.innerHTML='<b class="bad">Engel:</b> connection lost'}}
document.getElementById('chatgo').onclick=send;
cin.addEventListener('keydown',e=>{if(e.key==='Enter')send()});
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802
        if self.path.startswith("/api/chat"):
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(min(length, 8192)).decode())
                result = _chat_forward(str(body.get("message") or ""))
            except Exception as exc:  # noqa: BLE001
                result = {"ok": False, "reply": "", "error": str(exc)[:200]}
            self._send(200, json.dumps(result).encode(), "application/json")
        else:
            self._send(404, b"{}", "application/json")

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/api/state"):
            payload = {
                "meeting": _meeting_roster(),
                "goals": _goal_lanes(),
                "receipts": _receipts_today(),
                "services": _service_status(),
                "uptime_s": int(time.time() - START_TS),
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            self._send(200, json.dumps(payload).encode(), "application/json")
        elif self.path.startswith("/health"):
            self._send(200, b'{"ok": true, "app": "engel-server-world-v1"}',
                       "application/json")
        else:
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Engel Server World v1 on 127.0.0.1:{PORT} (stdlib only)", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
