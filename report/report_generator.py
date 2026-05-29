"""
report/report_generator.py
IEC 60287 ampacity PDF report generator.
Called by main.py:  generate_pdf(c, r, rb, rd, ra, log, log_bur, log_dct, log_air, filepath)
"""
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

# ── Page ─────────────────────────────────────────────────────────────────────
PAGE_W = 612.0
PAGE_H = 792.0

# ── Outer box ────────────────────────────────────────────────────────────────
BOX_X0    = 34.8
BOX_X1    = 581.5
BOX_Y_TOP = PAGE_H - 21.7     # 770.3
BOX_Y_BOT = PAGE_H - 675.0    # 117.0

# Header vertical divider x (label | value)
HDR_DIV_X = 183.1

# ── Footer ───────────────────────────────────────────────────────────────────
FOOTER_TOP = PAGE_H - 722.4   # 69.6
FOOTER_BOT = PAGE_H - 781.7   # 10.3
FOOTER_MID = PAGE_H - 731.9   # 60.1

# ── Column x positions (measured from reference PDF) ─────────────────────────
COL0_X = 34.8
COL1_X = 154.0   # Unit
COL2_X = 183.1   # Reference
COL3_X = 232.6   # Clause
COL5_X = 305.9   # Formula
PAD    = 1.8

# Result columns — centred
CX_GND  = (434.0 + 483.0) / 2   # 458.5
CX_DUCT = (483.0 + 536.3) / 2   # 509.65
CX_AIR  = (536.3 + 581.5) / 2   # 558.9
CX_SYM  = (272.4 + 303.9) / 2   # 288.15
CX_FRM  = (303.9 + 434.0) / 2   # 368.95

# ── Fonts ─────────────────────────────────────────────────────────────────────
FN = "Helvetica"
FB = "Helvetica-Bold"
FI = "Helvetica-Oblique"
SB = 7.8
SS = 7.2
ST = 10.4

# ── Y helper ─────────────────────────────────────────────────────────────────
def Y(top, size):
    return PAGE_H - top - 0.718 * size

# ── Baselines from reference measurements ────────────────────────────────────
Y_HDR    = [Y(t, SB) for t in (12.1, 22.0, 32.0, 41.9, 51.9)]
Y_ISSUE  = Y(61.8,  SB)
Y_DESC1  = Y(84.4,  SB)
Y_DESC2  = Y(94.6,  SB)
Y_COLHDR = Y(123.5, SS)
Y_TREF   = Y(123.7, SS)

# ── Row geometry ─────────────────────────────────────────────────────────────
SEC_H       = 22.9   # section title row height
ROW_H       = 9.95   # data row height
SEC_BL      = 13.9   # section title baseline offset from row bottom
DAT_BL      = 2.2    # data row baseline offset from row bottom
COL_HDR_SEP = 645.2  # y of separator below col headers = top of first data row

# ── Primitives ────────────────────────────────────────────────────────────────
def hl(c, x0, x1, y, lw=0.4):
    c.setLineWidth(lw); c.line(x0, y, x1, y)

def vl(c, x, y0, y1, lw=0.4):
    c.setLineWidth(lw); c.line(x, y0, x, y1)

def bx(c, x0, y0, x1, y1, lw=0.5):
    c.setLineWidth(lw); c.rect(x0, y0, x1-x0, y1-y0, stroke=1, fill=0)

def tx(c, x, y, s, font=FN, size=SS, align="L"):
    s = str(s)
    if not s.strip(): return
    c.setFont(font, size)
    if   align == "C": c.drawCentredString(x, y, s)
    elif align == "R": c.drawRightString(x, y, s)
    else:              c.drawString(x, y, s)

# ── Formatters ────────────────────────────────────────────────────────────────
def fv(v, d=1):
    if v is None or str(v).strip() in ("", "--"): return ""
    try:
        f = float(v)
        if abs(f) < 0.001 or abs(f) >= 1e6: return "{:.3E}".format(f)
        return "{:.{}f}".format(f, d)
    except: return str(v)

def fv3(v): return fv(v, 3)
def fv2(v): return fv(v, 2)
def fv1(v): return fv(v, 1)
def fv0(v):
    try: return str(int(round(float(v))))
    except: return str(v)

def gs(ci, key, default):
    v = ci.get(key, default)
    return str(v) if v is not None else str(default)

# ── Page components ───────────────────────────────────────────────────────────
def _draw_header(c, meta, page_num, total_pages):
    labels = ["CUSTOMER", "PROJECT", "MANUFACTURER", "DOCUMENT NO.", "DOC TITLE"]
    keys   = ["customer", "project", "manufacturer", "doc_no", "doc_title"]
    for label, key, y in zip(labels, keys, Y_HDR):
        tx(c, BOX_X0 + PAD,    y, label,               FN, SB)
        tx(c, HDR_DIV_X + PAD, y, meta.get(key, ""),   FN, SB)
    y = Y_ISSUE
    tx(c, BOX_X0 + PAD, y, "Issue by: " + meta.get("issued_by", ""), FN, SB)
    tx(c, 211.4, y, "Revision:",                     FN, SB)
    tx(c, 283.6, y, str(meta.get("revision", "1")),  FN, SB)
    tx(c, 328.5, y, "Date:",                         FN, SB)
    tx(c, 382.3, y, meta.get("date", ""),            FN, SB)
    tx(c, 498.1, y, "Page:",                         FN, SB)
    tx(c, 548.1, y, str(page_num) + " of " + str(total_pages), FN, SB)

def _draw_cable_desc(c, desc):
    max_w = BOX_X1 - BOX_X0 - PAD * 2
    words = desc.split()
    line1, split = "", len(words)
    for i, w in enumerate(words):
        test = (line1 + " " + w).strip()
        if stringWidth(test, FI, SB) > max_w:
            split = i; break
        line1 = test
    line2 = " ".join(words[split:])
    tx(c, BOX_X0 + PAD, Y_DESC1, line1, FI, SB)
    if line2:
        tx(c, BOX_X0 + PAD, Y_DESC2, line2, FI, SB)

def _draw_col_headers(c):
    y = Y_COLHDR
    tx(c, 159.1,  y, "Unit",      FN, SS)
    tx(c, 190.1,  y, "Reference", FN, SS)
    tx(c, 236.4,  y, "Clause",    FN, SS)
    tx(c, 274.4,  y, "Symbol",    FN, SS)
    tx(c, CX_FRM, y, "Formula",   FN, SS, "C")
    ty = Y_TREF
    tx(c, 436.0, ty, "TREFOIL GND",  FN, SS)
    tx(c, 484.8, ty, "TREFOIL DUCT", FN, SS)
    tx(c, 538.3, ty, "TREFOIL AIR",  FN, SS)
    hl(c, BOX_X0, BOX_X1, COL_HDR_SEP, lw=0.5)

def _draw_footer(c):
    bx(c, BOX_X0, FOOTER_BOT, BOX_X1, FOOTER_TOP)
    hl(c, BOX_X0, BOX_X1, FOOTER_MID, lw=0.4)
    vl(c, 183.1, FOOTER_BOT, FOOTER_TOP, lw=0.4)
    vl(c, 304.3, FOOTER_MID, FOOTER_TOP, lw=0.4)
    vl(c, 480.4, FOOTER_MID, FOOTER_TOP, lw=0.4)

def _sec(c, title, y_top):
    y_bot  = y_top - SEC_H
    y_base = y_bot + SEC_BL
    tx(c, BOX_X0 + PAD, y_base, title, FB, ST)
    hl(c, BOX_X0, BOX_X1, y_bot, lw=0.5)
    return y_bot

def _blank(c, y_top):
    y_bot = y_top - ROW_H
    hl(c, BOX_X0, BOX_X1, y_bot, lw=0.3)
    return y_bot

def _row(c, y_top, desc="", unit="", ref="", clause="",
         symbol="", formula="", gnd="", duct="", air=""):
    y_bot  = y_top - ROW_H
    y_base = y_bot + DAT_BL
    if desc:    tx(c, BOX_X0 + PAD, y_base, desc,    FN, SB)
    if unit:    tx(c, COL1_X + PAD, y_base, unit,    FN, SS)
    if ref:     tx(c, COL2_X + PAD, y_base, ref,     FN, SS)
    if clause:  tx(c, COL3_X + PAD, y_base, clause,  FN, SS)
    if symbol:  tx(c, CX_SYM,       y_base, symbol,  FN, SS, "C")
    if formula: tx(c, COL5_X,       y_base, formula, FN, SS)
    for cx, val in ((CX_GND, gnd), (CX_DUCT, duct), (CX_AIR, air)):
        if val == "--":  tx(c, cx, y_base, "--", FN, SS, "C")
        elif val:        tx(c, cx, y_base, str(val), FN, SS, "C")
    hl(c, BOX_X0, BOX_X1, y_bot, lw=0.3)
    return y_bot

def _page_frame(c, meta, page_num, total_pages):
    """Draw outer box, header, cable desc, col headers."""
    bx(c, BOX_X0, BOX_Y_BOT, BOX_X1, BOX_Y_TOP)
    _draw_header(c, meta, page_num, total_pages)
    _draw_cable_desc(c, meta.get("cable_desc", ""))
    _draw_col_headers(c)

# ─────────────────────────────────────────────────────────────────────────────
# PAGE 1:  DESIGN DATA  +  PARAMETER SETTING
# ─────────────────────────────────────────────────────────────────────────────
def _page1(c, ci, r, rb, rd, ra, meta, page_num, total_pages):
    _page_frame(c, meta, page_num, total_pages)
    y = COL_HDR_SEP

    bond = ci.get("bonding",     "SOLID BOND")
    mat  = ci.get("cond_mat",    "Aluminium")
    cd   = ci.get("cond_design", "CC")
    ins  = ci.get("ins_mat",     "XLPE")

    # DESIGN DATA
    y = _sec(c, "DESIGN DATA", y)
    y = _row(c, y, "Bonding Type","","Design data","","","",         bond,bond,bond)
    y = _row(c, y, "Cond Mat","","Design data","","","",             mat,mat,mat)
    y = _row(c, y, "Cond size","mm\u00b2","Design data","","","",
             gs(ci,"cond_size",185), gs(ci,"cond_size",185), gs(ci,"cond_size",185))
    y = _row(c, y, "Cond design","","Design data","","",cd,          cd,cd,cd)
    y = _row(c, y, "Cond Dn","mm","Design data","","Dc","",
             fv1(ci.get("Dc",15.9)), fv1(ci.get("Dc",15.9)), fv1(ci.get("Dc",15.9)))
    y = _row(c, y, "Cond Sc Dn","mm","Design data","","Ds","",
             fv1(ci.get("Ds",17.6)), fv1(ci.get("Ds",17.6)), fv1(ci.get("Ds",17.6)))
    y = _row(c, y, "Ins Mat","","Design data","","","",              ins,ins,ins)
    y = _row(c, y, "Ins Dn","mm","Design data","","Di","",
             fv1(ci.get("Di",35.9)), fv1(ci.get("Di",35.9)), fv1(ci.get("Di",35.9)))
    y = _row(c, y, "Ins Sc Dn","mm","Design data","","dx","",
             fv1(ci.get("dx",37.6)), fv1(ci.get("dx",37.6)), fv1(ci.get("dx",37.6)))
    y = _row(c, y, "Ins Tn","mm","Design data","","Ti","",
             fv2(ci.get("Ti",9.19)), fv2(ci.get("Ti",9.19)), fv2(ci.get("Ti",9.19)))
    y = _row(c, y, "Core Dn","mm","Design data","","Do","",          "--","--","--")
    y = _row(c, y, "Lay-up OD","mm","Design data","","Da","",        "--","--","--")
    y = _row(c, y, "Cable Dn","mm","Design data","","De","",
             fv1(ci.get("De",44.0)), fv1(ci.get("De",44.0)), fv1(ci.get("De",44.0)))
    y = _row(c, y, "Core No","nos","Design data","","n","1",         "1","1","1")
    y = _row(c, y, "Wire No","nos","Design data","","nw","",
             gs(ci,"nw",37), gs(ci,"nw",37), gs(ci,"nw",37))
    y = _row(c, y, "Cable weight","kg/km","Design data","","M","",
             gs(ci,"M",6731), gs(ci,"M",6731), gs(ci,"M",6731))
    y = _row(c, y, "Max cond temp","\u00b0C","Design Data","","\u03b8max","",
             gs(ci,"theta_max",90), gs(ci,"theta_max",90), gs(ci,"theta_max",90))
    y = _row(c, y, "Earth fault current","A","Design Data","",
             "Ix/1sec","1",
             gs(ci,"If",1493), gs(ci,"If",1493), gs(ci,"If",1493))
    y = _blank(c, y)
    y = _row(c, y, "Rated voltage","kV","IEC60502-2","Table 1","U","",
             gs(ci,"U",33), gs(ci,"U",33), gs(ci,"U",33))
    y = _row(c, y, "Earth voltage","kV","IEC60502-2","Table 1","U0","",
             fv0(ci.get("U0",19)), fv0(ci.get("U0",19)), fv0(ci.get("U0",19)))
    y = _row(c, y, "Impulse voltage","kV","IEC60502-2","Table 14","Up","",
             gs(ci,"Up",170), gs(ci,"Up",170), gs(ci,"Up",170))
    y = _blank(c, y)
    y = _blank(c, y)

    # PARAMETER SETTING
    y = _sec(c, "PARAMETER SETTING", y)

    rho  = fv1(ci.get("rho_soil", 1.2))
    fm   = gs(ci, "fm",   1)
    freq = gs(ci, "freq", 50)
    ta   = gs(ci, "theta_amb",     30)
    ta_a = gs(ci, "theta_amb_air", 40)
    dep  = gs(ci, "depth", 1200)
    dm   = ci.get("duct_mat", "PE")
    ddo  = gs(ci, "duct_Do", 160)
    dt   = gs(ci, "duct_t",  5)
    tdu  = gs(ci, "theta_duct", 85)

    y = _row(c, y, "Soil TR",  "K.m/W","Input","", "\u03c1",  "1.2",   rho,  rho,  rho)
    y = _row(c, y, "Multicore factor","","Input","","fm",      "1",     fm,   fm,   fm)
    y = _row(c, y, "Frequency","Hz",   "Input","", "f",       "50",    freq, freq, freq)
    y = _row(c, y, "Ambient temp.","°C","Input","","\u03b8a", "30",    ta,   ta,   ta_a)
    y = _row(c, y, "Depth",    "mm",   "Input","", "L",       "1200",  dep,  dep,  dep)
    y = _row(c, y, "Duct Type","",     "Input","", "",        dm,      dm,   dm,   dm)
    y = _row(c, y, "External diameter of duct","mm","Input","","dc","160",
             ddo, ddo, ddo)
    y = _row(c, y, "Thickness of duct","mm","Input","","Td",  "0",
             "0",  dt,   dt)
    y = _row(c, y, "Duct temperature","°C","Input","","\u03b8m","85",
             tdu,  tdu,  tdu)
    y = _row(c, y, "Core space factor","","Input","",  "fs",  "",      "1","1","1")
    y = _row(c, y, "Axial Circ distance H","mm","Input","","Sh","500", "0","0","0")
    y = _row(c, y, "Axial Circ distance V","mm","Input","","Sv","500", "0","0","0")
    y = _row(c, y, "Horizontal circuit","nos","Input","","nh","1",     "1","1","1")
    y = _row(c, y, "Vertical circuit",  "nos","Input","","nv","1",     "1","1","1")

    y = _blank(c, y)

    dtb  = gs(ci, "delta_theta_b", 60)
    dtd  = gs(ci, "delta_theta_d", 60)
    dta  = gs(ci, "delta_theta_a", 50)
    tcb  = gs(ci, "theta_c_b", 80)
    tcd  = gs(ci, "theta_c_d", 78)
    tca  = gs(ci, "theta_c_a", 75)

    y = _row(c, y, "Temp. rise, ambient to max.","°C",
             "IEC60287-1-1","1.4.1.1","\u0394\u03b8","\u03b8max - \u03b8a",
             dtb, dtd, dta)
    y = _row(c, y, "Core temperature, \u03b8c","°C",
             "Itteration","","\u03b8c","",
             tcb, tcd, tca)
    y = _row(c, y, "Axial Core distance","mm","","","S","",
             gs(ci,"S_b",44), gs(ci,"S_d",160), gs(ci,"S_a",44))
    y = _row(c, y, "Cable space","mm","","","S'","",
             "0", gs(ci,"Sp_d",116), "0")
    y = _row(c, y, "Circuit spacing H","mm","","","S'h","",  "0","0","0")
    y = _row(c, y, "Circuit spacing V","mm","","","S'v","",  "0","0","0")
    y = _row(c, y, "Axial distance cond to cab","mm","","","c","","0","0","0")
    y = _row(c, y, "Ins Tn between cond","mm","","","t","",  "0","0","0")
    y = _row(c, y, "Circumscribing radius cond","mm","","","r1","",
             "0.00","0.00","0.00")

# ─────────────────────────────────────────────────────────────────────────────
# PAGE 2:  DC RESISTANCE  +  AC RESISTANCE  +  SHEATH LOSS FACTOR
# ─────────────────────────────────────────────────────────────────────────────
def _page2(c, ci, r, rb, rd, ra, meta, page_num, total_pages):
    _page_frame(c, meta, page_num, total_pages)
    y = COL_HDR_SEP

    # Continuation of PARAMETER SETTING from page 1
    y = _row(c, y, "Coefficient belted cable","",
             "IEC60287-2","2.1.1.2","F2","1+3t/[2\u03c0(dx+t)-t]",
             "0.00","0.00","0.00")
    y = _row(c, y, "Geometric factor","",
             "IEC60287-2","2.1.1.2","G","3F2ln(da/2r1)",
             "0.000","0.000","0.000")
    y = _row(c, y, "Wire factor","",
             "BICC","Table 2.1","fw","",
             "0.0528","0.0528","0.0528")
    y = _row(c, y, "Temp coeff - conductor","",
             "IEC60287-1-1","Table 1","a20","",
             "0.004","0.004","0.004")
    y = _row(c, y, "Ins Relative permitivity","",
             "IEC60287-1-1","Table 3","er","",
             "2.5","2.5","2.5")
    y = _row(c, y, "Loss factor","",
             "IEC60287-1-1","Table 3","tan\u03b4","",
             "0.004","0.004","0.004")
    y = _row(c, y, "Dielectric loss","W/m/ph",
             "EC60287-1-1","2.2","Wd","\u03c9CU0\u00b2tan\u03b4",
             "0.000","0.000","0.000")

    # DC RESISTANCE
    y = _sec(c, "DC RESISTANCE", y)
    y = _row(c, y, "DC resistant at 20degC","ohm/m","IEC60228 Class 2","","R0","",
             fv3(r.get("R0_20")), fv3(r.get("R0_20")), fv3(r.get("R0_20")))
    y = _row(c, y, "DC resistant at ambient","ohm/m","IEC60287-1-1","2.1.1","R0amb","R0(1+a20(Ox-20))",
             fv3(r.get("R0_amb_b", r.get("R0_amb"))),
             fv3(r.get("R0_amb_d", r.get("R0_amb"))),
             fv3(r.get("R0_amb_a", r.get("R0_amb"))))
    y = _row(c, y, "DC resistant at 90degC","ohm/m","IEC60287-1-1","2.1.1","R0max","R0(1+a20(Omax-20))",
             fv3(r.get("R0_max")), fv3(r.get("R0_max")), fv3(r.get("R0_max")))

    # AC RESISTANCE
    y = _sec(c, "AC RESISTANCE", y)
    y = _row(c, y, "Strand constant","","IEC60287-1-1","Table 2","ks","",
             fv1(r.get("ks",1.0)), fv1(r.get("ks",1.0)), fv1(r.get("ks",1.0)))
    y = _row(c, y, "Strand constant","","IEC60287-1-1","Table 2","kp","",
             fv1(r.get("kp",0.8)), fv1(r.get("kp",0.8)), fv1(r.get("kp",0.8)))
    y = _row(c, y, "Spacing correction","","Mc Graw Hill Page 161","","","",
             "1.250","1.250","1.250")
    y = _row(c, y, "Bessel function","","IEC60287-1-1","2.1.2","Xs4","[ks(8pf/R0)10-7]2",
             fv3(r.get("Xs4_b")), fv3(r.get("Xs4_d")), fv3(r.get("Xs4_a")))
    y = _row(c, y, "Skin effect","","IEC60287-1-1","2.1.2","Ys","Xs4/(192+0.8Xs4)",
             fv3(r.get("Ys_b")), fv3(r.get("Ys_d")), fv3(r.get("Ys_a")))
    y = _row(c, y, "Proximity function","","IEC60287-1-1","2.1.4","Xp4","[kp(8pf/R0)10-7]2",
             fv3(r.get("Xp4_b")), fv3(r.get("Xp4_d")), fv3(r.get("Xp4_a")))
    y = _row(c, y, "Proximity function","","IEC60287-1-1","2.1.4","Yp\"","Xp4/(192+0.8Xp4)",
             fv3(r.get("Yp2_b")), fv3(r.get("Yp2_d")), fv3(r.get("Yp2_a")))
    y = _row(c, y, "Proximity effect","","IEC60287-1-1","2.1.4","Yp",
             "Yp\"(Dc/s)2[0.312(Dc/s)2+1.18/(Yp\"+0.27)]",
             fv3(r.get("Yp_b")), fv3(r.get("Yp_d")), fv3(r.get("Yp_a")))
    y = _row(c, y, "AC resistant at 20degC","ohm/m","IEC60287-1-1","2.1","R20","R0(1+Ys+Yp)",
             fv3(r.get("R_20")), fv3(r.get("R_20_duct")), fv3(r.get("R_20")))
    y = _row(c, y, "AC resistant at 20degC - isolated","ohm/m","IEC60287-1-1","2.1","R'20","R0(1+Ys)",
             fv3(r.get("R_20_iso")), fv3(r.get("R_20_iso")), fv3(r.get("R_20_iso")))
    y = _row(c, y, "AC resistant at 90degC","ohm/m","IEC60287-1-1","2.1","R90","R0max(1+Ys+Yp)",
             fv3(r.get("R_max")), fv3(r.get("R_max_duct")), fv3(r.get("R_max")))
    y = _row(c, y, "AC resistant at 90degC - isolated","ohm/m","IEC60287-1-1","2.1","R'90","R0max(1+Ys)",
             fv3(r.get("R_max_iso")), fv3(r.get("R_max_iso")), fv3(r.get("R_max_iso")))

    # SHEATH LOSS FACTOR
    y = _sec(c, "SHEATH LOSS FACTOR", y)
    y = _row(c, y, "Equivalent mean diameter","mm","Design data","","ds","",
             fv1(r.get("ds")), fv1(r.get("ds")), fv1(r.get("ds")))
    y = _row(c, y, "Equivalent resistant at 20degC","ohm/m","IEC60287-1-1","","R20","p/A",
             fv3(r.get("Rs0")), fv3(r.get("Rs0")), fv3(r.get("Rs0")))
    y = _row(c, y, "Equivalent resistant at ambient","ohm/m","IEC60287-1-1","","Rx","R20(1+a20(Ox-20))",
             fv3(r.get("Rs_amb_b")), fv3(r.get("Rs_amb_d")), fv3(r.get("Rs_amb_a")))
    y = _row(c, y, "Equivalent resistant at Oc","ohm/m","IEC60287-1-1","","Rs","R20(1+a20(Oc-20))",
             fv3(r.get("Rs_c_b")), fv3(r.get("Rs_c_d")), fv3(r.get("Rs_c_a")))
    y = _row(c, y, "Sheath Inductance","H/m","IEC60287-1-1","2.3.3","L","2ln(2s/Dm)x10-7",
             fv3(r.get("L_sh_b")), fv3(r.get("L_sh_d")), fv3(r.get("L_sh_a")))
    y = _row(c, y, "Sheath Reactance","ohm/m","IEC60287-1-1","2.3.3","X","2wln(2s/Dm)x10-7",
             fv3(r.get("X_sh_b")), fv3(r.get("X_sh_d")), fv3(r.get("X_sh_a")))
    y = _row(c, y, "Circulating current loss factor","","IEC60287-1-1","2.3.1","lam1'",
             "Rs/R/(1+(Rs/X)2)",
             fv3(rb.get("lam1_c")), fv3(rd.get("lam1_c")), fv3(ra.get("lam1_c")))
    y = _row(c, y, "Eddy current loss factor","","IEC60287-1-1","2.3.6.1","lam1\"","",
             fv3(rb.get("lam1_e",0)), fv3(rd.get("lam1_e",0)), fv3(ra.get("lam1_e",0)))
    y = _row(c, y, "Sheath loss factor","","IEC60287-1-1","2.3","lam1","lam1'+lam1\"",
             fv3(rb.get("lam1")), fv3(rd.get("lam1")), fv3(ra.get("lam1")))

# ─────────────────────────────────────────────────────────────────────────────
# PAGE 3:  THERMAL RESISTANCE  +  CURRENT RATING  +  ELECTRICAL DATA  + more
# ─────────────────────────────────────────────────────────────────────────────
def _page3(c, ci, r, rb, rd, ra, meta, page_num, total_pages):
    _page_frame(c, meta, page_num, total_pages)
    y = COL_HDR_SEP

    # THERMAL RESISTANCE
    y = _sec(c, "THERMAL RESISTANCE", y)
    y = _row(c, y, "Thermal Resistant Insulation","K.m/W","IEC60287-2-1","","T1","(p/2p)LN[1+(2t/dc)]",
             fv3(r.get("T1_buried")), fv3(r.get("T1_buried")), fv3(r.get("T1_buried")))
    y = _row(c, y, "Thermal Resistant filler","K.m/W","IEC60287-2-1","","T2f","",
             fv3(r.get("T2f_b",0)), fv3(r.get("T2f_d",0)), fv3(r.get("T2f_a",0)))
    y = _row(c, y, "Thermal Resistant Bedding","K.m/W","IEC60287-2-1","","T2","",
             fv3(r.get("T2_b",0)), fv3(r.get("T2_d",0)), fv3(r.get("T2_a",0)))
    y = _row(c, y, "Thermal Resistant Outercovering","K.m/W","IEC60287-2-1","","T3","(p/2p)LN[1+(2t/D)]",
             fv3(r.get("T3_buried")), fv3(r.get("T3_duct")), fv3(r.get("T3_air")))
    y = _row(c, y, "Thermal Resistant External","K.m/W","IEC60287-2-1","2.2","T4","",
             fv3(rb.get("T4")), fv3(rd.get("T4")), fv3(ra.get("T4")))

    # CURRENT RATING
    y = _sec(c, "CURRENT RATING", y)
    y = _row(c, y, "Critical Temp Rise of Soil","degC","IEC60287-1-1","","dO","Wk(pc/2p)LN(Gf)",
             fv1(rb.get("dtheta_soil",0)), fv1(rd.get("dtheta_soil",0)), fv1(ra.get("dtheta_soil",0)))
    y = _row(c, y, "Top Equation","","IEC60287-1-1","1.4.1","Etop",
             "dO-Wd(0.5T1+n(T2+T3)+T4)-dO",
             fv1(rb.get("Etop")), fv1(rd.get("Etop")), fv1(ra.get("Etop")))
    y = _row(c, y, "Bottom Equation","","IEC60287-1-1","1.4.1","Ebot",
             "RT1+nR(1+lam1)T2+nR(1+lam1+lam2)(T3+T4)",
             fv3(rb.get("Ebot")), fv3(rd.get("Ebot")), fv3(ra.get("Ebot")))
    y = _row(c, y, "Calculated Amps","A","IEC60287-1-1","1.4.1","I","sqrt(Etop/Ebot)",
             fv0(rb.get("I")), fv0(rd.get("I")), fv0(ra.get("I")))
    y = _row(c, y, "Calculated MVA","MVA","IEC60287-1-1","1.4.1","MVA","sqrt3*U*I",
             fv0(rb.get("MVA")), fv0(rd.get("MVA")), fv0(ra.get("MVA")))

    # ELECTRICAL DATA
    y = _sec(c, "ELECTRICAL DATA", y)
    y = _row(c, y, "Inductance","uH/m","IEC60287-1-1","2.3","L","0.2LN(2s/Dm)",
             fv3(rb.get("L_ind")), fv3(rd.get("L_ind")), fv3(ra.get("L_ind")))
    y = _row(c, y, "Reactance","uohm/m","IEC60287-1-1","2.3","X","w*Lm*10-3",
             fv1(rb.get("X_react")), fv1(rd.get("X_react")), fv1(ra.get("X_react")))
    y = _row(c, y, "Pos Seq Resistance","uohm/m","","","R1","R'1(1+lam1+lam2)",
             fv1(rb.get("R1_pos")), fv1(rd.get("R1_pos")), fv1(ra.get("R1_pos")))
    y = _row(c, y, "Pos Seq Reactance","uohm/m","","","X1","w*L*10-3",
             fv1(rb.get("X1_pos")), fv1(rd.get("X1_pos")), fv1(ra.get("X1_pos")))
    y = _row(c, y, "Pos Seq Impedance","uohm/m","","","Z1","sqrt(R12+Xm2)",
             fv1(rb.get("Z1_pos")), fv1(rd.get("Z1_pos")), fv1(ra.get("Z1_pos")))
    y = _row(c, y, "Zero Seq Resistance","uohm/m","","","R0","Rx+(n*R'x)",
             fv1(rb.get("R0_seq")), fv1(rd.get("R0_seq")), fv1(ra.get("R0_seq")))
    y = _row(c, y, "Capacitance","uF/km","IEC60287-1-1","2.2","C","e/(18LN(Di/ds))",
             fv3(r.get("C")), fv3(r.get("C")), fv3(r.get("C")))
    y = _row(c, y, "Charging current - Max","A/km","BICC Page 170","","Ic max","1.08*w*C*U0",
             fv2(r.get("Ic_max")), fv2(r.get("Ic_max")), fv2(r.get("Ic_max")))

    # THERMAL LOSS
    y = _sec(c, "THERMAL LOSS", y)
    y = _row(c, y, "Thermal Resistant Total","K.m/W","Mc Graw hill","Page 34","SumT","T1+T2+T3+T4",
             fv3(rb.get("T_total")), fv3(rd.get("T_total")), fv3(ra.get("T_total")))
    y = _row(c, y, "Thermal loss","W/m","Mc Graw hill","Page 34","W","(Oc-Oa)/SumT",
             fv2(rb.get("W_loss")), fv2(rd.get("W_loss")), fv2(ra.get("W_loss")))
    y = _row(c, y, "Losses - Conductor","W/m","IEC60287-1-1","2.4.2","Wc","3(I2R)",
             fv2(rb.get("Wc")), fv2(rd.get("Wc")), fv2(ra.get("Wc")))
    y = _row(c, y, "Losses - Dielectric","W/m","IEC60287-1-1","2.2","Wd","3*w*C*U02*tand",
             fv2(rb.get("Wd_loss",0)), fv2(rd.get("Wd_loss",0)), fv2(ra.get("Wd_loss",0)))
    y = _row(c, y, "Losses - Metal sheath","W/m","","IEC60287-1-1","Wm","Wc*lam1",
             fv2(rb.get("Wm")), fv2(rd.get("Wm")), fv2(ra.get("Wm")))

    # INDUCED PARAMETER
    y = _sec(c, "INDUCED PARAMETER", y)
    y = _row(c, y, "Normal - Sheath voltage","V/m","IEEE Std 575","Page 29","Us","I*X",
             fv3(rb.get("Us")), fv3(rd.get("Us")), fv3(ra.get("Us")))
    y = _row(c, y, "Normal - Circulating current","A","IEEE Std 575","Page 29","Is","sqrt(I2(R/Rs)lam1')",
             fv2(rb.get("Is")), fv2(rd.get("Is")), fv2(ra.get("Is")))
    y = _row(c, y, "Transient - Sheath voltage","V/m","IEEE Std 575","Page 29","Ust","Ix*X",
             fv3(rb.get("Ust")), fv3(rd.get("Ust")), fv3(ra.get("Ust")))
    y = _row(c, y, "Transient - Circulating current","A","IEEE Std 575","Page 29","Ist","sqrt(Ix2(R/Rs)lam1')",
             fv0(rb.get("Ist")), fv0(rd.get("Ist")), fv0(ra.get("Ist")))

    # VOLTAGE DROP
    y = _sec(c, "VOLTAGE DROP", y)
    y = _row(c, y, "Rated voltage","kV","IEC60840","Table 4","U","",
             gs(ci,"U",33), gs(ci,"U",33), gs(ci,"U",33))
    y = _row(c, y, "Pos Seq Impedance","uohm/m","","","Z1","sqrt(R12+Xm2)",
             fv1(rb.get("Z1_pos")), fv1(rd.get("Z1_pos")), fv1(ra.get("Z1_pos")))
    y = _row(c, y, "Calculated Amps","A","IEC60287-1-1","1.4.1","I","sqrt(Etop/Ebot)",
             fv0(rb.get("I")), fv0(rd.get("I")), fv0(ra.get("I")))
    y = _row(c, y, "Permissible limit","%","Input","","a","",        "2.5%","2.5%","2.5%")
    y = _row(c, y, "Permissible voltage drop","V","","","E","a*U",
             fv0(rb.get("V_drop_perm",825)), fv0(rd.get("V_drop_perm",825)), fv0(ra.get("V_drop_perm",825)))
    y = _row(c, y, "Voltage drop factor","mV/A/m","","","R","sqrt3*Z",
             fv3(rb.get("VDF")), fv3(rd.get("VDF")), fv3(ra.get("VDF")))
    y = _row(c, y, "Max permissible length","km","","","L","E/(I*R)",
             fv1(rb.get("L_max")), fv1(rd.get("L_max")), fv1(ra.get("L_max")))

    # CRITICAL LENGTH
    y = _sec(c, "CRITICAL LENGTH", y)
    y = _row(c, y, "Critical Length","km","","","Lmax","sqrt3(I/wCU)x103",
             fv0(rb.get("L_crit")), fv0(rd.get("L_crit")), fv0(ra.get("L_crit")))

    # RECEIVED POWER
    y = _sec(c, "RECEIVED POWER", y)
    y = _row(c, y, "Max Feeding Power","MVA","IEC60287-1-1","1.4.1","S","",
             fv1(rb.get("S_feed")), fv1(rd.get("S_feed")), fv1(ra.get("S_feed")))
    y = _row(c, y, "Max Received Power","MW","","","P","sqrt[S2-Q2]",
             fv1(rb.get("P_recv")), fv1(rd.get("P_recv")), fv1(ra.get("P_recv")))
    y = _row(c, y, "Power Losses","%","","","Ploss","P/S",
             str(fv1(rb.get("P_loss_pct")))+"%",
             str(fv1(rd.get("P_loss_pct")))+"%",
             str(fv1(ra.get("P_loss_pct")))+"%")

# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────
def print_results(c_in, r, rb, rd, ra,
                  log=None, log_bur=None, log_dct=None, log_air=None):
    print("=" * 68)
    print("IEC 60287  AMPACITY RESULTS")
    print("=" * 68)
    print("{:<35} {:>10} {:>12} {:>11}".format("Parameter","GND","DUCT","AIR"))
    print("-" * 68)
    print("{:<35} {:>10.0f} {:>12.0f} {:>11.0f}".format(
        "Ampacity [A]", rb.get("I",0), rd.get("I",0), ra.get("I",0)))
    print("{:<35} {:>10.4f} {:>12.4f} {:>11.4f}".format(
        "Sheath loss factor lam1",
        rb.get("lam1",0), rd.get("lam1",0), ra.get("lam1",0)))
    print("{:<35} {:>10.3f} {:>12.3f} {:>11.3f}".format(
        "T4 ext thermal [K.m/W]",
        rb.get("T4",0), rd.get("T4",0), ra.get("T4",0)))
    print("=" * 68)


def generate_pdf(c_in, r, rb, rd, ra,
                 log=None, log_bur=None, log_dct=None, log_air=None,
                 filepath="ampacity_report.pdf"):

    meta = {k: c_in.get(k, "") for k in
            ("customer","project","manufacturer","doc_no",
             "issued_by","revision","date","cable_desc")}
    meta["doc_title"] = c_in.get("doc_title", "Ampacity Calculation")

    total_pages = 3
    cv = rl_canvas.Canvas(filepath, pagesize=(PAGE_W, PAGE_H))

    # Page 1
    _page1(cv, c_in, r, rb, rd, ra, meta, 1, total_pages)
    cv.showPage()

    # Page 2
    _page2(cv, c_in, r, rb, rd, ra, meta, 2, total_pages)
    cv.showPage()

    # Page 3
    _page3(cv, c_in, r, rb, rd, ra, meta, 3, total_pages)

    cv.save()
    return True