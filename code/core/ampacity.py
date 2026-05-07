"""Ampacity iteration engine — IEC 60287-1-1 Cl.1.4

Buried : T4 fixed (soil thermal resistance)
Air    : T4 = 1/(π De* h x), x = (θj-θa)^(1/4)
         Inner iteration: x^5 = Wtotal/(π De* h)
         Outer iteration: updates lam1, Rs at new theta_s

Verified:
  TB880 CS0-1 buried:  821.81 A  (stranded_compact, GP8)
  TB880 CS0-4 air:     990.94 A  (solar H=1000, θa=25°C)
  Gunnerz air:         385 A     (no solar, θa=40°C)
"""

import math
from installation.air import get_ZEg, calc_h, solve_x_inner


# =============================================================================
# BURIED AMPACITY ITERATION
# =============================================================================

def iterate_buried(c, r_shared, log_buried):
    """Iterate ampacity for direct buried installation.
    IEC 60287-1-1 Cl.1.4.1.1
    """
    rb = {}

    T1   = r_shared['T1_buried']
    T2   = r_shared['T2_buried']
    T3   = r_shared['T3_buried']
    T4   = r_shared['T4_buried']
    Wd   = r_shared['Wd']
    lam2 = r_shared['lam2']
    R_ac = r_shared['R_max']
    n    = 1

    Dtheta    = c['theta_max'] - c['theta_amb']
    theta_s   = c['theta_max'] - 10.0
    I_prev    = 0.0
    converged = False

    for it in range(300):
        Rs, X, lam1p, lam1pp, lam1 = _lambda1(theta_s, R_ac, c, r_shared)

        Etop = Dtheta - Wd * (0.5*T1 + n*(T2 + T3 + T4))
        Ebot = (R_ac*T1
                + n*R_ac*(1+lam1)*T2
                + n*R_ac*(1+lam1+lam2)*(T3+T4))
        I  = math.sqrt(max(0.0, Etop / Ebot))
        Wc = I**2 * R_ac

        theta_j_new = c['theta_amb'] + n*(Wc*(1+lam1+lam2)+Wd)*T4
        theta_s_new = theta_j_new   + n*(Wc*(1+lam1+lam2)+Wd)*T3

        if it > 3 and abs(I-I_prev) < 1e-6 and abs(theta_s_new-theta_s) < 1e-7:
            converged = True
            break
        theta_s = theta_s_new
        I_prev  = I

    Wc = I**2 * R_ac
    Ws = lam1 * Wc
    Wa = lam2 * Wc

    theta_j      = c['theta_amb'] + n*(Wc*(1+lam1+lam2)+Wd)*T4
    theta_s_surf = theta_j + n*(Wc*(1+lam1+lam2)+Wd)*T3
    theta_c_calc = theta_s_surf + (Wc + 0.5*Wd)*T1

    rb.update({
        'I':            I,
        'I_rounded':    math.floor(I) if c['tb880_gp2_round_down'] else round(I),
        'MVA':          math.sqrt(3)*c['U_rated']*1e3*I/1e6,
        'lam1': lam1, 'lam1p': lam1p, 'lam1pp': lam1pp,
        'Rs': Rs, 'X_sheath': X,
        'Wc': Wc, 'Ws': Ws, 'Wa': Wa,
        'iters': it+1, 'converged': converged,
        'theta_s':      theta_s_surf,
        'theta_j':      theta_j,
        'theta_c_calc': theta_c_calc,
        'Etop': Etop, 'Ebot': Ebot,
        'T1': T1, 'T2': T2, 'T3': T3, 'T4': T4,
    })

    log_buried.append(('Sheath Losses at Convergence (Buried)', [
        ('theta_s at convergence',       f"{theta_s_surf:.6f}", 'degC'),
        ('Rs at theta_s',                f"{Rs:.4e}", 'ohm/m'),
        ('X  sheath reactance',          f"{X:.4e}", 'ohm/m'),
        ("lam1'  circulating current",   f"{lam1p:.10f}", ''),
        ("lam1'' eddy current",          f"{lam1pp:.10f}", ''),
        ("lam1 = lam1' + lam1''",        f"{lam1:.10f}", ''),
        ('lam2  armour',                 f"{lam2:.6f}", ''),
    ]))
    log_buried.append(('Ampacity — Direct Buried  [IEC 60287-1-1 Cl.1.4.1.1]', [
        ('Delta_theta = theta_max - theta_amb', f"{Dtheta:.2f}", 'K'),
        ('Etop  numerator',              f"{Etop:.10f}", ''),
        ('Ebot  denominator',            f"{Ebot:.4e}", ''),
        ('I = sqrt(Etop/Ebot)  exact',   f"{I:.10f}", 'A'),
        ('I  rounded  TB880 GP2',        f"{rb['I_rounded']}", 'A'),
        ('MVA = sqrt(3) x U x I',        f"{rb['MVA']:.4f}", 'MVA'),
        ('Iterations',                   f"{it+1}", ''),
        ('Convergence', 'YES' if converged else 'NOT CONVERGED', ''),
    ]))
    log_buried.append(('Temperature Profile — Buried', [
        ('theta_c  conductor  target',   f"{c['theta_max']:.1f}", 'degC'),
        ('theta_c  back-calculated',     f"{theta_c_calc:.6f}", 'degC'),
        ('theta_s  sheath surface',      f"{theta_s_surf:.6f}", 'degC'),
        ('theta_j  cable outer surface', f"{theta_j:.6f}", 'degC'),
        ('theta_a  ambient ground',      f"{c['theta_amb']:.1f}", 'degC'),
    ]))
    log_buried.append(('Loss Budget — Buried', [
        ('Conductor  Wc = I^2 x R',      f"{Wc:.6f}", 'W/m'),
        ('Sheath     Ws = lam1 x Wc',    f"{Ws:.6f}", 'W/m'),
        ('Armour     Wa = lam2 x Wc',    f"{Wa:.6f}", 'W/m'),
        ('Dielectric Wd',                f"{Wd:.6e}", 'W/m'),
        ('Total',  f"{Wc*(1+lam1+lam2)+Wd:.6f}", 'W/m'),
    ]))

    return rb


# =============================================================================
# FREE AIR AMPACITY ITERATION
# =============================================================================

def iterate_air(c, r_shared, log_air):
    """
    Iterate ampacity for free air installation.
    IEC 60287-1-1 Cl.1.4.4.1 (with solar radiation)

    Two-level iteration:
      OUTER: updates lam1, Rs at current theta_s
      INNER: converges x=(θj-θa)^(1/4) via x^5 = Wtotal/(π De* h)
             T4 = 1/(π De* h x)

    Verified: TB880 CS0-4 → 990.94 A, Gunnerz → 385 A
    """
    ra = {}

    T1   = r_shared['T1_air']
    T3   = r_shared['T3_air']
    Wd   = r_shared['Wd']
    lam2 = r_shared['lam2']
    R_ac = r_shared['R_max']
    De_m = c['De'] * 1e-3        # metres
    n    = 1

    Z, E, g = get_ZEg(c['formation'], c['air_mounting'])
    h       = calc_h(Z, E, g, De_m)

    solar       = c.get('solar', False)
    sigma       = c.get('solar_sigma', 0.4)
    H_solar     = c.get('solar_H', 0.0)
    theta_amb_a = c['theta_amb_air']
    Dtheta_air  = c['theta_max'] - theta_amb_a

    theta_s   = c['theta_max'] - 10.0
    I_prev    = 0.0
    converged = False
    T4        = 1.0
    x_fin     = 2.0
    solar_heat= 0.0
    Etop = Ebot = 0.0

    for it in range(300):
        Rs, X, lam1p, lam1pp, lam1 = _lambda1(theta_s, R_ac, c, r_shared)

        # INNER iteration: converge x = (θj-θa)^(1/4)
        # x^5 = Wtotal/(π De* h)
        x_fin, T4, I, Wc, solar_heat, inner_i = solve_x_inner(
            De_m=De_m, h=h,
            R_ac=R_ac, lam1=lam1, lam2=lam2,
            T1=T1, T3=T3, Wd=Wd,
            Dtheta=Dtheta_air,
            sigma=sigma, H_solar=H_solar, solar=solar,
            n=n, tol=1e-10, max_iter=100
        )

        Ws = lam1 * Wc
        # Recompute Etop/Ebot at converged T4
        Etop = Dtheta_air - Wd*(0.5*T1 + n*(T3+T4)) - solar_heat
        Ebot = R_ac*T1 + n*R_ac*(1+lam1+lam2)*(T3+T4)

        theta_j_new  = theta_amb_a + n*(Wc*(1+lam1+lam2)+Wd)*T4 + solar_heat
        theta_s_new  = theta_j_new + n*(Wc*(1+lam1+lam2)+Wd)*T3

        if it > 3 and abs(I-I_prev) < 1e-6 and abs(theta_s_new-theta_s) < 1e-7:
            converged = True
            break
        theta_s = theta_s_new
        I_prev  = I

    Wc = I**2 * R_ac
    Ws = lam1 * Wc
    Wa = lam2 * Wc

    theta_j      = theta_amb_a + n*(Wc*(1+lam1+lam2)+Wd)*T4 + solar_heat
    theta_s_surf = theta_j + n*(Wc*(1+lam1+lam2)+Wd)*T3
    theta_c_calc = theta_s_surf + (Wc + 0.5*Wd)*T1

    ra.update({
        'I':            I,
        'I_rounded':    math.floor(I) if c['tb880_gp2_round_down'] else round(I),
        'MVA':          math.sqrt(3)*c['U_rated']*1e3*I/1e6,
        'lam1': lam1, 'lam1p': lam1p, 'lam1pp': lam1pp,
        'Rs': Rs, 'X_sheath': X,
        'Wc': Wc, 'Ws': Ws, 'Wa': Wa,
        'iters': it+1, 'converged': converged,
        'theta_s':      theta_s_surf,
        'theta_j':      theta_j,
        'theta_c_calc': theta_c_calc,
        'T4':  T4, 'h': h, 'Z': Z, 'E': E, 'g': g,
        'x_converged':  x_fin,
        'solar_heat':   solar_heat,
        'Etop': Etop, 'Ebot': Ebot,
        'T1': T1, 'T2': 0.0, 'T3': T3,
    })

    log_air.append(('Free Air Parameters  [IEC 60287-2-1 Cl.2.2.1]', [
        ('Formation',
         c['formation'], ''),
        ('Mounting',
         c['air_mounting'], ''),
        ('Z  constant  (IEC Table 2)',
         f"{Z:.4f}", ''),
        ('E  constant  (IEC Table 2)',
         f"{E:.4f}", ''),
        ('g  exponent  (IEC Table 2)',
         f"{g:.4f}", ''),
        ('De* cable outer diameter',
         f"{De_m*1000:.2f}", 'mm'),
        ('De* in metres',
         f"{De_m:.6f}", 'm'),
        ('(De*)^g',
         f"{De_m**g:.6f}", ''),
        ('h = Z/(De*)^g + E',
         f"{h:.10f}", 'W/(m2 K^5/4)'),
        ('Solar radiation',
         'Yes' if solar else 'No', ''),
        ('Solar intensity H',
         f"{H_solar:.1f}" if solar else 'N/A', 'W/m2'),
        ('Solar absorption sigma',
         f"{sigma:.2f}" if solar else 'N/A', ''),
        ('Ambient air temperature',
         f"{theta_amb_a:.1f}", 'degC'),
        ('Delta_theta = theta_max - theta_a_air',
         f"{Dtheta_air:.2f}", 'K'),
    ]))
    log_air.append(('Free Air T4 Calculation  [IEC 60287-2-1 Cl.2.2.1]', [
        ('x = (theta_j - theta_a)^(1/4) converged',
         f"{x_fin:.10f}", 'K^(1/4)'),
        ('Dtheta_s = x^4 = theta_j - theta_a',
         f"{x_fin**4:.10f}", 'K'),
        ('T4 = 1/(pi*De*h*x)',
         f"{T4:.10f}", 'K.m/W'),
        ('Solar term sigma*De*H*T4',
         f"{solar_heat:.10f}", 'K'),
        ('Etop numerator (incl solar)',
         f"{Etop:.10f}", ''),
        ('Ebot denominator',
         f"{Ebot:.4e}", ''),
    ]))
    log_air.append(('Sheath Losses at Convergence (Air)', [
        ('theta_s at convergence',       f"{theta_s_surf:.6f}", 'degC'),
        ('Rs at theta_s',                f"{Rs:.4e}", 'ohm/m'),
        ('X  sheath reactance',          f"{X:.4e}", 'ohm/m'),
        ("lam1'  circulating current",   f"{lam1p:.10f}", ''),
        ("lam1'' eddy current",          f"{lam1pp:.10f}", ''),
        ("lam1 = lam1' + lam1''",        f"{lam1:.10f}", ''),
        ('lam2  armour',                 f"{lam2:.6f}", ''),
    ]))
    log_air.append(('Ampacity — Free Air  [IEC 60287-1-1 Cl.1.4.4.1]', [
        ('I = sqrt(Etop/Ebot)  exact',   f"{I:.10f}", 'A'),
        ('I  rounded  TB880 GP2',        f"{ra['I_rounded']}", 'A'),
        ('MVA = sqrt(3) x U x I',        f"{ra['MVA']:.4f}", 'MVA'),
        ('Iterations (outer)',            f"{it+1}", ''),
        ('Convergence', 'YES' if converged else 'NOT CONVERGED', ''),
    ]))
    log_air.append(('Temperature Profile — Free Air', [
        ('theta_c  conductor  target',   f"{c['theta_max']:.1f}", 'degC'),
        ('theta_c  back-calculated',     f"{theta_c_calc:.6f}", 'degC'),
        ('theta_s  sheath surface',      f"{theta_s_surf:.6f}", 'degC'),
        ('theta_j  cable outer surface', f"{theta_j:.6f}", 'degC'),
        ('theta_a  ambient air',         f"{theta_amb_a:.1f}", 'degC'),
    ]))
    log_air.append(('Loss Budget — Free Air', [
        ('Conductor  Wc = I^2 x R',      f"{Wc:.6f}", 'W/m'),
        ('Sheath     Ws = lam1 x Wc',    f"{Ws:.6f}", 'W/m'),
        ('Armour     Wa = lam2 x Wc',    f"{Wa:.6f}", 'W/m'),
        ('Dielectric Wd',                f"{Wd:.6e}", 'W/m'),
        ('Solar heat sigma*De*H*T4',     f"{solar_heat:.6f}", 'W/m'),
        ('Total',   f"{Wc*(1+lam1+lam2)+Wd:.6f}", 'W/m'),
    ]))

    return ra


# =============================================================================
# SHARED helper
# =============================================================================

def _lambda1(theta_s, R_ac, c, r):
    from core.losses import lambda1 as _lam
    return _lam(theta_s, R_ac, c, r)