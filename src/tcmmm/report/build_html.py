"""Build the self-contained HTML before-and-after view from results/*.json.

    python -m tcmmm.report.build_html            -> reports/before_after.html

No CDN, no external fonts: the file opens offline and can be emailed.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
PRIORS = {"spend_share": "results_spend_share", "equal": "results"}


def _load_prior(dirname: str) -> dict:
    base = ROOT / dirname
    out = {"scenarios": {}, "replicates": []}
    if not base.exists():
        return out
    for p in sorted(base.glob("*/result.json")):
        r = json.loads(p.read_text())
        tv = pd.read_csv(p.parent / "tv_monthly_by_version.csv")
        r["tv_monthly"] = {
            "months": [str(m)[:7] for m in tv["month"]],
            **{v: tv[v].round(0).tolist() for v in ("oracle", "naive_445", "naive_weekstart", "corrected")},
        }
        out["scenarios"][r["scenario"]] = r
    rep = base / "replicates"
    for p in sorted(rep.glob("*/result.json")):
        r = json.loads(p.read_text())
        out["replicates"].append({
            "run": r["scenario"], "truth": r["truth"]["verdict_if_known"],
            "p": {v: res["p_shift_helps"] for v, res in r["versions"].items()},
        })
    return out


def build() -> Path:
    payload = {"priors": {k: _load_prior(v) for k, v in PRIORS.items()}}
    vr = ROOT / "reports" / "validation" / "validation_report.json"
    ev = ROOT / "reports" / "validation" / "spec_reader_eval.json"
    payload["validation"] = json.loads(vr.read_text()) if vr.exists() else None
    payload["eval"] = json.loads(ev.read_text())["summary"] if ev.exists() else None
    html = TEMPLATE.replace("/*__DATA__*/null", json.dumps(payload, default=float))
    out = ROOT / "reports" / "before_after.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    return out


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Two Calendars: channel contributions before and after the calendar fix</title>
<style>
.viz-root{color-scheme:light;--surface-0:#f7f7f5;--surface-1:#ffffff;--text-primary:#191919;--text-secondary:#666666;
 --hairline:#e4e4e0;--grid:#ededea;--s-corrected:#257de0;--s-n445:#f47230;--s-nws:#00b894;--s-oracle:#8c8c8c;
 --good:#0a7d22;--bad:#c62f30;--warn:#9a6400;}
@media (prefers-color-scheme: dark){:root:where(:not([data-theme="light"])) .viz-root{color-scheme:dark;--surface-0:#111111;
 --surface-1:#191919;--text-primary:#efefef;--text-secondary:#9c9c9c;--hairline:#2e2e2e;--grid:#262626;
 --s-corrected:#338ced;--s-n445:#e76624;--s-nws:#00a888;--s-oracle:#8a8a8a;--good:#3fbf5a;--bad:#eb6263;--warn:#e0a640;}}
:root[data-theme="dark"] .viz-root{color-scheme:dark;--surface-0:#111111;--surface-1:#191919;--text-primary:#efefef;
 --text-secondary:#9c9c9c;--hairline:#2e2e2e;--grid:#262626;--s-corrected:#338ced;--s-n445:#e76624;--s-nws:#00a888;
 --s-oracle:#8a8a8a;--good:#3fbf5a;--bad:#eb6263;--warn:#e0a640;}
*{box-sizing:border-box}
body{margin:0}
.viz-root{background:var(--surface-0);color:var(--text-primary);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;min-height:100vh}
main{max-width:1080px;margin:0 auto;padding:32px 20px 64px}
h1{font-size:26px;line-height:1.25;margin:0 0 6px;letter-spacing:-0.01em}
h2{font-size:18px;margin:0 0 4px}
.sub{color:var(--text-secondary);margin:0 0 20px;max-width:760px}
.card{background:var(--surface-1);border:1px solid var(--hairline);border-radius:12px;padding:20px;margin:16px 0}
.filters{display:flex;gap:16px;flex-wrap:wrap;align-items:center;margin:8px 0 4px}
.filters label{font-size:13px;color:var(--text-secondary);display:flex;gap:8px;align-items:center}
select,button{font:inherit;font-size:14px;color:var(--text-primary);background:var(--surface-1);border:1px solid var(--hairline);border-radius:8px;padding:6px 10px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
.tile{background:var(--surface-1);border:1px solid var(--hairline);border-radius:12px;padding:14px 16px;position:relative}
.tile .k{font-size:13px;color:var(--text-secondary);display:flex;align-items:center;gap:8px}
.tile .v{font-size:28px;font-weight:650;margin:2px 0;font-variant-numeric:tabular-nums}
.tile .d{font-size:13px}
.key{display:inline-block;width:14px;height:3px;border-radius:2px}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;color:var(--text-secondary);margin:8px 0}
.legend span{display:flex;align-items:center;gap:6px}
svg text{fill:var(--text-secondary);font-size:12px}
svg .lbl{fill:var(--text-primary);font-size:12px}
.tip{position:fixed;pointer-events:none;background:var(--surface-1);border:1px solid var(--hairline);border-radius:8px;
 padding:8px 10px;font-size:12px;box-shadow:0 4px 16px rgba(0,0,0,.12);display:none;z-index:10;min-width:150px}
.tip .row{display:flex;align-items:center;gap:8px;justify-content:space-between}
.tip .row b{font-variant-numeric:tabular-nums}
.tip .hd{color:var(--text-secondary);margin-bottom:4px}
details{margin-top:10px}summary{cursor:pointer;color:var(--text-secondary);font-size:13px}
table{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums;margin-top:8px}
th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--hairline)}th{color:var(--text-secondary);font-weight:500}
.pill{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;border:1px solid var(--hairline)}
.ok{color:var(--good)}.bad{color:var(--bad)}.warnc{color:var(--warn)}
.note{font-size:13px;color:var(--text-secondary)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:820px){.grid2{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="viz-root">
<main>
<h1>The Two Calendars: does the TV calendar mismatch change the 15% TV-to-digital call?</h1>
<p class="sub">Synthetic diabetes-brand data with a <b>known</b> true effect per channel. TV arrives in Monday-to-Sunday media weeks on a 4-4-5 calendar; digital, email and sales arrive in calendar months. Four ways of building monthly TV are fitted with the same Bayesian MMM and scored against the truth.</p>

<div class="filters" role="group" aria-label="Filters">
 <label>Scenario <select id="scenarioSel"></select></label>
 <label>Model prior <select id="priorSel"></select></label>
 <button id="themeBtn" type="button">Light / dark</button>
</div>
<p class="note" id="scenarioNote"></p>

<section class="card" aria-labelledby="h-verdict">
 <h2 id="h-verdict">Verdict under the pre-registered rule</h2>
 <p class="note">Holds if P(the 15% shift raises sales) &ge; 0.80. Locked in git before any model was fitted.</p>
 <div class="tiles" id="tiles"></div>
</section>

<section class="card" aria-labelledby="h-tv">
 <h2 id="h-tv">1. The error: what monthly TV looks like under each rollup</h2>
 <p class="note" id="tvNote"></p>
 <div class="legend" id="tvLegend"></div>
 <div id="tvChart"></div>
 <details><summary>Table view</summary><div id="tvTable"></div></details>
</section>

<section class="card" aria-labelledby="h-contrib">
 <h2 id="h-contrib">2. Before and after: channel contribution to sales (90% interval)</h2>
 <p class="note">Dots are posterior means, whiskers are 90% intervals. The black tick is the true value the generator used.</p>
 <div class="legend" id="cLegend"></div>
 <div id="contribChart"></div>
 <details><summary>Table view</summary><div id="contribTable"></div></details>
</section>

<section class="card" aria-labelledby="h-mroi">
 <h2 id="h-mroi">3. What the decision should rest on: marginal ROI at current spend</h2>
 <p class="note">Revenue from the next dollar. Contribution share (chart 2) is not a reason to move budget; marginal ROI is.</p>
 <div id="mroiChart"></div>
 <details><summary>Table view</summary><div id="mroiTable"></div></details>
</section>

<section class="card" aria-labelledby="h-sweep">
 <h2 id="h-sweep">4. Does the answer survive other worlds? P(shift helps) by scenario and random seed</h2>
 <p class="note">Each row is one synthetic history. Shaded zone = "not supported" under the rule. Right column shows what the truth says.</p>
 <div class="legend" id="sLegend"></div>
 <div id="sweepChart"></div>
 <details><summary>Table view</summary><div id="sweepTable"></div></details>
</section>

<section class="card" aria-labelledby="h-val">
 <h2 id="h-val">5. The guardrail: refresh validation gate</h2>
 <p class="note">Runs on every data refresh, before any model is fitted. The LLM reads vendor specs; every claim is checked against the spec text and the data itself.</p>
 <div id="valBox"></div>
</section>
<div class="tip" id="tip" role="tooltip"></div>
</main>
</div>
<script>
const DATA = /*__DATA__*/null;
const V = [
 {k:"oracle", label:"Oracle (perfect data)", short:"Oracle", c:"--s-oracle", dash:"4 3"},
 {k:"naive_445", label:"Naive: 4-4-5 period as month", short:"Naive 4-4-5", c:"--s-n445"},
 {k:"naive_weekstart", label:"Naive: week-start month", short:"Naive week-start", c:"--s-nws"},
 {k:"corrected", label:"Corrected: split by day", short:"Corrected", c:"--s-corrected"}];
const CH = [["tv","TV"],["digital","Digital"],["email","Email"]];
const PRIOR_LABEL = {spend_share:"Spend-share prior (main)", equal:"Equal prior (sensitivity)"};
const SC_NOTE = {
 main:"Main world: a close call at the margin between TV and digital. Truth: the shift helps a little.",
 tv_clearly_better:"TV has the higher marginal ROI. Truth: the shift HURTS sales.",
 digital_clearly_better:"TV is heavily saturated. Truth: the shift helps.",
 always_on_tv:"TV runs every week instead of in bursts.",
 high_tv_digital_corr:"Digital budgets move with TV flights (correlation 0.7).",
 long_tv_adstock:"TV effect decays slowly (35-day half-life).",
 two_years_only:"Only 24 months of history."};
const css = n => getComputedStyle(document.querySelector(".viz-root")).getPropertyValue(n).trim();
const NS = "http://www.w3.org/2000/svg";
const el = (t, a={}, p) => {const e=document.createElementNS(NS,t); for(const k in a) e.setAttribute(k,a[k]); if(p) p.appendChild(e); return e;};
const fmt$ = v => "$"+(Math.abs(v)>=1e6?(v/1e6).toFixed(2)+"M":Math.round(v/1e3)+"K");
const pct = v => (100*v).toFixed(1)+"%";
const tip = document.getElementById("tip");
function showTip(ev, head, rows){
 tip.replaceChildren(); const h=document.createElement("div"); h.className="hd"; h.textContent=head; tip.appendChild(h);
 for(const r of rows){const d=document.createElement("div"); d.className="row";
  const l=document.createElement("span"); l.style.display="flex"; l.style.alignItems="center"; l.style.gap="6px";
  if(r.c){const k=document.createElement("span"); k.className="key"; k.style.background=css(r.c); l.appendChild(k);}
  l.appendChild(document.createTextNode(r.label)); const b=document.createElement("b"); b.textContent=r.value;
  d.append(l,b); tip.appendChild(d);}
 tip.style.display="block"; const x=Math.min(ev.clientX+14, innerWidth-tip.offsetWidth-8);
 tip.style.left=x+"px"; tip.style.top=(ev.clientY+14)+"px";}
const hideTip = () => tip.style.display="none";
function legend(id, items, kind="line"){const L=document.getElementById(id); L.replaceChildren();
 for(const it of items){const s=document.createElement("span"); const k=document.createElement("span"); k.className="key";
  if(kind==="dot"){k.style.width="10px";k.style.height="10px";k.style.borderRadius="50%";}
  k.style.background=css(it.c); s.append(k, document.createTextNode(it.label)); L.appendChild(s);}}
function table(id, head, rows){const t=document.createElement("table"); const tr=document.createElement("tr");
 head.forEach(h=>{const th=document.createElement("th"); th.textContent=h; tr.appendChild(th)}); t.appendChild(tr);
 rows.forEach(r=>{const tr=document.createElement("tr"); r.forEach(c=>{const td=document.createElement("td"); td.textContent=c; tr.appendChild(td)}); t.appendChild(tr)});
 const host=document.getElementById(id); host.replaceChildren(t);}
function ticks(lo, hi, n=5){const step=Math.pow(10,Math.floor(Math.log10((hi-lo)/n))); const err=(hi-lo)/n/step;
 const m = err>=7.5?10:err>=3.5?5:err>=1.5?2:1; const s=m*step, out=[]; for(let v=Math.ceil(lo/s)*s; v<=hi+1e-9; v+=s) out.push(+v.toFixed(10)); return out;}

// ------------------------------------------------------------------ chart 1: monthly TV lines
function tvChart(r){
 const host=document.getElementById("tvChart"); host.replaceChildren();
 const W=host.clientWidth||1000, H=300, m={l:56,r:150,t:10,b:28};
 const tm=r.tv_monthly, n=tm.months.length; const svg=el("svg",{width:W,height:H,viewBox:`0 0 ${W} ${H}`,role:"img","aria-label":"Monthly TV spend under four rollups"},host);
 const max=Math.max(...V.flatMap(v=>tm[v.k])); const yT=ticks(0,max*1.04); const yMax=Math.max(max*1.04,yT[yT.length-1]);
 const x=i=>m.l+i*(W-m.l-m.r)/(n-1), y=v=>H-m.b-(v/yMax)*(H-m.t-m.b);
 yT.forEach(t=>{el("line",{x1:m.l,x2:W-m.r,y1:y(t),y2:y(t),stroke:css("--grid")},svg); const tx=el("text",{x:m.l-8,y:y(t)+4,"text-anchor":"end"},svg); tx.textContent=fmt$(t);});
 tm.months.forEach((mo,i)=>{ if(mo.endsWith("-01")||i===0){const tx=el("text",{x:x(i),y:H-8,"text-anchor":"middle"},svg); tx.textContent=mo.slice(0,4);}});
 const ends=[];
 V.forEach(v=>{const d=tm[v.k].map((val,i)=>(i?"L":"M")+x(i).toFixed(1)+","+y(val).toFixed(1)).join("");
  el("path",{d,fill:"none",stroke:css(v.c),"stroke-width":2,"stroke-dasharray":v.dash||"","stroke-linejoin":"round"},svg);
  ends.push({v, y:y(tm[v.k][n-1])});});
 ends.sort((a,b)=>a.y-b.y); ends.forEach(e=>e.y=Math.max(m.t+8,e.y));
 for(let i=1;i<ends.length;i++) if(ends[i].y-ends[i-1].y<14) ends[i].y=ends[i-1].y+14;
 const over=ends[ends.length-1].y-(H-m.b); if(over>0) ends.forEach(e=>e.y-=over);
 ends.forEach(e=>{const tx=el("text",{x:W-m.r+8,y:e.y+4,class:"lbl"},svg); tx.textContent=e.v.short;});
 const hair=el("line",{y1:m.t,y2:H-m.b,stroke:css("--text-secondary"),"stroke-width":1,opacity:0},svg);
 const hit=el("rect",{x:m.l,y:m.t,width:W-m.l-m.r,height:H-m.t-m.b,fill:"transparent"},svg);
 hit.addEventListener("pointermove",ev=>{const bb=svg.getBoundingClientRect(); const i=Math.max(0,Math.min(n-1,Math.round((ev.clientX-bb.left-m.l)/((W-m.l-m.r)/(n-1)))));
  hair.setAttribute("x1",x(i)); hair.setAttribute("x2",x(i)); hair.setAttribute("opacity",.5);
  showTip(ev, tm.months[i], V.map(v=>({c:v.c,label:v.label,value:fmt$(tm[v.k][i])})));});
 hit.addEventListener("pointerleave",()=>{hideTip(); hair.setAttribute("opacity",0);});
 table("tvTable",["Month",...V.map(v=>v.label)], tm.months.map((mo,i)=>[mo,...V.map(v=>fmt$(tm[v.k][i]))]));
 const dist=r.distortion; const g=k=>dist.find(d=>d.version===k);
 document.getElementById("tvNote").textContent = `Average monthly TV error vs perfectly aligned data: 4-4-5 rollup ${g("naive_445").mean_abs_err_pct_of_avg_month.toFixed(0)}%, week-start rollup ${g("naive_weekstart").mean_abs_err_pct_of_avg_month.toFixed(0)}%, day-split fix ${g("corrected").mean_abs_err_pct_of_avg_month.toFixed(1)}%. Total TV spend is identical in all four: the error moves money between months, it does not lose it.`;
}

// ------------------------------------------------------------------ charts 2 and 3: interval dots
function intervalChart(hostId, r, metric, fmt, tableId){
 const host=document.getElementById(hostId); host.replaceChildren();
 const W=host.clientWidth||1000, rowH=18, gap=22, m={l:90,r:30,t:10,b:30};
 const H=m.t+m.b+CH.length*(V.length*rowH+gap);
 const svg=el("svg",{width:W,height:H,viewBox:`0 0 ${W} ${H}`,role:"img"},host);
 const vals=[]; CH.forEach(([c])=>{V.forEach(v=>{const s=r.versions[v.k][metric][c]; vals.push(s.ci90[0],s.ci90[1]);}); vals.push(r.truth[metric][c]);});
 const lo=Math.min(0,...vals), hi=Math.max(...vals)*1.05, xT=ticks(lo,hi);
 const x=v=>m.l+(v-xT[0])/(xT[xT.length-1]-xT[0])*(W-m.l-m.r);
 xT.forEach(t=>{el("line",{x1:x(t),x2:x(t),y1:m.t,y2:H-m.b,stroke:css("--grid")},svg); const tx=el("text",{x:x(t),y:H-10,"text-anchor":"middle"},svg); tx.textContent=fmt(t);});
 const rows=[];
 CH.forEach(([c,cl],ci)=>{const y0=m.t+ci*(V.length*rowH+gap);
  const tl=el("text",{x:8,y:y0+V.length*rowH/2+4,class:"lbl"},svg); tl.textContent=cl;
  const tv=r.truth[metric][c];
  el("line",{x1:x(tv),x2:x(tv),y1:y0-2,y2:y0+V.length*rowH+2,stroke:css("--text-primary"),"stroke-width":2},svg);
  V.forEach((v,vi)=>{const s=r.versions[v.k][metric][c], yy=y0+vi*rowH+rowH/2;
   el("line",{x1:x(s.ci90[0]),x2:x(s.ci90[1]),y1:yy,y2:yy,stroke:css(v.c),"stroke-width":2,"stroke-linecap":"round"},svg);
   el("circle",{cx:x(s.mean),cy:yy,r:4.5,fill:css(v.c),stroke:css("--surface-1"),"stroke-width":2},svg);
   const hit=el("rect",{x:x(s.ci90[0])-8,y:yy-rowH/2,width:Math.max(24,x(s.ci90[1])-x(s.ci90[0])+16),height:rowH,fill:"transparent",tabindex:0},svg);
   const rowsT=[{c:v.c,label:"Estimate",value:fmt(s.mean)},{label:"90% interval",value:fmt(s.ci90[0])+" to "+fmt(s.ci90[1])},{label:"Truth",value:fmt(tv)}];
   hit.addEventListener("pointermove",ev=>showTip(ev, cl+" | "+v.label, rowsT)); hit.addEventListener("pointerleave",hideTip);
   rows.push([cl,v.label,fmt(s.mean),fmt(s.ci90[0])+" to "+fmt(s.ci90[1]),fmt(tv)]);});});
 table(tableId,["Channel","Version","Estimate","90% interval","Truth"],rows);
}

// ------------------------------------------------------------------ chart 4: sweep
function sweepChart(P){
 const host=document.getElementById("sweepChart"); host.replaceChildren();
 const runs=[]; for(const [name,r] of Object.entries(P.scenarios)) runs.push({run:name,truth:r.truth.verdict_if_known,p:Object.fromEntries(Object.entries(r.versions).map(([k,v])=>[k,v.p_shift_helps]))});
 P.replicates.forEach(r=>runs.push(r));
 const W=host.clientWidth||1000, rowH=24, m={l:210,r:80,t:10,b:30}, H=m.t+m.b+runs.length*rowH;
 const svg=el("svg",{width:W,height:H,viewBox:`0 0 ${W} ${H}`,role:"img"},host);
 const x=p=>m.l+p*(W-m.l-m.r);
 el("rect",{x:x(0.2),y:m.t,width:x(0.8)-x(0.2),height:H-m.t-m.b,fill:css("--grid")},svg);
 [0,0.2,0.5,0.8,1].forEach(t=>{el("line",{x1:x(t),x2:x(t),y1:m.t,y2:H-m.b,stroke:css(t===0.8||t===0.2?"--text-secondary":"--grid"),"stroke-dasharray":t===0.8||t===0.2?"3 3":""},svg);
  const tx=el("text",{x:x(t),y:H-10,"text-anchor":"middle"},svg); tx.textContent=t.toFixed(1);});
 const rows=[];
 runs.forEach((r,i)=>{const yy=m.t+i*rowH+rowH/2; const lab=el("text",{x:8,y:yy+4,class:"lbl"},svg); lab.textContent=r.run.replace("__seed"," seed ");
  const tt=el("text",{x:W-m.r+10,y:yy+4,class:"lbl"},svg); tt.textContent="truth: "+r.truth.toLowerCase(); tt.setAttribute("fill",css(r.truth==="Helps"?"--good":"--bad"));
  V.forEach(v=>{const p=r.p[v.k]; if(p===undefined) return;
   el("circle",{cx:x(p),cy:yy,r:5,fill:css(v.c),stroke:css("--surface-1"),"stroke-width":2,opacity:.95},svg);
   const hit=el("circle",{cx:x(p),cy:yy,r:12,fill:"transparent"},svg);
   hit.addEventListener("pointermove",ev=>showTip(ev,r.run+" | truth: "+r.truth,[{c:v.c,label:v.label,value:p.toFixed(2)}])); hit.addEventListener("pointerleave",hideTip);});
  rows.push([r.run,r.truth,...V.map(v=>r.p[v.k]!==undefined?r.p[v.k].toFixed(2):"")]);});
 table("sweepTable",["Run","Truth",...V.map(v=>v.label)],rows);
}

// ------------------------------------------------------------------ tiles
function tiles(r){const T=document.getElementById("tiles"); T.replaceChildren();
 const truthBox=document.createElement("div"); truthBox.className="tile";
 truthBox.innerHTML='<div class="k">Truth (known only to the generator)</div><div class="v"></div><div class="d"></div>';
 truthBox.querySelector(".v").textContent=r.truth.verdict_if_known==="Helps"?"Shift helps":"Shift hurts";
 truthBox.querySelector(".v").className="v "+(r.truth.verdict_if_known==="Helps"?"ok":"bad");
 truthBox.querySelector(".d").textContent="Change in sales: "+(r.truth.shift_delta_pct_of_sales*100).toFixed(2)+"%";
 T.appendChild(truthBox);
 V.forEach(v=>{const s=r.versions[v.k]; const d=document.createElement("div"); d.className="tile";
  const k=document.createElement("div"); k.className="k"; const key=document.createElement("span"); key.className="key"; key.style.background=css(v.c); k.append(key, document.createTextNode(v.label));
  const val=document.createElement("div"); val.className="v"; val.textContent="P = "+s.p_shift_helps.toFixed(2);
  const ds=document.createElement("div"); ds.className="d"; ds.textContent=s.verdict;
  const wrongConfident = (s.verdict==="Holds" && r.truth.verdict_if_known==="Hurts") || (s.verdict==="Reverses" && r.truth.verdict_if_known==="Helps");
  if(wrongConfident){ds.className="d bad"; ds.textContent=s.verdict+": confidently wrong";}
  d.append(k,val,ds); T.appendChild(d);});}

// ------------------------------------------------------------------ validation
function validation(){const box=document.getElementById("valBox"); box.replaceChildren();
 if(!DATA.validation){box.textContent="Run `make validate` to populate."; return;}
 const rows=Object.entries(DATA.validation.sources).map(([f,s])=>[f,s.status,(s.transform||""),s.findings.map(x=>"["+x.status+"] "+x.message).join("  |  ")]);
 const h=document.createElement("p"); h.className="note"; h.textContent="Clean refresh, overall status: "+DATA.validation.status+". TV needs the day-split transform; the gate confirms it conserves spend to the cent.";
 box.appendChild(h); const t=document.createElement("div"); t.id="valT"; box.appendChild(t);
 table("valT",["File","Status","Transform","Findings"],rows);
 if(DATA.eval){const e=DATA.eval; const p=document.createElement("p"); p.className="note";
  p.textContent=`Spec-reader evaluation on ${e.n_specs} labelled vendor specs (week-ending labels, fiscal 4-4-5, broadcast months, a prompt injection, a mid-series grain change): misaligned specs that slipped through as PASS = ${e.unsafe_passes}. Field accuracy: grain ${pct(e.grain.raw_accuracy)}, calendar ${pct(e.calendar_system.raw_accuracy)}, week start ${pct(e.week_start_day.raw_accuracy)}, date label ${pct(e.date_label.raw_accuracy)}. Recorded readings were produced by Claude, which also wrote the labels, so this is not an independent score; the live Groq run is the independent check.`;
  box.appendChild(p);}
 const p2=document.createElement("p"); p2.className="note"; p2.textContent="Proven by tests: a hallucinated quote is discarded; an LLM that obeys an injected instruction is overruled by the data profile; a vendor that silently switches to week-ending dates is blocked; an unregistered file is never joined.";
 box.appendChild(p2);}

// ------------------------------------------------------------------ wiring
const priorSel=document.getElementById("priorSel"), scSel=document.getElementById("scenarioSel");
Object.keys(DATA.priors).filter(k=>Object.keys(DATA.priors[k].scenarios).length).forEach(k=>{const o=document.createElement("option"); o.value=k; o.textContent=PRIOR_LABEL[k]||k; priorSel.appendChild(o);});
function fillScenarios(){const cur=scSel.value; scSel.replaceChildren(); Object.keys(DATA.priors[priorSel.value].scenarios).forEach(k=>{const o=document.createElement("option"); o.value=k; o.textContent=k; scSel.appendChild(o);}); if([...scSel.options].some(o=>o.value===cur)) scSel.value=cur; else if([...scSel.options].some(o=>o.value==="main")) scSel.value="main";}
function render(){const P=DATA.priors[priorSel.value], r=P.scenarios[scSel.value];
 document.getElementById("scenarioNote").textContent=SC_NOTE[scSel.value]||"";
 legend("tvLegend",V.map(v=>({c:v.c,label:v.label}))); legend("cLegend",[...V.map(v=>({c:v.c,label:v.label})),{c:"--text-primary",label:"Truth"}],"dot");
 legend("sLegend",V.map(v=>({c:v.c,label:v.label})),"dot");
 tiles(r); tvChart(r); intervalChart("contribChart",r,"contribution_share",v=>pct(v),"contribTable");
 intervalChart("mroiChart",r,"marginal_roi",v=>"$"+v.toFixed(2),"mroiTable"); sweepChart(P); validation();}
priorSel.addEventListener("change",()=>{fillScenarios(); render();}); scSel.addEventListener("change",render);
document.getElementById("themeBtn").addEventListener("click",()=>{const d=document.documentElement; const dark=d.dataset.theme? d.dataset.theme==="dark" : matchMedia("(prefers-color-scheme: dark)").matches; d.dataset.theme=dark?"light":"dark"; render();});
addEventListener("resize",()=>render());
fillScenarios(); render();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    print(build())
