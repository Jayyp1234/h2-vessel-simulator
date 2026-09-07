# Hydrogen Storage Vessel Simulator

Predictive simulation for a Ca-exchanged zeolite-A hydrogen storage vessel. No physical
H₂ testing was performed; every number here is model output.

> The source specification document is unpublished academic material and is not included
> in this repository. Every parameter the engine needs is encoded in `engine/model.py`.

- **`engine/`** — Python. Isotherms, the charge/discharge duty cycle, and the Section 7
  deliverables (.xlsx, .docx, 300 dpi PNG).
- **`web/`** — static browser app. Same physics, recomputed live.

## Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
.venv/bin/python engine/run.py
```

```bash
python3 -m http.server 8792 --directory web
```

Then open <http://localhost:8792>.

## Deploying

`web/` is fully static — no build step, no backend, no external requests. Drop the folder
on any static host (Vercel, Netlify, GitHub Pages, S3) and it works. `model-constants.js`
is generated, so re-run `python engine/run.py --emit-web-constants` before deploying if
you have changed the engine.

## The four samples (spec Section 1, 2×2 design)

| # | Sample | Equivalent | Activation |
|---|--------|-----------|------------|
| 1 | Ca-activated powder | 5A (CaA) | CaCl₂, 300 °C |
| 2 | Regular powder | 4A (NaA) | — |
| 3 | Ca-activated granule | 5A (CaA) | CaCl₂, 300 °C |
| 4 | Regular granule | 4A (NaA) | — |

125 g per sample, run sequentially in one 50 mm × 250 mm vessel.

## Method

Langmuir isotherm (spec Section 2) fitted to Langmi et al. (2003) zeolite 5A data at 77 K,
transferred to the operating temperature through the affinity constant:

```
b(T) = b(77 K) × exp[(q_st / R) × (1/T − 1/77)]
```

The vessel is a lumped, well-mixed tank (Section 6) with ideal-gas behaviour (Section 5)
and instantaneous adsorption equilibrium (Section 5). Each cycle runs five stages: charge →
hold → heat → desorb → cool.

## Findings the specification does not anticipate

**Peak pressure exceeds the vessel design rating.** Heating a sealed vessel from −78 °C to
90 °C at 10 bar reaches **~19 bar** against the **15 bar** rating in Section 3. Gas-law
expansion accounts for most of it. Either vent during heating, lower the charge pressure,
or raise the rating. This is a safety item.

**Storage is dominated by compressed gas.** Adsorption contributes only **2–4%** of the
hydrogen in the vessel; the rest is free gas in the void volume. The sorbent is not doing
the storage work at this temperature.

**Distance from the DOE target.** The best sample reaches ~0.28% of the 5.5 wt% target.
That is the expected result for physisorption above 77 K and is better stated directly than
presented as a shortfall.

**Cycles are identical by construction.** No degradation mechanism is specified, so the
capacity-vs-cycle plot is flat by definition and demonstrates nothing about durability.
Set `--capacity-fade` only if you can justify a rate.

## Deviations from the specification

| Tag | Issue | What this tool does |
|-----|-------|---------------------|
| **1** | Section 2 cites "~2.2 wt% at near-ambient temperature" as a plausibility floor to exceed at −78 °C. That is a **77 K** figure — zeolites hold ~10⁻³ wt% at 25 °C. | Not used as a target. Recorded as a citation to correct before submission; anchoring to it would embed a 40–1000× error. |
| **2** | "Isothermal at −78 °C throughout" contradicts "desorb by heating to 80–100 °C". | Modelled as a temperature swing: isothermal within each stage, explicit ramps between. |
| **3** | "Charging source pressure: below 10 bar" cannot reach a 10 bar target. | Source pressure is a parameter defaulting above target. |
| **4** | "Zeolite-14A" is not a standard designation. | Modelled as 5A (Ca-exchanged) and 4A (untreated Na) — which means published isotherms already exist for the activated samples. |
| **5** | "Instantaneous equilibrium" means no adsorption kinetics exist, yet Section 7 asks for "desorption vs time". | Implemented as specified, with the curve labelled as schedule-driven rather than kinetic. |
| **6** | Five cycles requested, no degradation mechanism given. | Cycles are identical; `--capacity-fade` imposes a rate if justified. |

**The largest open assumption:** regular (4A) capacity is estimated at 75% of the
Ca-exchanged (5A) value. No published 4A isotherm is supplied by the specification, and
this single number sets the entire activated-vs-regular conclusion. Replace it with real
data before that comparison carries weight — the slider in the app shows how much it moves.

## Commands

```bash
python engine/run.py                        # deliverables at spec defaults
python engine/run.py --q-st 5               # isosteric heat
python engine/run.py --cycles 10
python engine/run.py --regular-factor 0.85  # sensitivity on the unanchored estimate
python engine/run.py --capacity-fade 0.02   # 2% loss per cycle
python engine/run.py --t-desorb 100         # top of the spec's 80-100 C range
python engine/run.py --emit-web-constants   # after changing the engine
python engine/parity_check.py               # Python vs JavaScript agreement
```

## Layout

```
engine/model.py          isotherms, 4 samples, vessel geometry
engine/cycle.py          transient charge/discharge duty cycle
engine/deliverables.py   xlsx / docx / 300 dpi png export
engine/run.py            CLI
engine/parity_check.py   144 option combinations, Python vs JavaScript
web/physics.js           same physics, shared by browser and parity test
web/model-constants.js   generated — do not edit by hand
out/                     generated deliverables
```

The physics exists in two languages so the browser can recompute without a server.
`parity_check.py` compares 2,304 values and fails on any disagreement; run it after
touching either implementation.
