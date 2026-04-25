"""
Warehouse Optimizer - FastAPI Backend
HackUPC 2026 - Mecalux Challenge
Run: python app.py → http://localhost:8000
"""

import os
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

try:
    from solver import (
        WarehouseSolver,
        parse_warehouse,
        parse_obstacles,
        parse_ceiling,
        parse_bays,
        solve_parallel,
    )
except ImportError:
    from solver import (
        WarehouseSolver,
        parse_warehouse,
        parse_obstacles,
        parse_ceiling,
        parse_bays,
    )
    solve_parallel = None


os.makedirs("static/js", exist_ok=True)

app = FastAPI(title="Warehouse Optimizer")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.post("/api/solve")
async def solve_warehouse(
    warehouse: UploadFile = File(...),
    obstacles: UploadFile = File(...),
    ceiling: UploadFile = File(...),
    bays: UploadFile = File(...),
):
    try:
        wh = parse_warehouse((await warehouse.read()).decode())
        obs = parse_obstacles((await obstacles.read()).decode())
        ceil = parse_ceiling((await ceiling.read()).decode())
        bt = parse_bays((await bays.read()).decode())

        if solve_parallel is not None:
            placed, stats = solve_parallel(wh, obs, ceil, bt, time_limit=25.0)
            return _build_response(placed, stats, wh, obs, ceil, bt, placed_are_dicts=True)

        solver = WarehouseSolver(wh, obs, ceil, bt)
        placed, stats = solver.solve(time_limit=25.0)
        return _build_response(placed, stats, wh, obs, ceil, bt, placed_are_dicts=False)

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


@app.post("/api/solve-text")
async def solve_text(
    warehouse: str = Form(...),
    obstacles: str = Form(...),
    ceiling: str = Form(...),
    bays: str = Form(...),
):
    try:
        wh = parse_warehouse(warehouse)
        obs = parse_obstacles(obstacles)
        ceil = parse_ceiling(ceiling)
        bt = parse_bays(bays)

        if solve_parallel is not None:
            placed, stats = solve_parallel(wh, obs, ceil, bt, time_limit=25.0)
            return _build_response(placed, stats, wh, obs, ceil, bt, placed_are_dicts=True)

        solver = WarehouseSolver(wh, obs, ceil, bt)
        placed, stats = solver.solve(time_limit=25.0)
        return _build_response(placed, stats, wh, obs, ceil, bt, placed_are_dicts=False)

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


def _build_response(placed, stats, wh, obs, ceil, bt, placed_are_dicts=False):
    placed_dicts = placed if placed_are_dicts else [b.to_dict() for b in placed]

    return JSONResponse({
        "success": True,
        "placed": placed_dicts,
        "stats": stats,
        "warehouse": [{"x": v[0], "y": v[1]} for v in wh],
        "obstacles": [{"x": o[0], "y": o[1], "w": o[2], "d": o[3]} for o in obs],
        "ceiling": [{"x": c[0], "h": c[1]} for c in ceil],
        "bayTypes": [
            {
                "id": int(b[0]),
                "w": b[1],
                "d": b[2],
                "h": b[3],
                "gap": b[4],
                "nLoads": int(b[5]),
                "price": b[6],
            }
            for b in bt
        ],
        "csv": "\n".join(
            f"{int(b['id'])}, {b['x']}, {b['y']}, {b['rotation']}"
            for b in placed_dicts
        ),
    })


FRONTEND_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Warehouse Optimizer — HackUPC 2026</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Outfit:wght@300;400;600;700;900&display=swap" rel="stylesheet">

<style>
:root {
  --bg:#070b14;
  --bg2:#0d1524;
  --srf:rgba(255,255,255,0.04);
  --brd:rgba(255,255,255,0.08);
  --txt:#e8edf5;
  --dim:rgba(255,255,255,0.42);
  --acc:#2a6fff;
  --acc2:#ff6b35;
  --ok:#2ed573;
  --no:#ff4757;
}

* {
  box-sizing:border-box;
  margin:0;
  padding:0;
}

body {
  font-family:'Outfit',sans-serif;
  background:
    radial-gradient(circle at 48% 2%, rgba(135,170,255,0.30), transparent 18%),
    radial-gradient(circle at 84% 18%, rgba(42,111,255,0.16), transparent 25%),
    linear-gradient(145deg,#090e19,#141c2d 45%,#070b13);
  color:var(--txt);
  min-height:100vh;
  overflow-x:hidden;
}

body::before {
  content:"";
  position:fixed;
  inset:0;
  pointer-events:none;
  background:
    linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
  background-size:56px 56px;
  opacity:.22;
  mask-image:radial-gradient(circle at 50% 10%, black, transparent 72%);
}

.hdr {
  margin:28px auto 0;
  width:calc(100% - 64px);
  max-width:1500px;
  padding:22px 26px;
  border:1px solid rgba(255,255,255,0.11);
  border-radius:30px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  background:
    linear-gradient(180deg,rgba(255,255,255,0.075),rgba(255,255,255,0.025)),
    rgba(12,18,31,0.82);
  backdrop-filter:blur(24px);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.12),
    0 28px 80px rgba(0,0,0,0.36);
  position:sticky;
  top:18px;
  z-index:100;
}

.logo-g {
  display:flex;
  align-items:center;
  gap:16px;
}

.logo-i {
  width:50px;
  height:50px;
  border-radius:16px;
  background:
    radial-gradient(circle at 30% 25%,rgba(255,255,255,0.65),transparent 24%),
    linear-gradient(135deg,#ff7a3d,#2a6fff);
  display:flex;
  align-items:center;
  justify-content:center;
  font-weight:900;
  font-size:22px;
  color:#fff;
  box-shadow:0 12px 35px rgba(42,111,255,0.35);
}

.logo-t {
  font-size:21px;
  font-weight:800;
  letter-spacing:-0.4px;
}

.logo-s {
  font-size:11px;
  color:rgba(255,255,255,0.44);
  letter-spacing:1.6px;
  text-transform:uppercase;
}

.btn {
  border:none;
  padding:12px 22px;
  border-radius:14px;
  font-size:14px;
  font-weight:800;
  cursor:pointer;
  font-family:'Outfit';
  letter-spacing:0.2px;
  transition:all .22s;
}

.btn-p {
  background:linear-gradient(135deg,#5b8cff,#185cff);
  color:#fff;
  box-shadow:0 12px 34px rgba(42,111,255,0.32);
}

.btn-p:hover {
  transform:translateY(-2px);
  box-shadow:0 16px 44px rgba(42,111,255,0.44);
}

.btn-p:disabled {
  opacity:.35;
  cursor:not-allowed;
  transform:none;
  box-shadow:none;
}

.btn-g {
  background:linear-gradient(180deg,rgba(255,255,255,0.08),rgba(255,255,255,0.03));
  color:var(--txt);
  border:1px solid rgba(255,255,255,0.10);
  box-shadow:inset 0 1px 0 rgba(255,255,255,0.08);
}

.btn-g:hover {
  background:rgba(255,255,255,0.10);
}

.btn-sm {
  padding:9px 16px;
  font-size:13px;
}

.up-pg {
  max-width:920px;
  margin:38px auto 0;
  padding:56px 24px;
  border:1px solid rgba(255,255,255,0.09);
  border-radius:34px;
  background:
    linear-gradient(180deg,rgba(255,255,255,0.055),rgba(255,255,255,0.018)),
    rgba(10,16,28,0.70);
  backdrop-filter:blur(24px);
  box-shadow:0 32px 90px rgba(0,0,0,0.36);
}

.up-t {
  font-size:46px;
  font-weight:900;
  letter-spacing:-1.5px;
  text-align:center;
  margin-bottom:10px;
  background:linear-gradient(135deg,#fff,#b9c8ff 60%,rgba(255,255,255,0.55));
  -webkit-background-clip:text;
  -webkit-text-fill-color:transparent;
}

.up-s {
  text-align:center;
  color:var(--dim);
  font-size:16px;
  margin-bottom:44px;
}

.up-gr {
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:16px;
  margin-bottom:40px;
}

.dz {
  border:1px solid rgba(255,255,255,0.10);
  border-radius:22px;
  padding:28px 20px;
  text-align:center;
  cursor:pointer;
  transition:all .25s;
  background:
    radial-gradient(circle at 85% 15%,rgba(42,111,255,0.12),transparent 32%),
    linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02));
  box-shadow:inset 0 1px 0 rgba(255,255,255,0.08);
}

.dz:hover {
  border-color:rgba(92,140,255,0.62);
  background:rgba(42,111,255,0.09);
  box-shadow:0 18px 44px rgba(42,111,255,0.12);
  transform:translateY(-2px);
}

.dz.ok {
  border-color:rgba(46,213,115,0.55);
  background:rgba(46,213,115,0.06);
}

.dz .ic {
  font-size:34px;
  margin-bottom:8px;
}

.dz .lb {
  font-weight:800;
  font-size:16px;
  margin-bottom:4px;
}

.dz .ds {
  font-size:12px;
  color:var(--dim);
}

.up-ac {
  text-align:center;
  display:flex;
  flex-direction:column;
  align-items:center;
  gap:14px;
}

.sv-pg {
  display:flex;
  flex-direction:column;
  align-items:center;
  justify-content:center;
  height:70vh;
  gap:20px;
}

.spin {
  width:74px;
  height:74px;
  border-radius:50%;
  border:3px solid rgba(92,140,255,0.14);
  border-top-color:#74a0ff;
  animation:sp .7s linear infinite;
  box-shadow:0 0 40px rgba(92,140,255,0.25);
}

@keyframes sp { to { transform:rotate(360deg); } }
@keyframes pu { 0%,100%{opacity:.35}50%{opacity:1} }
@keyframes su { from{opacity:0;transform:translateY(24px)} to{opacity:1;transform:translateY(0)} }
.ai { animation:su .5s ease-out; }

.rp {
  display:flex;
  flex-direction:column;
  height:calc(100vh - 128px);
  width:calc(100% - 64px);
  max-width:1500px;
  margin:18px auto 0;
  border-radius:34px;
  overflow:hidden;
  border:1px solid rgba(255,255,255,0.09);
  background:
    linear-gradient(180deg,rgba(255,255,255,0.045),rgba(255,255,255,0.018)),
    rgba(11,16,28,0.72);
  backdrop-filter:blur(22px);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.09),
    0 34px 90px rgba(0,0,0,0.42);
}

.sb {
  padding:20px 24px;
  display:grid;
  grid-template-columns:repeat(5,1fr);
  gap:16px;
  background:rgba(255,255,255,0.015);
  border-bottom:1px solid rgba(255,255,255,0.07);
}

.sc {
  background:
    radial-gradient(circle at 80% 15%,rgba(92,140,255,0.16),transparent 30%),
    linear-gradient(180deg,rgba(255,255,255,0.07),rgba(255,255,255,0.025));
  border:1px solid rgba(255,255,255,0.09);
  border-radius:22px;
  padding:20px 22px;
  min-width:130px;
  backdrop-filter:blur(16px);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.08),
    0 14px 32px rgba(0,0,0,0.22);
}

.sv {
  font-size:31px;
  font-weight:900;
  font-family:'JetBrains Mono';
  color:#74a0ff;
  background:none;
  -webkit-text-fill-color:#74a0ff;
  text-shadow:0 0 22px rgba(80,130,255,0.35);
}

.sl {
  font-size:10px;
  text-transform:uppercase;
  letter-spacing:3px;
  color:rgba(255,255,255,0.38);
  margin-top:7px;
  font-weight:800;
}

.ma {
  flex:1;
  display:flex;
  min-height:0;
}

.vc {
  flex:1;
  padding:18px;
  display:flex;
  flex-direction:column;
  min-height:0;
}

.vf {
  flex:1;
  border-radius:28px;
  overflow:hidden;
  border:1px solid rgba(255,255,255,0.09);
  min-height:0;
  background:
    radial-gradient(circle at 55% 12%,rgba(93,120,180,0.20),transparent 32%),
    #080d17;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.08),
    inset 0 0 70px rgba(42,111,255,0.08),
    0 22px 60px rgba(0,0,0,0.30);
}

.sp {
  width:310px;
  border-left:1px solid rgba(255,255,255,0.07);
  padding:20px;
  overflow-y:auto;
  background:
    linear-gradient(180deg,rgba(255,255,255,0.035),rgba(255,255,255,0.012)),
    rgba(6,10,18,0.45);
}

.sh {
  font-size:11px;
  font-weight:900;
  text-transform:uppercase;
  letter-spacing:2.6px;
  color:rgba(255,255,255,0.42);
  margin-bottom:14px;
}

.li {
  padding:13px 13px;
  border-radius:18px;
  background:
    linear-gradient(180deg,rgba(255,255,255,0.055),rgba(255,255,255,0.02));
  margin-bottom:10px;
  border:1px solid rgba(255,255,255,0.07);
  box-shadow:inset 0 1px 0 rgba(255,255,255,0.06);
}

.li .tp {
  display:flex;
  align-items:center;
  gap:9px;
  margin-bottom:5px;
}

.ld {
  width:13px;
  height:13px;
  border-radius:4px;
  display:inline-block;
  box-shadow:0 0 18px currentColor;
}

.li .mt {
  font-size:11px;
  color:rgba(255,255,255,0.42);
  font-family:'JetBrains Mono';
  line-height:1.35;
}

.co {
  font-size:10px;
  font-family:'JetBrains Mono';
  color:rgba(255,255,255,0.52);
  background:rgba(0,0,0,0.28);
  padding:12px;
  border-radius:14px;
  max-height:210px;
  overflow:auto;
  white-space:pre-wrap;
  word-break:break-all;
  border:1px solid rgba(255,255,255,0.07);
}

.tgl {
  display:flex;
  align-items:center;
  gap:9px;
  margin:12px 0;
  font-size:12px;
  color:rgba(255,255,255,0.48);
  cursor:pointer;
  font-weight:600;
}

.tgl input {
  accent-color:#74a0ff;
}

.view-tabs {
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:9px;
  margin:12px 0 18px;
  padding:6px;
  border-radius:18px;
  background:rgba(0,0,0,0.20);
  border:1px solid rgba(255,255,255,0.06);
}

.view-tab {
  border:1px solid transparent;
  background:transparent;
  color:rgba(255,255,255,0.50);
  padding:10px 10px;
  border-radius:13px;
  cursor:pointer;
  font-family:'Outfit';
  font-size:12px;
  font-weight:900;
  transition:all .22s;
}

.view-tab:hover {
  color:white;
  background:rgba(255,255,255,0.06);
}

.view-tab.active {
  color:white;
  background:
    radial-gradient(circle at 22% 20%,rgba(255,255,255,0.30),transparent 22%),
    linear-gradient(135deg,#5b8cff,#185cff);
  border-color:rgba(140,170,255,0.45);
  box-shadow:0 10px 28px rgba(42,111,255,0.30);
}

.canvas3d {
  width:100%;
  height:100%;
  display:block;
  background:radial-gradient(circle at 50% 20%,#101827,#060910 70%);
}

.camera-buttons {
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:8px;
  margin:8px 0 16px;
}

.mini-btn {
  border:1px solid rgba(255,255,255,0.08);
  background:linear-gradient(180deg,rgba(255,255,255,0.065),rgba(255,255,255,0.025));
  color:rgba(255,255,255,0.72);
  padding:9px 8px;
  border-radius:12px;
  cursor:pointer;
  font-family:'Outfit';
  font-size:11px;
  font-weight:900;
}

.mini-btn:hover {
  color:white;
  background:rgba(255,255,255,0.09);
}

@media (max-width: 1100px) {
  .sb {
    grid-template-columns:repeat(2,1fr);
  }

  .sp {
    width:280px;
  }

  .hdr,
  .rp {
    width:calc(100% - 28px);
  }
}
</style>
</head>

<body>
<div class="hdr">
  <div class="logo-g">
    <div class="logo-i">W</div>
    <div>
      <div class="logo-t">Warehouse Optimizer</div>
      <div class="logo-s">HackUPC 2026 · Mecalux Challenge</div>
    </div>
  </div>
  <div id="ha"></div>
</div>

<div id="app"></div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script src="/static/js/warehouse3d.js"></script>

<script>
const S={
  step:'upload',
  files:{warehouse:null,obstacles:null,ceiling:null,bays:null},
  result:null,
  showGaps:true,
  showCeiling:true,
  viewMode:'2d'
};

const BC=[
  'rgba(255,107,53,0.55)',
  'rgba(0,150,255,0.55)',
  'rgba(46,213,115,0.55)',
  'rgba(255,71,87,0.55)',
  'rgba(165,94,234,0.55)',
  'rgba(255,215,0,0.55)',
  'rgba(0,210,211,0.55)',
  'rgba(255,159,243,0.55)'
];

const BB=[
  '#ff6b35',
  '#0096ff',
  '#2ed573',
  '#ff4757',
  '#a55eea',
  '#ffd700',
  '#00d2d3',
  '#ff9ff3'
];

const EX={
warehouse:'0, 0\n10000, 0\n10000, 3000\n3000, 3000\n3000, 10000\n0, 10000',
obstacles:'750, 750, 750, 750\n8000, 2500, 1500, 300\n1500, 4200, 200, 4600',
ceiling:'0, 3000\n3000, 2000\n6000, 3000',
bays:'0, 800, 1200, 2800, 200, 4, 2000\n1, 1600, 1200, 2800, 200, 8, 2500\n2, 2400, 1200, 2800, 200, 12, 2800\n3, 800, 1000, 1800, 150, 3, 1800\n4, 1600, 1000, 1800, 150, 6, 2300\n5, 2400, 1000, 1800, 150, 9, 2600'
};

window.setViewMode = (mode) => {
  S.viewMode = mode;
  render();
};

function render(){
  const a=document.getElementById('app');
  const h=document.getElementById('ha');

  if(S.step==='upload'){
    h.innerHTML='';
    a.innerHTML=renderUpload();
    bindUpload();
  }
  else if(S.step==='solving'){
    h.innerHTML='';
    a.innerHTML='<div class="sv-pg ai"><div class="spin"></div><div style="font-size:22px;font-weight:800">Optimizing placement...</div><div style="color:var(--dim);font-size:14px;animation:pu 1.5s infinite">Running gap-aware multi-pass solver</div></div>';
  }
  else if(S.step==='result'){
    h.innerHTML='<button class="btn btn-g btn-sm" onclick="resetApp()">↺ New</button> <button class="btn btn-p btn-sm" onclick="dlCSV()">↓ Download CSV</button>';
    a.innerHTML=renderResult();
    bindResult();
  }
}

function renderUpload(){
  const zs=[
    {k:'warehouse',i:'⬡',l:'Warehouse',d:'Polygon vertices'},
    {k:'obstacles',i:'⊘',l:'Obstacles',d:'Blocked areas'},
    {k:'ceiling',i:'△',l:'Ceiling',d:'Height profile'},
    {k:'bays',i:'▦',l:'Bay Types',d:'Available racks'}
  ];

  const ok = Object.values(S.files).every(v => v !== null);

  return `<div class="up-pg ai">
    <div class="up-t">Drop your warehouse files</div>
    <div class="up-s">Upload the 4 CSV files to optimize bay placement</div>

    <div class="up-gr">
      ${zs.map(z=>{
        const loaded = S.files[z.k] !== null;
        return `<div class="dz ${loaded?'ok':''}" id="z-${z.k}" ondragover="event.preventDefault()" ondrop="hDrop(event,'${z.k}')">
          <input type="file" accept=".csv,.txt" id="f-${z.k}" style="display:none" onchange="hFile('${z.k}',this)">
          <div class="ic">${loaded?'✓':z.i}</div>
          <div class="lb" style="color:${loaded?'var(--ok)':'var(--txt)'}">${z.l}</div>
          <div class="ds">${loaded?'Loaded ✓':z.d}</div>
        </div>`;
      }).join('')}
    </div>

    <div class="up-ac">
      <button class="btn btn-p" ${ok?'':'disabled'} onclick="go()">⚡ Optimize Warehouse</button>
      <button class="btn btn-g btn-sm" onclick="ldEx()">Load Example Data</button>
    </div>
  </div>`;
}

function bindUpload(){
  ['warehouse','obstacles','ceiling','bays'].forEach(k=>{
    const z=document.getElementById('z-'+k);
    if(z)z.addEventListener('click',()=>document.getElementById('f-'+k).click());
  });
}

window.hDrop=(e,k)=>{
  e.preventDefault();
  const f=e.dataTransfer.files[0];
  if(f)f.text().then(t=>{S.files[k]=t;render();});
};

window.hFile=(k,inp)=>{
  const f=inp.files[0];
  if(f)f.text().then(t=>{S.files[k]=t;render();});
};

window.ldEx=()=>{
  S.files={...EX};
  render();
};

window.go=async()=>{
  S.step='solving';
  render();

  try{
    const fd=new FormData();

    const warehouseText = (S.files.warehouse || '').trim();
    const obstaclesText = (S.files.obstacles || '').trim();
    const ceilingText = (S.files.ceiling || '').trim();
    const baysText = (S.files.bays || '').trim();

    fd.append('warehouse', warehouseText);
    fd.append('obstacles', obstaclesText === '' ? ' ' : obstaclesText);
    fd.append('ceiling', ceilingText);
    fd.append('bays', baysText);

    const r=await fetch('/api/solve-text',{method:'POST',body:fd});
    const d=await r.json();

    if(d.success){
      S.result=d;
      S.step='result';
    }else{
      alert('Error: ' + (d.error || JSON.stringify(d.detail) || 'Unknown error'));
      S.step='upload';
    }
  }catch(e){
    alert('Error: '+e.message);
    S.step='upload';
  }

  render();
};

function renderResult(){
  const r=S.result;
  const s=r.stats;

  return `<div class="rp ai">
    <div class="sb">
      <div class="sc"><div class="sv">${s.totalBays}</div><div class="sl">Bays Placed</div></div>
      <div class="sc"><div class="sv">${s.totalLoads}</div><div class="sl">Total Loads</div></div>
      <div class="sc"><div class="sv">${s.areaUsage.toFixed(1)}%</div><div class="sl">Area Usage</div></div>
      <div class="sc"><div class="sv">${s.score.toFixed(2)}</div><div class="sl">Q Score</div></div>
      <div class="sc"><div class="sv">${s.solveTime}s</div><div class="sl">Solve Time</div></div>
    </div>

    <div class="ma">
      <div class="vc"><div class="vf" id="vz"></div></div>

      <div class="sp">
        <div class="sh">View Mode</div>
        <div class="view-tabs">
          <button class="view-tab ${S.viewMode==='2d'?'active':''}" onclick="setViewMode('2d')">2D Map</button>
          <button class="view-tab ${S.viewMode==='3d'?'active':''}" onclick="setViewMode('3d')">3D Rack</button>
        </div>

        <div class="sh">Controls</div>
        <label class="tgl"><input type="checkbox" ${S.showGaps?'checked':''} onchange="S.showGaps=this.checked;bindResult()"> Show gap zones</label>
        <label class="tgl"><input type="checkbox" ${S.showCeiling?'checked':''} onchange="S.showCeiling=this.checked;bindResult()"> Show ceiling zones</label>

        <div class="camera-buttons" style="display:${S.viewMode==='3d'?'grid':'none'}">
          <button class="mini-btn" onclick="set3DCamera('iso')">Iso View</button>
          <button class="mini-btn" onclick="set3DCamera('top')">Top View</button>
        </div>

        <div class="sh" style="margin-top:18px">Bay Types Legend</div>
        ${r.bayTypes.map(bt=>{
          const c=r.placed.filter(p=>p.id===bt.id).length;
          const ci=bt.id%BC.length;
          return `<div class="li">
            <div class="tp">
              <span class="ld" style="background:${BB[ci]}; color:${BB[ci]}"></span>
              <span style="font-weight:800;font-size:14px">Type ${bt.id}</span>
              <span style="margin-left:auto;font-family:'JetBrains Mono';font-size:13px;color:${BB[ci]}">×${c}</span>
            </div>
            <div class="mt">${bt.w}×${bt.d}×${bt.h} | gap:${bt.gap} | ${bt.nLoads}L | $${bt.price}</div>
          </div>`;
        }).join('')}

        <div class="sh" style="margin-top:22px">Output CSV</div>
        <div class="co">${r.csv}</div>
      </div>
    </div>
  </div>`;
}

function bindResult(){
  if(!S.result)return;

  if(S.viewMode === '3d'){
    render3D(S.result);
  }else{
    destroy3D();
    bindResult2D();
  }
}

function bindResult2D(){
  const f=document.getElementById('vz');
  if(!f||!S.result)return;

  const r=S.result;
  const wh=r.warehouse;

  let x0=Infinity,y0=Infinity,x1=-Infinity,y1=-Infinity;
  wh.forEach(v=>{
    x0=Math.min(x0,v.x);
    y0=Math.min(y0,v.y);
    x1=Math.max(x1,v.x);
    y1=Math.max(y1,v.y);
  });

  const ww=x1-x0;
  const hh=y1-y0;
  const pad=Math.max(ww,hh)*0.05;
  const pts=wh.map(v=>`${v.x},${v.y}`).join(' ');
  const sw=Math.max(8,ww/200);

  let svg=`<svg viewBox="${x0-pad} ${y0-pad} ${ww+pad*2} ${hh+pad*2}" style="width:100%;height:100%;background:#080c14" xmlns="http://www.w3.org/2000/svg">`;

  svg+=`
    <defs>
      <pattern id="gridPattern" width="${Math.max(100,ww/60)}" height="${Math.max(100,hh/60)}" patternUnits="userSpaceOnUse">
        <path d="M ${Math.max(100,ww/60)} 0 L 0 0 0 ${Math.max(100,hh/60)}" fill="none" stroke="rgba(255,255,255,0.035)" stroke-width="${Math.max(1,ww/1400)}"/>
      </pattern>

      <filter id="warehouseGlow">
        <feGaussianBlur stdDeviation="${ww*0.003}" result="blur"/>
        <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>

      <filter id="rackShadow">
        <feDropShadow dx="${ww/900}" dy="${ww/900}" stdDeviation="${ww/900}" flood-color="#000000" flood-opacity="0.55"/>
      </filter>

      <clipPath id="warehouseClip">
        <polygon points="${pts}" />
      </clipPath>
    </defs>
  `;

  svg+=`<rect x="${x0-pad}" y="${y0-pad}" width="${ww+pad*2}" height="${hh+pad*2}" fill="url(#gridPattern)"/>`;

  svg+=`
    <polygon points="${pts}"
      fill="rgba(17,27,44,0.92)"
      stroke="#4c78ff"
      stroke-width="${sw}"
      filter="url(#warehouseGlow)"/>
  `;

  svg+=`
    <polygon points="${pts}"
      fill="none"
      stroke="rgba(255,255,255,0.28)"
      stroke-width="${Math.max(1,ww/900)}"
      stroke-dasharray="${ww/180} ${ww/260}"
      opacity="0.75"/>
  `;

  svg+=`
    <polygon points="${pts}"
      fill="rgba(255,255,255,0.025)"
      stroke="none"/>
  `;

  function polyPts(coords){
    return coords.map(c=>c[0]+','+c[1]).join(' ');
  }

  function centroid(coords){
    let cx=0,cy=0;
    for(const c of coords){
      cx+=c[0];
      cy+=c[1];
    }
    return [cx/coords.length, cy/coords.length];
  }

  function bbox(coords){
    let bx0=Infinity,by0=Infinity,bx1=-Infinity,by1=-Infinity;
    for(const c of coords){
      bx0=Math.min(bx0,c[0]);
      by0=Math.min(by0,c[1]);
      bx1=Math.max(bx1,c[0]);
      by1=Math.max(by1,c[1]);
    }
    return {x0:bx0,y0:by0,x1:bx1,y1:by1,w:bx1-bx0,h:by1-by0};
  }

  function drawCeilingBaseLayer(){
    if(!S.showCeiling || !r.ceiling || r.ceiling.length===0)return '';

    const ceiling=[...r.ceiling].sort((a,b)=>a.x-b.x);
    const ceilingColors=[
      'rgba(42,111,255,0.15)',
      'rgba(46,213,115,0.15)',
      'rgba(255,215,0,0.15)',
      'rgba(255,107,53,0.15)',
      'rgba(165,94,234,0.15)'
    ];

    let out='';

    for(let i=0;i<ceiling.length;i++){
      const startX=Math.max(ceiling[i].x,x0);
      const endX=i<ceiling.length-1?Math.min(ceiling[i+1].x,x1):x1;
      const width=endX-startX;
      if(width<=0)continue;

      const hVal=ceiling[i].h;
      const color=ceilingColors[i%ceilingColors.length];

      out+=`
        <rect x="${startX}" y="${y0}" width="${width}" height="${hh}"
          fill="${color}"
          stroke="rgba(255,255,255,0.10)"
          stroke-width="${Math.max(1,ww/900)}"
          clip-path="url(#warehouseClip)"
        />
      `;

      out+=`
        <line x1="${startX}" y1="${y0}" x2="${startX}" y2="${y1}"
          stroke="rgba(255,255,255,0.20)"
          stroke-width="${Math.max(1,ww/700)}"
          stroke-dasharray="${ww/250} ${ww/300}"
          clip-path="url(#warehouseClip)"
        />
      `;

      const labelX=startX+width/2;
      const labelY=y0+hh*0.055;

      out+=`
        <text x="${labelX}" y="${labelY}"
          text-anchor="middle"
          dominant-baseline="central"
          fill="rgba(255,255,255,0.78)"
          font-weight="900"
          font-size="${Math.max(75,ww/110)}"
          style="pointer-events:none;text-shadow:0 2px 5px rgba(0,0,0,0.9);"
        >${hVal} mm</text>
      `;
    }

    out+=`
      <line x1="${x1}" y1="${y0}" x2="${x1}" y2="${y1}"
        stroke="rgba(255,255,255,0.16)"
        stroke-width="${Math.max(1,ww/700)}"
        stroke-dasharray="${ww/250} ${ww/300}"
        clip-path="url(#warehouseClip)"
      />
    `;

    return out;
  }

  function drawCeilingGlassLayer(){
    if(!S.showCeiling || !r.ceiling || r.ceiling.length===0)return '';

    const ceiling=[...r.ceiling].sort((a,b)=>a.x-b.x);
    let out='';

    for(let i=0;i<ceiling.length;i++){
      const startX=Math.max(ceiling[i].x,x0);
      const endX=i<ceiling.length-1?Math.min(ceiling[i+1].x,x1):x1;
      const width=endX-startX;
      if(width<=0)continue;

      out+=`
        <rect x="${startX}" y="${y0}" width="${width}" height="${hh}"
          fill="rgba(255,255,255,0.035)"
          stroke="rgba(255,255,255,0.13)"
          stroke-width="${Math.max(1,ww/1200)}"
          clip-path="url(#warehouseClip)"
        />
      `;
    }

    return out;
  }

  function drawRack2D(b, coords, ci, idx){
    const bb=bbox(coords);
    const clipId=`clip-rack-${idx}`;
    const patternId=`pattern-rack-${idx}`;

    const strokeW=Math.max(2,ww/650);
    const innerW=Math.max(1,ww/1600);

    const x=bb.x0;
    const y=bb.y0;
    const w=bb.w;
    const h=bb.h;
    const ctr=centroid(coords);

    let out='';
    const isHorizontal=w>=h;
    const spacing=Math.max(70,Math.min(w,h)/5);

    out+=`
      <defs>
        <clipPath id="${clipId}">
          <polygon points="${polyPts(coords)}"/>
        </clipPath>

        <pattern id="${patternId}" patternUnits="userSpaceOnUse" width="${spacing}" height="${spacing}">
          <path d="M 0 0 L ${spacing} 0" stroke="rgba(255,255,255,0.42)" stroke-width="${innerW}"/>
          <path d="M 0 ${spacing/2} L ${spacing} ${spacing/2}" stroke="rgba(255,255,255,0.22)" stroke-width="${innerW}"/>
        </pattern>
      </defs>
    `;

    out+=`
      <polygon points="${polyPts(coords)}"
        fill="rgba(0,0,0,0.28)"
        stroke="rgba(0,0,0,0.15)"
        stroke-width="${strokeW*2}"
        transform="translate(${strokeW*0.9},${strokeW*0.9})"
        opacity="0.65"/>
    `;

    out+=`
      <polygon points="${polyPts(coords)}"
        fill="${BC[ci].replace('0.55','0.36')}"
        stroke="${BB[ci]}"
        stroke-width="${strokeW}"
        filter="url(#rackShadow)"
        style="cursor:pointer">
        <title>Bay #${b.id} | ${b.w}×${b.d}×${b.h} | rot=${b.rotation}° | ${b.nLoads} loads | $${b.price}</title>
      </polygon>
    `;

    out+=`
      <polygon points="${polyPts(coords)}"
        fill="url(#${patternId})"
        opacity="0.34"
        clip-path="url(#${clipId})"/>
    `;

    if(isHorizontal){
      const rows=Math.max(4,Math.floor(h/Math.max(110,h/8)));
      for(let k=1;k<rows;k++){
        const yy=y+(h*k/rows);
        out+=`<line x1="${x}" y1="${yy}" x2="${x+w}" y2="${yy}"
          stroke="rgba(220,240,255,0.58)" stroke-width="${innerW}"
          clip-path="url(#${clipId})"/>`;
      }

      const cols=Math.max(5,Math.floor(w/Math.max(130,w/12)));
      for(let k=1;k<cols;k++){
        const xx=x+(w*k/cols);
        out+=`<line x1="${xx}" y1="${y}" x2="${xx}" y2="${y+h}"
          stroke="rgba(220,240,255,0.26)" stroke-width="${innerW}"
          clip-path="url(#${clipId})"/>`;
      }
    }else{
      const cols=Math.max(4,Math.floor(w/Math.max(110,w/8)));
      for(let k=1;k<cols;k++){
        const xx=x+(w*k/cols);
        out+=`<line x1="${xx}" y1="${y}" x2="${xx}" y2="${y+h}"
          stroke="rgba(220,240,255,0.58)" stroke-width="${innerW}"
          clip-path="url(#${clipId})"/>`;
      }

      const rows=Math.max(5,Math.floor(h/Math.max(130,h/12)));
      for(let k=1;k<rows;k++){
        const yy=y+(h*k/rows);
        out+=`<line x1="${x}" y1="${yy}" x2="${x+w}" y2="${yy}"
          stroke="rgba(220,240,255,0.26)" stroke-width="${innerW}"
          clip-path="url(#${clipId})"/>`;
      }
    }

    const support=Math.max(35,Math.min(w,h)*0.08);

    if(isHorizontal){
      out+=`<rect x="${x}" y="${y}" width="${support}" height="${h}" fill="rgba(15,23,42,0.62)" clip-path="url(#${clipId})"/>`;
      out+=`<rect x="${x+w-support}" y="${y}" width="${support}" height="${h}" fill="rgba(15,23,42,0.62)" clip-path="url(#${clipId})"/>`;
    }else{
      out+=`<rect x="${x}" y="${y}" width="${w}" height="${support}" fill="rgba(15,23,42,0.62)" clip-path="url(#${clipId})"/>`;
      out+=`<rect x="${x}" y="${y+h-support}" width="${w}" height="${support}" fill="rgba(15,23,42,0.62)" clip-path="url(#${clipId})"/>`;
    }

    out+=`
      <text x="${ctr[0]}" y="${ctr[1]}"
        text-anchor="middle"
        dominant-baseline="central"
        fill="white"
        font-weight="900"
        font-size="${Math.max(70,Math.min(w,h)*0.26)}"
        style="pointer-events:none;text-shadow:0 2px 6px rgba(0,0,0,0.95)"
      >${b.id}</text>
    `;

    if(Math.min(w,h)>ww*0.035){
      out+=`
        <text x="${ctr[0]}" y="${ctr[1]+Math.max(70,Math.min(w,h)*0.26)}"
          text-anchor="middle"
          dominant-baseline="central"
          fill="rgba(255,255,255,0.72)"
          font-weight="800"
          font-size="${Math.max(35,Math.min(w,h)*0.105)}"
          style="pointer-events:none;text-shadow:0 2px 5px rgba(0,0,0,0.9)"
        >${Math.round(b.h)} mm</text>
      `;
    }

    return out;
  }

  svg+=drawCeilingBaseLayer();

  r.obstacles.forEach((o,i)=>{
    svg+=`
      <defs>
        <pattern id="obsPattern-${i}" width="${ww/120}" height="${ww/120}" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="${ww/120}" stroke="rgba(255,100,100,0.28)" stroke-width="${Math.max(2,ww/900)}"/>
        </pattern>
      </defs>

      <rect x="${o.x}" y="${o.y}" width="${o.w}" height="${o.d}"
        fill="rgba(255,50,50,0.20)"
        stroke="#ff4d4d"
        stroke-width="${Math.max(3,ww/500)}"
        stroke-dasharray="${ww/100} ${ww/200}"/>

      <rect x="${o.x}" y="${o.y}" width="${o.w}" height="${o.d}"
        fill="url(#obsPattern-${i})"
        opacity="0.75"/>

      <line x1="${o.x}" y1="${o.y}" x2="${o.x+o.w}" y2="${o.y+o.d}" stroke="rgba(255,80,80,0.22)" stroke-width="${Math.max(2,ww/600)}"/>
      <line x1="${o.x+o.w}" y1="${o.y}" x2="${o.x}" y2="${o.y+o.d}" stroke="rgba(255,80,80,0.22)" stroke-width="${Math.max(2,ww/600)}"/>
    `;
  });

  if(S.showGaps){
    r.placed.forEach((b)=>{
      if(b.gapCoords&&b.gapCoords.length>2){
        svg+=`
          <polygon points="${polyPts(b.gapCoords)}"
            fill="rgba(160,210,255,0.075)"
            stroke="rgba(180,230,255,0.24)"
            stroke-width="${Math.max(1,ww/700)}"
            stroke-dasharray="${ww/260} ${ww/320}"/>
        `;
      }
    });
  }

  r.placed.forEach((b,i)=>{
    const ci=b.id%BC.length;
    const coords=b.footprintCoords;
    if(!coords||coords.length<3)return;
    svg+=drawRack2D(b,coords,ci,i);
  });

  svg+=drawCeilingGlassLayer();

  svg+='</svg>';
  f.innerHTML=svg;
}

window.resetApp=()=>{
  destroy3D();
  S.step='upload';
  S.files={warehouse:null,obstacles:null,ceiling:null,bays:null};
  S.result=null;
  S.viewMode='2d';
  render();
};

window.dlCSV=()=>{
  if(!S.result)return;
  const b=new Blob([S.result.csv],{type:'text/csv'});
  const u=URL.createObjectURL(b);
  const a=document.createElement('a');
  a.href=u;
  a.download='solution.csv';
  a.click();
  URL.revokeObjectURL(u);
};

render();
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return FRONTEND_HTML


if __name__ == "__main__":
    print("\n🏭 Warehouse Optimizer — HackUPC 2026")
    print("   Open http://localhost:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)