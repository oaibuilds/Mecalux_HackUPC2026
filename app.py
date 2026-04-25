"""
Warehouse Optimizer - FastAPI Backend
HackUPC 2026 - Mecalux Challenge
Run: python app.py → http://localhost:8000
"""

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from solver import (
    WarehouseSolver, parse_warehouse, parse_obstacles,
    parse_ceiling, parse_bays
)

app = FastAPI(title="Warehouse Optimizer")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.post("/api/solve")
async def solve_warehouse(
    warehouse: UploadFile = File(...), obstacles: UploadFile = File(...),
    ceiling: UploadFile = File(...), bays: UploadFile = File(...),
):
    try:
        wh = parse_warehouse((await warehouse.read()).decode())
        obs = parse_obstacles((await obstacles.read()).decode())
        ceil = parse_ceiling((await ceiling.read()).decode())
        bt = parse_bays((await bays.read()).decode())
        solver = WarehouseSolver(wh, obs, ceil, bt)
        placed, stats = solver.solve(time_limit=25.0)
        return _build_response(placed, stats, wh, obs, ceil, bt)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


@app.post("/api/solve-text")
async def solve_text(
    warehouse: str = Form(...), obstacles: str = Form(...),
    ceiling: str = Form(...), bays: str = Form(...),
):
    try:
        wh = parse_warehouse(warehouse)
        obs = parse_obstacles(obstacles)
        ceil = parse_ceiling(ceiling)
        bt = parse_bays(bays)
        solver = WarehouseSolver(wh, obs, ceil, bt)
        placed, stats = solver.solve(time_limit=25.0)
        return _build_response(placed, stats, wh, obs, ceil, bt)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


def _build_response(placed, stats, wh, obs, ceil, bt):
    return JSONResponse({
        "success": True,
        "placed": [b.to_dict() for b in placed],
        "stats": stats,
        "warehouse": [{"x": v[0], "y": v[1]} for v in wh],
        "obstacles": [{"x": o[0], "y": o[1], "w": o[2], "d": o[3]} for o in obs],
        "ceiling": [{"x": c[0], "h": c[1]} for c in ceil],
        "bayTypes": [{"id": int(b[0]), "w": b[1], "d": b[2], "h": b[3],
                      "gap": b[4], "nLoads": int(b[5]), "price": b[6]} for b in bt],
        "csv": "\n".join(f"{b.type_id}, {b.x}, {b.y}, {b.rotation}" for b in placed),
    })


FRONTEND_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Warehouse Optimizer — HackUPC 2026</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Outfit:wght@300;400;600;700;900&display=swap" rel="stylesheet">
<style>
:root { --bg:#070b14; --bg2:#0d1524; --srf:rgba(255,255,255,0.04); --brd:rgba(255,255,255,0.06);
  --txt:#e8edf5; --dim:rgba(255,255,255,0.4); --acc:#2a6fff; --acc2:#ff6b35; --ok:#2ed573; --no:#ff4757; }
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Outfit',sans-serif;background:linear-gradient(145deg,var(--bg),var(--bg2),#0a1020);color:var(--txt);min-height:100vh;overflow-x:hidden}
.hdr{padding:20px 32px;border-bottom:1px solid var(--brd);display:flex;align-items:center;justify-content:space-between;background:rgba(0,0,0,0.2);backdrop-filter:blur(20px);position:sticky;top:0;z-index:100}
.logo-g{display:flex;align-items:center;gap:14px}
.logo-i{width:44px;height:44px;border-radius:12px;background:linear-gradient(135deg,var(--acc2),var(--acc));display:flex;align-items:center;justify-content:center;font-weight:900;font-size:20px;color:#fff}
.logo-t{font-size:20px;font-weight:700;letter-spacing:-0.3px}
.logo-s{font-size:11px;color:var(--dim);letter-spacing:1.5px;text-transform:uppercase}
.btn{border:none;padding:12px 28px;border-radius:10px;font-size:14px;font-weight:700;cursor:pointer;font-family:'Outfit';letter-spacing:0.3px;transition:all .25s}
.btn-p{background:linear-gradient(135deg,var(--acc),#1a4fd0);color:#fff}
.btn-p:hover{transform:translateY(-2px);box-shadow:0 8px 30px rgba(42,111,255,0.4)}
.btn-p:disabled{opacity:.35;cursor:not-allowed;transform:none;box-shadow:none}
.btn-g{background:var(--srf);color:var(--txt);border:1px solid var(--brd)}
.btn-g:hover{background:rgba(255,255,255,0.08)}
.btn-sm{padding:8px 18px;font-size:13px}
.up-pg{max-width:880px;margin:0 auto;padding:56px 24px}
.up-t{font-size:44px;font-weight:900;letter-spacing:-1.5px;text-align:center;margin-bottom:10px;background:linear-gradient(135deg,#fff,rgba(255,255,255,0.55));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.up-s{text-align:center;color:var(--dim);font-size:16px;margin-bottom:48px}
.up-gr{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:40px}
.dz{border:2px dashed rgba(42,111,255,0.25);border-radius:14px;padding:28px 20px;text-align:center;cursor:pointer;transition:all .3s;background:rgba(42,111,255,0.02)}
.dz:hover{border-color:var(--acc);background:rgba(42,111,255,0.06);box-shadow:0 0 40px rgba(42,111,255,0.08)}
.dz.ok{border-color:var(--ok);background:rgba(46,213,115,0.04)}
.dz .ic{font-size:34px;margin-bottom:8px}
.dz .lb{font-weight:700;font-size:16px;margin-bottom:4px}
.dz .ds{font-size:12px;color:var(--dim)}
.up-ac{text-align:center;display:flex;flex-direction:column;align-items:center;gap:14px}
.sv-pg{display:flex;flex-direction:column;align-items:center;justify-content:center;height:70vh;gap:20px}
.spin{width:70px;height:70px;border-radius:50%;border:3px solid rgba(42,111,255,0.15);border-top-color:var(--acc);animation:sp .7s linear infinite}
@keyframes sp{to{transform:rotate(360deg)}}
@keyframes pu{0%,100%{opacity:.35}50%{opacity:1}}
@keyframes su{from{opacity:0;transform:translateY(24px)}to{opacity:1;transform:translateY(0)}}
.ai{animation:su .5s ease-out}
.rp{display:flex;flex-direction:column;height:calc(100vh - 85px)}
.sb{padding:14px 32px;display:flex;gap:14px;background:rgba(0,0,0,0.15);border-bottom:1px solid var(--brd);flex-wrap:wrap}
.sc{background:var(--srf);border:1px solid var(--brd);border-radius:14px;padding:16px 20px;flex:1;min-width:130;backdrop-filter:blur(10px)}
.sv{font-size:26px;font-weight:900;font-family:'JetBrains Mono';background:linear-gradient(135deg,var(--acc),#00d2d3);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.sl{font-size:10px;text-transform:uppercase;letter-spacing:2px;color:var(--dim);margin-top:3px}
.ma{flex:1;display:flex;min-height:0}
.vc{flex:1;padding:14px;display:flex;flex-direction:column;min-height:0}
.vf{flex:1;border-radius:16px;overflow:hidden;border:1px solid var(--brd);min-height:0;background:#0a0e17}
.sp{width:270px;border-left:1px solid var(--brd);padding:18px;overflow-y:auto;background:rgba(0,0,0,0.1)}
.sh{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:var(--dim);margin-bottom:14px}
.li{padding:10px 12px;border-radius:10px;background:rgba(255,255,255,0.025);margin-bottom:7px;border:1px solid rgba(255,255,255,0.03)}
.li .tp{display:flex;align-items:center;gap:8px;margin-bottom:4px}
.ld{width:12px;height:12px;border-radius:3px;display:inline-block}
.li .mt{font-size:11px;color:var(--dim);font-family:'JetBrains Mono'}
.co{font-size:10px;font-family:'JetBrains Mono';color:rgba(255,255,255,0.45);background:rgba(0,0,0,0.3);padding:12px;border-radius:8px;max-height:200px;overflow:auto;white-space:pre-wrap;word-break:break-all;border:1px solid var(--brd)}
.tgl{display:flex;align-items:center;gap:8px;margin:12px 0;font-size:12px;color:var(--dim);cursor:pointer}
.tgl input{accent-color:var(--acc)}
</style>
</head>
<body>
<div class="hdr">
  <div class="logo-g"><div class="logo-i">W</div><div><div class="logo-t">Warehouse Optimizer</div><div class="logo-s">HackUPC 2026 · Mecalux Challenge</div></div></div>
  <div id="ha"></div>
</div>
<div id="app"></div>
<script>
const S={step:'upload',files:{warehouse:null,obstacles:null,ceiling:null,bays:null},result:null,showGaps:true};
const BC=['rgba(255,107,53,0.55)','rgba(0,150,255,0.55)','rgba(46,213,115,0.55)','rgba(255,71,87,0.55)','rgba(165,94,234,0.55)','rgba(255,215,0,0.55)','rgba(0,210,211,0.55)','rgba(255,159,243,0.55)'];
const BB=['#ff6b35','#0096ff','#2ed573','#ff4757','#a55eea','#ffd700','#00d2d3','#ff9ff3'];
const EX={warehouse:'0, 0\n10000, 0\n10000, 3000\n3000, 3000\n3000, 10000\n0, 10000',obstacles:'750, 750, 750, 750\n8000, 2500, 1500, 300\n1500, 4200, 200, 4600',ceiling:'0, 3000\n3000, 2000\n6000, 3000',bays:'0, 800, 1200, 2800, 200, 4, 2000\n1, 1600, 1200, 2800, 200, 8, 2500\n2, 2400, 1200, 2800, 200, 12, 2800\n3, 800, 1000, 1800, 150, 3, 1800\n4, 1600, 1000, 1800, 150, 6, 2300\n5, 2400, 1000, 1800, 150, 9, 2600'};

function render(){
  const a=document.getElementById('app'),h=document.getElementById('ha');
  if(S.step==='upload'){h.innerHTML='';a.innerHTML=renderUpload();bindUpload();}
  else if(S.step==='solving'){h.innerHTML='';a.innerHTML='<div class="sv-pg ai"><div class="spin"></div><div style="font-size:22px;font-weight:700">Optimizing placement...</div><div style="color:var(--dim);font-size:14px;animation:pu 1.5s infinite">Running gap-aware multi-pass solver</div></div>';}
  else if(S.step==='result'){h.innerHTML='<button class="btn btn-g btn-sm" onclick="resetApp()">↺ New</button> <button class="btn btn-p btn-sm" onclick="dlCSV()">↓ Download CSV</button>';a.innerHTML=renderResult();bindResult();}
}

function renderUpload(){
  const zs=[{k:'warehouse',i:'⬡',l:'Warehouse',d:'Polygon vertices'},{k:'obstacles',i:'⊘',l:'Obstacles',d:'Blocked areas'},{k:'ceiling',i:'△',l:'Ceiling',d:'Height profile'},{k:'bays',i:'▦',l:'Bay Types',d:'Available racks'}];
  const ok=Object.values(S.files).every(Boolean);
  return `<div class="up-pg ai"><div class="up-t">Drop your warehouse files</div><div class="up-s">Upload the 4 CSV files to optimize bay placement</div>
  <div class="up-gr">${zs.map(z=>`<div class="dz ${S.files[z.k]?'ok':''}" id="z-${z.k}" ondragover="event.preventDefault()" ondrop="hDrop(event,'${z.k}')">
  <input type="file" accept=".csv,.txt" id="f-${z.k}" style="display:none" onchange="hFile('${z.k}',this)">
  <div class="ic">${S.files[z.k]?'✓':z.i}</div><div class="lb" style="color:${S.files[z.k]?'var(--ok)':'var(--txt)'}">${z.l}</div><div class="ds">${S.files[z.k]?'Loaded ✓':z.d}</div></div>`).join('')}</div>
  <div class="up-ac"><button class="btn btn-p" ${ok?'':'disabled'} onclick="go()">⚡ Optimize Warehouse</button><button class="btn btn-g btn-sm" onclick="ldEx()">Load Example Data</button></div></div>`;
}
function bindUpload(){['warehouse','obstacles','ceiling','bays'].forEach(k=>{const z=document.getElementById('z-'+k);if(z)z.addEventListener('click',()=>document.getElementById('f-'+k).click());});}
window.hDrop=(e,k)=>{e.preventDefault();const f=e.dataTransfer.files[0];if(f)f.text().then(t=>{S.files[k]=t;render();});};
window.hFile=(k,inp)=>{const f=inp.files[0];if(f)f.text().then(t=>{S.files[k]=t;render();});};
window.ldEx=()=>{S.files={...EX};render();};

window.go=async()=>{
  S.step='solving';render();
  try{
    const fd=new FormData();fd.append('warehouse',S.files.warehouse);fd.append('obstacles',S.files.obstacles);fd.append('ceiling',S.files.ceiling);fd.append('bays',S.files.bays);
    const r=await fetch('/api/solve-text',{method:'POST',body:fd});const d=await r.json();
    if(d.success){S.result=d;S.step='result';}else{alert('Error: '+d.error);S.step='upload';}
  }catch(e){alert('Error: '+e.message);S.step='upload';}
  render();
};

function renderResult(){
  const r=S.result,s=r.stats;
  return `<div class="rp ai"><div class="sb">
  <div class="sc"><div class="sv">${s.totalBays}</div><div class="sl">Bays Placed</div></div>
  <div class="sc"><div class="sv">${s.totalLoads}</div><div class="sl">Total Loads</div></div>
  <div class="sc"><div class="sv">${s.areaUsage.toFixed(1)}%</div><div class="sl">Area Usage</div></div>
  <div class="sc"><div class="sv">${s.score.toFixed(2)}</div><div class="sl">Q Score</div></div>
  <div class="sc"><div class="sv">${s.solveTime}s</div><div class="sl">Solve Time</div></div>
  </div><div class="ma"><div class="vc"><div class="vf" id="vz"></div></div>
  <div class="sp">
    <div class="sh">Controls</div>
    <label class="tgl"><input type="checkbox" ${S.showGaps?'checked':''} onchange="S.showGaps=this.checked;bindResult()"> Show gap zones</label>
    <div class="sh" style="margin-top:16px">Bay Types Legend</div>
    ${r.bayTypes.map(bt=>{const c=r.placed.filter(p=>p.id===bt.id).length;const ci=bt.id%BC.length;
    return `<div class="li"><div class="tp"><span class="ld" style="background:${BB[ci]}"></span><span style="font-weight:700;font-size:14px">Type ${bt.id}</span><span style="margin-left:auto;font-family:'JetBrains Mono';font-size:13px;color:${BB[ci]}">×${c}</span></div><div class="mt">${bt.w}×${bt.d}×${bt.h} | gap:${bt.gap} | ${bt.nLoads}L | $${bt.price}</div></div>`;}).join('')}
    <div class="sh" style="margin-top:22px">Output CSV</div>
    <div class="co">${r.csv}</div>
  </div></div></div>`;
}

function bindResult(){
  const f=document.getElementById('vz');if(!f||!S.result)return;
  const r=S.result,wh=r.warehouse;
  let x0=Infinity,y0=Infinity,x1=-Infinity,y1=-Infinity;
  wh.forEach(v=>{x0=Math.min(x0,v.x);y0=Math.min(y0,v.y);x1=Math.max(x1,v.x);y1=Math.max(y1,v.y);});
  const ww=x1-x0,hh=y1-y0,pad=Math.max(ww,hh)*0.05;
  const pts=wh.map(v=>`${v.x},${v.y}`).join(' ');
  const sw=Math.max(8,ww/200);
  let svg=`<svg viewBox="${x0-pad} ${y0-pad} ${ww+pad*2} ${hh+pad*2}" style="width:100%;height:100%;background:#0a0e17" xmlns="http://www.w3.org/2000/svg">`;
  svg+=`<defs><pattern id="g" width="${Math.max(100,ww/50)}" height="${Math.max(100,hh/50)}" patternUnits="userSpaceOnUse"><path d="M ${Math.max(100,ww/50)} 0 L 0 0 0 ${Math.max(100,hh/50)}" fill="none" stroke="rgba(255,255,255,0.04)" stroke-width="${Math.max(1,ww/1000)}"/></pattern>`;
  svg+=`<filter id="gl"><feGaussianBlur stdDeviation="${ww*0.003}" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>`;
  svg+=`<rect x="${x0-pad}" y="${y0-pad}" width="${ww+pad*2}" height="${hh+pad*2}" fill="url(#g)"/>`;
  svg+=`<polygon points="${pts}" fill="rgba(20,30,50,0.8)" stroke="#2a6fff" stroke-width="${sw}" filter="url(#gl)"/>`;

  // Ceiling overlay
  if(r.ceiling.length>1){const mh=Math.max(...r.ceiling.map(c=>c.h));let gs=r.ceiling.map(c=>`<stop offset="${((c.x-x0)/ww*100)}%" stop-color="rgba(0,150,255,${(c.h/mh)*0.12+0.02})"/>`).join('');svg+=`<defs><linearGradient id="cg" x1="0%" y1="0%" x2="100%" y2="0%">${gs}</linearGradient></defs><polygon points="${pts}" fill="url(#cg)"/>`;}

  // Obstacles
  r.obstacles.forEach(o=>{svg+=`<rect x="${o.x}" y="${o.y}" width="${o.w}" height="${o.d}" fill="rgba(255,50,50,0.25)" stroke="#ff3232" stroke-width="${Math.max(3,ww/500)}" stroke-dasharray="${ww/100} ${ww/200}"/>`;svg+=`<line x1="${o.x}" y1="${o.y}" x2="${o.x+o.w}" y2="${o.y+o.d}" stroke="rgba(255,50,50,0.15)" stroke-width="${Math.max(2,ww/600)}"/>`;svg+=`<line x1="${o.x+o.w}" y1="${o.y}" x2="${o.x}" y2="${o.y+o.d}" stroke="rgba(255,50,50,0.15)" stroke-width="${Math.max(2,ww/600)}"/>`;});

  // Helper: polygon points string from coords array
  function polyPts(coords){return coords.map(c=>c[0]+','+c[1]).join(' ');}
  // Helper: centroid of a polygon coords array
  function centroid(coords){
    let cx=0,cy=0;
    for(const c of coords){cx+=c[0];cy+=c[1];}
    return [cx/coords.length, cy/coords.length];
  }
  // Helper: bounding box of coords
  function bbox(coords){
    let x0=Infinity,y0=Infinity,x1=-Infinity,y1=-Infinity;
    for(const c of coords){x0=Math.min(x0,c[0]);y0=Math.min(y0,c[1]);x1=Math.max(x1,c[0]);y1=Math.max(y1,c[1]);}
    return {x0,y0,x1,y1,w:x1-x0,h:y1-y0};
  }

  // Gap zones (render BEFORE bays — underneath)
  if(S.showGaps){r.placed.forEach(b=>{
    if(b.gapCoords&&b.gapCoords.length>2){
      svg+=`<polygon points="${polyPts(b.gapCoords)}" fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.15)" stroke-width="${Math.max(1,ww/600)}" stroke-dasharray="${ww/200} ${ww/300}"/>`;
    }
  });}

  // Bays — draw as actual polygons using footprintCoords
  r.placed.forEach((b,i)=>{
    const ci=b.id%BC.length;
    const coords=b.footprintCoords;
    if(!coords||coords.length<3)return;
    const ctr=centroid(coords);
    const bb=bbox(coords);
    svg+=`<polygon points="${polyPts(coords)}" fill="${BC[ci]}" stroke="${BB[ci]}" stroke-width="${Math.max(2,ww/400)}" style="cursor:pointer"><title>Bay #${b.id} | ${b.w}×${b.d} | rot=${b.rotation}° | ${b.nLoads} loads | $${b.price}</title></polygon>`;
    if(bb.w>ww*0.035&&bb.h>hh*0.025){
      svg+=`<text x="${ctr[0]}" y="${ctr[1]}" text-anchor="middle" dominant-baseline="central" fill="white" font-weight="700" font-size="${Math.min(bb.w,bb.h)*0.35}" style="pointer-events:none;text-shadow:0 1px 3px rgba(0,0,0,0.8)">${b.id}</text>`;
    }
  });

  svg+='</svg>';f.innerHTML=svg;
}

window.resetApp=()=>{S.step='upload';S.files={warehouse:null,obstacles:null,ceiling:null,bays:null};S.result=null;render();};
window.dlCSV=()=>{if(!S.result)return;const b=new Blob([S.result.csv],{type:'text/csv'});const u=URL.createObjectURL(b);const a=document.createElement('a');a.href=u;a.download='solution.csv';a.click();URL.revokeObjectURL(u);};
render();
</script>
</body></html>"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return FRONTEND_HTML


if __name__ == "__main__":
    print("\n🏭 Warehouse Optimizer — HackUPC 2026")
    print("   Open http://localhost:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
