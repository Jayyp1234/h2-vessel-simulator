"""
Transient charge/discharge duty cycle for the vessel. Spec Sections 4-6.

Model: lumped, well-mixed tank (spec Section 6), ideal gas (Section 5), instantaneous
adsorption equilibrium (Section 5). Because equilibrium is instantaneous [SPEC-DEV-5],
the sorbent contributes no time constant of its own -- every curve below is shaped by
the temperature and pressure schedule, not by adsorption kinetics. That is a property
of the specification, not of this implementation, and it is reported rather than hidden.

Each cycle runs five stages:

    charge   -- at T_charge, pressure ramps from P_discharge to P_charge
    hold     -- at T_charge and P_charge, equilibrating
    heat     -- T ramps to T_desorb at closed volume; pressure rises as gas desorbs
    desorb   -- at T_desorb, pressure vented down to P_discharge; H2 is delivered
    cool     -- T ramps back to T_charge, ready for the next charge
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

import model as M

STAGES = (
    ("charge",  20.0),   # minutes; spec leaves charge duration to the simulation
    ("hold",    10.0),
    ("heat",    30.0),
    ("desorb",  20.0),
    ("cool",    40.0),
)
DT_MIN = 0.5             # spec Section 6: "time resolution: minutes"


def _adsorbed_g(s: M.Sample, T: float, P: float, opts: M.Options,
                fade: float = 1.0) -> float:
    """Adsorbed hydrogen in grams, at instantaneous equilibrium."""
    wt = float(M.uptake(s, T, P, opts.q_st, opts.regular_factor))
    return wt / 100.0 * M.SAMPLE_MASS_G * fade


def _gas_g(P_bar: float, T: float, v_cm3: float) -> float:
    """Free gas in grams. Ideal gas per spec Section 5."""
    return (P_bar * 1e5) * (v_cm3 * 1e-6) / (M.R * T) * M.M_H2


def simulate_cycles(opts: M.Options) -> dict:
    """Run the full duty cycle for all four samples."""
    results = []
    for s in M.SAMPLES:
        v_free = M.free_gas_volume_cm3(s.form)
        t = 0.0
        trace = {k: [] for k in ("time_min", "cycle", "stage", "T_K", "P_bar",
                                 "adsorbed_g", "gas_g", "total_g", "delivered_g")}
        per_cycle, delivered_total = [], 0.0

        for c in range(1, opts.cycles + 1):
            # [SPEC-DEV-6] No degradation mechanism is specified. With pure equilibrium
            # thermodynamics every cycle is identical by construction -- which is itself
            # a finding. capacity_fade lets a loss rate be imposed if one is justified.
            fade = (1.0 - opts.capacity_fade) ** (c - 1)
            delivered_cycle = 0.0

            for stage, dur in STAGES:
                n = max(int(dur / DT_MIN), 1)
                for i in range(n):
                    f = (i + 1) / n
                    if stage == "charge":
                        T, P = opts.T_charge, opts.P_discharge + f * (opts.P_charge - opts.P_discharge)
                    elif stage == "hold":
                        T, P = opts.T_charge, opts.P_charge
                    elif stage == "heat":
                        T = opts.T_charge + f * (opts.T_desorb - opts.T_charge)
                        P = _closed_volume_pressure(s, T, v_free, opts, fade)
                    elif stage == "desorb":
                        T = opts.T_desorb
                        P_peak = _closed_volume_pressure(s, opts.T_desorb, v_free, opts, fade)
                        P = P_peak + f * (opts.P_discharge - P_peak)
                    else:  # cool
                        T = opts.T_desorb + f * (opts.T_charge - opts.T_desorb)
                        P = opts.P_discharge

                    ads, gas = _adsorbed_g(s, T, P, opts, fade), _gas_g(P, T, v_free)
                    total = ads + gas
                    if trace["total_g"] and stage in ("desorb", "heat"):
                        out = trace["total_g"][-1] - total
                        if out > 0:
                            delivered_cycle += out
                            delivered_total += out
                    t += DT_MIN
                    for k, val in (("time_min", t), ("cycle", c), ("stage", stage),
                                   ("T_K", T), ("P_bar", P), ("adsorbed_g", ads),
                                   ("gas_g", gas), ("total_g", total),
                                   ("delivered_g", delivered_total)):
                        trace[k].append(val)

            charged = _adsorbed_g(s, opts.T_charge, opts.P_charge, opts, fade)
            residual = _adsorbed_g(s, opts.T_desorb, opts.P_discharge, opts, fade)
            per_cycle.append({
                "cycle": c,
                "charged_adsorbed_g": charged,
                "residual_adsorbed_g": residual,
                "working_capacity_g": charged - residual,
                "working_capacity_wt_pct": (charged - residual) / M.SAMPLE_MASS_G * 100.0,
                "delivered_g": delivered_cycle,
                "peak_pressure_bar": _closed_volume_pressure(s, opts.T_desorb, v_free, opts, fade),
            })

        results.append({
            "id": s.id, "label": s.label, "equivalent": s.equivalent,
            "form": s.form, "activation": s.activation,
            "free_gas_cm3": v_free, "trace": trace, "per_cycle": per_cycle,
            "total_delivered_g": delivered_total,
        })
    return {"samples": results, "stages": [k for k, _ in STAGES], "dt_min": DT_MIN}


def _closed_volume_pressure(s: M.Sample, T: float, v_free: float,
                            opts: M.Options, fade: float) -> float:
    """Pressure when the vessel is heated with the outlet shut.

    Total hydrogen is conserved; it redistributes between adsorbed and gas phases as
    the sorbent releases it. Solved by bisection since adsorbed amount depends on P.
    """
    total = (_adsorbed_g(s, opts.T_charge, opts.P_charge, opts, fade)
             + _gas_g(opts.P_charge, opts.T_charge, v_free))
    lo, hi = 0.01, 200.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if _adsorbed_g(s, T, mid, opts, fade) + _gas_g(mid, T, v_free) < total:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def summarise(sim: dict, opts: M.Options) -> dict:
    """Headline numbers, including the checks the specification does not ask for."""
    rows = []
    for r in sim["samples"]:
        c1 = r["per_cycle"][0]
        charged_wt = c1["charged_adsorbed_g"] / M.SAMPLE_MASS_G * 100.0
        gas_at_charge = _gas_g(opts.P_charge, opts.T_charge, r["free_gas_cm3"])
        rows.append({
            "id": r["id"], "label": r["label"], "equivalent": r["equivalent"],
            "charged_wt_pct": charged_wt,
            "charged_g": c1["charged_adsorbed_g"],
            "working_capacity_g": c1["working_capacity_g"],
            "working_capacity_wt_pct": c1["working_capacity_wt_pct"],
            "delivered_per_cycle_g": c1["delivered_g"],
            "peak_pressure_bar": c1["peak_pressure_bar"],
            "exceeds_design_pressure": c1["peak_pressure_bar"] > M.MAX_DESIGN_BAR,
            "pct_of_doe_target": charged_wt / M.DOE_TARGET_WT * 100.0,
            "free_gas_g": gas_at_charge,
            "adsorbed_fraction": c1["charged_adsorbed_g"] / (c1["charged_adsorbed_g"] + gas_at_charge),
            "total_delivered_g": r["total_delivered_g"],
        })
    best = max(rows, key=lambda r: r["working_capacity_g"])
    return {
        "rows": rows, "best": best["id"],
        "any_over_pressure": any(r["exceeds_design_pressure"] for r in rows),
        "identical_cycles": opts.capacity_fade == 0.0,
    }
