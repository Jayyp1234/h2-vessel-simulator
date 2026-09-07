/* Shared physics core. Mirrors engine/model.py and engine/cycle.py.
   Loaded by the browser app and by engine/parity_check.py under node, so the two
   implementations are tested against each other rather than assumed to agree. */
(function (root, factory) {
  const mod = factory();
  if (typeof module === "object" && module.exports) module.exports = mod;
  else root.VesselPhysics = mod;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const langmuir = (P, qMax, b) => qMax * b * P / (1 + b * P);

  function make(MC) {
    const { R, M_H2, T_BENCH, SAMPLE_MASS_G, DOE_TARGET_WT, MAX_DESIGN_BAR } = MC.constants;

    function sampleQMax(s, regularFactor) {
      let q = MC.fit.q_max;
      if (s.activation === "regular") q *= regularFactor;
      q *= s.form === "powder" ? MC.factors.powder : (1 - MC.factors.binder);
      return q;
    }

    /** Equilibrium uptake, wt%. Temperature enters through b(T). */
    function uptake(s, T, P, qst, regularFactor) {
      const bT = MC.fit.b_77K * Math.exp((qst * 1000 / R) * (1 / T - 1 / T_BENCH));
      return langmuir(P, sampleQMax(s, regularFactor), bT);
    }

    function freeGasVolume(form) {
      const v = MC.vessel.internal_cm3;
      const bulk = Math.min(SAMPLE_MASS_G / MC.bulk_density[form], v);
      return (v - bulk) + bulk * MC.vessel.void_fraction;
    }

    const adsorbedG = (s, T, P, o, fade) =>
      uptake(s, T, P, o.qst, o.regularFactor) / 100 * SAMPLE_MASS_G * (fade == null ? 1 : fade);
    const gasG = (P, T, vCm3) => (P * 1e5) * (vCm3 * 1e-6) / (R * T) * M_H2;

    /** Sealed-vessel pressure after heating: total H2 conserved, redistributed. */
    function closedVolumePressure(s, T, vFree, o, fade) {
      const total = adsorbedG(s, o.T_charge, o.P_charge, o, fade)
                  + gasG(o.P_charge, o.T_charge, vFree);
      let lo = 0.01, hi = 200;
      for (let i = 0; i < 80; i++) {
        const mid = 0.5 * (lo + hi);
        if (adsorbedG(s, T, mid, o, fade) + gasG(mid, T, vFree) < total) lo = mid;
        else hi = mid;
      }
      return 0.5 * (lo + hi);
    }

    function isothermTable(o) {
      return MC.samples.map(s => {
        const wt = o.pressures.map(p => uptake(s, o.T_charge, p, o.qst, o.regularFactor));
        return Object.assign({}, s, {
          q_max: sampleQMax(s, o.regularFactor),
          pressures: o.pressures, wt_pct: wt,
          grams: wt.map(v => v / 100 * SAMPLE_MASS_G),
          pct_of_doe: wt.map(v => v / DOE_TARGET_WT * 100),
        });
      });
    }

    function simulate(o) {
      const dt = MC.dt_min || 0.5;
      return MC.samples.map(s => {
        const vFree = freeGasVolume(s.form);
        const trace = { t: [], T: [], P: [], ads: [], gas: [], total: [], stage: [], cycle: [] };
        const perCycle = [];
        let clock = 0;

        for (let c = 1; c <= o.cycles; c++) {
          const fade = Math.pow(1 - o.capacityFade, c - 1);
          for (const st of MC.stages) {
            const n = Math.max(Math.round(st.minutes / dt), 1);
            for (let i = 1; i <= n; i++) {
              const f = i / n;
              let T, P;
              if (st.name === "charge") {
                T = o.T_charge; P = o.P_discharge + f * (o.P_charge - o.P_discharge);
              } else if (st.name === "hold") {
                T = o.T_charge; P = o.P_charge;
              } else if (st.name === "heat") {
                T = o.T_charge + f * (o.T_desorb - o.T_charge);
                P = closedVolumePressure(s, T, vFree, o, fade);
              } else if (st.name === "desorb") {
                T = o.T_desorb;
                const peak = closedVolumePressure(s, o.T_desorb, vFree, o, fade);
                P = peak + f * (o.P_discharge - peak);
              } else {
                T = o.T_desorb + f * (o.T_charge - o.T_desorb); P = o.P_discharge;
              }
              const ads = adsorbedG(s, T, P, o, fade), gas = gasG(P, T, vFree);
              clock += dt;
              trace.t.push(clock); trace.T.push(T); trace.P.push(P);
              trace.ads.push(ads); trace.gas.push(gas); trace.total.push(ads + gas);
              trace.stage.push(st.name); trace.cycle.push(c);
            }
          }
          const charged = adsorbedG(s, o.T_charge, o.P_charge, o, fade);
          const residual = adsorbedG(s, o.T_desorb, o.P_discharge, o, fade);
          perCycle.push({
            cycle: c, charged, residual, working: charged - residual,
            workingWt: (charged - residual) / SAMPLE_MASS_G * 100,
            peakP: closedVolumePressure(s, o.T_desorb, vFree, o, fade),
          });
        }

        const c1 = perCycle[0];
        const freeAtCharge = gasG(o.P_charge, o.T_charge, vFree);
        return Object.assign({}, s, {
          vFree, trace, perCycle,
          chargedWt: c1.charged / SAMPLE_MASS_G * 100,
          charged: c1.charged, working: c1.working, peakP: c1.peakP,
          overPressure: c1.peakP > MAX_DESIGN_BAR,
          pctOfDoe: (c1.charged / SAMPLE_MASS_G * 100) / DOE_TARGET_WT * 100,
          freeGas: freeAtCharge,
          adsorbedFraction: c1.charged / (c1.charged + freeAtCharge),
        });
      });
    }

    return { uptake, sampleQMax, freeGasVolume, closedVolumePressure,
             isothermTable, simulate, adsorbedG, gasG, MC };
  }

  return { make, langmuir };
});
