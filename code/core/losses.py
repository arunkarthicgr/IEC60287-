"""Dielectric, sheath, and armour loss calculations.

IEC 60287-1-1 Cl. 2.2, 2.3, 2.4

Fixes:
  FIX A: Capacitance uses Di/Dc_sc  (correct IEC formula)
  FIX B: Eddy current λ1'' only calculated for Milliken conductors
         For stranded/solid with solid bonding: λ1'' = 0 per IEC 2.3.1
         GP6 only overrides for Milliken (TB880 CS0 confirms this)
  FIX C: d_mean for reactance X uses D_sc_outer for dual layer cables
  FIX D: T3 reference diameter for Al/Pb solid sheath = ds + ts (outer surface)
"""

import math
from config.constants import RHO_ELEC, ALPHA20


# =============================================================================
# DIELECTRIC LOSSES  IEC 60287-1-1 Cl.2.2
# =============================================================================

def dielectric_losses(c, r, log):
    """Populate r with omega, U0, C, Wd."""
    omega = 2 * math.pi * c['freq']
    r['omega'] = omega
    U0 = c['U0'] * 1e3
    r['U0'] = U0

    # IEC 60287-1-1 Eq.5: C = er/(18 × ln(Di/Dc_sc)) × 1e-9
    C  = c['eps_r'] / (18 * math.log(c['Di'] / c['Dc_sc'])) * 1e-9
    Wd = (omega * C * U0**2 * c['tan_d']
          if c['tb880_gp7_wd'] or U0 >= 127e3 else 0.0)

    r['C']  = C
    r['Wd'] = Wd

    log.append(('Dielectric Losses  [IEC 60287-1-1 Cl.2.2]', [
        ('Relative permittivity er',
         f"{c['eps_r']:.4f}", ''),
        ('Loss tangent tan(delta)',
         f"{c['tan_d']:.6f}", ''),
        ('U0 line-to-earth',
         f"{U0/1e3:.4f}", 'kV'),
        ('Di insulation outer diameter',
         f"{c['Di']:.4f}", 'mm'),
        ('Dc_sc conductor screen OD',
         f"{c['Dc_sc']:.4f}", 'mm'),
        ('Capacitance C = er/(18 ln(Di/Dc_sc)) 10^-9',
         f"{C*1e9:.6f}", 'nF/m'),
        ('omega = 2 pi f',
         f"{omega:.6f}", 'rad/s'),
        ('Wd = omega C U0^2 tan(delta)',
         f"{Wd:.10e}", 'W/m'),
        ('TB880 GP7',
         'Applied' if c['tb880_gp7_wd'] else 'IEC rule', ''),
    ]))


# =============================================================================
# SCREEN / SHEATH SETUP  IEC 60287-1-1 Cl.2.3
# =============================================================================

def sheath_setup(c, r, log):
    """
    Populate r with screen resistance Rs0, lay factor LFs,
    D_sc_outer, and Al foil data if present.

    FIX D: For Al or Pb solid sheath, outer surface diameter
           = ds + ts (not just ds).
           This is used as reference for T3 in thermal.py.
    """
    st    = c['screen_type']
    mat_s = 'Pb' if st == 'Pb' else ('Al' if st == 'Al' else 'Cu')
    r['mat_s']   = mat_s
    r['alpha_s'] = ALPHA20[mat_s]
    r['rho_s']   = RHO_ELEC[mat_s]

    As = c['As']

    # Outer diameter of screen/sheath
    if st in ('Al', 'Pb'):
        # Solid metallic sheath: outer surface = ds + ts
        D_sc_outer = c['ds'] + c['ts']
    elif st == 'Cu_wire' and c.get('ds_wire', 0) > 0:
        D_sc_outer = c.get('D_tuws', c['Di_sc']) + 2 * c['ds_wire']
    else:
        D_sc_outer = c['ds']
    r['D_sc_outer'] = D_sc_outer

    # Lay factor
    if st == 'Cu_wire' and c.get('Ls', 0) > 0 and c.get('ds_wire', 0) > 0:
        Ds_lay = D_sc_outer - c['ds_wire']
        Ls     = c['Ls']
        LFs    = math.sqrt(1 + (math.pi * Ds_lay)**2 / Ls**2)
    else:
        LFs = 1.0
    r['LFs'] = LFs

    # Screen resistance at 20°C
    if As > 0:
        r['Rs0'] = LFs * RHO_ELEC[mat_s] / (As * 1e-6)
    else:
        area     = math.pi * c['ts'] * (c['ds'] - c['ts']) * 1e-6
        r['Rs0'] = LFs * RHO_ELEC[mat_s] / area

    rows = [
        ('Screen material',                   mat_s, ''),
        ('Screen resistivity rho_s',          f"{RHO_ELEC[mat_s]:.4e}", 'ohm.m'),
        ('Screen area As',                    f"{As:.4f}", 'mm2'),
        ('Wire/sheath outer OD D_sc_outer',   f"{D_sc_outer:.4f}", 'mm'),
        ('Lay factor LFs',                    f"{LFs:.6f}", ''),
        ('Screen Rs0 at 20 degC (with LFs)',  f"{r['Rs0']:.4e}", 'ohm/m'),
    ]

    # Al laminated foil
    r['has_foil'] = c.get('has_foil', False)
    if r['has_foil']:
        t_fl   = c['t_fl']
        D_fl   = c['D_fl']
        rho_fl = RHO_ELEC['Al']
        A_fl   = t_fl * 1e-3 * math.pi * (D_fl - t_fl) * 1e-3
        r['Rso_fl']  = rho_fl / A_fl
        r['alpha_fl'] = ALPHA20['Al']
        r['t_fl']    = t_fl
        r['D_fl']    = D_fl
        rows += [
            ('--- Al laminated foil ---',     '', ''),
            ('Foil thickness t_fl',           f"{t_fl:.4f}", 'mm'),
            ('Foil outer diameter D_fl',      f"{D_fl:.4f}", 'mm'),
            ('Foil area A_fl',                f"{A_fl*1e6:.6f}", 'mm2'),
            ('Foil Rso_fl at 20 degC',        f"{r['Rso_fl']:.4e}", 'ohm/m'),
        ]

    log.append(('Screen / Sheath Setup  [IEC 60287-1-1 Cl.2.3]', rows))


# =============================================================================
# LAMBDA 1 — SHEATH LOSS FACTOR  IEC 60287-1-1 Cl.2.3
# =============================================================================

def lambda1(theta_s, R_ac, c, r):
    """
    Sheath loss factor at given sheath temperature.

    FIX B: Eddy current λ1'' rules:
      - Milliken conductor:  always calculate λ1'' (IEC 2.3.1 exception)
      - Stranded/solid + solid bonding: λ1'' = 0 per IEC 2.3.1
      - GP6 flag: overrides ONLY for Milliken cables, not stranded
        (TB880 CS0 confirms: "conductor is not Milliken, eddy ignored")

    Returns (Rs, X, lam1p, lam1pp, lam1_total).
    """
    omega    = r['omega']
    has_foil = r.get('has_foil', False)
    is_milliken = c['cond_type'] in ('milliken', 'milliken_uni',
                                      'milliken_insulated')

    # Screen resistance at operating temperature
    Rs_sc = r['Rs0'] * (1 + r['alpha_s'] * (theta_s - 20))

    if has_foil:
        theta_fl = theta_s
        Rs_fl    = r['Rso_fl'] * (1 + r['alpha_fl'] * (theta_fl - 20))
        Rs       = (Rs_sc * Rs_fl) / (Rs_sc + Rs_fl)
    else:
        Rs    = Rs_sc
        Rs_fl = 0.0

    # Reactance X
    if has_foil:
        D_sc_out = r.get('D_sc_outer', c['ds'])
        d_cw     = c.get('ds_wire', 0.0)
        D_fl     = r['D_fl']
        t_fl     = r['t_fl']
        d_mean   = math.sqrt(
            ((D_sc_out - d_cw)**2 + (D_fl - t_fl)**2) / 2
        )
    elif c['screen_type'] == 'Cu_wire' and c.get('ds_wire', 0) > 0:
        d_mean = r.get('D_sc_outer', c['ds'] + c['ds_wire'])
    else:
        d_mean = c['ds']

    s_m = c['spacing_s'] * 1e-3
    d_m = d_mean * 1e-3
    X   = 2 * omega * 1e-7 * math.log(2 * s_m / d_m)

    # Circulating current loss λ1'
    if c['bonding'] == 'solid':
        lam1p_com = (Rs / R_ac) / (1 + (Rs / X)**2)
    else:
        lam1p_com = 0.0

    if has_foil:
        lam1p_cws = lam1p_com * (Rs_fl / (Rs_sc + Rs_fl))
        lam1p_fl  = lam1p_com * (Rs_sc / (Rs_sc + Rs_fl))
    else:
        lam1p_cws = lam1p_com
        lam1p_fl  = 0.0

    # Eddy current loss λ1''
    # FIX B: Only calculate for Milliken conductors
    # For stranded/solid: IEC 2.3.1 says ignore λ1'' when solid bonded
    # GP6 only applies to Milliken (not stranded)
    lam1pp_cws = 0.0
    lam1pp_fl  = 0.0

    if has_foil:
        # Dual layer — eddy on Al foil only
        m_fl       = (omega / Rs_fl) * 1e-7
        d_fl_inner = r['D_fl'] - r['t_fl']
        lam0_fl    = (3*(m_fl**2/(1+m_fl**2)) *
                      (d_fl_inner/(2*c['spacing_s']))**2)
        D1_fl      = ((1.14*m_fl**2.45 + 0.33) *
                      (d_fl_inner/(2*c['spacing_s']))**(0.92*m_fl+1.66))
        rho_fl_op  = RHO_ELEC['Al'] * (1 + ALPHA20['Al']*(theta_fl-20))
        beta1_fl   = math.sqrt(4*math.pi*omega/(1e7*rho_fl_op))
        gs_fl      = max(1.0,
                         1 + (r['t_fl']/r['D_fl'])**1.74 *
                         (beta1_fl*r['D_fl']*1e-3 - 1.6))
        lam1pp_raw = (Rs_fl/R_ac)*(
            gs_fl*lam0_fl*(1+D1_fl) +
            (beta1_fl*r['t_fl'])**4/12e12
        )
        F = 1.0
        if c['bonding'] == 'solid':
            M = Rs/X; N = Rs/X
            F = (4*M**2*N**2+(M+N)**2)/(4*(M**2+1)*(N**2+1))
        lam1pp_fl = F * lam1pp_raw

    elif is_milliken:
        # Milliken: always calculate eddy (IEC 2.3.1 exception + GP6)
        m      = (omega / Rs) * 1e-7
        lam0   = (3*(m**2/(1+m**2)) *
                  (c['ds']/(2*c['spacing_s']))**2)
        D1     = ((1.14*m**2.45 + 0.33) *
                  (c['ds']/(2*c['spacing_s']))**(0.92*m+1.66))
        rho_st = r['rho_s'] * (1 + r['alpha_s']*(theta_s-20))
        beta1  = math.sqrt(4*math.pi*omega/(1e7*rho_st))
        gs     = max(1.0,
                     1 + (c['ts']/c['ds'])**1.74 *
                     (beta1*c['ds']*1e-3 - 1.6))
        raw    = (Rs/R_ac)*(gs*lam0*(1+D1) +
                            (beta1*c['ts'])**4/12e12)
        F = 1.0
        if c['bonding'] == 'solid':
            M = Rs/X; N = Rs/X
            F = (4*M**2*N**2+(M+N)**2)/(4*(M**2+1)*(N**2+1))
        lam1pp_cws = F * raw

    # else: stranded/solid — λ1'' = 0 per IEC 2.3.1

    lam1_cws   = lam1p_cws + lam1pp_cws
    lam1_fl    = lam1p_fl  + lam1pp_fl
    lam1_total = lam1_cws  + lam1_fl

    r['lam1_cws'] = lam1_cws
    r['lam1_fl']  = lam1_fl
    r['Rs_op']    = Rs

    return Rs, X, lam1p_com, lam1pp_cws + lam1pp_fl, lam1_total


# =============================================================================
# ARMOUR LOSSES  IEC 60287-1-1 Cl.2.4
# =============================================================================

def armour_loss(c, r, log):
    """Populate r with lam2."""
    if c['armour_type'] == 'none':
        r['lam2'] = 0.0
        log.append(('Armour Losses  [IEC 60287-1-1 Cl.2.4]', [
            ('Armour type', 'None', ''),
            ('lam2', '0.000000', ''),
        ]))
        return

    mat_a   = 'steel' if c['armour_type'] in ('SWA', 'STA') else 'Al'
    rho_a   = RHO_ELEC[mat_a]
    alpha_a = ALPHA20[mat_a]

    if c['na'] > 0 and c['da'] > 0:
        Aa   = c['na'] * math.pi * (c['da']/2)**2 * 1e-6
        Ra0  = rho_a / Aa
        Ra   = Ra0 * (1 + alpha_a*(c['theta_max']-20))
        Xa   = 2*r['omega']*1e-7*math.log(2*c['spacing_s']/c['Da'])
        lam2 = (Ra/r['R_max']) / (1 + (Ra/Xa)**2)
    else:
        lam2 = 0.05

    r['lam2'] = lam2
    log.append(('Armour Losses  [IEC 60287-1-1 Cl.2.4]', [
        ('Armour material', mat_a, ''),
        ('lam2', f"{lam2:.6f}", ''),
    ]))