"""Console print and PDF report generation — InnoVites branded.

New signature:
    print_results(c, r, rb, ra, log, log_bur, log_air)
    generate_pdf (c, r, rb, ra, log, log_bur, log_air, filepath)

Where:
    c       = inputs dict
    r       = shared cable properties (Rac, losses, thermal)
    rb      = buried result dict
    ra      = free air result dict
    log     = shared calculation log  (cable properties)
    log_bur = buried-specific log
    log_air = air-specific log
"""

import math
from datetime import datetime

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle,
        Paragraph, Spacer, KeepTogether,
    )
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False


# ─────────────────────────────────────────────────────────────────────────────
# CONSOLE OUTPUT
# ─────────────────────────────────────────────────────────────────────────────

def print_results(c, r, rb, ra, log, log_bur, log_air):
    sep  = '─' * 68
    sep2 = '=' * 68

    # shared cable properties
    print('\n' + sep)
    print('  RESULTS SUMMARY')
    print(sep)
    for section, rows in log:
        print(f"\n  [ {section} ]")
        for label, val, unit in rows:
            print(f"    {label:<50} {val:>14}  {unit}")

    # buried detail
    for section, rows in log_bur:
        print(f"\n  [ {section} ]")
        for label, val, unit in rows:
            print(f"    {label:<50} {val:>14}  {unit}")

    # air detail
    for section, rows in log_air:
        print(f"\n  [ {section} ]")
        for label, val, unit in rows:
            print(f"    {label:<50} {val:>14}  {unit}")

    # dual summary banner
    print('\n' + sep2)
    print(f"  {'':30} {'BURIED':>15}  {'FREE AIR':>15}")
    print(sep2)
    print(f"  {'AMPACITY (exact)':<30} "
          f"{rb['I']:>14.4f}A  {ra['I']:>14.4f}A")
    print(f"  {'AMPACITY (rounded)':<30} "
          f"{rb['I_rounded']:>15}  {ra['I_rounded']:>15}")
    print(f"  {'MVA':<30} "
          f"{rb['MVA']:>12.3f} MVA  {ra['MVA']:>12.3f} MVA")
    print(f"  {'Sheath temperature':<30} "
          f"{rb['theta_s']:>12.2f} °C  {ra['theta_s']:>12.2f} °C")
    print(f"  {'Conductor temperature':<30} "
          f"{rb['theta_c_calc']:>12.2f} °C  {ra['theta_c_calc']:>12.2f} °C")
    print(f"  {'T4 external':<30} "
          f"{rb['T4']:>11.4f} K.m/W  {ra['T4']:>11.4f} K.m/W")
    print(f"  {'λ1 sheath loss':<30} "
          f"{rb['lam1']:>15.6f}  {ra['lam1']:>15.6f}")
    print(f"  {'Iterations':<30} "
          f"{rb['iters']:>15}  {ra['iters']:>15}")
    conv_b = 'YES' if rb['converged'] else 'NOT CONVERGED'
    conv_a = 'YES' if ra['converged'] else 'NOT CONVERGED'
    print(f"  {'Convergence':<30} {conv_b:>15}  {conv_a:>15}")
    print(sep2 + '\n')


# ─────────────────────────────────────────────────────────────────────────────
# PDF GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def generate_pdf(c, r, rb, ra, log, log_bur, log_air, filepath):
    if not REPORTLAB_OK:
        print("\n  [!] reportlab not installed — skipping PDF.")
        print("      Run:  pip install reportlab")
        return None

    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        leftMargin=14*mm, rightMargin=14*mm,
        topMargin=14*mm,  bottomMargin=14*mm
    )
    W = A4[0] - 28*mm

    # ── InnoVites brand colours ───────────────────────────────────────────
    C_HDR     = colors.HexColor('#8B2FC9')   # purple   — headers
    C_ALT     = colors.HexColor('#F5F0FC')   # lt purple — alt rows
    C_NRM     = colors.white
    C_BRD     = colors.HexColor('#D4B8F0')   # border
    C_GRID    = colors.HexColor('#E8D8F8')   # grid
    C_BAN     = colors.HexColor('#FEF3E2')   # banner bg
    C_OK      = colors.HexColor('#E8391D')   # red — converged
    C_WARN    = colors.HexColor('#F5A623')   # orange — warning
    C_TITLE   = colors.HexColor('#8B2FC9')
    C_SEC     = colors.HexColor('#8B2FC9')
    C_HDR_BG  = colors.HexColor('#F0E8FA')
    C_SYM     = colors.HexColor('#8B2FC9')
    C_NOTE    = colors.HexColor('#666666')
    C_BUR     = colors.HexColor('#1a4a8a')   # dark blue — buried sections
    C_AIR     = colors.HexColor('#1a6b3a')   # dark green — air sections
    C_BUR_BG  = colors.HexColor('#E8F0FA')   # light blue bg
    C_AIR_BG  = colors.HexColor('#E8F5EE')   # light green bg

    def para(txt, fs=8, fn='Helvetica', clr=colors.black, align=TA_LEFT):
        return Paragraph(str(txt), ParagraphStyle('p',
            fontSize=fs, fontName=fn, leading=10,
            textColor=clr, alignment=align))

    story = []

    # ── Page header ───────────────────────────────────────────────────────
    hdr_data = [[
        para('IEC 60287 Ampacity Calculation Report',
             14, 'Helvetica-Bold', C_TITLE, TA_CENTER),
        para(c['cable_desc'],
             8.5, 'Helvetica', colors.HexColor('#555555'), TA_CENTER),
        para(f"Doc: {c['doc_no']}   Project: {c['project']}   "
             f"Engineer: {c['engineer']}   "
             f"Date: {datetime.now().strftime('%d %b %Y')}",
             8, 'Helvetica', colors.HexColor('#555555'), TA_CENTER),
        para('Powered by InnoVites',
             7, 'Helvetica-Oblique', C_TITLE, TA_CENTER),
    ]]
    hdr = Table(hdr_data, colWidths=[W])
    hdr.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), C_HDR_BG),
        ('BOX',           (0,0), (-1,-1), 1.0, C_HDR),
        ('TOPPADDING',    (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING',   (0,0), (-1,-1), 10),
    ]))
    story.append(hdr)

    # colour accent bar
    acc = Table([[' ',' ',' ']], colWidths=[W/3]*3)
    acc.setStyle(TableStyle([
        ('BACKGROUND', (0,0),(0,0), colors.HexColor('#E8391D')),
        ('BACKGROUND', (1,0),(1,0), colors.HexColor('#F5A623')),
        ('BACKGROUND', (2,0),(2,0), colors.HexColor('#8B2FC9')),
        ('TOPPADDING', (0,0),(-1,-1), 2),
        ('BOTTOMPADDING',(0,0),(-1,-1), 2),
    ]))
    story.append(acc)
    story.append(Spacer(1, 3*mm))

    # ── Dual summary banner ───────────────────────────────────────────────
    def _tot(res):
        return res['Wc']*(1+res['lam1']+r['lam2']) + r['Wd']

    ban_data = [
        ['', 'AMPACITY', 'MVA RATING', 'COND TEMP',
         'SHEATH TEMP', 'TOTAL LOSS', 'STATUS'],
        [
            para('BURIED', 8, 'Helvetica-Bold', colors.white, TA_CENTER),
            para(f"{rb['I_rounded']} A", 10, 'Helvetica-Bold',
                 colors.HexColor('#E8391D'), TA_CENTER),
            para(f"{rb['MVA']:.2f} MVA",  8, 'Helvetica-Bold',
                 colors.HexColor('#404040'), TA_CENTER),
            para(f"{rb['theta_c_calc']:.1f} °C", 8, 'Helvetica-Bold',
                 colors.HexColor('#404040'), TA_CENTER),
            para(f"{rb['theta_s']:.1f} °C", 8, 'Helvetica-Bold',
                 colors.HexColor('#404040'), TA_CENTER),
            para(f"{_tot(rb):.3f} W/m", 8, 'Helvetica-Bold',
                 colors.HexColor('#404040'), TA_CENTER),
            para('Converged' if rb['converged'] else 'NOT OK', 8,
                 'Helvetica-Bold',
                 C_OK if rb['converged'] else C_WARN, TA_CENTER),
        ],
        [
            para('FREE AIR', 8, 'Helvetica-Bold', colors.white, TA_CENTER),
            para(f"{ra['I_rounded']} A", 10, 'Helvetica-Bold',
                 colors.HexColor('#E8391D'), TA_CENTER),
            para(f"{ra['MVA']:.2f} MVA",  8, 'Helvetica-Bold',
                 colors.HexColor('#404040'), TA_CENTER),
            para(f"{ra['theta_c_calc']:.1f} °C", 8, 'Helvetica-Bold',
                 colors.HexColor('#404040'), TA_CENTER),
            para(f"{ra['theta_s']:.1f} °C", 8, 'Helvetica-Bold',
                 colors.HexColor('#404040'), TA_CENTER),
            para(f"{_tot(ra):.3f} W/m", 8, 'Helvetica-Bold',
                 colors.HexColor('#404040'), TA_CENTER),
            para('Converged' if ra['converged'] else 'NOT OK', 8,
                 'Helvetica-Bold',
                 C_OK if ra['converged'] else C_WARN, TA_CENTER),
        ],
    ]
    col_w_ban = [20*mm, 28*mm, 26*mm, 26*mm, 26*mm, 26*mm, 28*mm]
    ban = Table(ban_data, colWidths=col_w_ban)
    ban.setStyle(TableStyle([
        # header row
        ('BACKGROUND',    (0,0), (-1,0),  C_HDR),
        ('TEXTCOLOR',     (0,0), (-1,0),  colors.white),
        ('FONTNAME',      (0,0), (-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0,0), (-1,0),  8),
        # buried row
        ('BACKGROUND',    (0,1), (0,1),   C_BUR),
        ('BACKGROUND',    (1,1), (-1,1),  C_BUR_BG),
        # air row
        ('BACKGROUND',    (0,2), (0,2),   C_AIR),
        ('BACKGROUND',    (1,2), (-1,2),  C_AIR_BG),
        ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('BOX',           (0,0), (-1,-1), 1.0, C_HDR),
        ('INNERGRID',     (0,0), (-1,-1), 0.3, C_BRD),
        ('TOPPADDING',    (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(ban)
    story.append(Spacer(1, 4*mm))

    # ── Section table builder ─────────────────────────────────────────────
    col_w = [90*mm, 42*mm, 32*mm, 16*mm]

    def section_style(header_clr=None):
        hc = header_clr or C_HDR
        return ParagraphStyle('H', fontSize=9, fontName='Helvetica-Bold',
                              spaceBefore=7, spaceAfter=2, textColor=hc)

    def make_table(title, rows_data, hdr_clr=None, title_clr=None):
        hc = hdr_clr  or C_HDR
        tc = title_clr or C_SEC
        story.append(Paragraph(title, section_style(tc)))

        tbl_data = [[
            para('Parameter',        8, 'Helvetica-Bold', colors.white),
            para('Formula / Symbol', 8, 'Helvetica-Bold', colors.white),
            para('Value',            8, 'Helvetica-Bold', colors.white, TA_RIGHT),
            para('Unit',             8, 'Helvetica-Bold', colors.white),
        ]]
        cmds = [
            ('BACKGROUND', (0,0), (-1,0),  hc),
            ('BOX',        (0,0), (-1,-1), 0.5, C_BRD),
            ('INNERGRID',  (0,0), (-1,-1), 0.3, C_GRID),
            ('TOPPADDING',    (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('LEFTPADDING',   (0,0), (-1,-1), 5),
            ('RIGHTPADDING',  (0,0), (-1,-1), 5),
            ('ALIGN',      (2,0), (2,-1),  'RIGHT'),
        ]
        for idx, (label, val, unit) in enumerate(rows_data):
            sym = ''
            if label.startswith('(') and ')' in label:
                e   = label.index(')')
                sym = label[1:e]
                label = label[e+1:].strip()
            bg = C_ALT if idx % 2 == 0 else C_NRM
            tbl_data.append([
                para(label, 8),
                para(sym,   8, 'Helvetica-Oblique', C_SYM),
                para(val,   8, 'Courier',  colors.black, TA_RIGHT),
                para(unit,  8, 'Helvetica', colors.HexColor('#666677')),
            ])
            cmds.append(('BACKGROUND', (0,idx+1), (-1,idx+1), bg))

        t = Table(tbl_data, colWidths=col_w)
        t.setStyle(TableStyle(cmds))
        story.append(KeepTogether(t))
        story.append(Spacer(1, 2*mm))

    # ── 1. Design Data ────────────────────────────────────────────────────
    solar_str = (f"H={c['solar_H']:.0f} W/m², σ={c['solar_sigma']:.2f}"
                 if c.get('solar') else 'None')
    make_table('1. Design Data & Input Parameters', [
        ('Conductor material',                c['cond_mat'],                ''),
        ('Conductor size',                    f"{c['cond_size']}",          'mm2'),
        ('Conductor type',                    c['cond_type'],               ''),
        ('Conductor diameter Dc',             f"{c['Dc']:.1f}",             'mm'),
        ('Conductor screen OD Dc_sc',         f"{c['Dc_sc']:.1f}",          'mm'),
        ('Max conductor temp theta_max',      f"{c['theta_max']}",          'degC'),
        ('Insulation material',               c['ins_mat'],                 ''),
        ('Insulation outer diameter Di',      f"{c['Di']:.1f}",             'mm'),
        ('Insulation screen OD Di_sc',        f"{c['Di_sc']:.1f}",          'mm'),
        ('Insulation thickness t_ins',        f"{c['t_ins']:.2f}",          'mm'),
        ('Relative permittivity er',          f"{c['eps_r']:.4f}",          ''),
        ('Loss tangent tan(delta)',            f"{c['tan_d']:.6f}",          ''),
        ('Screen type',                       c['screen_type'],             ''),
        ('Screen mean diameter ds',           f"{c['ds']:.1f}",             'mm'),
        ('Screen area As',                    f"{c['As']:.1f}",             'mm2'),
        ('Armour type',                       c['armour_type'],             ''),
        ('Oversheath material',               c['osh_mat'],                 ''),
        ('Cable outer diameter De',           f"{c['De']:.1f}",             'mm'),
        ('Rated voltage U',                   f"{c['U_rated']:.1f}",        'kV'),
        ('U0 line-to-earth',                  f"{c['U0']:.3f}",             'kV'),
        ('Frequency',                         f"{c['freq']}",               'Hz'),
        ('Bonding',                           c['bonding'],                 ''),
        ('Formation',                         c['formation'],               ''),
        # buried
        ('Depth to cable centre L',           f"{c['depth']}",              'mm'),
        ('Axial spacing s',                   f"{c['spacing_s']:.1f}",      'mm'),
        ('Ambient ground temp theta_a',       f"{c['theta_amb']}",          'degC'),
        ('Soil thermal resistivity rho_soil', f"{c['rho_soil']:.2f}",       'K.m/W'),
        # air
        ('Ambient air temp theta_a_air',      f"{c['theta_amb_air']}",      'degC'),
        ('Air mounting',                      c['air_mounting'],            ''),
        ('Solar radiation',                   solar_str,                    ''),
        ('Wind speed',
         f"{c['wind_speed']:.1f} m/s" if c.get('wind') else 'None', ''),
    ])

    # ── 2. Shared cable sections ──────────────────────────────────────────
    sec_num = 2
    for title, rows in log:
        make_table(f"{sec_num}. {title}", rows)
        sec_num += 1

    # ── Buried sections (blue) ────────────────────────────────────────────
    for title, rows in log_bur:
        make_table(f"{sec_num}. {title}", rows,
                   hdr_clr=C_BUR, title_clr=C_BUR)
        sec_num += 1

    # ── Free air sections (green) ─────────────────────────────────────────
    for title, rows in log_air:
        make_table(f"{sec_num}. {title}", rows,
                   hdr_clr=C_AIR, title_clr=C_AIR)
        sec_num += 1

    # ── Electrical parameters ─────────────────────────────────────────────
    if 'L_uHm' in r:
        make_table(f"{sec_num}. Electrical Parameters", [
            ('Inductance L',          f"{r['L_uHm']:.6f}",   'uH/m'),
            ('Reactance X = omega L', f"{r['X_uOhm']:.4f}",  'uOhm/m'),
            ('Pos-seq resistance R1', f"{r['R1_uOhm']:.4f}", 'uOhm/m'),
            ('Pos-seq impedance Z1',  f"{r['Z1_uOhm']:.4f}", 'uOhm/m'),
            ('Capacitance C',         f"{r['C']*1e9:.6f}",   'nF/m'),
            ('Charging current Ic',   f"{r['Ic_mA_m']:.4f}", 'mA/m'),
        ])
        sec_num += 1

    # ── Footer ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 4*mm))
    foot_bar = Table([[' ',' ',' ']], colWidths=[W/3]*3)
    foot_bar.setStyle(TableStyle([
        ('BACKGROUND', (0,0),(0,0), colors.HexColor('#8B2FC9')),
        ('BACKGROUND', (1,0),(1,0), colors.HexColor('#F5A623')),
        ('BACKGROUND', (2,0),(2,0), colors.HexColor('#E8391D')),
        ('TOPPADDING', (0,0),(-1,-1), 2),
        ('BOTTOMPADDING',(0,0),(-1,-1), 2),
    ]))
    story.append(foot_bar)
    story.append(Spacer(1, 2*mm))

    gp_line = ('GP2: ampacity rounded down. '
               'GP6: eddy losses always calculated. '
               'GP7: dielectric losses always calculated. '
               'GP8: exact T4 formula. '
               'T3: 1.6x factor for touching trefoil (buried only).')
    solar_note = (f'Solar: H={c["solar_H"]:.0f} W/m², '
                  f'σ={c["solar_sigma"]:.2f}.'
                  if c.get('solar') else 'Solar radiation: not included.')

    st_note = ParagraphStyle('N', fontSize=7.5, fontName='Helvetica',
                             leading=10, textColor=C_NOTE)
    for note in [
        'Standards: IEC 60287-1-1:2023 | IEC 60287-2-1:2015 | '
        'CIGRE TB 880 guidance applied.',
        gp_line,
        solar_note,
        f'Report generated by InnoVites IEC 60287 Calculator — '
        f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
    ]:
        story.append(Paragraph(note, st_note))

    doc.build(story)
    return filepath