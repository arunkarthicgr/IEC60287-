"""Electrical losses — dielectric, sheath, armour.
IEC 60287-1-1 Cl. 2.2, 2.3, 2.4

GP6 eddy current (IEC 60287-1-1 Cl.2.3.6.1):
  IEC rule: lam1'' = 0 for stranded/solid conductors (non-Milliken)
  GP6=y:    lam1'' always calculated for solid metallic sheaths (Al/Pb)

Formula for solid metallic sheath eddy:
    beta1  = sqrt(8*pi^2*f / (rho_s * 1e7))
    m      = beta1 * ts   (ts in metres)
    gs     = 1 + m^4 / (3*(1+m^4))
    lam0   = (Rs/R) * (Ds/(2*s))^2 * gs
    D1     = 0 when m <= 0.1  (IEC simplification)
    F_gp31 = 1/(1+(Rs/X)^2)  for solid bonding
    lam1'' = lam0 * (1+D1) * F_gp31

Bonding behaviour (IEC 60287-1-1 Cl.2.3.1, 2.3.2, 2.3.3):
    solid bonding  : circulating currents flow → lam1' calculated normally
    single-point   : no closed loop → lam1' = 0
    cross bonding  : phase sectionalisation cancels lam1' → lam1' = 0
    Eddy losses (lam1'') still apply for single/cross when sheath is
    solid metallic (Al/Pb); F factor in _eddy_solid_sheath already
    handles this via 'bonding == solid' check.
"""

import math
from config.constants import RHO_ELEC, ALPHA20


def dielectric_losses(c, r, log):
    """Wd = omega*C*U0^2*tan(delta)  IEC 60287-1-1 Cl.2.2"""
    omega = 2 * math.pi * c['freq']
    r['omega'] = omega

    er    = c['eps_r']
    tan_d = c['tan_d']
    Di    = c['Di']
    Dc_sc = c['Dc_sc']
    U0    = c['U0'] * 1e3   # V

    C  = er / (18 * math.log(Di / Dc_sc)) * 1e-9
    Wd = omega * C * U0**2 * tan_d

    r['C']  = C
    r['U0'] = U0
    r['Wd'] = Wd if c.get('tb880_gp7_wd', True) else 0.0

    log.append(('Dielectric Losses  [IEC 60287-1-1 Cl.2.2]', [
        ('Relative permittivity er',       f"{er:.4f}", ''),
        ('Loss tangent tan(delta)',         f"{tan_d:.6f}", ''),
        ('U0 line-to-earth',               f"{U0/1e3:.4f}", 'kV'),
        ('Di insulation outer diameter',   f"{Di:.4f}", 'mm'),
        ('Dc_sc conductor screen OD',      f"{Dc_sc:.4f}", 'mm'),
        ('Capacitance C = er/(18 ln(Di/Dc_sc)) 10^-9',
         f"{C*1e9:.6f}", 'nF/m'),
        ('omega = 2 pi f',                 f"{omega:.6f}", 'rad/s'),
        ('Wd = omega C U0^2 tan(delta)',   f"{r['Wd']:.10e}", 'W/m'),
        ('TB880 GP7',
         'Applied' if c.get('tb880_gp7_wd', True) else 'Skipped', ''),
    ]))


def sheath_setup(c, r, log):
    """
    Sheath/screen resistance Rs0 and reactance X.
    Separate X for buried/air (s=spacing_s) and duct (s=Do).
    IEC 60287-1-1 Cl.2.3
    """
    omega = r['omega']
    st    = c['screen_type']

    # Electrical resistivity — user override or IEC Table 1 default
    _rho_default = {
        'Cu': 1.7241e-8, 'Al': 2.8264e-8, 'Pb': 21.4e-8,
        'Cu_tape': 1.7241e-8, 'Cu_wire': 1.7241e-8,
    }.get(st, 1.7241e-8)
    rho_s_in = c.get('rho_s_user', 0.0)
    rho_s = rho_s_in if (rho_s_in and rho_s_in > 0) else _rho_default

    alpha_s = ALPHA20.get(
        {'Cu': 'Cu', 'Al': 'Al', 'Pb': 'Pb',
         'Cu_tape': 'Cu', 'Cu_wire': 'Cu'}.get(st, 'Cu'), 3.93e-3)

    # Screen area
    As_m2 = (c['As'] * 1e-6) if c.get('As', 0) > 0 \
            else (math.pi * c['ds'] * c['ts'] * 1e-6)

    LFs = 1.0
    if st == 'Cu_wire' and c.get('ns', 0) > 0:
        LFs = math.sqrt(1 + (math.pi * c['ds'] / c.get('Ls', 300))**2)

    Rs0        = rho_s * LFs / As_m2
    D_sc_outer = (c['ds'] + c['ts']) if st in ('Al', 'Pb') else \
                 (c.get('D_fl', c['ds']) if c.get('has_foil') else c['ds'])

    r.update({
        'rho_s':      rho_s,
        'alpha_s':    alpha_s,
        'Rs0':        Rs0,
        'LFs':        LFs,
        'As_m2':      As_m2,
        'D_sc_outer': D_sc_outer,
        'has_foil':   c.get('has_foil', False),
    })

    # X for buried/air
    s_bur = c['spacing_s'] * 1e-3
    ds_m  = c['ds'] * 1e-3
    X_bur = 2 * omega * 1e-7 * math.log(2 * s_bur / ds_m)
    r['X_sheath'] = X_bur

    # X for duct (s = Do)
    if 'duct_Do' in c:
        s_dct = c['duct_Do'] * 1e-3
        r['X_sheath_duct'] = 2 * omega * 1e-7 * math.log(2 * s_dct / ds_m)
    else:
        r['X_sheath_duct'] = X_bur

    log.append(('Screen / Sheath Setup  [IEC 60287-1-1 Cl.2.3]', [
        ('Screen material',                  st, ''),
        ('Screen resistivity rho_s',         f"{rho_s:.4e}", 'ohm.m'),
        ('Screen area As',                   f"{As_m2*1e6:.4f}", 'mm2'),
        ('Wire/sheath outer OD D_sc_outer',  f"{D_sc_outer:.4f}", 'mm'),
        ('Lay factor LFs',                   f"{LFs:.6f}", ''),
        ('Screen Rs0 at 20 degC',            f"{Rs0:.4e}", 'ohm/m'),
        ('X_sheath (s=spacing_s buried)',     f"{X_bur:.4e}", 'ohm/m'),
        ('X_sheath_duct (s=Do duct)',         f"{r['X_sheath_duct']:.4e}", 'ohm/m'),
    ]))


def _eddy_solid_sheath(Rs, R_ac, rho_s, ts_m, Ds_m, s_m, X, bonding, freq):
    """
    Eddy current factor for solid metallic sheath.
    IEC 60287-1-1 Cl.2.3.6.1

    beta1 = sqrt(8*pi^2*f / (rho_s*1e7))
    m     = beta1 * ts
    gs    = 1 + m^4/(3*(1+m^4))
    lam0  = (Rs/R) * (Ds/(2*s))^2 * gs
    D1    = 0 if m <= 0.1,  else 2*m^2/(1+m^2)
    F     = 1/(1+(Rs/X)^2)  for solid bonding (GP31)
    lam1''= lam0 * (1+D1) * F
    """
    beta1 = math.sqrt(8 * math.pi**2 * freq / (rho_s * 1e7))
    m     = beta1 * ts_m
    m4    = m**4
    gs    = 1.0 + m4 / (3.0 * (1.0 + m4))
    lam0  = (Rs / R_ac) * (Ds_m / (2.0 * s_m))**2 * gs
    D1    = (2.0 * m**2 / (1.0 + m**2)) if m > 0.1 else 0.0
    F     = 1.0 / (1.0 + (Rs / X)**2) if bonding == 'solid' else 1.0
    return lam0 * (1.0 + D1) * F


def lambda1(theta_s, R_ac, c, r, installation='buried'):
    """
    Compute (Rs, X, lam1', lam1'', lam1) at temperature theta_s.

    installation: 'buried'/'air' → uses R_max,      X_sheath
                  'duct'         → uses R_max_duct,  X_sheath_duct

    GP6 behaviour:
      GP6=n: lam1'' = 0 for non-Milliken (IEC rule)
      GP6=y: lam1'' calculated for solid metallic sheath (Al/Pb)
             regardless of conductor type

    Bonding behaviour:
      solid   : lam1' calculated normally (default — TB880/Gunnerz path)
      single  : lam1' = 0  (no closed loop for circulating currents)
      cross   : lam1' = 0  (phase rotation cancels circulating currents)
    """
    Rs0     = r['Rs0']
    alpha_s = r['alpha_s']
    Rs      = Rs0 * (1 + alpha_s * (theta_s - 20))

    if installation == 'duct':
        X   = r['X_sheath_duct']
        Rac = r['R_max_duct']
    else:
        X   = r['X_sheath']
        Rac = R_ac

    bonding = c['bonding']

    # lam1' — circulating current
    # IEC 60287-1-1: only solid bonding produces circulating currents.
    # Single-point and cross-bonded systems are designed to eliminate them.
    if bonding == 'solid':
        lam1p = (Rs / Rac) / (1 + (Rs / X)**2)
    else:
        lam1p = 0.0

    # lam1'' — eddy current
    lam1pp  = 0.0
    st      = c['screen_type']
    is_mill = c['cond_type'] in ('milliken', 'milliken_uni', 'milliken_insulated')
    gp6     = c.get('tb880_gp6_eddy', True)

    # Calculate eddy if: Milliken (always), OR GP6=y with solid metallic sheath
    calc_eddy = is_mill or (gp6 and st in ('Al', 'Pb'))

    if calc_eddy:
        rho_s  = r['rho_s']
        ts_m   = c['ts'] * 1e-3
        Ds_m   = r['D_sc_outer'] * 1e-3
        freq   = c['freq']
        s_m    = (c['duct_Do'] if installation == 'duct'
                  else c['spacing_s']) * 1e-3

        lam1pp = _eddy_solid_sheath(
            Rs, Rac, rho_s, ts_m, Ds_m, s_m, X, bonding, freq
        )

    return Rs, X, lam1p, lam1pp, lam1p + lam1pp


def armour_loss(c, r, log):
    """Armour loss factor lambda2.  IEC 60287-1-1 Cl.2.4"""
    at = c.get('armour_type', 'none')
    if at == 'none':
        r['lam2'] = 0.0
        log.append(('Armour Losses  [IEC 60287-1-1 Cl.2.4]', [
            ('Armour type', 'None', ''),
            ('lam2', '0.000000', ''),
        ]))
        return

    omega   = r['omega']
    da      = c['da']; na = c['na']; Da = c['Da']
    rho_a   = RHO_ELEC['steel'] if at in ('SWA', 'STA') else RHO_ELEC['Al']
    alpha_a = ALPHA20.get('steel', 4.5e-3)
    As_a    = math.pi * (da/2)**2 * 1e-6
    Ra0     = rho_a / As_a
    Ra_90   = Ra0 * (1 + alpha_a*(c['theta_max']-20))
    Xa      = 2*omega*1e-7*math.log(2*c['spacing_s']*1e-3 / (Da*1e-3))
    lam2    = na * Ra_90 / r['R_max'] / (1 + (Ra_90/Xa)**2)

    r['lam2'] = lam2
    log.append(('Armour Losses  [IEC 60287-1-1 Cl.2.4]', [
        ('Armour type',    at, ''),
        ('Ra0 at 20 degC', f"{Ra0:.4e}", 'ohm/m'),
        ('lam2',           f"{lam2:.6f}", ''),
    ]))