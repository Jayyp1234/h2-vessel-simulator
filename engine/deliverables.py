"""Deliverable export for spec Section 7."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

import model as M
import cycle as C

DPI = 300
COLORS = {1: "#1f4e79", 2: "#2e75b6", 3: "#843c0c", 4: "#c55a11"}
HEAD_FILL = PatternFill("solid", fgColor="1F4E79")
HEAD_FONT = Font(bold=True, color="FFFFFF", size=11)


def _hdr(ws, row, labels):
    for c, lab in enumerate(labels, start=1):
        cell = ws.cell(row=row, column=c, value=lab)
        cell.fill, cell.font = HEAD_FILL, HEAD_FONT
        cell.alignment = Alignment(horizontal="center", wrap_text=True)

def _widths(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

# ------------------------------------------------------------------- figures
def plot_isotherms(iso, opts, path):
    fig, ax = plt.subplots(figsize=(9, 6))
    for r in iso:
        ax.plot(r["pressures_bar"], r["wt_pct"], marker="o", markersize=5, linewidth=1.9,
                color=COLORS[r["id"]], linestyle="-" if r["form"] == "powder" else "--",
                label=f"{r['id']}. {r['label']} — {r['equivalent']}")
    ax.set_xlabel("Pressure (bar)", fontsize=11)
    ax.set_ylabel("Adsorption capacity (wt%)", fontsize=11)
    ax.set_title(f"H₂ Adsorption Isotherms — 4 Samples at {opts.T_charge - 273.15:.0f} °C\n"
                 f"q$_{{st}}$ = {opts.q_st:g} kJ/mol, Langmuir model",
                 fontsize=12, fontweight="bold")
    ax.grid(alpha=0.3, linestyle=":"); ax.set_xlim(0, max(opts.pressures) * 1.05)
    ax.set_ylim(bottom=0); ax.legend(fontsize=9, framealpha=0.95)
    fig.tight_layout(); fig.savefig(path, dpi=DPI); plt.close(fig)
    return path

def plot_desorption(sim, opts, path):
    """Spec Section 7: 'Desorption vs. time'."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    for r in sim["samples"]:
        t = r["trace"]
        ax1.plot(t["time_min"], t["adsorbed_g"], linewidth=1.7, color=COLORS[r["id"]],
                 label=f"{r['id']}. {r['label']}")
    ax1.set_ylabel("H₂ adsorbed (g)", fontsize=11)
    ax1.set_title(f"Charge / Discharge Duty Cycle — {opts.cycles} cycles\n"
                  f"charge {opts.T_charge-273.15:.0f} °C at {opts.P_charge:g} bar, "
                  f"desorb {opts.T_desorb-273.15:.0f} °C",
                  fontsize=12, fontweight="bold")
    ax1.grid(alpha=0.3, linestyle=":"); ax1.legend(fontsize=9, framealpha=0.95)

    t0 = sim["samples"][0]["trace"]
    ax2.plot(t0["time_min"], t0["P_bar"], color="#548235", linewidth=1.7, label="Pressure")
    ax2.axhline(M.MAX_DESIGN_BAR, color="#c62828", linestyle="--", linewidth=1.5,
                label=f"Design limit {M.MAX_DESIGN_BAR:g} bar")
    ax2.set_ylabel("Vessel pressure (bar)", fontsize=11)
    ax2.set_xlabel("Time (min)", fontsize=11)
    ax2b = ax2.twinx()
    ax2b.plot(t0["time_min"], [T - 273.15 for T in t0["T_K"]], color="#7030a0",
              linewidth=1.3, alpha=0.75, label="Temperature")
    ax2b.set_ylabel("Temperature (°C)", fontsize=11, color="#7030a0")
    ax2.grid(alpha=0.3, linestyle=":")
    h1, l1 = ax2.get_legend_handles_labels(); h2, l2 = ax2b.get_legend_handles_labels()
    ax2.legend(h1 + h2, l1 + l2, fontsize=9, framealpha=0.95, loc="upper right")
    fig.tight_layout(); fig.savefig(path, dpi=DPI); plt.close(fig)
    return path

def plot_cycles(sim, opts, path):
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for r in sim["samples"]:
        cyc = [c["cycle"] for c in r["per_cycle"]]
        wc = [c["working_capacity_g"] for c in r["per_cycle"]]
        ax.plot(cyc, wc, marker="s", markersize=7, linewidth=1.9, color=COLORS[r["id"]],
                label=f"{r['id']}. {r['label']}")
    ax.set_xlabel("Cycle number", fontsize=11)
    ax.set_ylabel("Working capacity (g H₂)", fontsize=11)
    ax.set_title("Working Capacity vs Cycle Number", fontsize=12, fontweight="bold")
    ax.set_xticks(range(1, opts.cycles + 1))
    ax.grid(alpha=0.3, linestyle=":"); ax.legend(fontsize=9, framealpha=0.95)
    ax.set_ylim(bottom=0)
    if opts.capacity_fade == 0:
        ax.text(0.5, 0.5, "No degradation mechanism specified —\ncycles identical by construction",
                transform=ax.transAxes, ha="center", va="center", fontsize=11,
                color="#b26a00", alpha=0.75,
                bbox=dict(boxstyle="round,pad=0.5", fc="#fff4e5", ec="#b26a00", alpha=0.9))
    fig.tight_layout(); fig.savefig(path, dpi=DPI); plt.close(fig)
    return path

def plot_doe(summary, path):
    fig, ax = plt.subplots(figsize=(9, 5.5))
    rows = summary["rows"]
    ax.bar([f"{r['id']}. {r['label']}" for r in rows], [r["charged_wt_pct"] for r in rows],
           color=[COLORS[r["id"]] for r in rows], width=0.6)
    ax.axhline(M.DOE_TARGET_WT, color="#c62828", linestyle="--", linewidth=1.8,
               label=f"DOE target {M.DOE_TARGET_WT:g} wt%")
    ax.set_yscale("log")
    ax.set_ylabel("Gravimetric capacity (wt%, log scale)", fontsize=11)
    ax.set_title("Predicted Capacity against the US DOE Target", fontsize=12, fontweight="bold")
    for i, r in enumerate(rows):
        ax.text(i, r["charged_wt_pct"] * 1.15, f"{r['charged_wt_pct']:.4f}\n({r['pct_of_doe_target']:.2f}% of target)",
                ha="center", fontsize=8.5)
    ax.legend(fontsize=9); ax.grid(alpha=0.3, linestyle=":", which="both", axis="y")
    plt.setp(ax.get_xticklabels(), rotation=15, ha="right", fontsize=9)
    fig.tight_layout(); fig.savefig(path, dpi=DPI); plt.close(fig)
    return path

# ---------------------------------------------------------------------- xlsx
def write_xlsx(iso, sim, summary, opts, path):
    wb = Workbook()
    ws = wb.active; ws.title = "Isotherms"
    ws["A1"] = f"H₂ Adsorption Isotherms at {opts.T_charge-273.15:.0f} °C"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = (f"Langmuir model | q_st = {opts.q_st:g} kJ/mol | "
                f"{M.SAMPLE_MASS_G:g} g per sample | regular-form factor {opts.regular_factor:.2f}")
    ws["A2"].font = Font(italic=True, size=9)
    _hdr(ws, 4, ["#", "Sample", "Equivalent", "q_max (wt%)"] + [f"{p:g} bar" for p in opts.pressures])
    for i, r in enumerate(iso, start=5):
        ws.cell(row=i, column=1, value=r["id"]); ws.cell(row=i, column=2, value=r["label"])
        ws.cell(row=i, column=3, value=r["equivalent"])
        ws.cell(row=i, column=4, value=round(r["q_max_wt_pct"], 4))
        for j, v in enumerate(r["wt_pct"], start=5):
            ws.cell(row=i, column=j, value=round(v, 6))
    _widths(ws, [4, 22, 12, 12] + [10] * len(opts.pressures))

    ws2 = wb.create_sheet("Cycle Summary")
    ws2["A1"] = "Duty cycle performance"; ws2["A1"].font = Font(bold=True, size=14)
    _hdr(ws2, 3, ["#", "Sample", "Charged (wt%)", "Charged (g)", "Working cap (g)",
                  "Delivered/cycle (g)", "Peak P (bar)", "Over design?",
                  "% of DOE", "Adsorbed fraction"])
    for i, r in enumerate(summary["rows"], start=4):
        for j, v in enumerate([r["id"], r["label"], round(r["charged_wt_pct"], 5),
                               round(r["charged_g"], 5), round(r["working_capacity_g"], 5),
                               round(r["delivered_per_cycle_g"], 5),
                               round(r["peak_pressure_bar"], 2),
                               "YES" if r["exceeds_design_pressure"] else "no",
                               round(r["pct_of_doe_target"], 3),
                               round(r["adsorbed_fraction"] * 100, 2)], start=1):
            ws2.cell(row=i, column=j, value=v)
    _widths(ws2, [4, 22, 14, 12, 15, 18, 12, 13, 10, 16])

    ws3 = wb.create_sheet("Per Cycle")
    _hdr(ws3, 1, ["#", "Sample", "Cycle", "Charged (g)", "Residual (g)",
                  "Working cap (g)", "Working cap (wt%)", "Peak P (bar)"])
    row = 2
    for r in sim["samples"]:
        for c in r["per_cycle"]:
            for j, v in enumerate([r["id"], r["label"], c["cycle"],
                                   round(c["charged_adsorbed_g"], 6),
                                   round(c["residual_adsorbed_g"], 6),
                                   round(c["working_capacity_g"], 6),
                                   round(c["working_capacity_wt_pct"], 6),
                                   round(c["peak_pressure_bar"], 3)], start=1):
                ws3.cell(row=row, column=j, value=v)
            row += 1
    _widths(ws3, [4, 22, 8, 13, 13, 15, 17, 12])

    ws4 = wb.create_sheet("Trace")
    _hdr(ws4, 1, ["#", "Sample", "Time (min)", "Cycle", "Stage", "T (°C)", "P (bar)",
                  "Adsorbed (g)", "Gas (g)", "Total (g)"])
    row = 2
    for r in sim["samples"]:
        t = r["trace"]
        for k in range(0, len(t["time_min"]), 2):     # thin for file size
            for j, v in enumerate([r["id"], r["label"], round(t["time_min"][k], 2),
                                   t["cycle"][k], t["stage"][k],
                                   round(t["T_K"][k] - 273.15, 2), round(t["P_bar"][k], 3),
                                   round(t["adsorbed_g"][k], 6), round(t["gas_g"][k], 5),
                                   round(t["total_g"][k], 5)], start=1):
                ws4.cell(row=row, column=j, value=v)
            row += 1
    _widths(ws4, [4, 20, 11, 7, 9, 9, 9, 13, 10, 10])

    ws5 = wb.create_sheet("Parameters")
    ws5["A1"] = "Run parameters"; ws5["A1"].font = Font(bold=True, size=14)
    v = M.vessel_geometry()
    for i, (k, val) in enumerate([
        ("q_st (kJ/mol)", opts.q_st), ("Charge temperature (°C)", opts.T_charge - 273.15),
        ("Desorption temperature (°C)", opts.T_desorb - 273.15),
        ("Charge pressure (bar)", opts.P_charge), ("Source pressure (bar)", opts.P_source),
        ("Discharge pressure (bar)", opts.P_discharge), ("Cycles", opts.cycles),
        ("Sample mass (g)", M.SAMPLE_MASS_G), ("Regular-form factor", opts.regular_factor),
        ("Capacity fade / cycle", opts.capacity_fade),
        ("Vessel internal volume (cm³)", round(v["internal_cm3"], 1)),
        ("Vessel max design (bar)", v["max_design_bar"]),
        ("Bed void fraction", v["void_fraction"]),
        ("Isotherm model", "Langmuir (spec Section 2)"),
        ("Benchmark", "Langmi et al. (2003), zeolite 5A at 77 K"),
    ], start=3):
        ws5.cell(row=i, column=1, value=k).font = Font(bold=True)
        ws5.cell(row=i, column=2, value=val)
    _widths(ws5, [30, 46])

    wb.save(path); return path

# ---------------------------------------------------------------------- docx
def _table(doc, headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers)); t.style = "Light Grid Accent 1"
    for c, h in enumerate(headers):
        cell = t.rows[0].cells[c]; cell.text = str(h)
        for p in cell.paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs: r.font.bold = True; r.font.size = Pt(9)
    for row in rows:
        cells = t.add_row().cells
        for c, v in enumerate(row):
            cells[c].text = str(v)
            for p in cells[c].paragraphs:
                if c > 1: p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for r in p.runs: r.font.size = Pt(9)
    if widths:
        for row in t.rows:
            for c, w in enumerate(widths): row.cells[c].width = Inches(w)
    return t

def write_docx(iso, sim, summary, opts, path, figures=None):
    doc = Document()
    doc.add_heading("Hydrogen Storage Vessel Simulation — Results", 0)
    doc.add_paragraph("Generated against 'H2 Zeolite Vessel Simulation Spec.docx'. "
                      "Predictive simulation; no physical H₂ testing was performed.").italic = True

    doc.add_heading("1. Adsorption Isotherms", level=1)
    doc.add_paragraph(
        f"Equilibrium capacity at {opts.T_charge-273.15:.0f} °C for each of the four samples, "
        f"Langmuir model with q_st = {opts.q_st:g} kJ/mol.")
    _table(doc, ["#", "Sample", "q_max (wt%)"] + [f"{p:g} bar" for p in (1, 5, 10)],
           [[r["id"], f"{r['label']} ({r['equivalent']})", f"{r['q_max_wt_pct']:.4f}"]
            + [f"{r['wt_pct'][r['pressures_bar'].index(p)]:.5f}" for p in (1.0, 5.0, 10.0)]
            for r in iso], [0.4, 2.4, 1.1, 1.0, 1.0, 1.0])
    if figures and figures.get("isotherms"):
        doc.add_picture(str(figures["isotherms"]), width=Inches(6.2))

    doc.add_heading("2. Duty Cycle Performance", level=1)
    _table(doc, ["#", "Sample", "Charged (g)", "Working (g)", "Peak P (bar)", "% of DOE"],
           [[r["id"], r["label"], f"{r['charged_g']:.5f}", f"{r['working_capacity_g']:.5f}",
             f"{r['peak_pressure_bar']:.2f}", f"{r['pct_of_doe_target']:.3f}%"]
            for r in summary["rows"]], [0.4, 2.1, 1.1, 1.1, 1.1, 1.0])
    if figures and figures.get("desorption"):
        doc.add_picture(str(figures["desorption"]), width=Inches(6.2))

    doc.add_heading("3. Findings the Specification Does Not Anticipate", level=1)
    for title, body in [
        ("Peak pressure exceeds the vessel design rating",
         f"Heating a sealed vessel from {opts.T_charge-273.15:.0f} °C to "
         f"{opts.T_desorb-273.15:.0f} °C at {opts.P_charge:g} bar raises pressure to "
         f"{summary['rows'][0]['peak_pressure_bar']:.1f} bar, against the "
         f"{M.MAX_DESIGN_BAR:g} bar design rating in Section 3. Gas-law expansion alone "
         f"accounts for most of it; desorbed hydrogen adds the rest. Either the outlet "
         f"must be open during heating, the charge pressure reduced, or the rating raised. "
         f"This is a safety item, not a modelling artefact."),
        ("Storage is dominated by compressed gas, not adsorption",
         f"At the charged state the best sample holds "
         f"{summary['rows'][0]['adsorbed_g'] if 'adsorbed_g' in summary['rows'][0] else summary['rows'][0]['charged_g']:.4f} g "
         f"by adsorption against {summary['rows'][0]['free_gas_g']:.4f} g as free gas in the "
         f"void volume — adsorption contributes only "
         f"{summary['rows'][0]['adsorbed_fraction']*100:.1f}%. The sorbent is not doing the "
         f"storage work at this temperature."),
        ("Distance from the DOE target",
         f"The best sample reaches {summary['rows'][0]['charged_wt_pct']:.4f} wt%, which is "
         f"{summary['rows'][0]['pct_of_doe_target']:.2f}% of the {M.DOE_TARGET_WT:g} wt% target "
         f"named in Section 1. This is the expected result for physisorption above 77 K and "
         f"should be stated directly rather than presented as a shortfall to explain away."),
        ("Cycles are identical by construction",
         "No degradation mechanism is specified. With instantaneous equilibrium and no fade "
         "term, all five cycles return exactly the same numbers. The capacity-vs-cycle plot "
         "is therefore flat by definition and demonstrates nothing about durability. A "
         "measured or literature fade rate is needed before that plot carries meaning."),
    ]:
        doc.add_heading(title, level=2); doc.add_paragraph(body)
    doc.save(path); return path

def write_methodology(opts, path):
    doc = Document()
    doc.add_heading("Model Parameters, Assumptions and Deviations", 0)

    doc.add_heading("Approach", level=1)
    doc.add_paragraph(
        "Langmuir isotherm (spec Section 2) fitted to Langmi et al. (2003) zeolite 5A data "
        "at 77 K, transferred to the operating temperature through the affinity constant "
        "b(T) = b(77 K) × exp[(q_st/R)(1/T − 1/77)]. Saturation capacity counts adsorption "
        "sites and is held temperature-independent. The vessel is a lumped, well-mixed tank "
        "(Section 6) with ideal-gas behaviour (Section 5) and instantaneous adsorption "
        "equilibrium (Section 5).")

    doc.add_heading("Fitted parameters", level=1)
    _table(doc, ["Quantity", "Value", "Source"],
           [["q_max (5A basis)", f"{M.FIT['q_max']:.4f} wt%", "Fitted to Langmi (2003)"],
            ["b at 77 K", f"{M.FIT['b_77K']:.4f} /bar", "Fitted to Langmi (2003)"],
            ["Fit max error", f"{M.FIT['max_abs_error_pct']:.2f}%", "Langmuir, 5 points"],
            ["Powder enhancement", f"×{M.POWDER_ENHANCEMENT}", "Erdogan et al. (2024)"],
            ["Granule binder fraction", f"{M.BINDER_FRACTION:.3f}", "Sister spec; not given here"],
            ["Regular-form factor", f"×{opts.regular_factor:.2f}", "ESTIMATE — see below"]],
           [1.9, 1.5, 2.4])

    doc.add_heading("Deviations and flagged assumptions", level=1)
    for title, body in [
        ("The 2.2 wt% plausibility floor is a 77 K figure [SPEC-DEV-1]",
         "Section 2's developer note cites '~2.2 wt% at near-ambient temperature, 0–15 bar' "
         "and instructs treating it as a floor to exceed at −78 °C. Zeolites hold on the "
         "order of 1e-3 wt% at 25 °C and ~0.05 wt% at −78 °C; 2.2 wt% is a liquid-nitrogen "
         "result. Anchoring to it would embed a 40–1000× error. It is recorded here as a "
         "citation to correct before submission."),
        ("Isothermal and thermal-swing cannot both hold [SPEC-DEV-2]",
         "Section 5 fixes the model isothermal at −78 °C; Section 4 desorbs by heating to "
         "80–100 °C. Modelled as isothermal within each stage with explicit ramps between."),
        ("Source pressure cannot fill to target [SPEC-DEV-3]",
         "Section 4 gives a source 'below 10 bar' and a target of 10 bar. Source pressure is "
         "a parameter defaulting above the target so charging can complete."),
        ("'Zeolite-14A' is not a standard designation [SPEC-DEV-4]",
         "LTA is supplied as 3A/4A/5A; 13X is a FAU framework. Ca-exchanged zeolite A is 5A "
         "and untreated Na-form zeolite A is 4A. The activated/regular pair is modelled as "
         "5A/4A — which means published isotherms already exist for the activated samples."),
        ("No adsorption kinetics exist in this model [SPEC-DEV-5]",
         "Section 5 specifies instantaneous equilibrium, so the sorbent contributes no time "
         "constant. The 'desorption vs time' curve required by Section 7 is shaped entirely "
         "by the heating and venting schedule."),
        ("Regular-form capacity is an unanchored estimate",
         M.REGULAR_FACTOR_NOTE),
        ("Heating assumed to occur with the outlet closed",
         "The specification does not say whether the vessel is sealed during the heating "
         "stage. Sealed is modelled as the conservative case, and it is what produces the "
         "over-pressure finding. If the outlet is open to the delivery line throughout "
         "heating, peak pressure stays at the delivery value and the finding does not apply."),
        ("Insulation not specified",
         "Section 3 notes insulation is present but gives no type or thickness. The "
         "isothermal assumption stands in for perfect insulation; no heat-leak term is "
         "modelled, so hold-time performance is optimistic."),
    ]:
        doc.add_heading(title, level=2); doc.add_paragraph(body)
    doc.save(path); return path

# --------------------------------------------------------------------- driver
def export_all(opts: M.Options, outdir: Path) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    iso = M.isotherm_table(opts)
    sim = C.simulate_cycles(opts)
    summary = C.summarise(sim, opts)

    figs = {
        "isotherms": plot_isotherms(iso, opts, outdir / "isotherms_4_samples.png"),
        "desorption": plot_desorption(sim, opts, outdir / "duty_cycle.png"),
        "cycles": plot_cycles(sim, opts, outdir / "capacity_vs_cycle.png"),
        "doe": plot_doe(summary, outdir / "doe_comparison.png"),
    }
    xlsx = write_xlsx(iso, sim, summary, opts, outdir / "vessel_simulation_results.xlsx")
    docx = write_docx(iso, sim, summary, opts, outdir / "vessel_simulation_results.docx", figs)
    method = write_methodology(opts, outdir / "methodology_and_assumptions.docx")

    thin = {"samples": [{k: v for k, v in s.items() if k != "trace"} for s in sim["samples"]],
            "stages": sim["stages"], "dt_min": sim["dt_min"]}
    (outdir / "raw_results.json").write_text(json.dumps(
        {"options": asdict(opts), "isotherms": iso, "cycle_summary": summary,
         "cycles": thin, "fit": M.FIT, "vessel": M.vessel_geometry()}, indent=2))

    return {"xlsx": xlsx, "docx": docx, "methodology": method,
            "raw": outdir / "raw_results.json", **figs,
            "iso": iso, "sim": sim, "summary": summary}
