"""Ampacity iteration engine — IEC 60287-1-1 Cl.1.4

Buried : T4 fixed (soil)   s=spacing_s for Rac, X, lam1
Duct   : T4=T4'+T4''+T4''' s=Do for Rac, X, lam1   T4' iterative (theta_m)
Air    : T4=1/(pi*De*h*x)  s=spacing_s for Rac, X, lam1

Verified:
  TB880 CS0-1 buried:  821.81 A  (stranded_compact, GP8)
  TB880 CS0-2 duct:    682.81 A  (HDPE touching trefoil)  our: 682.72 A
  TB880 CS0-4 air:     990.94 A  (solar H=1000, theta_a=25°C)
  Gunnerz air:         385 A
"""

import math
from installation.air  import get_ZEg, calc_h, solve_x_inner
from installation.duct import (
    get_duct_constants, calc_T4_prime, calc_T4_double,
    calc_T4_triple_touching_trefoil, calc_T4_triple_flat_spaced,
    update_theta_m, DUCT_RHO_THERM,
)


# =============================================================================
# BURIED
# =============================================================================

def iterate_buried(c, r_shared, log_buried):
    """Direct buried — IEC 60287-1-1 Cl.1.4.1.1"""
    T1   = r_shared['T1_buried']
    T2   = r_shared['T2_buried']
    T3   = r_shared['T3_buried']
    T4   = r_shared['T4_buried']
    Wd   = r_shared['Wd']
    lam2 = r_shared['lam2']
    R_ac = r_shared['R_max']        # s=spacing_s
    n    = 1

    Dtheta  = c['theta_max'] - c['theta_amb']
    theta_s = c['theta_max'] - 10.0
    I_prev  = 0.0
    converged = False

    for it in range(300):
        Rs, X, lam1p, lam1pp, lam1 = _lambda1(
            theta_s, R_ac, c, r_shared, 'buried')

        Etop = Dtheta - Wd*(0.5*T1 + n*(T2+T3+T4))
        Ebot = R_ac*T1 + n*R_ac*(1+lam1)*T2 + n*R_ac*(1+lam1+lam2)*(T3+T4)
        I    = math.sqrt(max(0.0, Etop/Ebot))
        Wc   = I**2 * R_ac

        theta_j_new = c['theta_amb'] + n*(Wc*(1+lam1+lam2)+Wd)*T4
        theta_s_new = theta_j_new   + n*(Wc*(1+lam1+lam2)+Wd)*T3

        if it > 3 and abs(I-I_prev) < 1e-6 and abs(theta_s_new-theta_s) < 1e-7:
            converged = True; break
        theta_s = theta_s_new; I_prev = I

    Wc = I**2*R_ac; Ws = lam1*Wc; Wa = lam2*Wc
    theta_j      = c['theta_amb'] + n*(Wc*(1+lam1+lam2)+Wd)*T4
    theta_s_surf = theta_j + n*(Wc*(1+lam1+lam2)+Wd)*T3
    theta_c_calc = theta_s_surf + (Wc+0.5*Wd)*T1

    rb = {
        'I': I,
        'I_rounded': math.floor(I) if c['tb880_gp2_round_down'] else round(I),
        'MVA':       math.sqrt(3)*c['U_rated']*1e3*I/1e6,
        'lam1': lam1, 'lam1p': lam1p, 'lam1pp': lam1pp,
        'Rs': Rs, 'X_sheath': X,
        'Wc': Wc, 'Ws': Ws, 'Wa': Wa,
        'iters': it+1, 'converged': converged,
        'theta_s': theta_s_surf, 'theta_j': theta_j, 'theta_c_calc': theta_c_calc,
        'Etop': Etop, 'Ebot': Ebot,
        'T1': T1, 'T2': T2, 'T3': T3, 'T4': T4,
    }

    _log_section(log_buried, 'Buried', rb, c, Wd, lam2, Dtheta, it)
    return rb


# =============================================================================
# DUCT
# =============================================================================

def iterate_duct(c, r_shared, log_duct):
    """
    Duct installation — IEC 60287-1-1 Cl.1.4.1.1

    Uses s=Do for Rac (R_max_duct) and X (X_sheath_duct).
    T4' is temperature-dependent → updated each outer iteration.

    TB880 CS0-2 target: 682.8145 A  our result: 682.72 A (0.013% diff)
    """
    T1   = r_shared['T1_buried']    # cable geometry unchanged
    T2   = r_shared['T2_buried']
    T3   = r_shared['T3_duct']      # NO 1.6× factor
    Wd   = r_shared['Wd']
    lam2 = r_shared['lam2']
    R_ac = r_shared['R_max_duct']   # s=Do spacing
    n    = 1

    duct_mat = c.get('duct_mat', 'HDPE')
    Do_mm    = c['duct_Do']
    Di_mm    = c['duct_Di']
    De_mm    = c['De']
    L_mm     = c['depth']
    rho_soil = c['rho_soil']
    rho_duct = DUCT_RHO_THERM.get(duct_mat, 3.5)
    formation= c['formation']
    touching = c.get('duct_touching', True)
    U, V, Y  = get_duct_constants(duct_mat)

    Dtheta = c['theta_max'] - c['theta_amb']

    # Fixed T4 components
    T4_double = calc_T4_double(rho_duct, Do_mm, Di_mm)
    if touching and formation in ('trefoil',):
        T4_triple = calc_T4_triple_touching_trefoil(rho_soil, L_mm, Do_mm)
    else:
        s_mm = c.get('duct_spacing', Do_mm)
        T4_triple = calc_T4_triple_flat_spaced(rho_soil, L_mm, Do_mm, s_mm)

    theta_m  = c['theta_max'] - 20.0     # TB880 recommended initial value
    T4_prime = calc_T4_prime(U, V, Y, theta_m, De_mm)
    T4       = T4_prime + T4_double + T4_triple

    theta_s   = c['theta_max'] - 10.0
    I_prev    = 0.0
    converged = False

    for it in range(300):
        Rs, X, lam1p, lam1pp, lam1 = _lambda1(
            theta_s, R_ac, c, r_shared, 'duct')

        Etop = Dtheta - Wd*(0.5*T1 + n*(T2+T3+T4))
        Ebot = R_ac*T1 + n*R_ac*(1+lam1)*T2 + n*R_ac*(1+lam1+lam2)*(T3+T4)
        I    = math.sqrt(max(0.0, Etop/Ebot))
        Wc   = I**2 * R_ac
        Ws   = lam1 * Wc

        theta_j_new  = c['theta_amb'] + n*(Wc*(1+lam1+lam2)+Wd)*T4
        theta_s_new  = theta_j_new   + n*(Wc*(1+lam1+lam2)+Wd)*T3
        theta_m_new  = update_theta_m(theta_j_new, T4_prime, Wc, Ws, Wd)

        T4_prime = calc_T4_prime(U, V, Y, theta_m_new, De_mm)
        T4       = T4_prime + T4_double + T4_triple

        if it > 3 and abs(I-I_prev) < 1e-6 and abs(theta_s_new-theta_s) < 1e-7:
            converged = True; break
        theta_s = theta_s_new; theta_m = theta_m_new; I_prev = I

    Wc = I**2*R_ac; Ws = lam1*Wc; Wa = lam2*Wc
    theta_j      = c['theta_amb'] + n*(Wc*(1+lam1+lam2)+Wd)*T4
    theta_s_surf = theta_j + n*(Wc*(1+lam1+lam2)+Wd)*T3
    theta_c_calc = theta_s_surf + (Wc+0.5*Wd)*T1
    theta_duct_in= theta_j - n*(Wc*(1+lam1+lam2)+Wd)*T4_prime

    rd = {
        'I': I,
        'I_rounded': math.floor(I) if c['tb880_gp2_round_down'] else round(I),
        'MVA':       math.sqrt(3)*c['U_rated']*1e3*I/1e6,
        'lam1': lam1, 'lam1p': lam1p, 'lam1pp': lam1pp,
        'Rs': Rs, 'X_sheath': X,
        'Wc': Wc, 'Ws': Ws, 'Wa': Wa,
        'iters': it+1, 'converged': converged,
        'theta_s': theta_s_surf, 'theta_j': theta_j, 'theta_c_calc': theta_c_calc,
        'theta_duct_in': theta_duct_in, 'theta_m': theta_m,
        'Etop': Etop, 'Ebot': Ebot,
        'T1': T1, 'T2': T2, 'T3': T3,
        'T4': T4, 'T4_prime': T4_prime,
        'T4_double': T4_double, 'T4_triple': T4_triple,
    }

    _log_duct(log_duct, rd, c, Wd, lam2, Dtheta, it, U, V, Y, Do_mm, Di_mm, touching)
    return rd


# =============================================================================
# FREE AIR
# =============================================================================

def iterate_air(c, r_shared, log_air):
    """
    Free air — IEC 60287-1-1 Cl.1.4.4.1
    Inner loop: x^5 = Wtotal/(pi*De*h), T4=1/(pi*De*h*x)
    """
    T1   = r_shared['T1_air']
    T3   = r_shared['T3_air']
    Wd   = r_shared['Wd']
    lam2 = r_shared['lam2']
    R_ac = r_shared['R_max']        # s=spacing_s
    De_m = c['De'] * 1e-3
    n    = 1

    Z, E, g = get_ZEg(c['formation'], c['air_mounting'])
    h       = calc_h(Z, E, g, De_m)

    solar       = c.get('solar', False)
    sigma       = c.get('solar_sigma', 0.4)
    H_solar     = c.get('solar_H', 0.0)
    theta_amb_a = c['theta_amb_air']
    Dtheta_air  = c['theta_max'] - theta_amb_a

    theta_s = c['theta_max'] - 10.0
    I_prev  = 0.0; converged = False
    T4 = 1.0; x_fin = 2.0; solar_heat = 0.0; Etop = Ebot = 0.0

    for it in range(300):
        Rs, X, lam1p, lam1pp, lam1 = _lambda1(
            theta_s, R_ac, c, r_shared, 'air')

        x_fin, T4, I, Wc, solar_heat, _ = solve_x_inner(
            De_m=De_m, h=h, R_ac=R_ac, lam1=lam1, lam2=lam2,
            T1=T1, T3=T3, Wd=Wd, Dtheta=Dtheta_air,
            sigma=sigma, H_solar=H_solar, solar=solar, n=n, tol=1e-10,
        )

        Etop = Dtheta_air - Wd*(0.5*T1+n*(T3+T4)) - solar_heat
        Ebot = R_ac*T1 + n*R_ac*(1+lam1+lam2)*(T3+T4)

        theta_j_new  = theta_amb_a + n*(Wc*(1+lam1+lam2)+Wd)*T4 + solar_heat
        theta_s_new  = theta_j_new + n*(Wc*(1+lam1+lam2)+Wd)*T3

        if it > 3 and abs(I-I_prev) < 1e-6 and abs(theta_s_new-theta_s) < 1e-7:
            converged = True; break
        theta_s = theta_s_new; I_prev = I

    Wc = I**2*R_ac; Ws = lam1*Wc; Wa = lam2*Wc
    theta_j      = theta_amb_a + n*(Wc*(1+lam1+lam2)+Wd)*T4 + solar_heat
    theta_s_surf = theta_j + n*(Wc*(1+lam1+lam2)+Wd)*T3
    theta_c_calc = theta_s_surf + (Wc+0.5*Wd)*T1

    ra = {
        'I': I,
        'I_rounded': math.floor(I) if c['tb880_gp2_round_down'] else round(I),
        'MVA':       math.sqrt(3)*c['U_rated']*1e3*I/1e6,
        'lam1': lam1, 'lam1p': lam1p, 'lam1pp': lam1pp,
        'Rs': Rs, 'X_sheath': X,
        'Wc': Wc, 'Ws': Ws, 'Wa': Wa,
        'iters': it+1, 'converged': converged,
        'theta_s': theta_s_surf, 'theta_j': theta_j, 'theta_c_calc': theta_c_calc,
        'T4': T4, 'h': h, 'Z': Z, 'E': E, 'g': g,
        'x_converged': x_fin, 'solar_heat': solar_heat,
        'Etop': Etop, 'Ebot': Ebot,
        'T1': T1, 'T2': 0.0, 'T3': T3,
    }

    _log_air(log_air, ra, c, Wd, lam2, Dtheta_air, it, h, Z, E, g,
             De_m, solar, sigma, H_solar, theta_amb_a)
    return ra


# =============================================================================
# HELPER: route lambda1 call with installation type
# =============================================================================

def _lambda1(theta_s, R_ac, c, r, installation='buried'):
    from core.losses import lambda1 as _lam
    return _lam(theta_s, R_ac, c, r, installation)


# =============================================================================
# LOGGING
# =============================================================================

def _log_section(log, label, res, c, Wd, lam2, Dtheta, it):
    """Generic log for buried results."""
    log.append((f'Sheath Losses at Convergence ({label})', [
        ('theta_s at convergence',     f"{res['theta_s']:.6f}", 'degC'),
        ('Rs at theta_s',              f"{res['Rs']:.4e}", 'ohm/m'),
        ('X  sheath reactance',        f"{res['X_sheath']:.4e}", 'ohm/m'),
        ("lam1'  circulating",         f"{res['lam1p']:.10f}", ''),
        ("lam1'' eddy",                f"{res['lam1pp']:.10f}", ''),
        ("lam1 = lam1' + lam1''",      f"{res['lam1']:.10f}", ''),
        ('lam2  armour',               f"{lam2:.6f}", ''),
    ]))
    log.append((f'Ampacity — Direct Buried  [IEC 60287-1-1 Cl.1.4.1.1]', [
        ('Delta_theta',                f"{Dtheta:.2f}", 'K'),
        ('Etop  numerator',            f"{res['Etop']:.10f}", ''),
        ('Ebot  denominator',          f"{res['Ebot']:.4e}", ''),
        ('I = sqrt(Etop/Ebot)  exact', f"{res['I']:.10f}", 'A'),
        ('I  rounded  TB880 GP2',      f"{res['I_rounded']}", 'A'),
        ('MVA = sqrt(3) x U x I',      f"{res['MVA']:.4f}", 'MVA'),
        ('Iterations',                 f"{it+1}", ''),
        ('Convergence', 'YES' if res['converged'] else 'NOT CONVERGED', ''),
    ]))
    log.append((f'Temperature Profile — {label}', [
        ('theta_c  conductor  target', f"{c['theta_max']:.1f}", 'degC'),
        ('theta_c  back-calculated',   f"{res['theta_c_calc']:.6f}", 'degC'),
        ('theta_s  sheath surface',    f"{res['theta_s']:.6f}", 'degC'),
        ('theta_j  cable surface',     f"{res['theta_j']:.6f}", 'degC'),
        ('theta_a  ambient',           f"{c['theta_amb']:.1f}", 'degC'),
    ]))
    log.append((f'Loss Budget — {label}', [
        ('Conductor  Wc',  f"{res['Wc']:.6f}", 'W/m'),
        ('Sheath     Ws',  f"{res['Ws']:.6f}", 'W/m'),
        ('Armour     Wa',  f"{res['Wa']:.6f}", 'W/m'),
        ('Dielectric Wd',  f"{Wd:.6e}", 'W/m'),
        ('Total', f"{res['Wc']*(1+res['lam1']+lam2)+Wd:.6f}", 'W/m'),
    ]))


def _log_duct(log, rd, c, Wd, lam2, Dtheta, it, U, V, Y, Do, Di, touching):
    log.append(('Duct Installation Parameters  [IEC 60287-2-1 Cl.4.2.7]', [
        ('Duct material',           c.get('duct_mat','HDPE'), ''),
        ('Formation',               c['formation'], ''),
        ('Touching ducts',          'Yes' if touching else 'No', ''),
        ('Duct outer diameter Do',  f"{Do:.1f}", 'mm'),
        ('Duct inner diameter Di',  f"{Di:.1f}", 'mm'),
        ('Di/De',                   f"{Di/c['De']:.3f}", ''),
        ('U (IEC Table 4)',         f"{U:.2f}", ''),
        ('V (IEC Table 4)',         f"{V:.3f}", ''),
        ('Y (IEC Table 4)',         f"{Y:.4f}", ''),
        ('theta_m initial',         f"{c['theta_max']-20:.1f}", 'degC'),
    ]))
    log.append(('Duct T4 Components  [IEC 60287-2-1 Cl.4.2.7]', [
        ("T4'  air gap (converged)",  f"{rd['T4_prime']:.10f}", 'K.m/W'),
        ("T4'' duct wall",            f"{rd['T4_double']:.10f}", 'K.m/W'),
        ("T4''' soil external",       f"{rd['T4_triple']:.10f}", 'K.m/W'),
        ("T4 total",                  f"{rd['T4']:.10f}", 'K.m/W'),
        ("theta_m converged",         f"{rd['theta_m']:.4f}", 'degC'),
    ]))
    log.append(('Sheath Losses at Convergence (Duct)', [
        ('theta_s at convergence',     f"{rd['theta_s']:.6f}", 'degC'),
        ('Rs at theta_s',              f"{rd['Rs']:.4e}", 'ohm/m'),
        ('X  sheath reactance (s=Do)', f"{rd['X_sheath']:.4e}", 'ohm/m'),
        ("lam1'  circulating",         f"{rd['lam1p']:.10f}", ''),
        ("lam1'' eddy",                f"{rd['lam1pp']:.10f}", ''),
        ("lam1 = lam1' + lam1''",      f"{rd['lam1']:.10f}", ''),
        ('lam2  armour',               f"{lam2:.6f}", ''),
    ]))
    log.append(('Ampacity — Duct  [IEC 60287-1-1 Cl.1.4.1.1]', [
        ('Delta_theta',                f"{Dtheta:.2f}", 'K'),
        ('Etop  numerator',            f"{rd['Etop']:.10f}", ''),
        ('Ebot  denominator',          f"{rd['Ebot']:.4e}", ''),
        ('I = sqrt(Etop/Ebot)  exact', f"{rd['I']:.10f}", 'A'),
        ('I  rounded  TB880 GP2',      f"{rd['I_rounded']}", 'A'),
        ('MVA = sqrt(3) x U x I',      f"{rd['MVA']:.4f}", 'MVA'),
        ('Iterations',                 f"{it+1}", ''),
        ('Convergence', 'YES' if rd['converged'] else 'NOT CONVERGED', ''),
    ]))
    log.append(('Temperature Profile — Duct', [
        ('theta_c  conductor  target', f"{c['theta_max']:.1f}", 'degC'),
        ('theta_c  back-calculated',   f"{rd['theta_c_calc']:.6f}", 'degC'),
        ('theta_s  sheath surface',    f"{rd['theta_s']:.6f}", 'degC'),
        ('theta_j  cable surface',     f"{rd['theta_j']:.6f}", 'degC'),
        ('theta_duct_inner',           f"{rd['theta_duct_in']:.6f}", 'degC'),
        ('theta_m  mean air gap',      f"{rd['theta_m']:.4f}", 'degC'),
        ('theta_a  ambient',           f"{c['theta_amb']:.1f}", 'degC'),
    ]))
    log.append(('Loss Budget — Duct', [
        ('Conductor  Wc',  f"{rd['Wc']:.6f}", 'W/m'),
        ('Sheath     Ws',  f"{rd['Ws']:.6f}", 'W/m'),
        ('Armour     Wa',  f"{rd['Wa']:.6f}", 'W/m'),
        ('Dielectric Wd',  f"{Wd:.6e}", 'W/m'),
        ('Total', f"{rd['Wc']*(1+rd['lam1']+lam2)+Wd:.6f}", 'W/m'),
    ]))


def _log_air(log, ra, c, Wd, lam2, Dtheta, it, h, Z, E, g,
             De_m, solar, sigma, H_solar, theta_amb_a):
    log.append(('Free Air Parameters  [IEC 60287-2-1 Cl.2.2.1]', [
        ('Formation',          c['formation'], ''),
        ('Mounting',           c['air_mounting'], ''),
        ('Z  (IEC Table 2)',   f"{Z:.4f}", ''),
        ('E  (IEC Table 2)',   f"{E:.4f}", ''),
        ('g  (IEC Table 2)',   f"{g:.4f}", ''),
        ('De* (m)',             f"{De_m:.6f}", 'm'),
        ('h = Z/(De*)^g + E',  f"{h:.10f}", 'W/(m2 K^5/4)'),
        ('Solar',              'Yes' if solar else 'No', ''),
        ('H',      f"{H_solar:.1f}" if solar else 'N/A', 'W/m2'),
        ('sigma',  f"{sigma:.2f}"   if solar else 'N/A', ''),
        ('theta_a_air',        f"{theta_amb_a:.1f}", 'degC'),
        ('Delta_theta',        f"{Dtheta:.2f}", 'K'),
    ]))
    log.append(('Free Air T4  [IEC 60287-2-1 Cl.2.2.1]', [
        ('x = (theta_j-theta_a)^(1/4)', f"{ra['x_converged']:.10f}", 'K^(1/4)'),
        ('Dtheta_s = theta_j - theta_a', f"{ra['x_converged']**4:.10f}", 'K'),
        ('T4 = 1/(pi*De*h*x)',           f"{ra['T4']:.10f}", 'K.m/W'),
        ('Solar sigma*De*H*T4',          f"{ra['solar_heat']:.10f}", 'K'),
    ]))
    log.append(('Sheath Losses at Convergence (Air)', [
        ('theta_s at convergence',   f"{ra['theta_s']:.6f}", 'degC'),
        ('Rs at theta_s',            f"{ra['Rs']:.4e}", 'ohm/m'),
        ('X  sheath reactance',      f"{ra['X_sheath']:.4e}", 'ohm/m'),
        ("lam1'",                    f"{ra['lam1p']:.10f}", ''),
        ("lam1''",                   f"{ra['lam1pp']:.10f}", ''),
        ("lam1",                     f"{ra['lam1']:.10f}", ''),
        ('lam2',                     f"{lam2:.6f}", ''),
    ]))
    log.append(('Ampacity — Free Air  [IEC 60287-1-1 Cl.1.4.4.1]', [
        ('Etop  numerator (incl solar)', f"{ra['Etop']:.10f}", ''),
        ('Ebot  denominator',            f"{ra['Ebot']:.4e}", ''),
        ('I = sqrt(Etop/Ebot)  exact',   f"{ra['I']:.10f}", 'A'),
        ('I  rounded  TB880 GP2',        f"{ra['I_rounded']}", 'A'),
        ('MVA = sqrt(3) x U x I',        f"{ra['MVA']:.4f}", 'MVA'),
        ('Iterations',                   f"{it+1}", ''),
        ('Convergence', 'YES' if ra['converged'] else 'NOT CONVERGED', ''),
    ]))
    log.append(('Temperature Profile — Free Air', [
        ('theta_c  conductor  target',   f"{c['theta_max']:.1f}", 'degC'),
        ('theta_c  back-calculated',     f"{ra['theta_c_calc']:.6f}", 'degC'),
        ('theta_s  sheath surface',      f"{ra['theta_s']:.6f}", 'degC'),
        ('theta_j  cable surface',       f"{ra['theta_j']:.6f}", 'degC'),
        ('theta_a  ambient air',         f"{theta_amb_a:.1f}", 'degC'),
    ]))
    log.append(('Loss Budget — Free Air', [
        ('Conductor  Wc',  f"{ra['Wc']:.6f}", 'W/m'),
        ('Sheath     Ws',  f"{ra['Ws']:.6f}", 'W/m'),
        ('Armour     Wa',  f"{ra['Wa']:.6f}", 'W/m'),
        ('Dielectric Wd',  f"{Wd:.6e}", 'W/m'),
        ('Solar heat',     f"{ra['solar_heat']:.6f}", 'W/m'),
        ('Total',          f"{ra['Wc']*(1+ra['lam1']+lam2)+Wd:.6f}", 'W/m'),
    ]))