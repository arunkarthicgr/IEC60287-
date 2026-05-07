"""Thermal resistance calculations — IEC 60287-2-1

Fixes:
  FIX C: T2 uses D_sc_outer (D_tuws + 2*ds_wire) not mean ds
  FIX D: T3 starting diameter uses D_sc_outer for solid Al/Pb sheath
         TB880 CS0: D'a = ds + ts = 67.7 + 0.8 = 68.5mm (NOT 67.7mm)
         T3 buried: × 1.6 for touching trefoil
         T3 air:    × 1.0 always (TB880 confirmed)
"""

import math
from config.constants import RHO_THERM_INS, RHO_THERM_OSH
from installation.buried import calc_T4, touching_factor


def thermal_resistances(c, r, log):
    """Populate r with T1, T2, T3, T4 for both buried and air."""

    rho_ins  = RHO_THERM_INS.get(c['ins_mat'], 3.5)
    rho_osh  = RHO_THERM_OSH.get(c['osh_mat'], 5.0)
    has_foil = r.get('has_foil', False)

    # ── T1 — layer by layer ───────────────────────────────────────────────
    rho_sc   = c.get('rho_sc',   2.5)
    rho_tape = c.get('rho_tape', 6.0)

    T1_cs   = (rho_sc  / (2*math.pi)) * math.log(c['Dc_sc'] / c['Dc'])
    T1_i    = (rho_ins / (2*math.pi)) * math.log(c['Di']    / c['Dc_sc'])
    T1_si   = (rho_sc  / (2*math.pi)) * math.log(c['Di_sc'] / c['Di'])
    D_tuws  = c.get('D_tuws', c['Di_sc'])
    T1_uwbt = (rho_tape / (2*math.pi)) * math.log(D_tuws / c['Di_sc'])
    T1_raw  = T1_cs + T1_i + T1_si + T1_uwbt

    # Coverage correction — only if no Al foil
    T1_correction = 1.0
    coverage = 1.0
    if c['screen_type'] == 'Cu_wire' and c.get('ns', 0) > 0:
        LFs     = r.get('LFs', 1.0)
        ds_wire = c.get('ds_wire', c['ts'])
        ns      = c['ns']
        coverage = (ds_wire * ns / (math.pi * (D_tuws + ds_wire))) * LFs
        if coverage < 0.50 and not has_foil:
            T1_correction = 1.07

    T1 = T1_correction * T1_raw
    r['T1_correction'] = T1_correction
    r['T1_raw']        = T1_raw
    r['coverage']      = coverage
    r['T1_buried']     = T1
    r['T1_air']        = T1

    # ── T2 — between wire screen and Al foil ─────────────────────────────
    if has_foil and c.get('D_owt', 0) > 0:
        rho_wb     = c.get('rho_wb', 12.0)
        D_owt      = c['D_owt']
        if c['screen_type'] == 'Cu_wire' and c.get('ds_wire', 0) > 0:
            D_sc_outer = D_tuws + 2 * c['ds_wire']
        else:
            D_sc_outer = c['ds']
        T2 = (rho_wb / (2*math.pi)) * math.log(D_owt / D_sc_outer)
    else:
        T2         = 0.0
        D_sc_outer = r.get('D_sc_outer', c['ds'])

    r['T2_buried'] = T2
    r['T2_air']    = 0.0

    # ── T3 — oversheath ───────────────────────────────────────────────────
    # FIX D: Starting diameter for T3
    # For solid metallic sheath (Al, Pb): use D_sc_outer = ds + ts
    #   TB880 CS0: D'a = 67.7 + 0.8 = 68.5mm → T3 = 0.05420 K.m/W ✓
    # For Cu wire screen + foil: use D_fl
    # For wire/tape screen (no foil): use ds (mean)

    st = c['screen_type']
    if has_foil:
        D_start = c.get('D_fl', c['ds'])
    elif st in ('Al', 'Pb'):
        # Solid sheath — use outer surface diameter
        D_start = r.get('D_sc_outer', c['ds'] + c['ts'])
    else:
        D_start = c['ds']

    has_outer_sc = c.get('has_outer_sc', False)

    if has_outer_sc and c.get('De_1', 0) > 0:
        rho_osh_sc = c.get('rho_osh_sc', 2.5)
        De_1       = c['De_1']
        De_2       = c['De']
        T3_oc      = (rho_osh    / (2*math.pi)) * math.log(De_1 / D_start)
        T3_sc      = (rho_osh_sc / (2*math.pi)) * math.log(De_2 / De_1)
        T3_raw     = T3_oc + T3_sc
    else:
        T3_raw = (rho_osh / (2*math.pi)) * math.log(
            1 + 2 * c['t_osh'] / D_start)

    # Buried: 1.6× for touching trefoil
    Tf_buried = touching_factor(c['formation'], c['spacing_s'], c['De'],
                                c['t3_touching_factor'])
    T3_buried = Tf_buried * T3_raw

    # Air: NO 1.6× factor (TB880 CS0-4 confirmed)
    T3_air = T3_raw

    r['T3_buried']        = T3_buried
    r['T3_air']           = T3_air
    r['T3_raw']           = T3_raw
    r['T3_factor_buried'] = Tf_buried
    r['T3_factor_air']    = 1.0
    r['D_start_T3']       = D_start

    # ── T4 — buried soil ──────────────────────────────────────────────────
    T4_buried, u = calc_T4(
        c['depth'], c['De'], c['rho_soil'],
        c['formation'], c['spacing_s'],
        c['tb880_gp8_exact_t4']
    )
    r['T4_buried'] = T4_buried
    r['u_buried']  = u

    log.append(('Thermal Resistances  [IEC 60287-2-1]', [
        ('rho_ins insulation',
         f"{rho_ins:.2f}", 'K.m/W'),
        ('rho_sc semiconducting screens',
         f"{rho_sc:.2f}", 'K.m/W'),
        ('rho_tape bedding tape under wire screen',
         f"{rho_tape:.2f}", 'K.m/W'),
        ('T1_cs   conductor screen',
         f"{T1_cs:.10f}", 'K.m/W'),
        ('T1_i    insulation',
         f"{T1_i:.10f}", 'K.m/W'),
        ('T1_si   insulation screen',
         f"{T1_si:.10f}", 'K.m/W'),
        ('T1_uwbt bedding tape under wire screen',
         f"{T1_uwbt:.10f}", 'K.m/W'),
        ('T1_raw = sum of all layers',
         f"{T1_raw:.10f}", 'K.m/W'),
        (f'T1 correction x{T1_correction:.2f} '
         f'(foil={has_foil}, cover={coverage:.1%})',
         f"{T1:.10f}", 'K.m/W'),
        ('T2  buried  (screen to foil tape)',
         f"{T2:.10f}", 'K.m/W'),
        ('T3 reference diameter D_start',
         f"{D_start:.4f}", 'mm'),
        ('T3_raw oversheath'
         + (' (two-layer)' if has_outer_sc else ' (single-layer)'),
         f"{T3_raw:.10f}", 'K.m/W'),
        (f'T3 buried x{Tf_buried:.1f} (touching trefoil factor)',
         f"{T3_buried:.10f}", 'K.m/W'),
        ('T3 air  x1.0 (no touching factor in air)',
         f"{T3_air:.10f}", 'K.m/W'),
        ('u = 2L/De  (buried)',
         f"{u:.6f}", ''),
        ('T4 buried  (soil)',
         f"{T4_buried:.10f}", 'K.m/W'),
        ('T4 air     (iterative — see air section)',
         'see air section', ''),
    ]))