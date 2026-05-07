"""
IEC 60287 MV/HV Cable Ampacity Calculator
==========================================
Phase 1+2: Direct Buried + Free Air

Run:
    python main.py
"""

import sys
from input.input_parser import get_inputs
from core.cable       import dc_resistance, ac_resistance, electrical_params
from core.losses      import dielectric_losses, sheath_setup, armour_loss
from core.thermal     import thermal_resistances
from core.ampacity    import iterate_buried, iterate_air
from report.report_generator import print_results, generate_pdf


def run():
    # ── 1. Collect inputs ─────────────────────────────────────────────────
    try:
        c = get_inputs()
    except KeyboardInterrupt:
        print("\n\n  Cancelled.")
        sys.exit(0)

    print("\n  Running IEC 60287 calculations...\n")

    # ── 2. Shared cable properties (same for both installations) ──────────
    r       = {}       # shared results dict
    log     = []       # shared log (cable properties)
    log_bur = []       # buried-specific log
    log_air = []       # air-specific log

    dc_resistance(c, r, log)
    ac_resistance(c, r, log)
    dielectric_losses(c, r, log)
    sheath_setup(c, r, log)
    armour_loss(c, r, log)
    thermal_resistances(c, r, log)

    # ── 3. Run buried iteration ───────────────────────────────────────────
    rb = iterate_buried(c, r, log_bur)

    # ── 4. Run free air iteration ─────────────────────────────────────────
    ra = iterate_air(c, r, log_air)

    # ── 5. Electrical parameters (use buried λ1 as primary) ───────────────
    r['lam1'] = rb['lam1']
    r['lam2'] = r['lam2']
    electrical_params(c, r, log)

    # ── 6. Print to console ───────────────────────────────────────────────
    print_results(c, r, rb, ra, log, log_bur, log_air)

    # ── 7. Generate PDF ───────────────────────────────────────────────────
    pdf_path = c['pdf_name']
    result   = generate_pdf(c, r, rb, ra, log, log_bur, log_air, pdf_path)
    if result:
        import os
        print(f"\n  PDF saved: {os.path.abspath(pdf_path)}\n")


if __name__ == '__main__':
    run()