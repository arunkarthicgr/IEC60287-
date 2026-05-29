"""DC/AC conductor resistance and electrical parameter calculations.
IEC 60287-1-1 Cl. 2.1.1, 2.1.2, 2.1.4

Key points:
  - ks/kp read from KS_KP table — never hardcoded
  - Skin effect boundary check uses xs (not xs²)
  - For duct: R_max_duct computed with s=Do (duct outer diameter)
    TB880 CS0-2: s=Do=140mm → yp=0.010108, Rac=3.861967e-5  ✓
  - For buried/air: R_max computed with s=spacing_s (cable spacing)
    TB880 CS0-1: s=De=75.5mm → yp=0.035100, Rac=3.952153e-5  ✓
"""

import math
from config.constants import IEC60228_Cu, IEC60228_Al, ALPHA20, KS_KP


def dc_resistance(c, r, log):
    """Populate r with R0_20, R0_amb, R0_max. IEC 60287-1-1 Cl.2.1.1"""
    tbl   = IEC60228_Cu if c['cond_mat'] == 'Cu' else IEC60228_Al
    alpha = ALPHA20[c['cond_mat']]
    r['alpha']  = alpha
    r['R0_20']  = tbl[c['cond_size']] * 1e-3
    r['R0_amb'] = r['R0_20'] * (1 + alpha*(c['theta_amb'] - 20))
    r['R0_max'] = r['R0_20'] * (1 + alpha*(c['theta_max'] - 20))

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


def _skin_proximity(Rdc, s_mm, ks, kp, Dc_mm, freq):
    """
    Skin and proximity factors. IEC 60287-1-1 Cl.2.1.2 & 2.1.4
    s_mm : cable centre-to-centre spacing (mm)

    Skin boundary on xs (not xs²):
        xs ≤ 2.8  → ys = xs⁴/(192 + 0.8·xs⁴)
        2.8–3.8   → polynomial
        > 3.8     → linear
    Returns (xs4, ys, xp4, ypp, yp).
    """
    xs_sq = ks * (8*math.pi*freq / Rdc) * 1e-7
    xs4   = xs_sq**2
    xs    = math.sqrt(xs_sq)

    if xs <= 2.8:
        ys = xs4 / (192 + 0.8*xs4)
    elif xs <= 3.8:
        A  = xs4/192
        ys = -0.136 - 0.0177*A + 0.0563*A*A
    else:
        ys = 0.354*(xs/3.8) - 0.733
    ys = max(0.0, ys)

    xp_sq = kp * (8*math.pi*freq / Rdc) * 1e-7
    xp4   = xp_sq**2
    ypp   = xp4 / (192 + 0.8*xp4)
    rat   = Dc_mm / s_mm
    yp    = ypp * rat**2 * (0.312*rat**2 + 1.18/(ypp+0.27))

    return xs4, ys, xp4, ypp, yp


def ac_resistance(c, r, log):
    """
    Populate r with:
      r['R_max']      = Rac using s = c['spacing_s']  (buried/air)
      r['R_max_duct'] = Rac using s = c['duct_Do']    (duct, if present)

    IEC 60287-1-1 Cl.2.1.2 and 2.1.4
    """
    ct     = c['cond_type']
    ks, kp = KS_KP.get(ct, (1.0, 0.8))
    r['ks'] = ks
    r['kp'] = kp

    # ── Buried / Air: s = spacing_s ──────────────────────────────────────
    s = c['spacing_s']
    xs4m, ys_m, xp4m, ypp_m, yp_m = _skin_proximity(
        r['R0_max'], s, ks, kp, c['Dc'], c['freq']
    )
    r.update({
        'xs4_max': xs4m, 'ys_max': ys_m,
        'xp4_max': xp4m, 'ypp_max': ypp_m, 'yp_max': yp_m,
    })
    r['R_max'] = r['R0_max'] * (1 + ys_m + yp_m)

    # ── Duct: s = Do (duct outer diameter) ───────────────────────────────
    # TB880 CS0-2: s=Do=140mm → different yp, lower Rac, higher lam1
    if 'duct_Do' in c:
        s_duct = c['duct_Do']
        xs4d, ys_d, xp4d, ypp_d, yp_d = _skin_proximity(
            r['R0_max'], s_duct, ks, kp, c['Dc'], c['freq']
        )
        r['R_max_duct'] = r['R0_max'] * (1 + ys_d + yp_d)
        r['yp_duct']    = yp_d
    else:
        r['R_max_duct'] = r['R_max']
        r['yp_duct']    = yp_m

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
        ("yp'' intermediate proximity (s=spacing_s)",
         f"{ypp_m:.10f}", ''),
        ('yp   proximity factor (s=spacing_s)',
         f"{yp_m:.10f}", ''),
        ('R at theta_max AC (buried/air)',
         f"{r['R_max']:.10e}", 'ohm/m'),
        ('yp   proximity factor (s=Do duct)',
         f"{r['yp_duct']:.10f}", ''),
        ('R at theta_max AC (duct)',
         f"{r['R_max_duct']:.10e}", 'ohm/m'),
    ]))


def electrical_params(c, r, log):
    """Inductance, impedance, charging current. IEC 60287-1-1 Cl.2.3"""
    omega  = r['omega']
    L_H    = 0.2e-6 * math.log(2*c['spacing_s'] / c['ds'])
    X_uohm = omega * L_H * 1e6
    R1     = r['R_max'] * (1 + r['lam1'] + r['lam2']) * 1e6
    Z1     = math.sqrt(R1**2 + X_uohm**2)
    Ic     = omega * r['C'] * r['U0']

    r.update({
        'L_uHm':   L_H*1e6,
        'X_uOhm':  X_uohm,
        'R1_uOhm': R1,
        'Z1_uOhm': Z1,
        'Ic_mA_m': Ic*1000,
    })

    log.append(('Electrical Parameters', [
        ('Inductance L',          f"{L_H*1e6:.6f}", 'uH/m'),
        ('Reactance X = omega L', f"{X_uohm:.4f}",  'uOhm/m'),
        ('Pos-seq resistance R1', f"{R1:.4f}",       'uOhm/m'),
        ('Pos-seq impedance Z1',  f"{Z1:.4f}",       'uOhm/m'),
        ('Capacitance C',         f"{r['C']*1e9:.6f}", 'nF/m'),
        ('Charging current Ic',   f"{Ic*1000:.4f}",  'mA/m'),
    ]))