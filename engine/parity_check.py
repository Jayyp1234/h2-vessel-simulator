#!/usr/bin/env python3
"""Cross-check the browser physics (web/physics.js) against the Python engine.

The physics is implemented twice -- Python for the deliverables, JavaScript so the
browser recomputes live without a server. This sweeps the option space and fails if
the two ever disagree.

    python engine/parity_check.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import model as M
import cycle as C

ROOT = Path(__file__).resolve().parent.parent
TOLERANCE = 1e-9

NODE = """
const physics = require(process.argv[1]);
const MC = require(process.argv[2]);
const grid = JSON.parse(process.argv[3]);
const p = physics.make(MC);
process.stdout.write(JSON.stringify(grid.map(c => {
  const o = { qst: c.qst, T_charge: c.T_charge, T_desorb: c.T_desorb,
              P_charge: c.P_charge, P_discharge: c.P_discharge, cycles: c.cycles,
              regularFactor: c.regularFactor, capacityFade: c.capacityFade,
              pressures: c.pressures };
  return p.simulate(o).map(s => [s.charged, s.working, s.peakP, s.adsorbedFraction]);
})));
"""


def main() -> int:
    web = ROOT / "web"
    if not (web / "model-constants.json").exists():
        print("model-constants.json missing — run: python engine/run.py --emit-web-constants")
        return 2

    pressures = list(M.Options().pressures)
    grid = [
        {"qst": q, "T_charge": tc, "T_desorb": td, "P_charge": pc, "P_discharge": 1.0,
         "cycles": 3, "regularFactor": rf, "capacityFade": cf, "pressures": pressures}
        for q, tc, td, pc, rf, cf in product(
            [5.0, 6.0, 8.0], [195.15, 233.15], [353.15, 373.15],
            [8.0, 10.0], [0.6, 0.75, 0.9], [0.0, 0.03],
        )
    ]

    proc = subprocess.run(
        ["node", "-e", NODE, str(web / "physics.js"),
         str(web / "model-constants.json"), json.dumps(grid)],
        capture_output=True, text=True)
    if proc.returncode != 0:
        print("node failed:\n" + proc.stderr)
        return 2
    js = json.loads(proc.stdout)

    worst, worst_key, checked, failures = 0.0, None, 0, []
    for idx, c in enumerate(grid):
        opts = M.Options(q_st=c["qst"], T_charge=c["T_charge"], T_desorb=c["T_desorb"],
                         P_charge=c["P_charge"], P_discharge=c["P_discharge"],
                         cycles=c["cycles"], regular_factor=c["regularFactor"],
                         capacity_fade=c["capacityFade"])
        summary = C.summarise(C.simulate_cycles(opts), opts)
        for i, row in enumerate(summary["rows"]):
            py = [row["charged_g"], row["working_capacity_g"],
                  row["peak_pressure_bar"], row["adsorbed_fraction"]]
            for k, (pv, jv) in enumerate(zip(py, js[idx][i])):
                checked += 1
                rel = abs(pv - jv) / max(abs(pv), 1e-30)
                if rel > worst:
                    worst, worst_key = rel, (f"q{c['qst']} Tc{c['T_charge']} Td{c['T_desorb']} "
                                             f"P{c['P_charge']} rf{c['regularFactor']} "
                                             f"fade{c['capacityFade']} sample{i+1} field{k}")
                if rel > TOLERANCE:
                    failures.append((worst_key, pv, jv, rel))

    print(f"Parity check — {len(grid)} option combinations, {checked} values compared")
    print(f"  worst relative difference: {worst:.3e}  ({worst_key})")
    if failures:
        print(f"  FAIL — {len(failures)} value(s) exceed {TOLERANCE:g}")
        for f in failures[:10]:
            print(f"    {f[0]}: python={f[1]:.12g} js={f[2]:.12g} rel={f[3]:.2e}")
        return 1
    print(f"  PASS — Python and JavaScript agree to within {TOLERANCE:g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
