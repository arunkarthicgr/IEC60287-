"""
IEC 60287 MV/HV Cable Ampacity Calculator
==========================================
Phase 1+2+3: Direct Buried + Duct + Free Air
"""

import sys
from input.input_parser       import get_inputs
from core.cable               import dc_resistance, ac_resistance, electrical_params
from core.losses              import dielectric_losses, sheath_setup, armour_loss
from core.thermal             import thermal_resistances
from core.ampacity            import iterate_buried, iterate_air, iterate_duct
from report.report_generator  import print_results, generate_pdf


def run():
    # 1. Collect inputs
    try:
        c = get_inputs()
    except KeyboardInterrupt:
        print("\n\n  Cancelled.")
        sys.exit(0)

    print("\n  Running IEC 60287 calculations...\n")

    # 2. Shared cable properties
    r       = {}
    log     = []
    log_bur = []
    log_dct = []
    log_air = []

    dc_resistance(c, r, log)
    ac_resistance(c, r, log)
    dielectric_losses(c, r, log)
    sheath_setup(c, r, log)
    armour_loss(c, r, log)
    thermal_resistances(c, r, log)

    # 3. Direct buried
    rb = iterate_buried(c, r, log_bur)

    # 4. Duct
    rd = iterate_duct(c, r, log_dct)

    # 5. Free air
    ra = iterate_air(c, r, log_air)

    # 6. Electrical parameters (uses buried lam1 as reference)
    r['lam1'] = rb['lam1']
    r['lam2'] = r.get('lam2', 0.0)
    electrical_params(c, r, log)

    # 7. Print to terminal (3 columns: buried / duct / air)
    print_results(c, r, rb, rd, ra, log, log_bur, log_dct, log_air)

    # 8. Generate PDF
    import os
    pdf_path = c['pdf_name']
    result = generate_pdf(
        c, r, rb, rd, ra,
        log, log_bur, log_dct, log_air,
        pdf_path
    )
    if result:
        print(f"  PDF saved: {os.path.abspath(pdf_path)}\n")


if __name__ == '__main__':
    run()