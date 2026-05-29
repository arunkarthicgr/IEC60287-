"""Interactive CLI input — IEC 60287 ampacity calculator.
Buried + Duct + Free Air in one session.
"""

import math
from config.constants import (
    IEC60228_Cu, IEC60228_Al, EPS_R, TAN_DELTA,
    CONDUCTOR_DIAMETERS, CONDUCTOR_SIZES, KS_KP,
)
from utils.helpers import ask, separator


def get_inputs():
    print("\n" + "="*70)
    print("   IEC 60287 MV/HV CABLE AMPACITY CALCULATOR")
    print("   Phase 1+2+3 — Direct Buried + Duct + Free Air")
    print("="*70)

    c = {}

    # ── Project info ──────────────────────────────────────────────────────
    separator("PROJECT INFORMATION")
    c['project']    = ask("Project name",    default="MY PROJECT")
    c['doc_no']     = ask("Document number", default="DOC-001")
    c['engineer']   = ask("Engineer name",   default="Engineer")
    c['cable_desc'] = ask("Cable description",
                          default="MV Cable Ampacity Calculation")

    # ── Conductor ─────────────────────────────────────────────────────────
    separator("CONDUCTOR")
    c['cond_mat'] = ask("Conductor material", default="Al",
                        choices=["Al", "Cu"])

    print(f"  Available sizes (mm2): {CONDUCTOR_SIZES}")
    while True:
        sz = ask("Conductor size (mm2)", default=185, typ=int)
        if sz in CONDUCTOR_SIZES:
            c['cond_size'] = sz
            break
        print(f"      Must be one of {CONDUCTOR_SIZES}")

    print("  Conductor type options:")
    print("      stranded           ks=1.0  kp=0.8   IEC Table 2 (standard)")
    print("      stranded_compact   ks=1.0  kp=1.0   TB880 CS0 compacted round")
    print("      solid              ks=1.0  kp=1.0")
    print("      milliken           ks=0.8  kp=0.37  HV bare bidirectional")
    print("      milliken_uni       ks=1.0  kp=0.37  HV bare unidirectional")
    print("      milliken_insulated ks=0.435 kp=0.37")
    c['cond_type'] = ask("Conductor type", default="stranded",
                         choices=["stranded", "stranded_compact", "solid",
                                  "milliken", "milliken_uni",
                                  "milliken_insulated"])

    tbl = IEC60228_Cu if c['cond_mat'] == 'Cu' else IEC60228_Al
    if c['cond_size'] in tbl:
        print(f"      IEC 60228 R0 at 20 degC = {tbl[c['cond_size']]} ohm/km")
    ks, kp = KS_KP.get(c['cond_type'], (1.0, 0.8))
    print(f"      ks = {ks}, kp = {kp}  (IEC 60287-1-1 Table 2)")

    dc_def = CONDUCTOR_DIAMETERS.get(c['cond_size'], 15.9)
    c['Dc']    = ask("Conductor diameter Dc (mm)", default=dc_def, typ=float)
    c['Dc_sc'] = ask("Conductor screen outer diameter Dc_sc (mm)",
                     default=round(c['Dc'] + 1.7, 1), typ=float)
    c['theta_max'] = ask("Max conductor temperature theta_max (degC)",
                         default=90, typ=int)

    # ── Insulation ────────────────────────────────────────────────────────
    separator("INSULATION")
    c['ins_mat'] = ask("Insulation material", default="XLPE",
                       choices=["XLPE", "XLPE_filled", "EPR", "PILC"])
    c['Di']    = ask("Insulation outer diameter Di (mm)",
                     default=round(c['Dc'] + 18.0, 1), typ=float)
    c['Di_sc'] = ask("Insulation screen outer diameter Di_sc (mm)",
                     default=round(c['Di'] + 1.7, 1), typ=float)
    c['t_ins'] = ask("Insulation thickness t_ins (mm)",
                     default=round((c['Di'] - c['Dc_sc']) / 2, 2), typ=float)
    eps_def  = EPS_R.get(c['ins_mat'], 2.5)
    tand_def = TAN_DELTA.get(c['ins_mat'], 0.001)
    print(f"      Standard: er={eps_def}, tan(delta)={tand_def}")
    c['eps_r'] = ask("Relative permittivity er", default=eps_def, typ=float)
    c['tan_d'] = ask("Loss tangent tan(delta)",  default=tand_def, typ=float)

    # ── Screen / Sheath ───────────────────────────────────────────────────
    separator("SCREEN / SHEATH")
    c['screen_type'] = ask("Screen type", default="Cu_tape",
                           choices=["Cu_tape", "Cu_wire", "Pb", "Al"])
    c['ds'] = ask("Mean screen diameter ds (mm)",
                  default=round(c['Di_sc'] + 0.4, 1), typ=float)
    c['ts'] = ask("Screen thickness ts (mm)", default=0.10, typ=float)
    c['As'] = ask("Screen cross-section area As (mm2) [0=calc from ts]",
                  default=50.0, typ=float)

    if c['screen_type'] == 'Cu_wire':
        c['ns']      = ask("Number of screen wires ns", default=56, typ=int)
        c['ds_wire'] = ask("Screen wire diameter ds_wire (mm)",
                           default=0.9, typ=float)
        c['Ls']      = ask("Length of lay Ls (mm)", default=240, typ=float)
    else:
        c['ns'] = 0; c['ds_wire'] = c['ts']; c['Ls'] = 0.0

    # Screen/sheath electrical resistivity
    # IEC Table 1 defaults: Cu=1.7241e-8, Al=2.8264e-8, Pb=21.4e-8
    # TB880 CS0 uses Al=2.84e-8 (manufacturer datasheet) — enter 0 for IEC default
    _rho_defaults = {'Cu_tape': 1.7241e-8, 'Cu_wire': 1.7241e-8,
                     'Al': 2.8264e-8, 'Pb': 21.4e-8}
    _rho_def = _rho_defaults.get(c['screen_type'], 1.7241e-8)
    print(f"      IEC default rho_s = {_rho_def:.4e} ohm.m  (enter 0 to use this)")
    rho_s_in = ask("Screen resistivity rho_s (ohm.m) [0 = IEC default]",
                   default=0.0, typ=float)
    c['rho_s_user'] = rho_s_in

    c['rho_sc']   = ask("rho_sc semiconducting screens (K.m/W)",
                        default=2.5, typ=float)
    c['rho_tape'] = ask("rho_tape bedding tape (K.m/W)", default=6.0, typ=float)
    c['D_tuws']   = ask("D_tuws over tape under wire screen (mm)",
                        default=round(c['Di_sc'] + 1.0, 1), typ=float)

    # ── Al laminated foil ─────────────────────────────────────────────────
    separator("AL LAMINATED FOIL  (HV only — press Enter to skip)")
    yn = ask("Has Al laminated foil? (y/n)", default="n")
    c['has_foil'] = yn.lower() == 'y'
    if c['has_foil']:
        c['t_fl']   = ask("Foil thickness t_fl (mm)", default=0.2, typ=float)
        c['D_fl']   = ask("Foil outer diameter D_fl (mm)",
                          default=round(c['ds'] + 1.5, 1), typ=float)
        c['D_owt']  = ask("OD of tape over wire screen D_owt (mm)",
                          default=round(c['ds'] + 0.6, 1), typ=float)
        c['rho_wb'] = ask("rho_wb water blocking tape (K.m/W)",
                          default=12.0, typ=float)
    else:
        c['t_fl'] = 0.0; c['D_fl'] = 0.0
        c['D_owt'] = 0.0; c['rho_wb'] = 12.0

    # ── Armour ────────────────────────────────────────────────────────────
    separator("ARMOUR")
    c['armour_type'] = ask("Armour type", default="none",
                           choices=["none", "SWA", "STA", "AWA"])
    if c['armour_type'] != 'none':
        c['da'] = ask("Armour wire diameter da (mm)", default=3.0, typ=float)
        c['na'] = ask("Number of armour wires na", default=24, typ=int)
        c['Da'] = ask("Mean armour diameter Da (mm)", default=60.0, typ=float)
    else:
        c['da'] = 0.0; c['na'] = 0; c['Da'] = 0.0

    # ── Oversheath ────────────────────────────────────────────────────────
    separator("OVERSHEATH")
    c['osh_mat'] = ask("Oversheath material", default="PVC",
                       choices=["PVC", "PE", "HDPE", "LSOH"])
    c['t_osh']   = ask("Oversheath thickness t_osh (mm)", default=3.2, typ=float)
    c['De']      = ask("Cable outer diameter De (mm)",
                       default=round(c['ds'] + 2*c['t_osh'] + 1.0, 1), typ=float)
    yn = ask("Outer semiconducting layer over oversheath? (y/n)", default="n")
    c['has_outer_sc'] = yn.lower() == 'y'
    if c['has_outer_sc']:
        c['De_1']       = ask("OD without outer semicon De_1 (mm)",
                              default=round(c['De'] - 1.0, 1), typ=float)
        c['t_osh_sc']   = ask("Outer semicon thickness (mm)",
                              default=0.5, typ=float)
        c['rho_osh_sc'] = ask("rho_osh_sc outer semicon (K.m/W)",
                              default=2.5, typ=float)
    else:
        c['De_1'] = c['De']; c['t_osh_sc'] = 0.0; c['rho_osh_sc'] = 2.5

    # ── System ────────────────────────────────────────────────────────────
    separator("SYSTEM & ELECTRICAL")
    c['U_rated'] = ask("Rated voltage U line-to-line (kV)",
                       default=33.0, typ=float)
    c['U0']      = ask("U0 line-to-earth (kV)",
                       default=round(c['U_rated'] / math.sqrt(3), 3), typ=float)
    c['freq']    = ask("Frequency (Hz)", default=50, choices=[50, 60])
    if isinstance(c['freq'], str):
        c['freq'] = int(c['freq'])
    c['bonding']   = ask("Sheath bonding", default="solid",
                         choices=["solid", "single", "cross"])
    c['formation'] = ask("Cable formation", default="trefoil",
                         choices=["trefoil", "trefoil_spaced",
                                  "flat", "flat_spaced"])

    # ── DIRECT BURIED ─────────────────────────────────────────────────────
    separator("DIRECT BURIED INSTALLATION")
    c['depth']     = ask("Depth to cable centre L (mm)", default=1000, typ=int)
    c['spacing_s'] = ask("Axial spacing centre-to-centre s (mm)",
                         default=int(c['De']), typ=float)
    c['theta_amb'] = ask("Ambient ground temperature theta_a (degC)",
                         default=30, typ=int)
    c['rho_soil']  = ask("Soil thermal resistivity rho_soil (K.m/W)",
                         default=1.2, typ=float)

    # ── DUCT INSTALLATION ─────────────────────────────────────────────────
    separator("DUCT INSTALLATION")
    print("  Duct material options:")
    print("      HDPE / PE / PVC / fibre_cement : U=1.87, V=0.312, Y=0.0037")
    print("      concrete                       : U=2.31, V=0.346, Y=0.0057")
    c['duct_mat'] = ask("Duct material", default="HDPE",
                        choices=["HDPE", "PE", "PVC",
                                 "fibre_cement", "concrete"])

    c['duct_Do'] = ask("Duct outer diameter Do (mm)", default=110.0, typ=float)
    c['duct_t']  = ask("Duct wall thickness t_duct (mm)", default=5.0, typ=float)
    c['duct_Di'] = round(c['duct_Do'] - 2 * c['duct_t'], 2)
    print(f"      Duct inner diameter Di = {c['duct_Di']:.1f} mm")

    ratio = c['duct_Di'] / c['De']
    print(f"      Di/De = {ratio:.3f}  (IEC minimum = 1.5)")
    if ratio < 1.5:
        print("      WARNING: Di/De < 1.5 — cable may not fit in duct!")

    yn = ask("Are ducts touching? (y/n)", default="y")
    c['duct_touching'] = yn.lower() != 'n'
    if not c['duct_touching']:
        c['duct_spacing'] = ask(
            "Centre-to-centre duct spacing (mm)",
            default=int(c['duct_Do'] * 2), typ=float)
    else:
        c['duct_spacing'] = c['duct_Do']
        print(f"      Touching ducts: centre-to-centre spacing = Do = {c['duct_Do']:.1f} mm")

    c['cables_per_duct'] = ask("Number of cables per duct",
                               default=1, typ=int)
    if c['cables_per_duct'] > 1:
        print("      Note: Multi-cable per duct uses 1 cable for now.")
        c['cables_per_duct'] = 1

    # ── FREE AIR ──────────────────────────────────────────────────────────
    separator("FREE AIR INSTALLATION")
    c['theta_amb_air'] = ask("Ambient air temperature theta_a_air (degC)",
                             default=40, typ=int)
    print("  Mounting: free = away from wall,  wall = touching surface")
    c['air_mounting'] = ask("Cable mounting in air", default="free",
                            choices=["free", "wall"])

    yn = ask("Include solar radiation? (y/n)", default="n")
    c['solar'] = yn.lower() == 'y'
    if c['solar']:
        c['solar_H']     = ask("Solar intensity H (W/m2)",
                               default=1000.0, typ=float)
        c['solar_sigma'] = ask("Surface absorption sigma",
                               default=0.4, typ=float)
    else:
        c['solar_H'] = 0.0; c['solar_sigma'] = 0.4

    yn = ask("Include wind / forced convection? (y/n)", default="n")
    c['wind'] = yn.lower() == 'y'
    c['wind_speed'] = (ask("Wind speed (m/s)", default=1.0, typ=float)
                       if c['wind'] else 0.0)

    # ── TB880 options ─────────────────────────────────────────────────────
    separator("TB 880 CALCULATION OPTIONS")
    print("  (press Enter to accept recommended defaults)")
    yn = ask("GP2 round ampacity DOWN? (y/n)", default="y")
    c['tb880_gp2_round_down'] = yn.lower() != 'n'
    yn = ask("GP6 always calculate eddy current losses? (y/n)", default="y")
    c['tb880_gp6_eddy'] = yn.lower() != 'n'
    yn = ask("GP7 always calculate dielectric losses? (y/n)", default="y")
    c['tb880_gp7_wd'] = yn.lower() != 'n'
    yn = ask("GP8 use exact T4 formula? (y/n)", default="y")
    c['tb880_gp8_exact_t4'] = yn.lower() != 'n'
    yn = ask("Apply 1.6x T3 factor for touching trefoil (buried only)? (y/n)",
             default="y")
    c['t3_touching_factor'] = yn.lower() != 'n'

    # ── Output ────────────────────────────────────────────────────────────
    separator("OUTPUT")
    default_pdf = (f"Ampacity_{c['cond_size']}mm2_"
                   f"{c['cond_mat']}_{c['U_rated']:.0f}kV.pdf")
    c['pdf_name'] = ask("PDF filename", default=default_pdf)
    if not c['pdf_name'].endswith('.pdf'):
        c['pdf_name'] += '.pdf'

    return c