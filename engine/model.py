"""
Isotherm core for the Zeolite-A hydrogen storage vessel simulation.

Implements the project specification, with documented departures where that
specification is internally inconsistent or physically unsupportable. Each is
tagged [SPEC-DEV-n], surfaced in the app, and written into the methodology note
so it can be defended rather than discovered.

  [SPEC-DEV-1] The spec's plausibility note cites "~2.2 wt% at near-ambient temperature,
               0-15 bar" and instructs treating it as a floor to exceed at -78 C. That
               figure is a 77 K result. Zeolites hold ~1e-3 wt% at 298 K and ~0.05 wt%
               at 195 K. Anchoring to it as a floor would bake in a 40-1000x error, so
               it is recorded as a citation to correct, not used as a target.

  [SPEC-DEV-2] "Isothermal, held at -78 C throughout charge/discharge" cannot coexist
               with "desorption trigger: heating to 80-100 C". Modelled instead as a
               temperature-swing cycle: isothermal WITHIN each stage, with explicit
               ramps between them.

  [SPEC-DEV-3] "Charging source pressure: below 10 bar" cannot reach a "target charge
               pressure: 10 bar". Source pressure is a parameter defaulting above the
               target; the spec's value is retained as a flagged inconsistency.

  [SPEC-DEV-4] "Zeolite-14A" is not a standard designation. LTA is 3A/4A/5A; 13X is FAU.
               Ca-exchanged zeolite A IS 5A and untreated (Na) zeolite A is 4A, so the
               activated/regular pair is modelled as 5A/4A -- which means published data
               already exists for the activated form.

  [SPEC-DEV-5] "Instantaneous equilibrium (not rate-limited)" means no adsorption
               kinetics exist in the model. The requested "desorption vs time" curve is
               therefore set entirely by the heating and venting schedule, not by the
               sorbent. Stated plainly rather than presented as kinetic behaviour.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import numpy as np
from scipy.optimize import curve_fit

R = 8.314
M_H2 = 2.016
T_BENCH = 77.0
DOE_TARGET_WT = 5.5          # US DOE gravimetric target, spec Section 1

# ---------------------------------------------------------------- benchmark data
# Langmi et al. (2003) J. Alloys Compd. 356-357, 710-715 -- zeolite 5A at 77 K.
# Ca-exchanged zeolite A is 5A, so this anchors the ACTIVATED samples to published
# data. The regular (Na, 4A) form has no equivalent anchor here -- see REGULAR_FACTOR.
LANGMI_5A_77K = {"pressures": (1.0, 3.0, 5.0, 7.0, 10.0),
                 "wt_pct": (0.32, 0.58, 0.74, 0.85, 0.94)}

# [SPEC-DEV-4] Na-form zeolite A (4A) has a 3.8 A aperture against 5A's 4.2 A. Ca2+
# replaces two Na+, clearing cation sites and opening the 8-ring. The spec's own note
# ("pore-blocking by extraframework cations") argues the same direction. No published
# 4A isotherm is supplied, so this is an ESTIMATE and exposed as a parameter.
REGULAR_FACTOR = 0.75
REGULAR_FACTOR_NOTE = (
    "Regular (Na-form, 4A) capacity is estimated at {:.0%} of the Ca-exchanged (5A) "
    "value. No published 4A isotherm is supplied by the specification. This single "
    "number sets the entire activated-vs-regular result and must be replaced with a "
    "measured or literature isotherm before the comparison carries any weight."
).format(REGULAR_FACTOR)

# Powder vs granule: granules carry a clay/silica binder that dilutes the active phase.
POWDER_ENHANCEMENT = 1.15    # Erdogan et al. (2024)
BINDER_FRACTION = 0.175      # not given in this spec; taken from the sister 13X/5A spec

SAMPLE_MASS_G = 125.0        # spec Section 3

# ------------------------------------------------------------------ vessel (Sec 3)
VESSEL_ID_MM = 50.0
VESSEL_L_MM = 250.0
WALL_MM = 10.0
VOID_FRACTION = 0.375        # spec gives 0.35-0.40
MAX_DESIGN_BAR = 15.0
BULK_DENSITY = {"powder": 0.60, "granule": 0.70}   # g/cm3

def vessel_geometry() -> dict:
    r_cm, l_cm = VESSEL_ID_MM / 20.0, VESSEL_L_MM / 10.0
    internal = math.pi * r_cm ** 2 * l_cm
    outer_r = (VESSEL_ID_MM / 2 + WALL_MM) / 10.0
    return {
        "internal_cm3": internal,
        "outer_diameter_mm": VESSEL_ID_MM + 2 * WALL_MM,
        "outer_volume_cm3": math.pi * outer_r ** 2 * l_cm,
        "wall_thickness_mm": WALL_MM,
        "max_design_bar": MAX_DESIGN_BAR,
        "void_fraction": VOID_FRACTION,
    }

def free_gas_volume_cm3(form: str, mass_g: float = SAMPLE_MASS_G) -> float:
    """Gas-accessible volume: headspace above the bed plus interparticle void in it."""
    v = vessel_geometry()["internal_cm3"]
    bed_bulk = mass_g / BULK_DENSITY[form]
    bed_bulk = min(bed_bulk, v)
    return (v - bed_bulk) + bed_bulk * VOID_FRACTION

# ------------------------------------------------------------------ the 4 samples
@dataclass(frozen=True)
class Sample:
    id: int
    activation: str      # "activated" | "regular"
    form: str            # "powder" | "granule"

    @property
    def label(self) -> str:
        a = "Ca-activated" if self.activation == "activated" else "Regular"
        return f"{a} {self.form}"

    @property
    def equivalent(self) -> str:
        return "5A (CaA)" if self.activation == "activated" else "4A (NaA)"

SAMPLES = [
    Sample(1, "activated", "powder"),
    Sample(2, "regular",   "powder"),
    Sample(3, "activated", "granule"),
    Sample(4, "regular",   "granule"),
]

# ------------------------------------------------------------------ isotherm model
def langmuir(P, q_max, b):
    return q_max * b * P / (1.0 + b * P)

def fit_activated_benchmark() -> dict:
    """Langmuir fit to Langmi's 5A data at 77 K. The spec mandates Langmuir (Section 2)."""
    P = np.array(LANGMI_5A_77K["pressures"], float)
    n = np.array(LANGMI_5A_77K["wt_pct"], float)
    (q_max, b), _ = curve_fit(langmuir, P, n, p0=[1.2, 0.5], maxfev=40000)
    resid = (langmuir(P, q_max, b) - n) / n * 100.0
    return {"q_max": float(q_max), "b_77K": float(b),
            "residuals_pct": [round(float(x), 3) for x in resid],
            "max_abs_error_pct": float(np.abs(resid).max()),
            "rmse_pct": float(np.sqrt((resid ** 2).mean()))}

FIT = fit_activated_benchmark()

def sample_q_max(s: Sample, regular_factor: float = REGULAR_FACTOR) -> float:
    """Predicted saturation capacity, wt%. Spec Section 2 asks for this per sample."""
    q = FIT["q_max"]
    if s.activation == "regular":
        q *= regular_factor
    q *= POWDER_ENHANCEMENT if s.form == "powder" else (1.0 - BINDER_FRACTION)
    return q

def uptake(s: Sample, T: float, P, q_st_kj: float,
           regular_factor: float = REGULAR_FACTOR):
    """Equilibrium uptake in wt%. Temperature enters through the affinity constant:

        b(T) = b(77 K) * exp[(q_st/R) * (1/T - 1/77)]

    q_max counts sites and is held temperature-independent.
    """
    P = np.asarray(P, float)
    b_T = FIT["b_77K"] * math.exp((q_st_kj * 1000.0 / R) * (1.0 / T - 1.0 / T_BENCH))
    return langmuir(P, sample_q_max(s, regular_factor), b_T)

# ------------------------------------------------------------------- run options
@dataclass
class Options:
    q_st: float = 6.0                    # kJ/mol; spec says ~5-8
    T_charge: float = 195.15             # K  (-78 C)
    T_desorb: float = 363.15             # K  (90 C, midpoint of the spec's 80-100 C)
    T_ambient: float = 298.15            # K  (25 C)
    P_charge: float = 10.0               # bar target
    P_source: float = 12.0               # bar  [SPEC-DEV-3]
    P_discharge: float = 1.0             # bar
    pressures: tuple = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0)
    regular_factor: float = REGULAR_FACTOR
    cycles: int = 5                      # spec Section 4
    capacity_fade: float = 0.0           # per-cycle fractional loss; see cycle.py

def isotherm_table(opts: Options) -> list:
    """Equilibrium isotherms for all four samples at the charge temperature."""
    out = []
    for s in SAMPLES:
        wt = uptake(s, opts.T_charge, opts.pressures, opts.q_st, opts.regular_factor)
        out.append({
            "id": s.id, "label": s.label, "activation": s.activation, "form": s.form,
            "equivalent": s.equivalent,
            "q_max_wt_pct": sample_q_max(s, opts.regular_factor),
            "pressures_bar": [float(p) for p in opts.pressures],
            "wt_pct": [float(v) for v in wt],
            "mg_per_g": [float(v) * 10 for v in wt],
            "grams_in_sample": [float(v) / 100.0 * SAMPLE_MASS_G for v in wt],
            "pct_of_doe": [float(v) / DOE_TARGET_WT * 100.0 for v in wt],
        })
    return out
