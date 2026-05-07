"""DC/AC conductor resistance and electrical parameter calculations.

IEC 60287-1-1 Cl. 2.1.1, 2.1.2, 2.1.4

Key points:
  - ks and kp always read from KS_KP table in constants.py — never hardcoded
  - Skin effect boundary check uses xs (not xs²)
  - stranded          → ks=1.0, kp=0.8  (IEC Table 2 strict)
  - stranded_compact  → ks=1.0, kp=1.0  (TB880 CS0 compacted round)
  - solid             → ks=1.0, kp=1.0
  - milliken          → ks=0.8, kp=0.37
  - milliken_uni      → ks=1.0, kp=0.37
  - milliken_insulated→ ks=0.435, kp=0.37
"""

import math
from config.constants import IEC60228_Cu, IEC60228_Al, ALPHA20, KS_KP


# =============================================================================
# DC RESISTANCE
# =============================================================================

def dc_resistance(c, r, log):
    """
    Populate r with R0_20, R0_amb, R0_max.
    IEC 60287-1-1 Cl.2.1.1
    """
    tbl   = IEC60228_Cu if c['cond_mat'] == 'Cu' else IEC60228_Al
    alpha = ALPHA20[c['cond_mat']]

    r['alpha']  = alpha
    r['R0_20']  = tbl[c['cond_size']] * 1e-3           # ohm/m
    r['R0_amb'] = r['R0_20'] * (1 + alpha * (c['theta_amb'] - 20))
    r['R0_max'] = r['R0_20'] * (1 + alpha * (c['theta_max'] - 20))

    log.append(('DC Resistance  [IEC 60287-1-1 Cl.2.1.1]', [
        ('IEC 60228 R0 at 20 degC',
         f"{r['R0_20']:.4e}", 'ohm/m'),
        ('Temperature coefficient a20',
         f"{alpha:.4e}", '1/K'),
        (f'R0 at theta_amb = {c["theta_amb"]} degC',
         f"{r['R0_amb']:.4e}", 'ohm/m'),
        (f'R0 at theta_max = {c["theta_max"]} degC',
         f"{r['R0_max']:.4e}", 'ohm/m'),
    ]))


# =============================================================================
# SKIN AND PROXIMITY EFFECT
# =============================================================================

def _skin_proximity(Rdc, s, ks, kp, Dc, freq):
    """
    Skin and proximity effect factors.
    IEC 60287-1-1 Cl.2.1.2 (skin) and Cl.2.1.4 (proximity).

    IEC notation:
        xs²  = ks × (8πf/R') × 1e-7     ← xs SQUARED
        xs⁴  = (xs²)²                    ← xs to the FOURTH power
        xs   = sqrt(xs²)                 ← xs itself

    Boundary selection uses xs (not xs²):
        0 < xs ≤ 2.8   →  ys = xs⁴ / (192 + 0.8×xs⁴)
        2.8 < xs ≤ 3.8 →  polynomial in xs⁴/192
        xs > 3.8        →  ys = 0.354×(xs/3.8) − 0.733

    Returns (xs4, ys, xp4, ypp, yp).
    """
    # ── Skin effect ───────────────────────────────────────────────────────
    xs_sq = ks * (8 * math.pi * freq / Rdc) * 1e-7   # xs²
    xs4   = xs_sq * xs_sq                              # xs⁴
    xs    = math.sqrt(xs_sq)                           # xs  ← boundary check

    if xs <= 2.8:
        ys = xs4 / (192 + 0.8 * xs4)
    elif xs <= 3.8:
        A  = xs4 / 192
        ys = -0.136 - 0.0177 * A + 0.0563 * A * A
    else:
        ys = 0.354 * (xs / 3.8) - 0.733
    ys = max(0.0, ys)

    # ── Proximity effect ──────────────────────────────────────────────────
    xp_sq = kp * (8 * math.pi * freq / Rdc) * 1e-7   # xp²
    xp4   = xp_sq * xp_sq                              # xp⁴
    ypp   = xp4 / (192 + 0.8 * xp4)
    rat   = Dc / s
    yp    = ypp * rat**2 * (0.312 * rat**2 + 1.18 / (ypp + 0.27))

    return xs4, ys, xp4, ypp, yp


# =============================================================================
# AC RESISTANCE
# =============================================================================

def ac_resistance(c, r, log):
    """
    Populate r with ks, kp, R_max, and skin/proximity factors.
    IEC 60287-1-1 Cl.2.1.2 and Cl.2.1.4

    ks and kp are always read from the KS_KP table.
    Never hardcoded — the table in constants.py is the single source of truth.

    Conductor type → (ks, kp):
      stranded           → (1.00, 0.80)  IEC Table 2 strict
      stranded_compact   → (1.00, 1.00)  TB880 CS0 simplification
      solid              → (1.00, 1.00)
      milliken           → (0.80, 0.37)  bare bidirectional
      milliken_uni       → (1.00, 0.37)  bare unidirectional
      milliken_insulated → (0.435, 0.37) insulated wires
    """
    ct     = c['cond_type']
    ks, kp = KS_KP.get(ct, (1.0, 0.8))   # default to stranded if unknown
    r['ks'] = ks
    r['kp'] = kp

    s = c['spacing_s']

    xs4m, ys_m, xp4m, ypp_m, yp_m = _skin_proximity(
        r['R0_max'], s, ks, kp, c['Dc'], c['freq']
    )

    r.update({
        'xs4_max':  xs4m,
        'ys_max':   ys_m,
        'xp4_max':  xp4m,
        'ypp_max':  ypp_m,
        'yp_max':   yp_m,
    })
    r['R_max'] = r['R0_max'] * (1 + ys_m + yp_m)

    log.append(('AC Resistance at theta_max  [IEC 60287-1-1 Cl.2.1.2, 2.1.4]', [
        ('ks  strand constant  (IEC 60287-1-1 Table 2)',
         f"{ks:.4f}", ''),
        ('kp  proximity constant  (IEC 60287-1-1 Table 2)',
         f"{kp:.4f}", ''),
        ('xs²  = ks*(8pif/R0)*1e-7',
         f"{math.sqrt(xs4m):.10f}", ''),
        ('xs⁴  = (xs²)²',
         f"{xs4m:.10f}", ''),
        ('ys   skin effect factor',
         f"{ys_m:.10f}", ''),
        ('xp⁴  = (xp²)²',
         f"{xp4m:.10f}", ''),
        ("yp'' intermediate proximity",
         f"{ypp_m:.10f}", ''),
        ('yp   proximity factor',
         f"{yp_m:.10f}", ''),
        ('R at theta_max  AC = R0(1+ys+yp)',
         f"{r['R_max']:.10e}", 'ohm/m'),
    ]))


# =============================================================================
# ELECTRICAL PARAMETERS
# =============================================================================

def electrical_params(c, r, log):
    """
    Populate r with inductance, impedance, and charging current.
    IEC 60287-1-1 Cl.2.3
    """
    omega  = r['omega']
    L_H    = 0.2e-6 * math.log(2 * c['spacing_s'] / c['ds'])
    X_uohm = omega * L_H * 1e6
    R1     = r['R_max'] * (1 + r['lam1'] + r['lam2']) * 1e6
    Z1     = math.sqrt(R1**2 + X_uohm**2)
    Ic     = omega * r['C'] * r['U0']

    r.update({
        'L_uHm':   L_H * 1e6,
        'X_uOhm':  X_uohm,
        'R1_uOhm': R1,
        'Z1_uOhm': Z1,
        'Ic_mA_m': Ic * 1000,
    })

    log.append(('Electrical Parameters', [
        ('Inductance L',
         f"{L_H*1e6:.6f}", 'uH/m'),
        ('Reactance X = omega L',
         f"{X_uohm:.4f}", 'uOhm/m'),
        ('Pos-seq resistance R1',
         f"{R1:.4f}", 'uOhm/m'),
        ('Pos-seq impedance Z1',
         f"{Z1:.4f}", 'uOhm/m'),
        ('Capacitance C',
         f"{r['C']*1e9:.6f}", 'nF/m'),
        ('Charging current Ic',
         f"{Ic*1000:.4f}", 'mA/m'),
    ]))