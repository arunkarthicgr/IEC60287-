"""IEC 60287 material constants — IEC 60287-1-1 Tables 1, 2 & 3."""

# ── Electrical resistivity at 20°C (ohm.m) ───────────────────────────────────
RHO_ELEC = {
    'Cu':    1.7241e-8,
    'Al':    2.8264e-8,
    'Pb':    21.4e-8,
    'steel': 13.8e-8,
}

# ── Temperature coefficient at 20°C (1/K) ────────────────────────────────────
ALPHA20 = {
    'Cu':    3.93e-3,
    'Al':    4.03e-3,
    'Pb':    4.0e-3,
    'steel': 4.5e-3,
}

# ── Thermal resistivity (K.m/W) ───────────────────────────────────────────────
RHO_THERM_INS = {
    'XLPE':        3.5,
    'XLPE_filled': 3.5,
    'EPR':         3.5,
    'PILC':        6.0,
}
RHO_THERM_OSH = {
    'PVC':  5.0,
    'PE':   3.5,
    'HDPE': 3.5,
    'LSOH': 3.5,
}

# ── Dielectric constants (IEC 60287-1-1 Table 3) ─────────────────────────────
EPS_R = {
    'XLPE':        2.5,
    'XLPE_filled': 2.5,
    'EPR':         3.0,
    'PILC':        4.0,
}
TAN_DELTA = {
    'XLPE':        0.001,
    'XLPE_filled': 0.004,
    'EPR':         0.005,
    'PILC':        0.01,
}

# ── IEC 60228 Class 2 DC resistance at 20°C (ohm/km) ─────────────────────────
IEC60228_Al = {
    95:   0.320,  120:  0.253,  150:  0.206,  185:  0.164,  240:  0.125,
    300:  0.100,  400:  0.0778, 500:  0.0605,  630:  0.0469,
    800:  0.0367, 1000: 0.0291,
}
IEC60228_Cu = {
    95:   0.193,  120:  0.153,  150:  0.124,  185:  0.0991, 240:  0.0754,
    300:  0.0601, 400:  0.0470, 500:  0.0366,  630:  0.0283,
    800:  0.0221, 1000: 0.0176, 1200: 0.0151,
}

# ── Skin & proximity constants (IEC 60287-1-1 Table 2) ───────────────────────
# (ks, kp)
#
# stranded          → ks=1.0, kp=0.8   IEC Table 2 strict value
#                     Use for: standard MV/HV cables, Gunnerz, CS4
#
# stranded_compact  → ks=1.0, kp=1.0   TB880 CS0 treatment
#                     TB880 explicitly states ks=kp for compacted round
#                     when no Milliken calculation is needed
#                     Use for: TB880 CS0 (630mm² Cu Al sheath 132kV)
#
# solid             → ks=1.0, kp=1.0   IEC Table 2
#
# milliken          → ks=0.8, kp=0.37  bare bidirectional (most common HV)
# milliken_uni      → ks=1.0, kp=0.37  bare unidirectional
# milliken_insulated→ ks=0.435, kp=0.37 insulated segment wires
#
KS_KP = {
    'stranded':           (1.00, 0.80),
    'stranded_compact':   (1.00, 1.00),
    'solid':              (1.00, 1.00),
    'milliken':           (0.80, 0.37),
    'milliken_uni':       (1.00, 0.37),
    'milliken_insulated': (0.435, 0.37),
}

# ── Typical conductor diameters (mm) — defaults ──────────────────────────────
CONDUCTOR_DIAMETERS = {
    95:   11.3, 120:  12.8, 150:  14.2, 185:  15.9, 240:  18.1,
    300:  20.3, 400:  23.2, 500:  26.0, 630:  29.2, 800:  33.0,
    1000: 36.9, 1200: 43.1,
}

CONDUCTOR_SIZES = [
    95, 120, 150, 185, 240, 300, 400, 500, 630, 800, 1000, 1200
]

# ── Max conductor temperatures by insulation ──────────────────────────────────
TEMP_LIMITS = {
    'XLPE':        90,
    'XLPE_filled': 90,
    'EPR':         90,
    'PILC':        70,
}