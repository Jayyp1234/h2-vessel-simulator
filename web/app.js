/* Hydrogen storage vessel simulator — browser app.
   Physics lives in web/physics.js, shared with engine/parity_check.py. */
(() => {
"use strict";
const MC = window.MODEL_CONSTANTS;
if (!MC) { document.body.innerHTML = "<p style='padding:2rem'>model-constants.js failed to load. Run <code>python engine/run.py --emit-web-constants</code>.</p>"; return; }

const K = MC.constants;
const COLORS = { 1:"#1f4e79", 2:"#2e75b6", 3:"#843c0c", 4:"#c55a11" };

function specDefaults() {
  const d = MC.defaults || {};
  return {
    qst: d.q_st != null ? d.q_st : 6.0,
    T_charge: d.T_charge != null ? d.T_charge : 195.15,
    T_desorb: d.T_desorb != null ? d.T_desorb : 363.15,
    P_charge: d.P_charge != null ? d.P_charge : 10,
    P_discharge: d.P_discharge != null ? d.P_discharge : 1,
    cycles: d.cycles != null ? d.cycles : 5,
    regularFactor: d.regular_factor != null ? d.regular_factor : 0.75,
    capacityFade: d.capacity_fade != null ? d.capacity_fade : 0,
    pressures: d.pressures || [1,2,3,4,5,6,7,8,9,10],
  };
}
const state = { screen: "setup", ...specDefaults() };
const PHYS = window.VesselPhysics.make(MC);

const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const fmt = (v,d=4) => Number(v).toFixed(d);
const C2K = c => c + 273.15, K2C = k => k - 273.15;

/* ------------------------------------------------------------------- charts */
function lineChart(series, opts = {}) {
  const W=760, H=opts.height||380, m={t:18,r:opts.r2?58:18,b:52,l:74};
  const iw=W-m.l-m.r, ih=H-m.t-m.b, logY=!!opts.logY;
  const xs=series.flatMap(s=>s.x), ys=series.flatMap(s=>s.y).filter(v=>logY? v>0 : true);
  const xMin=opts.xMin!=null?opts.xMin:0, xMax=Math.max(...xs);
  let yMax=Math.max(...ys), yMin=logY?Math.min(...ys):0;
  if (logY){ yMax=Math.pow(10,Math.ceil(Math.log10(yMax))); yMin=Math.pow(10,Math.floor(Math.log10(yMin))); }
  else { yMax=yMax*1.08||1; if(opts.yMin!=null) yMin=opts.yMin; }
  const px=v=>m.l+(v-xMin)/((xMax-xMin)||1)*iw;
  const py=v=>logY? m.t+ih-(Math.log10(Math.max(v,yMin))-Math.log10(yMin))/((Math.log10(yMax)-Math.log10(yMin))||1)*ih
                  : m.t+ih-(v-yMin)/((yMax-yMin)||1)*ih;
  let g="";
  const yT=[]; if(logY){for(let e=Math.log10(yMin);e<=Math.log10(yMax)+1e-9;e++) yT.push(Math.pow(10,e));}
  else for(let i=0;i<=5;i++) yT.push(yMin+(yMax-yMin)*i/5);
  yT.forEach(t=>{ g+=`<line class="grid" x1="${m.l}" y1="${py(t).toFixed(1)}" x2="${m.l+iw}" y2="${py(t).toFixed(1)}"/>`;
    g+=`<text x="${m.l-9}" y="${(py(t)+4).toFixed(1)}" text-anchor="end">${logY?t.toExponential(0):(Math.abs(yMax)<1?t.toFixed(4):t.toFixed(1))}</text>`; });
  const xT=opts.xTicks||Array.from({length:6},(_,i)=>xMin+(xMax-xMin)*i/5);
  xT.forEach(t=>{ g+=`<line class="grid" x1="${px(t).toFixed(1)}" y1="${m.t}" x2="${px(t).toFixed(1)}" y2="${m.t+ih}"/>`;
    g+=`<text x="${px(t).toFixed(1)}" y="${m.t+ih+19}" text-anchor="middle">${Number(t).toFixed(xMax>50?0:(xMax>10?0:0))}</text>`; });
  if (opts.hline != null && !logY && opts.hline<=yMax)
    g+=`<line x1="${m.l}" y1="${py(opts.hline).toFixed(1)}" x2="${m.l+iw}" y2="${py(opts.hline).toFixed(1)}" stroke="#c62828" stroke-width="1.6" stroke-dasharray="7 4"/>`
      +`<text x="${m.l+iw-5}" y="${(py(opts.hline)-6).toFixed(1)}" text-anchor="end" style="fill:#c62828;font-weight:650">${esc(opts.hlineLabel||"")}</text>`;
  g+=`<line class="axis" x1="${m.l}" y1="${m.t+ih}" x2="${m.l+iw}" y2="${m.t+ih}"/>`;
  g+=`<line class="axis" x1="${m.l}" y1="${m.t}" x2="${m.l}" y2="${m.t+ih}"/>`;
  let paths="";
  series.forEach(s=>{
    const pts=s.x.map((x,i)=>[px(x),py(s.y[i])]);
    paths+=`<polyline fill="none" stroke="${s.color}" stroke-width="${s.w||2}" ${s.dash?'stroke-dasharray="6 4"':""} opacity="${s.op||1}" points="${pts.map(p=>`${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ")}"/>`;
    if(s.markers!==false && s.x.length<=15) pts.forEach(p=>paths+=`<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="3.4" fill="${s.color}"/>`);
  });
  const legend=series.filter(s=>s.label).map(s=>`<span><i class="swatch" style="background:${s.color}"></i>${esc(s.label)}</span>`).join("");
  return `<svg class="chart" viewBox="0 0 ${W} ${H}">${g}${paths}
    <text class="axis-title" x="${m.l+iw/2}" y="${H-9}" text-anchor="middle">${esc(opts.xLabel||"")}</text>
    <text class="axis-title" x="${-(m.t+ih/2)}" y="16" text-anchor="middle" transform="rotate(-90)">${esc(opts.yLabel||"")}</text>
    </svg><div class="legend">${legend}</div>`;
}

function barChart(items, opts={}) {
  const W=760,H=340,m={t:22,r:18,b:88,l:80}, iw=W-m.l-m.r, ih=H-m.t-m.b;
  const logY=!!opts.logY;
  let yMax=Math.max(...items.map(i=>i.value), opts.hline||0);
  let yMin=logY?Math.pow(10,Math.floor(Math.log10(Math.min(...items.map(i=>i.value))))):0;
  if(logY) yMax=Math.pow(10,Math.ceil(Math.log10(yMax))); else yMax*=1.15;
  const py=v=>logY? m.t+ih-(Math.log10(Math.max(v,yMin))-Math.log10(yMin))/((Math.log10(yMax)-Math.log10(yMin))||1)*ih
                  : m.t+ih-(v/yMax)*ih;
  const bw=iw/items.length; let g="";
  const yT=[]; if(logY){for(let e=Math.log10(yMin);e<=Math.log10(yMax)+1e-9;e++) yT.push(Math.pow(10,e));}
  else for(let i=0;i<=5;i++) yT.push(yMax*i/5);
  yT.forEach(t=>{ g+=`<line class="grid" x1="${m.l}" y1="${py(t).toFixed(1)}" x2="${m.l+iw}" y2="${py(t).toFixed(1)}"/>`;
    g+=`<text x="${m.l-9}" y="${(py(t)+4).toFixed(1)}" text-anchor="end">${logY?t.toExponential(0):t.toFixed(3)}</text>`; });
  items.forEach((it,i)=>{
    const x=m.l+i*bw+bw*0.2, w=bw*0.6, y=py(it.value), h=m.t+ih-y;
    g+=`<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${w.toFixed(1)}" height="${Math.max(h,1).toFixed(1)}" fill="${it.color}" rx="3"/>`;
    g+=`<text x="${(x+w/2).toFixed(1)}" y="${(y-6).toFixed(1)}" text-anchor="middle" style="font-weight:650;font-size:10px">${esc(it.top||fmt(it.value,4))}</text>`;
    it.label.split(" ").reduce((acc,wd)=>{ if((acc[acc.length-1]+" "+wd).trim().length>14) acc.push(wd); else acc[acc.length-1]=(acc[acc.length-1]+" "+wd).trim(); return acc; },[""])
      .slice(0,3).forEach((L,k)=> g+=`<text x="${(x+w/2).toFixed(1)}" y="${m.t+ih+18+k*12}" text-anchor="middle" style="font-size:9.5px">${esc(L)}</text>`);
  });
  if(opts.hline!=null) g+=`<line x1="${m.l}" y1="${py(opts.hline).toFixed(1)}" x2="${m.l+iw}" y2="${py(opts.hline).toFixed(1)}" stroke="#c62828" stroke-width="1.8" stroke-dasharray="7 4"/>`
    +`<text x="${m.l+iw-5}" y="${(py(opts.hline)-6).toFixed(1)}" text-anchor="end" style="fill:#c62828;font-weight:650">${esc(opts.hlineLabel||"")}</text>`;
  g+=`<line class="axis" x1="${m.l}" y1="${m.t+ih}" x2="${m.l+iw}" y2="${m.t+ih}"/><line class="axis" x1="${m.l}" y1="${m.t}" x2="${m.l}" y2="${m.t+ih}"/>`;
  return `<svg class="chart" viewBox="0 0 ${W} ${H}">${g}
    <text class="axis-title" x="${-(m.t+ih/2)}" y="16" text-anchor="middle" transform="rotate(-90)">${esc(opts.yLabel||"")}</text></svg>`;
}

/* ------------------------------------------------------------------ screens */
const SCREENS = [["setup","Setup","Samples & vessel"],["vessel3d","3D Vessel","Charge / desorb"],
                 ["isotherms","Isotherms","4 samples"],
                 ["cycle","Duty Cycle","Charge / discharge"],["performance","Performance","DOE & findings"]];

function screenSetup() {
  const rows = MC.samples.map(s => `<tr>
    <td><span class="swatch" style="background:${COLORS[s.id]}"></span>${s.id}</td>
    <td>${esc(s.label)}</td><td style="text-align:left">${esc(s.equivalent)}</td>
    <td style="text-align:left">${s.activation === "activated" ? "CaCl₂, 300 °C" : "—"}</td>
    <td>${fmt(PHYS.sampleQMax(s, state.regularFactor),4)}</td>
    <td>${fmt(PHYS.freeGasVolume(s.form),1)} cm³</td></tr>`).join("");
  const v = MC.vessel;
  return `
  <div class="card"><h3>Sample matrix — 2×2 design (spec Section 1)</h3><div class="body">
    <div class="note warn"><span class="dev-tag">SPEC-DEV-4</span><span>
      “Zeolite-14A” is not a standard designation. LTA is supplied as 3A/4A/5A; 13X is FAU.
      Ca-exchanged zeolite A <b>is</b> 5A and untreated Na-form <b>is</b> 4A — so published
      isotherms already exist for the activated samples.</span></div>
    <div class="tbl-wrap"><table><thead><tr><th>#</th><th>Sample</th>
      <th style="text-align:left">Equivalent</th><th style="text-align:left">Activation</th>
      <th>q_max (wt%)</th><th>Free gas vol</th></tr></thead><tbody>${rows}</tbody></table></div>
    <p class="hint">${MC.samples.length} samples × ${fmt(K.SAMPLE_MASS_G,0)} g each, run sequentially in one vessel.</p>
  </div></div>

  <div class="grid2">
    <div class="card"><h3>Vessel (spec Section 3)</h3><div class="body">
      <div class="tbl-wrap"><table><tbody>
        <tr><td>Internal volume</td><td>${fmt(v.internal_cm3,1)} cm³</td></tr>
        <tr><td>Geometry</td><td>50 mm ⌀ × 250 mm</td></tr>
        <tr><td>Wall thickness</td><td>${v.wall_thickness_mm} mm (outer ⌀ ${v.outer_diameter_mm} mm)</td></tr>
        <tr><td>Bed void fraction</td><td>${v.void_fraction}</td></tr>
        <tr><td>Max design pressure</td><td><b>${v.max_design_bar} bar</b></td></tr>
      </tbody></table></div>
    </div></div>
    <div class="card"><h3>Flagged assumptions</h3><div class="body">
      <div class="note bad"><span class="dev-tag">SPEC-DEV-1</span><span>
        The spec's “~2.2 wt% at near-ambient” plausibility floor is a <b>77 K</b> figure.
        Zeolites hold ~10⁻³ wt% at 25 °C. Anchoring to it embeds a 40–1000× error.</span></div>
      <div class="note warn"><span class="dev-tag">SPEC-DEV-2</span><span>
        “Isothermal at −78 °C” cannot coexist with “desorb by heating to 80–100 °C”.
        Modelled as a temperature swing, isothermal within each stage.</span></div>
      <div class="note warn"><span class="dev-tag">SPEC-DEV-3</span><span>
        Source “below 10 bar” cannot fill to a 10 bar target. Source pressure is a
        parameter defaulting above target.</span></div>
      <div class="note info"><span>⚠️ ${esc(MC.notes.regular_factor)}</span></div>
    </div></div>
  </div>`;
}

function screenIsotherms() {
  const iso = PHYS.isothermTable(state);
  const series = iso.map(r => ({ label:`${r.id}. ${r.label}`, color:COLORS[r.id],
                                 dash:r.form === "granule", x:r.pressures, y:r.wt_pct }));
  const rows = iso.map(r => `<tr>
    <td><span class="swatch" style="background:${COLORS[r.id]}"></span>${r.id}</td>
    <td>${esc(r.label)}</td><td>${fmt(r.q_max,4)}</td>
    ${[1,5,10].map(p=>`<td>${fmt(r.wt_pct[r.pressures.indexOf(p)],5)}</td>`).join("")}
    <td>${fmt(r.grams[r.grams.length-1],4)} g</td>
    <td>${fmt(r.pct_of_doe[r.pct_of_doe.length-1],3)}%</td></tr>`).join("");
  return `
  <div class="card"><h3>Adsorption isotherms at ${fmt(K2C(state.T_charge),0)} °C</h3><div class="body">
    <div class="note info"><span>Langmuir model (spec Section 2), q<sub>st</sub> =
      <b>${state.qst} kJ/mol</b>, fitted to Langmi et al. (2003) zeolite 5A at 77 K then
      transferred through b(T). Solid = powder, dashed = granule.</span></div>
    ${lineChart(series, { xLabel:"Pressure (bar)", yLabel:"Capacity (wt%)" })}
  </div></div>
  <div class="card"><h3>Capacity table</h3><div class="body"><div class="tbl-wrap">
    <table><thead><tr><th>#</th><th>Sample</th><th>q_max</th><th>1 bar</th><th>5 bar</th>
      <th>10 bar</th><th>g per 125 g</th><th>% of DOE</th></tr></thead>
      <tbody>${rows}</tbody></table></div>
    <p class="hint" style="margin-top:8px">All values wt% unless noted. DOE target is
      ${K.DOE_TARGET_WT} wt%.</p></div></div>`;
}

function screenCycle() {
  const sim = PHYS.simulate(state);
  const ads = sim.map(r => ({ label:`${r.id}. ${r.label}`, color:COLORS[r.id],
                              x:r.trace.t, y:r.trace.ads, markers:false }));
  const t0 = sim[0].trace;
  const pt = [{ label:"Pressure (bar)", color:"#548235", x:t0.t, y:t0.P, markers:false }];
  const tt = [{ label:"Temperature (°C)", color:"#7030a0", x:t0.t, y:t0.T.map(K2C), markers:false }];
  const over = sim.filter(r => r.overPressure);
  const stageRow = MC.stages.map(s => `<td>${esc(s.name)}<br><small style="color:var(--ink-2)">${s.minutes} min</small></td>`).join("");
  return `
  ${over.length ? `<div class="note bad"><span class="dev-tag">SAFETY</span><span>
    Peak pressure reaches <b>${fmt(Math.max(...sim.map(r=>r.peakP)),2)} bar</b> against the
    <b>${K.MAX_DESIGN_BAR} bar</b> design rating when the vessel is heated sealed.
    Gas-law expansion accounts for most of it. Either vent during heating, lower the charge
    pressure, or raise the rating.</span></div>` : ""}
  <div class="card"><h3>H₂ adsorbed vs time — ${state.cycles} cycles</h3><div class="body">
    <div class="tbl-wrap"><table style="margin-bottom:10px"><thead><tr><th style="text-align:left">Stage</th>${stageRow}</tr></thead></table></div>
    ${lineChart(ads, { xLabel:"Time (min)", yLabel:"H₂ adsorbed (g)", height:340 })}
  </div></div>
  <div class="grid2">
    <div class="card"><h3>Vessel pressure</h3><div class="body">
      ${lineChart(pt, { xLabel:"Time (min)", yLabel:"Pressure (bar)", height:320,
                        hline:K.MAX_DESIGN_BAR, hlineLabel:`design ${K.MAX_DESIGN_BAR} bar` })}
    </div></div>
    <div class="card"><h3>Temperature schedule</h3><div class="body">
      ${lineChart(tt, { xLabel:"Time (min)", yLabel:"Temperature (°C)", height:320 })}
      <div class="note warn" style="margin-top:10px"><span class="dev-tag">SPEC-DEV-5</span>
        <span>Equilibrium is instantaneous per Section 5, so the sorbent adds no time
        constant — these curves are shaped entirely by the heating and venting schedule,
        not by adsorption kinetics.</span></div>
    </div></div>
  </div>`;
}

function screenPerformance() {
  const sim = PHYS.simulate(state);
  const items = sim.map(r => ({ label:r.label, value:r.chargedWt, color:COLORS[r.id],
                                top:`${fmt(r.chargedWt,4)} (${fmt(r.pctOfDoe,2)}%)` }));
  const ranked = [...sim].sort((a,b) => b.working - a.working);
  const rows = ranked.map((r,i) => `<tr class="${i===0?"best":""}">
    <td>${i+1}</td><td><span class="swatch" style="background:${COLORS[r.id]}"></span>${r.id}</td>
    <td style="text-align:left">${esc(r.label)}</td>
    <td>${fmt(r.chargedWt,5)}</td><td>${fmt(r.working,5)}</td>
    <td>${fmt(r.peakP,2)}${r.overPressure?' <span class="pill bad">over</span>':""}</td>
    <td>${fmt(r.pctOfDoe,3)}%</td><td>${fmt(r.adsorbedFraction*100,1)}%</td></tr>`).join("");
  const cyc = sim.map(r => ({ label:`${r.id}. ${r.label}`, color:COLORS[r.id],
                              x:r.perCycle.map(c=>c.cycle), y:r.perCycle.map(c=>c.working) }));
  const best = ranked[0];
  return `
  <div class="card"><h3>Against the US DOE target (${K.DOE_TARGET_WT} wt%)</h3><div class="body">
    ${barChart(items, { yLabel:"Capacity (wt%, log scale)", logY:true,
                        hline:K.DOE_TARGET_WT, hlineLabel:`DOE ${K.DOE_TARGET_WT} wt%` })}
    <div class="note warn" style="margin-top:10px"><span>Best sample reaches
      <b>${fmt(best.pctOfDoe,2)}%</b> of the DOE target. This is the expected result for
      physisorption above 77 K — state it directly rather than presenting it as a
      shortfall to explain away.</span></div>
  </div></div>
  <div class="grid2">
    <div class="card"><h3>Ranked performance</h3><div class="body"><div class="tbl-wrap">
      <table><thead><tr><th>#</th><th>ID</th><th style="text-align:left">Sample</th>
        <th>Charged wt%</th><th>Working g</th><th>Peak bar</th><th>% DOE</th>
        <th>Ads. frac</th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="note warn" style="margin-top:11px"><span>Adsorption accounts for only
        <b>${fmt(best.adsorbedFraction*100,1)}%</b> of stored H₂ in the best case — the
        vessel is storing mostly as compressed gas in the void volume.</span></div>
    </div></div>
    <div class="card"><h3>Working capacity vs cycle</h3><div class="body">
      ${lineChart(cyc, { xLabel:"Cycle", yLabel:"Working capacity (g)", height:300,
                         xMin:1, xTicks:Array.from({length:state.cycles},(_,i)=>i+1) })}
      ${state.capacityFade === 0 ? `<div class="note warn" style="margin-top:10px">
        <span class="dev-tag">SPEC-DEV-6</span><span>No degradation mechanism is specified,
        so every cycle is identical by construction and this plot is flat by definition.
        Set a fade rate on the left to impose one.</span></div>` : ""}
    </div></div>
  </div>`;
}


/* ------------------------------------------------------- 3D vessel screen */
let V3D = null, v3dPlaying = true;
const V3D_STAGES = [
  { name: "Charge",       P: 10, T: 195, sat: 0.85 },
  { name: "Hold",         P: 10, T: 195, sat: 1.00 },
  { name: "Heat (sealed)",P: 19, T: 300, sat: 0.55 },
  { name: "Desorb",       P: 1,  T: 363, sat: 0.05 },
  { name: "Cool",         P: 1,  T: 195, sat: 0.05 },
];

function screenVessel3D() {
  const sim = PHYS.simulate(state);
  const best = sim.reduce((a,b) => b.working > a.working ? b : a);
  const peak = Math.max(...sim.map(r => r.peakP));
  return `
  <div class="card"><h3>3D vessel — duty cycle</h3><div class="body">
    <div class="note info"><span>Built from the spec's dimensions: 50&nbsp;mm ⌀ ×
      250&nbsp;mm, ${MC.vessel.wall_thickness_mm}&nbsp;mm wall, bed void fraction
      ${MC.vessel.void_fraction}. Drag to orbit, scroll to zoom.</span></div>
    <div class="v3d-wrap" id="v3dHost">
      <div class="v3d-stage"><span class="dot"></span><span id="v3dStage">Charge</span></div>
      <div class="v3d-hint">drag to orbit &middot; scroll to zoom &middot; right-drag to pan</div>
    </div>
    <div class="v3d-bar">
      <button id="v3dPlay" class="on">Pause</button>
      <button id="v3dCut" class="on">Cutaway</button>
      <button id="v3dLabels" class="on">Labels</button>
      <button id="v3dReset">Reset view</button>
      <button id="v3dShot">Save PNG</button>
      <span style="flex:1"></span>
      <span class="hint" style="margin:0">Showing sample ${best.id} — ${esc(best.label)}</span>
    </div>
    <div class="v3d-layers" id="v3dLayers"></div>
  </div></div>

  <div class="grid2">
    <div class="card"><h3>Cycle stages</h3><div class="body">
      <div class="tbl-wrap"><table><thead><tr><th style="text-align:left">Stage</th>
        <th>Pressure</th><th>Temperature</th><th>Bed loading</th></tr></thead><tbody>
        ${V3D_STAGES.map((s,i)=>`<tr id="v3dRow${i}"><td style="text-align:left">${s.name}</td>
          <td>${s.P} bar</td><td>${s.T} K (${(s.T-273.15).toFixed(0)} °C)</td>
          <td>${(s.sat*100).toFixed(0)}%</td></tr>`).join("")}
      </tbody></table></div>
      <div class="note bad" style="margin-top:11px"><span class="dev-tag">SAFETY</span><span>
        The heat stage is where pressure peaks at <b>${fmt(peak,1)} bar</b> against the
        <b>${K.MAX_DESIGN_BAR} bar</b> rating. The animation holds the vessel sealed through
        heating, which is the conservative reading of the spec.</span></div>
    </div></div>
    <div class="card"><h3>What the animation is showing</h3><div class="body">
      <div class="note warn"><span class="dev-tag">READ THIS</span><span>
        Particle counts are <b>illustrative, not quantitative</b>. The bed holds
        ${fmt(best.charged,4)}&nbsp;g of H&#8322; across ${K.SAMPLE_MASS_G}&nbsp;g of adsorbent;
        the scene draws a few hundred molecules so the mechanism reads.</span></div>
      <div class="kpis">
        <div class="kpi"><div class="lab">Adsorbed at charge</div>
          <div class="val">${fmt(best.charged,4)}</div><div class="sub">g H₂</div></div>
        <div class="kpi"><div class="lab">Free gas</div>
          <div class="val">${fmt(best.freeGas,3)}</div><div class="sub">g H₂ in void</div></div>
        <div class="kpi"><div class="lab">By adsorption</div>
          <div class="val">${fmt(best.adsorbedFraction*100,1)}%</div><div class="sub">of total stored</div></div>
      </div>
    </div></div>
  </div>`;
}

function mountVessel3D() {
  const host = document.getElementById("v3dHost");
  if (!host || !window.__createVesselView) return;
  if (V3D) { V3D.dispose(); V3D = null; }
  V3D = window.__createVesselView(host, {
    dims: { innerDiaMm: 50, lengthMm: 250, wallMm: MC.vessel.wall_thickness_mm,
            deadSpaceMm: 25, showCarbon: false, heatingTape: true, bathFill: 0.6 },
    vesselLabel: "Vessel · SS, ID 50 × 250 mm, 15 bar",
    gaugeLabel: "Pressure indicator",
    bedLabel: "Zeolite-A bed · 125 g",
    bathLabel: "Dry ice + acetone, −78 °C",
  });
  const names = { shell:"Vessel shell", caps:"End caps", bed:"Adsorbent bed",
                  screens:"Mesh filters", bath:"Cooling bath",
                  piping:"Piping & instruments", tape:"Heating element", flow:"H₂ molecules" };
  document.getElementById("v3dLayers").innerHTML = V3D.getLayers().map(k =>
    `<label><input type="checkbox" data-layer="${k}" checked> ${names[k]||k}</label>`).join("");
  document.querySelectorAll("[data-layer]").forEach(cb =>
    cb.onchange = () => V3D.setLayer(cb.dataset.layer, cb.checked));

  const btn = (id, fn) => { const e = document.getElementById(id); if (e) e.onclick = () => fn(e); };
  btn("v3dPlay", e => { v3dPlaying = !v3dPlaying;
    e.textContent = v3dPlaying ? "Pause" : "Play"; e.classList.toggle("on", v3dPlaying); });
  btn("v3dCut", e => e.classList.toggle("on", V3D.toggleCutaway()));
  btn("v3dLabels", e => { const on = !e.classList.contains("on"); e.classList.toggle("on", on); V3D.setLabels(on); });
  btn("v3dReset", () => V3D.resetView());
  btn("v3dShot", () => { const a = document.createElement("a");
    a.href = V3D.snapshot(); a.download = "vessel_3d.png"; a.click(); });

  clearInterval(mountVessel3D._timer);
  let i = 0;
  const apply = () => {
    const s = V3D_STAGES[i];
    V3D.setState({ pressure: s.P, temperature: s.T, saturation: s.sat, flowing: s.sat > 0.1 });
    if (i === 0) V3D.resetAdsorption();
    const el = document.getElementById("v3dStage"); if (el) el.textContent = s.name;
    V3D_STAGES.forEach((_, k) => { const r = document.getElementById("v3dRow"+k);
      if (r) r.className = k === i ? "best" : ""; });
  };
  apply();
  mountVessel3D._timer = setInterval(() => {
    if (!v3dPlaying || state.screen !== "vessel3d") return;
    i = (i + 1) % V3D_STAGES.length; apply();
  }, 4200);
}

const RENDER = { setup:screenSetup, vessel3d:screenVessel3D, isotherms:screenIsotherms, cycle:screenCycle, performance:screenPerformance };

/* -------------------------------------------------------------------- shell */
function renderRails() {
  const sim = PHYS.simulate(state);
  const best = sim.reduce((a,b) => b.working > a.working ? b : a);
  const over = sim.some(r => r.overPressure);
  document.getElementById("rail-right").innerHTML = `
    <div class="card"><h3>Live readings</h3><div class="body">
      <div class="readout"><div class="k">Charge<b>${fmt(K2C(state.T_charge),0)} °C @ ${state.P_charge} bar</b></div>
        <div class="v">${state.cycles}×</div></div>
      <div class="readout"><div class="k">Isosteric heat<b>q_st</b></div>
        <div class="v">${state.qst} <small>kJ/mol</small></div></div>
      <div class="readout"><div class="k">Best sample<b>${esc(best.label)}</b></div>
        <div class="v">${fmt(best.working,4)} g</div></div>
      <div class="readout"><div class="k">Of DOE target<b>${K.DOE_TARGET_WT} wt%</b></div>
        <div class="v">${fmt(best.pctOfDoe,2)}%</div></div>
      <div class="readout"><div class="k">Peak pressure<b>design ${K.MAX_DESIGN_BAR} bar</b></div>
        <div class="v"><span class="pill ${over?"bad":"ok"}">${fmt(Math.max(...sim.map(r=>r.peakP)),1)} bar</span></div></div>
    </div></div>
    <div class="card"><h3>Export</h3><div class="body">
      <button class="btn ghost" id="csvBtn">Download results (CSV)</button>
      <p class="hint">For the .xlsx, .docx and 300 dpi figures, run the engine:</p>
      <code style="display:block;background:var(--panel-2);border:1px solid var(--line);
        border-radius:6px;padding:8px;font-size:11px;margin-top:6px;overflow-x:auto">python engine/run.py --q-st ${state.qst}</code>
    </div></div>`;
  document.getElementById("csvBtn").onclick = downloadCsv;
}

function render() {
  document.querySelectorAll(".step").forEach(el => el.classList.toggle("active", el.dataset.screen === state.screen));
  document.getElementById("main").innerHTML = RENDER[state.screen]();
  renderRails();
  if (state.screen === "vessel3d") mountVessel3D();
  else if (V3D) { clearInterval(mountVessel3D._timer); V3D.dispose(); V3D = null; }
}

function downloadCsv() {
  const sim = PHYS.simulate(state), iso = PHYS.isothermTable(state);
  const L = [`# Vessel simulation — charge ${fmt(K2C(state.T_charge),0)} C @ ${state.P_charge} bar, desorb ${fmt(K2C(state.T_desorb),0)} C`,
             `# q_st=${state.qst} kJ/mol, cycles=${state.cycles}, regular_factor=${state.regularFactor}`,
             "", "# Isotherms (wt%)", ["id","sample",...iso[0].pressures.map(p=>`${p}bar`)].join(",")];
  iso.forEach(r => L.push([r.id, `"${r.label}"`, ...r.wt_pct.map(v=>v.toFixed(6))].join(",")));
  L.push("", "# Cycle performance",
         ["id","sample","charged_wt_pct","charged_g","working_g","peak_bar","pct_of_doe","adsorbed_fraction"].join(","));
  sim.forEach(r => L.push([r.id, `"${r.label}"`, r.chargedWt.toFixed(6), r.charged.toFixed(6),
    r.working.toFixed(6), r.peakP.toFixed(3), r.pctOfDoe.toFixed(4), (r.adsorbedFraction*100).toFixed(2)].join(",")));
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([L.join("\n")], {type:"text/csv"}));
  a.download = `vessel_simulation_qst${state.qst}.csv`; a.click(); URL.revokeObjectURL(a.href);
}

function syncControls() {
  Object.assign(state, specDefaults());
  const set = (id,v) => { const e=document.getElementById(id); if(e) e.value=v; };
  set("qst", state.qst); set("tcharge", K2C(state.T_charge).toFixed(0));
  set("tdesorb", K2C(state.T_desorb).toFixed(0)); set("pcharge", state.P_charge);
  set("cycles", state.cycles); set("regfac", state.regularFactor); set("fade", state.capacityFade);
  document.getElementById("qstVal").textContent = Number(state.qst).toFixed(1);
  document.getElementById("regfacVal").textContent = Number(state.regularFactor).toFixed(2);
  document.getElementById("fadeVal").textContent = (state.capacityFade*100).toFixed(0) + "%";
}

function init() {
  document.getElementById("steps").innerHTML = SCREENS.map(([k,t,s],i) =>
    `<button class="step" data-screen="${k}"><span class="n">${i+1}</span>
      <span><b style="display:block;font-size:12.5px">${t}</b>
      <span style="font-size:10.5px;opacity:.8">${s}</span></span></button>`).join("");
  document.querySelectorAll(".step").forEach(el => el.onclick = () => { state.screen = el.dataset.screen; render(); });

  const bind = (id, fn) => document.getElementById(id).addEventListener("input", e => { fn(e.target.value); render(); });
  bind("qst", v => { state.qst = parseFloat(v); document.getElementById("qstVal").textContent = state.qst.toFixed(1); });
  bind("tcharge", v => state.T_charge = C2K(parseFloat(v)));
  bind("tdesorb", v => state.T_desorb = C2K(parseFloat(v)));
  bind("pcharge", v => state.P_charge = parseFloat(v));
  bind("cycles", v => state.cycles = parseInt(v,10));
  bind("regfac", v => { state.regularFactor = parseFloat(v); document.getElementById("regfacVal").textContent = state.regularFactor.toFixed(2); });
  bind("fade", v => { state.capacityFade = parseFloat(v); document.getElementById("fadeVal").textContent = (state.capacityFade*100).toFixed(0)+"%"; });

  document.getElementById("resetBtn").onclick = () => { syncControls(); render(); };
  document.getElementById("themeBtn").onclick = () => {
    const dark = document.documentElement.dataset.theme === "dark";
    document.documentElement.dataset.theme = dark ? "light" : "dark";
    document.getElementById("themeBtn").textContent = dark ? "☾" : "☀";
  };
  window.addEventListener("vessel3d-ready", () => {
    if (state.screen === "vessel3d") mountVessel3D();
  });
  syncControls(); render();
}
document.addEventListener("DOMContentLoaded", init);
})();
