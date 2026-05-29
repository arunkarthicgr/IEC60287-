"""Duct installation — IEC 60287-2-1 Cl.4.2.7

T4 = T4' + T4'' + T4'''

T4'   = cable-to-duct air gap     (temperature-dependent, iterative theta_m)
T4''  = duct wall                 (fixed)
T4''' = external soil of duct     (fixed)

─────────────────────────────────────────────────────────────────
T4' formula  IEC 60287-2-1 Cl.4.2.7.2:
    T4' = U / (1 + 0.1 × (V + Y × θm) × De)
    θm update: θm = θj - 0.5 × T4' × (Wc + Ws + Wd)

IEC Table 4 constants:
    HDPE/PE/PVC/fibre_cement : U=1.87, V=0.312, Y=0.0037
    concrete                 : U=2.31, V=0.346, Y=0.0057

TB880 CS0-2: T4' = 0.3520961015 at θm=70°C, De=75.5mm  ✓

─────────────────────────────────────────────────────────────────
T4'' formula  IEC 60287-2-1 Cl.4.2.7.3:
    T4'' = (ρduct / 2π) × ln(Do / Di)

TB880 CS0-2: T4'' = 0.0886606472  ✓

─────────────────────────────────────────────────────────────────
T4''' formula  IEC 60287-2-1 Cl.4.2.7.4 + Cl.4.2.4.3.4
Touching trefoil ducts — Kennelly method of images:
    u         = 2L / Do
    T4_self   = (ρ/2π) × ln(u + √(u²−1))
    T4_mutual = (ρ/2π) × ln(√(4L² + Do²) / Do)
    T4'''     = T4_self + 2 × T4_mutual

TB880 CS0-2:
    T4_self   = 0.5333568559
    T4_mutual = 0.4236233572
    T4'''     = 1.3806035704   TB880: 1.3800209396  diff=0.042%  ✓
    Final I   = 682.72 A       TB880: 682.81 A       diff=0.013%  ✓
"""

import math


# ── IEC 60287-2-1 Table 4 ─────────────────────────────────────────────────────
DUCT_CONSTANTS = {
    'HDPE':         (1.87, 0.312, 0.0037),
    'PE':           (1.87, 0.312, 0.0037),
    'PVC':          (1.87, 0.312, 0.0037),
    'fibre_cement': (1.87, 0.312, 0.0037),
    'concrete':     (2.31, 0.346, 0.0057),
}

DUCT_RHO_THERM = {
    'HDPE':         3.5,
    'PE':           3.5,
    'PVC':          6.0,
    'fibre_cement': 1.0,
    'concrete':     1.0,
}


def get_duct_constants(duct_mat):
    """Return (U, V, Y) from IEC 60287-2-1 Table 4."""
    return DUCT_CONSTANTS.get(duct_mat, (1.87, 0.312, 0.0037))


# ── T4' ───────────────────────────────────────────────────────────────────────

def calc_T4_prime(U, V, Y, theta_m, De_mm):
    """
    Air gap thermal resistance.  IEC 60287-2-1 Cl.4.2.7.2

        T4' = U / (1 + 0.1 × (V + Y × θm) × De)

    TB880 CS0-2 first iter: 0.3520961015  ✓
    """
    return U / (1.0 + 0.1 * (V + Y * theta_m) * De_mm)


def update_theta_m(theta_j, T4_prime, Wc, Ws, Wd):
    """
    Mean air gap temperature update.  TB880 CS0-2 confirmed:

        θm = θj - 0.5 × T4' × (Wc + Ws + Wd)
    """
    return theta_j - 0.5 * T4_prime * (Wc + Ws + Wd)


# ── T4'' ──────────────────────────────────────────────────────────────────────

def calc_T4_double(rho_duct, Do_mm, Di_duct_mm):
    """
    Duct wall thermal resistance.  IEC 60287-2-1 Cl.4.2.7.3

        T4'' = (ρduct / 2π) × ln(Do / Di)

    TB880 CS0-2: 0.0886606472  ✓
    """
    return (rho_duct / (2.0 * math.pi)) * math.log(Do_mm / Di_duct_mm)


# ── T4''' ─────────────────────────────────────────────────────────────────────

def calc_T4_triple_touching_trefoil(rho_soil, L_mm, Do_mm):
    """
    External soil resistance — touching trefoil ducts.
    IEC 60287-2-1 Cl.4.2.7.4 + Cl.4.2.4.3.4  (Kennelly method)

        u         = 2L / Do
        T4_self   = (ρ/2π) × ln(u + √(u²−1))
        T4_mutual = (ρ/2π) × ln(√(4L² + Do²) / Do)
        T4'''     = T4_self + 2 × T4_mutual

    TB880 CS0-2: 1.3806035704  (TB880: 1.3800209396, diff=0.042%)  ✓
    """
    L  = L_mm  * 1e-3
    Do = Do_mm * 1e-3

    u         = 2.0 * L / Do
    T4_self   = (rho_soil / (2.0 * math.pi)) * math.log(u + math.sqrt(u**2 - 1.0))
    T4_mutual = (rho_soil / (2.0 * math.pi)) * math.log(
        math.sqrt(4.0 * L**2 + Do**2) / Do
    )
    return T4_self + 2.0 * T4_mutual


def calc_T4_triple_flat_spaced(rho_soil, L_mm, Do_mm, s_mm):
    """
    External soil resistance — spaced ducts (flat or trefoil spaced).
    Kennelly method: self + mutual from 2 adjacent ducts at spacing s.

        u         = 2L / Do
        T4_self   = (ρ/2π) × ln(u + √(u²−1))
        T4_mutual = (ρ/2π) × ln(√(4L² + s²) / s)
        T4'''     = T4_self + 2 × T4_mutual

    L_mm  : depth to group centre (mm)
    Do_mm : duct outer diameter (mm)
    s_mm  : centre-to-centre duct spacing (mm)
    """
    L  = L_mm  * 1e-3
    Do = Do_mm * 1e-3
    s  = s_mm  * 1e-3

    u         = 2.0 * L / Do
    T4_self   = (rho_soil / (2.0 * math.pi)) * math.log(u + math.sqrt(u**2 - 1.0))
    T4_mutual = (rho_soil / (2.0 * math.pi)) * math.log(
        math.sqrt(4.0 * L**2 + s**2) / s
    )
    return T4_self + 2.0 * T4_mutual