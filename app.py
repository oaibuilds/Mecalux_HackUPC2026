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
            placed, stats = solve_parallel(wh, obs, ceil, bt, time_limit=29.0)
            return _build_response(placed, stats, wh, obs, ceil, bt, placed_are_dicts=True)

        solver = WarehouseSolver(wh, obs, ceil, bt)
        placed, stats = solver.solve(time_limit=29.0)
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
            placed, stats = solve_parallel(wh, obs, ceil, bt, time_limit=29.0)
            return _build_response(placed, stats, wh, obs, ceil, bt, placed_are_dicts=True)

        solver = WarehouseSolver(wh, obs, ceil, bt)
        placed, stats = solver.solve(time_limit=29.0)
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
<title>Warehouse Optimizer — Mecalux</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">

<style>
/* ─── Reset ───────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:        #f5f5f4;
  --surface:   #ffffff;
  --surface-2: #fafaf9;
  --border:    #e5e5e4;
  --border-2:  #d4d4d3;
  --text-1:    #1a1a19;
  --text-2:    #525251;
  --text-3:    #8a8a88;
  --accent:    #1d4ed8;
  --danger:    #b91c1c;
  --success:   #15803d;
  --radius:    3px;
  --font:      'Inter', system-ui, -apple-system, sans-serif;
}

html {
  min-height: 100%;
  background: #f5f5f4;
}

body {
  font-family: var(--font);
  color: var(--text-1);
  font-size: 13px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  min-height: 100vh;
  position: relative;
  overflow-x: hidden;
  background: transparent;
}

/* Global warehouse background, behind all UI */
body::before {
  content: "";
  position: fixed;
  inset: 0;
  z-index: -2;
  background:
    url("/static/img/rack-bg.png") center center / cover no-repeat fixed;
  filter: blur(5px) brightness(1.18) saturate(0.75);
  transform: scale(1.03);
  pointer-events: none;
}

/* Soft white layer to make the background brighter and less visible */
body::after {
  content: "";
  position: fixed;
  inset: 0;
  z-index: -1;
  background: rgba(255,255,255,0.72);
  pointer-events: none;
}

/* ─── Header ──────────────────────────────────────────────── */
.header {
  height: 52px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 24px;
  gap: 16px;
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-logo svg { height: 20px; width: auto; display: block; }

.header-sep {
  width: 1px;
  height: 16px;
  background: var(--border);
  flex-shrink: 0;
}

.header-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-2);
}

.header-spacer { flex: 1; }

.header-actions { display: flex; align-items: center; gap: 8px; }

/* ─── Buttons ─────────────────────────────────────────────── */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 0 14px;
  height: 32px;
  font-family: var(--font);
  font-size: 13px;
  font-weight: 500;
  border-radius: var(--radius);
  border: 1px solid transparent;
  cursor: pointer;
  transition: background 0.1s, border-color 0.1s;
  white-space: nowrap;
  line-height: 1;
}

.btn-primary {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}
.btn-primary:hover:not(:disabled) { background: #1e40af; }
.btn-primary:disabled { opacity: 0.35; cursor: not-allowed; }

.btn-default {
  background: var(--surface);
  color: var(--text-1);
  border-color: var(--border-2);
}
.btn-default:hover { background: var(--surface-2); border-color: var(--text-3); }

.btn-ghost {
  background: transparent;
  color: var(--text-2);
  border-color: transparent;
}
.btn-ghost:hover { background: var(--bg); color: var(--text-1); }

/* ─── Upload view ─────────────────────────────────────────── */
.upload-view {
  max-width: 680px;
  margin: 60px auto 0;
  padding: 0 24px 60px;
}

.upload-eyebrow {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-3);
  margin-bottom: 8px;
}

.upload-title {
  font-size: 21px;
  font-weight: 600;
  color: var(--text-1);
  letter-spacing: -0.015em;
  margin-bottom: 4px;
}

.upload-desc {
  font-size: 13px;
  color: var(--text-2);
  margin-bottom: 32px;
}

.upload-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 20px;
}

.dropzone {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px 20px;
  cursor: pointer;
  transition: border-color 0.1s, background 0.1s;
  user-select: none;
}

.dropzone:hover { border-color: var(--accent); }

.dropzone.loaded {
  border-color: #86efac;
  background: #f0fdf4;
}

.dz-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 3px;
}

.dz-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-1);
}

.dz-badge {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--success);
}

.dz-desc { font-size: 12px; color: var(--text-3); }

.dz-cta {
  font-size: 12px;
  color: var(--accent);
  margin-top: 8px;
}

/* Rack visual on upload page */
.rack-vis {
  width: 180px;
  margin: 0 auto 32px;
  position: relative;
}

.rack-frame {
  position: relative;
  height: 140px;
  border-left: 3px solid var(--border-2);
  border-right: 3px solid var(--border-2);
  display: flex;
  flex-direction: column-reverse;
  gap: 0;
}

.rack-shelf {
  flex: 1;
  border-top: 2px solid var(--border-2);
  position: relative;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: 0 8px 3px;
}

.rack-pallet {
  width: 100%;
  height: calc(100% - 5px);
  border-radius: 2px;
  opacity: 0;
  transform: scaleX(0);
  transition: all 0.45s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.rack-pallet.from-left  { transform-origin: left center; }
.rack-pallet.from-right { transform-origin: right center; }

.rack-pallet.in {
  opacity: 1;
  transform: scaleX(1);
}

.rack-pallet:nth-child(1) { background: var(--accent); }
.rack-pallet:nth-child(1).in { background: #3b82f6; }
.rack-shelf:nth-child(2) .rack-pallet.in { background: #8b5cf6; }
.rack-shelf:nth-child(3) .rack-pallet.in { background: #f59e0b; }
.rack-shelf:nth-child(4) .rack-pallet.in { background: #10b981; }

.rack-base {
  width: calc(100% + 16px);
  height: 3px;
  background: var(--border-2);
  margin: 0 -8px;
  border-radius: 0 0 2px 2px;
}

.upload-footer { display: flex; align-items: center; gap: 10px; }

/* ─── Solving / loading ───────────────────────────────────── */
.solving-view {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: calc(100vh - 52px);
  gap: 20px;
}

/* Stacking boxes animation */
.stack-wrap {
  display: flex;
  flex-direction: column-reverse;
  align-items: center;
  height: 88px;
  gap: 3px;
  overflow: hidden;
}

.s-box {
  width: 44px;
  height: 13px;
  background: var(--accent);
  border-radius: 2px;
  opacity: 0;
}

.s-box:nth-child(1) { animation: stkL 3.2s 0.00s ease infinite; }
.s-box:nth-child(2) { animation: stkR 3.2s 0.40s ease infinite; }
.s-box:nth-child(3) { animation: stkL 3.2s 0.80s ease infinite; }
.s-box:nth-child(4) { animation: stkR 3.2s 1.20s ease infinite; }

@keyframes stkL {
  0%   { opacity: 0; transform: translateX(-40px); }
  8%   { opacity: 1; transform: translateX(0); }
  62%  { opacity: 1; transform: translateX(0); }
  75%  { opacity: 0; transform: translateX(0); }
  100% { opacity: 0; transform: translateX(-40px); }
}

@keyframes stkR {
  0%   { opacity: 0; transform: translateX(40px); }
  8%   { opacity: 1; transform: translateX(0); }
  62%  { opacity: 1; transform: translateX(0); }
  75%  { opacity: 0; transform: translateX(0); }
  100% { opacity: 0; transform: translateX(40px); }
}

.solving-text {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-1);
}

.solving-sub {
  font-size: 12px;
  color: var(--text-3);
  margin-top: -12px;
}

/* ─── Result layout ───────────────────────────────────────── */
.result-view {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 52px);
}

/* Metrics */
.metrics-bar {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  display: flex;
  flex-shrink: 0;
}

.metric {
  flex: 1;
  padding: 12px 20px 14px;
  border-right: 1px solid var(--border);
}
.metric:last-child { border-right: none; }

.metric-val {
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--text-1);
  line-height: 1.1;
}

.metric-key {
  font-size: 11px;
  color: var(--text-3);
  margin-top: 3px;
}

/* Body */
.result-body {
  flex: 1;
  display: flex;
  min-height: 0;
}

/* Viz */
.viz-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
}

.viz-toolbar {
  height: 40px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.view-seg {
  display: flex;
  border: 1px solid var(--border-2);
  border-radius: var(--radius);
  overflow: hidden;
}

.vsb {
  height: 28px;
  padding: 0 14px;
  font-family: var(--font);
  font-size: 12px;
  font-weight: 500;
  background: transparent;
  color: var(--text-2);
  border: none;
  border-right: 1px solid var(--border-2);
  cursor: pointer;
  transition: background 0.1s, color 0.1s;
}
.vsb:last-child { border-right: none; }
.vsb:hover:not(.active) { background: var(--bg); color: var(--text-1); }
.vsb.active { background: var(--accent); color: #fff; }

.viz-sp { flex: 1; }

.viz-frame {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  position: relative;
  background: transparent;
}

.canvas3d { width: 100%; height: 100%; display: block; }

/* Sidebar */
.sidebar {
  width: 272px;
  flex-shrink: 0;
  background: var(--surface);
  border-left: 1px solid var(--border);
  overflow-y: auto;
}

.sb-block {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}
.sb-block:last-child { border-bottom: none; }

.sb-head {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--text-3);
  margin-bottom: 12px;
}

/* Toggle */
.tgl-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0;
}

.tgl-label { font-size: 13px; color: var(--text-1); }

.tgl {
  position: relative;
  width: 32px;
  height: 18px;
  flex-shrink: 0;
}

.tgl input { opacity: 0; position: absolute; width: 0; height: 0; }

.tgl-track {
  position: absolute;
  inset: 0;
  background: var(--border-2);
  border-radius: 9px;
  cursor: pointer;
  transition: background 0.14s;
}

.tgl input:checked ~ .tgl-track { background: var(--accent); }

.tgl-track::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 14px;
  height: 14px;
  background: #fff;
  border-radius: 50%;
  transition: transform 0.14s;
}

.tgl input:checked ~ .tgl-track::after { transform: translateX(14px); }

/* Camera buttons */
.cam-row {
  display: flex;
  gap: 6px;
  margin-top: 10px;
}

.cam-btn {
  flex: 1;
  height: 28px;
  font-family: var(--font);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-2);
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  cursor: pointer;
  transition: background 0.1s, color 0.1s;
}
.cam-btn:hover { background: var(--bg); color: var(--text-1); }

/* Bay table */
.bay-tbl { width: 100%; border-collapse: collapse; }

.bay-tbl tr { border-bottom: 1px solid var(--border); }
.bay-tbl tr:last-child { border-bottom: none; }

.bay-tbl td { padding: 8px 0; font-size: 12px; vertical-align: top; }

.bay-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 1px;
  margin-right: 6px;
  vertical-align: middle;
  position: relative;
  top: -1px;
  flex-shrink: 0;
}

.bay-id { font-weight: 600; color: var(--text-1); font-size: 13px; }

.bay-spec {
  font-size: 11px;
  color: var(--text-3);
  margin-top: 2px;
  font-variant-numeric: tabular-nums;
}

.bay-ct {
  text-align: right;
  font-size: 12px;
  color: var(--text-3);
  padding-left: 8px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

/* CSV */
.csv-pre {
  font-family: 'SFMono-Regular', 'Consolas', 'Menlo', monospace;
  font-size: 11px;
  color: var(--text-2);
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 10px 12px;
  max-height: 180px;
  overflow-y: auto;
  white-space: pre;
  line-height: 1.55;
}


/* ─── Global glass / background integration ─────────────────── */
.header,
.metrics-bar,
.viz-toolbar,
.sidebar,
.dropzone,
.csv-pre {
  background: rgba(255,255,255,0.78);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.result-view,
.result-body,
.viz-pane,
.viz-frame,
.solving-view,
.upload-view {
  background: transparent;
}

.sb-block {
  background: transparent;
}

.btn-default,
.cam-btn {
  background: rgba(255,255,255,0.72);
}

.viz-frame {
  background: transparent;
}
.custom-tooltip {
  position: fixed;
  z-index: 9999;
  max-width: 260px;
  padding: 10px 12px;
  background: rgba(20, 24, 32, 0.92);
  color: white;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.45;
  pointer-events: none;
  opacity: 0;
  transform: translate(12px, 12px);
  transition: opacity 0.08s ease;
  box-shadow: 0 8px 24px rgba(0,0,0,0.18);
}

.custom-tooltip.visible {
  opacity: 1;
}
</style>
</head>
<body>

<header class="header">
  <div class="header-logo">
    <svg viewBox="0 0 180 28" fill="none" xmlns="http://www.w3.org/2000/svg">
      <!-- Blue shield block -->
      <rect width="26" height="28" rx="2" fill="#1d4ed8"/>
      <!-- Stylised M paths inside shield -->
      <polyline points="5,22 5,7 13,16 21,7 21,22" stroke="white" stroke-width="2.5"
        stroke-linecap="round" stroke-linejoin="round" fill="none"/>
      <!-- MECALUX wordmark -->
      <text x="34" y="20" font-family="'Inter',system-ui,sans-serif"
        font-size="13.5" font-weight="700" fill="#1a1a19" letter-spacing="1.8">MECALUX</text>
    </svg>
  </div>
  <div class="header-sep"></div>
  <span class="header-title">Warehouse Optimizer</span>
  <div class="header-spacer"></div>
  <div class="header-actions" id="ha"></div>
</header>

<div id="app"></div>
<div id="tooltip" class="custom-tooltip"></div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script src="/static/js/warehouse3d.js"></script>

<script>
const S = {
  step: 'upload',
  files: { warehouse: null, obstacles: null, ceiling: null, bays: null },
  result: null,
  showGaps: true,
  showCeiling: true,
  viewMode: '2d'
};

const SWATCH = [
  '#2563eb','#d97706','#16a34a','#dc2626',
  '#7c3aed','#0891b2','#be185d','#65a30d'
];

const EX = {
  warehouse: '0, 0\n10000, 0\n10000, 3000\n3000, 3000\n3000, 10000\n0, 10000',
  obstacles:  '750, 750, 750, 750\n8000, 2500, 1500, 300\n1500, 4200, 200, 4600',
  ceiling:    '0, 3000\n3000, 2000\n6000, 3000',
  bays:       '0, 800, 1200, 2800, 200, 4, 2000\n1, 1600, 1200, 2800, 200, 8, 2500\n2, 2400, 1200, 2800, 200, 12, 2800\n3, 800, 1000, 1800, 150, 3, 1800\n4, 1600, 1000, 1800, 150, 6, 2300\n5, 2400, 1000, 1800, 150, 9, 2600'
};

window.setViewMode = (m) => { S.viewMode = m; render(); };

/* ─── Render dispatcher ─────────────────────────────────────── */
function render() {
  const app = document.getElementById('app');
  const ha  = document.getElementById('ha');

  if (S.step === 'upload') {
    ha.innerHTML = '';
    app.innerHTML = renderUpload();
    bindUpload();

  } else if (S.step === 'solving') {
    ha.innerHTML = '';
    app.innerHTML = `
      <div class="solving-view">
        <div class="stack-wrap">
          <div class="s-box"></div>
          <div class="s-box"></div>
          <div class="s-box"></div>
          <div class="s-box"></div>
        </div>
        <div class="solving-text">Computing optimal placement</div>
        <div class="solving-sub">Running gap-aware multi-pass solver</div>
      </div>`;

  } else if (S.step === 'result') {
    ha.innerHTML = `
      <button class="btn btn-default" onclick="resetApp()">New analysis</button>
      <button class="btn btn-primary" onclick="dlCSV()">Export CSV</button>`;
    app.innerHTML = renderResult();
    bindResult();
  }
}

/* ─── Upload ────────────────────────────────────────────────── */
const FILES = [
  { k: 'warehouse', name: 'Warehouse',  desc: 'Polygon boundary vertices' },
  { k: 'obstacles', name: 'Obstacles',  desc: 'Blocked area coordinates'  },
  { k: 'ceiling',   name: 'Ceiling',    desc: 'Height profile sections'   },
  { k: 'bays',      name: 'Bay Types',  desc: 'Available rack configurations' }
];

function renderUpload() {
  const ready = Object.values(S.files).every(v => v !== null);
  const loaded = FILES.map(f => S.files[f.k] !== null);
  return `
    <div class="upload-view">
      <div class="upload-eyebrow">HackUPC 2026 — Mecalux Challenge</div>
      <div class="upload-title">Warehouse Optimizer</div>
      <div class="upload-desc">Upload the four configuration files to compute optimal bay placement.</div>

      <div class="rack-vis">
        <div class="rack-frame">
          ${FILES.map((f, i) => {
            const side = i % 2 === 0 ? 'from-left' : 'from-right';
            const on = loaded[i] ? 'in' : '';
            return `<div class="rack-shelf"><div class="rack-pallet ${side} ${on}"></div></div>`;
          }).join('')}
        </div>
        <div class="rack-base"></div>
      </div>

      <div class="upload-grid">
        ${FILES.map(f => {
          const ok = S.files[f.k] !== null;
          return `
            <div class="dropzone ${ok ? 'loaded' : ''}" id="z-${f.k}"
              ondragover="event.preventDefault()"
              ondrop="hDrop(event,'${f.k}')">
              <input type="file" accept=".csv,.txt" id="f-${f.k}"
                style="display:none" onchange="hFile('${f.k}',this)">
              <div class="dz-top">
                <span class="dz-name">${f.name}</span>
                ${ok ? '<span class="dz-badge">Ready</span>' : ''}
              </div>
              <div class="dz-desc">${f.desc}</div>
              ${!ok ? '<div class="dz-cta">Click or drop to upload</div>' : ''}
            </div>`;
        }).join('')}
      </div>

      <div class="upload-footer">
        <button class="btn btn-primary" ${ready ? '' : 'disabled'} onclick="go()">
          Run optimization
        </button>
        <button class="btn btn-ghost" onclick="ldEx()">Load example data</button>
      </div>
    </div>`;
}

function bindUpload() {
  FILES.forEach(f => {
    const z = document.getElementById('z-' + f.k);
    if (z) z.addEventListener('click', () => document.getElementById('f-' + f.k).click());
  });
}

window.hDrop = (e, k) => {
  e.preventDefault();
  const f = e.dataTransfer.files[0];
  if (f) f.text().then(t => { S.files[k] = t; render(); });
};

window.hFile = (k, inp) => {
  const f = inp.files[0];
  if (f) f.text().then(t => { S.files[k] = t; render(); });
};

window.ldEx = () => {
  const order = ['warehouse','obstacles','ceiling','bays'];
  S.files = { warehouse:null, obstacles:null, ceiling:null, bays:null };
  render();
  order.forEach((k, i) => {
    setTimeout(() => { S.files[k] = EX[k]; render(); }, 350 * (i + 1));
  });
};

/* ─── Solve ─────────────────────────────────────────────────── */
window.go = async () => {
  S.step = 'solving'; render();
  try {
    const fd = new FormData();
    fd.append('warehouse', (S.files.warehouse || '').trim());
    const obs = (S.files.obstacles || '').trim();
    fd.append('obstacles', obs === '' ? ' ' : obs);
    fd.append('ceiling', (S.files.ceiling || '').trim());
    fd.append('bays', (S.files.bays || '').trim());

    const res = await fetch('/api/solve-text', { method: 'POST', body: fd });
    const d   = await res.json();

    if (d.success) { S.result = d; S.step = 'result'; }
    else { alert('Error: ' + (d.error || JSON.stringify(d.detail) || 'Unknown')); S.step = 'upload'; }
  } catch(e) {
    alert('Error: ' + e.message); S.step = 'upload';
  }
  render();
};

/* ─── Result ─────────────────────────────────────────────────── */
function renderResult() {
  const r = S.result, s = r.stats;
  return `
    <div class="result-view">

      <div class="metrics-bar">
        <div class="metric">
          <div class="metric-val">${s.totalBays}</div>
          <div class="metric-key">Bays placed</div>
        </div>
        <div class="metric">
          <div class="metric-val">${s.totalLoads}</div>
          <div class="metric-key">Total loads</div>
        </div>
        <div class="metric">
          <div class="metric-val">${s.areaUsage.toFixed(1)}%</div>
          <div class="metric-key">Area usage</div>
        </div>
        <div class="metric">
          <div class="metric-val">${s.score.toFixed(2)}</div>
          <div class="metric-key">Quality score</div>
        </div>
        <div class="metric">
          <div class="metric-val">${s.solveTime}s</div>
          <div class="metric-key">Solve time</div>
        </div>
      </div>

      <div class="result-body">
        <div class="viz-pane">
          <div class="viz-toolbar">
            <div class="view-seg">
              <button class="vsb ${S.viewMode==='2d'?'active':''}" onclick="setViewMode('2d')">2D Plan</button>
              <button class="vsb ${S.viewMode==='3d'?'active':''}" onclick="setViewMode('3d')">3D View</button>
            </div>
            <div class="viz-sp"></div>
          </div>
          <div class="viz-frame" id="vz"></div>
        </div>

        <div class="sidebar">

          <div class="sb-block">
            <div class="sb-head">Display</div>
            <div class="tgl-row">
              <span class="tgl-label">Gap zones</span>
              <label class="tgl">
                <input type="checkbox" ${S.showGaps ? 'checked' : ''}
                  onchange="S.showGaps=this.checked;bindResult()">
                <span class="tgl-track"></span>
              </label>
            </div>
            <div class="tgl-row">
              <span class="tgl-label">Ceiling zones</span>
              <label class="tgl">
                <input type="checkbox" ${S.showCeiling ? 'checked' : ''}
                  onchange="S.showCeiling=this.checked;bindResult()">
                <span class="tgl-track"></span>
              </label>
            </div>
            ${S.viewMode === '3d' ? `
            <div class="cam-row">
              <button class="cam-btn" onclick="set3DCamera('iso')">Isometric</button>
              <button class="cam-btn" onclick="set3DCamera('top')">Top</button>
            </div>` : ''}
          </div>

          <div class="sb-block">
            <div class="sb-head">Bay types</div>
            <table class="bay-tbl">
              ${r.bayTypes.map(bt => {
                const count = r.placed.filter(p => p.id === bt.id).length;
                const sw    = SWATCH[bt.id % SWATCH.length];
                return `<tr>
                  <td>
                    <span class="bay-dot" style="background:${sw}"></span>
                    <span class="bay-id">Type ${bt.id}</span>
                    <div class="bay-spec">${bt.w} x ${bt.d} x ${bt.h} mm &nbsp;·&nbsp; gap ${bt.gap} &nbsp;·&nbsp; ${bt.nLoads} loads &nbsp;·&nbsp; €${bt.price}</div>
                  </td>
                  <td class="bay-ct">${count}</td>
                </tr>`;
              }).join('')}
            </table>
          </div>

          

        </div>
      </div>
    </div>`;
}

/* ─── Result binding ─────────────────────────────────────────── */
function bindResult() {
  if (!S.result) return;
  if (S.viewMode === '3d') { render3D(S.result); }
  else { destroy3D(); bindResult2D(); }
}

/* ─── 2D Visualisation ───────────────────────────────────────── */
function bindResult2D() {
  const f = document.getElementById('vz');
  if (!f || !S.result) return;

  const r = S.result, wh = r.warehouse;
  let x0=Infinity, y0=Infinity, x1=-Infinity, y1=-Infinity;
  wh.forEach(v => {
    x0=Math.min(x0,v.x); y0=Math.min(y0,v.y);
    x1=Math.max(x1,v.x); y1=Math.max(y1,v.y);
  });

  const ww=x1-x0, hh=y1-y0, pad=Math.max(ww,hh)*0.05;
  const pts=wh.map(v=>`${v.x},${v.y}`).join(' ');
  const sw=Math.max(8,ww/200);

  let svg=`<svg viewBox="${x0-pad} ${y0-pad} ${ww+pad*2} ${hh+pad*2}"
    style="width:100%;height:100%;display:block;background:transparent"
    xmlns="http://www.w3.org/2000/svg">`;

  svg+=`<defs>
    <pattern id="grid" width="${Math.max(100,ww/60)}" height="${Math.max(100,hh/60)}" patternUnits="userSpaceOnUse">
      <path d="M ${Math.max(100,ww/60)} 0 L 0 0 0 ${Math.max(100,hh/60)}"
        fill="none" stroke="rgba(255,255,255,0.04)" stroke-width="${Math.max(1,ww/1400)}"/>
    </pattern>
    <filter id="glow">
      <feGaussianBlur stdDeviation="${ww*0.002}" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="rshadow">
      <feDropShadow dx="${ww/1000}" dy="${ww/1000}" stdDeviation="${ww/1000}"
        flood-color="#000" flood-opacity="0.5"/>
    </filter>
    <clipPath id="wc"><polygon points="${pts}"/></clipPath>
  </defs>`;

  svg+=`<rect x="${x0-pad}" y="${y0-pad}" width="${ww+pad*2}" height="${hh+pad*2}" fill="url(#grid)"/>`;
  svg+=`<polygon points="${pts}" fill="rgba(255,255,255,0.35)" stroke="rgba(80,90,110,0.35)" stroke-width="${sw}" filter="url(#glow)"/>`;

  /* helpers */
  const polyPts = c => c.map(p=>p[0]+','+p[1]).join(' ');
  const centroid = c => {
    let cx=0,cy=0; c.forEach(p=>{cx+=p[0];cy+=p[1];});
    return [cx/c.length,cy/c.length];
  };
  const bbox = c => {
    let bx0=Infinity,by0=Infinity,bx1=-Infinity,by1=-Infinity;
    c.forEach(p=>{bx0=Math.min(bx0,p[0]);by0=Math.min(by0,p[1]);bx1=Math.max(bx1,p[0]);by1=Math.max(by1,p[1]);});
    return {x0:bx0,y0:by0,x1:bx1,y1:by1,w:bx1-bx0,h:by1-by0};
  };
  const hexAlpha = (hex,a) => {
    const rv=parseInt(hex.slice(1,3),16);
    const gv=parseInt(hex.slice(3,5),16);
    const bv=parseInt(hex.slice(5,7),16);
    return `rgba(${rv},${gv},${bv},${a})`;
  };

  /* ceiling base */
  if (S.showCeiling && r.ceiling && r.ceiling.length) {
    const cl=[...r.ceiling].sort((a,b)=>a.x-b.x);
    cl.forEach((c,i)=>{
      const sx=Math.max(c.x,x0);
      const ex=i<cl.length-1?Math.min(cl[i+1].x,x1):x1;
      const w=ex-sx; if(w<=0)return;
      svg+=`<rect x="${sx}" y="${y0}" width="${w}" height="${hh}"
        fill="rgba(255,255,255,0.022)" stroke="rgba(255,255,255,0.06)"
        stroke-width="${Math.max(1,ww/900)}" clip-path="url(#wc)"/>`;
      svg+=`<line x1="${sx}" y1="${y0}" x2="${sx}" y2="${y1}"
        stroke="rgba(255,255,255,0.08)" stroke-width="${Math.max(1,ww/700)}"
        stroke-dasharray="${ww/250} ${ww/300}" clip-path="url(#wc)"/>`;
      const lx=sx+w/2,ly=y0+hh*0.055;
      svg+=`<text x="${lx}" y="${ly}" text-anchor="middle" dominant-baseline="central"
        fill="rgba(255,255,255,0.28)" font-weight="500"
        font-size="${Math.max(75,ww/110)}"
        style="pointer-events:none">${c.h} mm</text>`;
    });
    svg+=`<line x1="${x1}" y1="${y0}" x2="${x1}" y2="${y1}"
      stroke="rgba(255,255,255,0.08)" stroke-width="${Math.max(1,ww/700)}"
      stroke-dasharray="${ww/250} ${ww/300}" clip-path="url(#wc)"/>`;
  }

  /* obstacles */
  r.obstacles.forEach((o,i)=>{
    svg+=`<defs>
      <pattern id="op${i}" width="${ww/120}" height="${ww/120}"
        patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <line x1="0" y1="0" x2="0" y2="${ww/120}"
          stroke="rgba(220,38,38,0.35)" stroke-width="${Math.max(2,ww/900)}"/>
      </pattern>
    </defs>
    <rect x="${o.x}" y="${o.y}" width="${o.w}" height="${o.d}"
      fill="rgba(220,38,38,0.1)" stroke="rgba(220,38,38,0.55)"
      stroke-width="${Math.max(3,ww/500)}" stroke-dasharray="${ww/100} ${ww/200}"/>
    <rect x="${o.x}" y="${o.y}" width="${o.w}" height="${o.d}"
      fill="url(#op${i})" opacity="0.65"/>`;
  });

  /* gap zones */
  if (S.showGaps) {
    r.placed.forEach(b=>{
      if(b.gapCoords&&b.gapCoords.length>2){
        svg+=`<polygon points="${polyPts(b.gapCoords)}"
          fill="rgba(255,255,255,0.02)" stroke="rgba(255,255,255,0.07)"
          stroke-width="${Math.max(1,ww/700)}"
          stroke-dasharray="${ww/260} ${ww/320}"/>`;
      }
    });
  }

  /* racks */
  r.placed.forEach((b,i)=>{
    if(!b.footprintCoords||b.footprintCoords.length<3)return;
    const coords=b.footprintCoords;
    const ci=b.id%SWATCH.length;
    const bb2=bbox(coords);
    const cId=`c${i}`, pId=`p${i}`;
    const strokeW=Math.max(2,ww/650);
    const innerW=Math.max(1,ww/1600);
    const {x,y,w,h}={x:bb2.x0,y:bb2.y0,w:bb2.w,h:bb2.h};
    const ctr=centroid(coords);
    const isH=w>=h;
    const spc=Math.max(70,Math.min(w,h)/5);
    const color=SWATCH[ci];

    svg+=`<defs>
      <clipPath id="${cId}"><polygon points="${polyPts(coords)}"/></clipPath>
      <pattern id="${pId}" patternUnits="userSpaceOnUse" width="${spc}" height="${spc}">
        <path d="M 0 0 L ${spc} 0" stroke="rgba(255,255,255,0.22)" stroke-width="${innerW}"/>
        <path d="M 0 ${spc/2} L ${spc} ${spc/2}" stroke="rgba(255,255,255,0.1)" stroke-width="${innerW}"/>
      </pattern>
    </defs>`;

    svg+=`<polygon points="${polyPts(coords)}"
      fill="${hexAlpha(color,0.42)}" stroke="${color}"
      stroke-width="${strokeW}" filter="url(#rshadow)" style="cursor:pointer">
      <title>Type ${b.id}
      Size: ${b.w} x ${b.d} x ${b.h} mm
      Rotation: ${b.rotation}°
      Loads: ${b.nLoads}
      Gap: ${b.gap} mm
      Price: €${b.price}
      Position: x=${b.x}, y=${b.y}</title>
    </polygon>`;

    svg+=`<polygon points="${polyPts(coords)}"
      fill="url(#${pId})" opacity="0.22" clip-path="url(#${cId})"/>`;

    /* shelf lines */
    if(isH){
      const rows=Math.max(4,Math.floor(h/Math.max(110,h/8)));
      for(let k=1;k<rows;k++){
        const yy=y+h*k/rows;
        svg+=`<line x1="${x}" y1="${yy}" x2="${x+w}" y2="${yy}"
          stroke="rgba(255,255,255,0.28)" stroke-width="${innerW}" clip-path="url(#${cId})"/>`;
      }
      const cols=Math.max(5,Math.floor(w/Math.max(130,w/12)));
      for(let k=1;k<cols;k++){
        const xx=x+w*k/cols;
        svg+=`<line x1="${xx}" y1="${y}" x2="${xx}" y2="${y+h}"
          stroke="rgba(255,255,255,0.1)" stroke-width="${innerW}" clip-path="url(#${cId})"/>`;
      }
    } else {
      const cols=Math.max(4,Math.floor(w/Math.max(110,w/8)));
      for(let k=1;k<cols;k++){
        const xx=x+w*k/cols;
        svg+=`<line x1="${xx}" y1="${y}" x2="${xx}" y2="${y+h}"
          stroke="rgba(255,255,255,0.28)" stroke-width="${innerW}" clip-path="url(#${cId})"/>`;
      }
      const rows=Math.max(5,Math.floor(h/Math.max(130,h/12)));
      for(let k=1;k<rows;k++){
        const yy=y+h*k/rows;
        svg+=`<line x1="${x}" y1="${yy}" x2="${x+w}" y2="${yy}"
          stroke="rgba(255,255,255,0.1)" stroke-width="${innerW}" clip-path="url(#${cId})"/>`;
      }
    }

    /* uprights */
    const sup=Math.max(35,Math.min(w,h)*0.08);
    if(isH){
      svg+=`<rect x="${x}" y="${y}" width="${sup}" height="${h}"
        fill="rgba(0,0,0,0.42)" clip-path="url(#${cId})"/>`;
      svg+=`<rect x="${x+w-sup}" y="${y}" width="${sup}" height="${h}"
        fill="rgba(0,0,0,0.42)" clip-path="url(#${cId})"/>`;
    } else {
      svg+=`<rect x="${x}" y="${y}" width="${w}" height="${sup}"
        fill="rgba(0,0,0,0.42)" clip-path="url(#${cId})"/>`;
      svg+=`<rect x="${x}" y="${y+h-sup}" width="${w}" height="${sup}"
        fill="rgba(0,0,0,0.42)" clip-path="url(#${cId})"/>`;
    }

    /* id label */
    svg+=`<text x="${ctr[0]}" y="${ctr[1]}" text-anchor="middle"
      dominant-baseline="central" fill="white" font-weight="600"
      font-size="${Math.max(70,Math.min(w,h)*0.26)}"
      style="pointer-events:none;font-family:'Inter',sans-serif;
        text-shadow:0 1px 3px rgba(0,0,0,0.9)">${b.id}</text>`;

    if(Math.min(w,h)>ww*0.035){
      svg+=`<text x="${ctr[0]}" y="${ctr[1]+Math.max(70,Math.min(w,h)*0.26)}"
        text-anchor="middle" dominant-baseline="central"
        fill="rgba(255,255,255,0.5)" font-weight="400"
        font-size="${Math.max(35,Math.min(w,h)*0.105)}"
        style="pointer-events:none;font-family:'Inter',sans-serif"
        >${Math.round(b.h)} mm</text>`;
    }
  });

  /* ceiling glass overlay */
  if(S.showCeiling&&r.ceiling&&r.ceiling.length){
    const cl=[...r.ceiling].sort((a,b)=>a.x-b.x);
    cl.forEach((c,i)=>{
      const sx=Math.max(c.x,x0);
      const ex=i<cl.length-1?Math.min(cl[i+1].x,x1):x1;
      const w=ex-sx; if(w<=0)return;
      svg+=`<rect x="${sx}" y="${y0}" width="${w}" height="${hh}"
        fill="rgba(255,255,255,0.012)" stroke="rgba(255,255,255,0.05)"
        stroke-width="${Math.max(1,ww/1200)}" clip-path="url(#wc)"/>`;
    });
  }

  svg+='</svg>';
  f.innerHTML=svg;
}

/* ─── Global actions ─────────────────────────────────────────── */
window.resetApp = () => {
  destroy3D();
  S.step='upload';
  S.files={warehouse:null,obstacles:null,ceiling:null,bays:null};
  S.result=null;
  S.viewMode='2d';
  render();
};

window.dlCSV = () => {
  if(!S.result)return;
  const b=new Blob([S.result.csv],{type:'text/csv'});
  const u=URL.createObjectURL(b);
  const a=document.createElement('a');
  a.href=u; a.download='solution.csv'; a.click();
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
    print("\nWarehouse Optimizer — HackUPC 2026")
    print("   Open http://localhost:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)