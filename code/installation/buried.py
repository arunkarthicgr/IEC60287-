"""Direct buried installation — IEC 60287-2-1 thermal resistance T4."""

import math


def calc_T4(depth, De, rho_soil, formation, spacing_s, exact=True):
    """
    External thermal resistance T4 for direct buried cable.

    For TOUCHING TREFOIL — uses grouped trefoil formula
    IEC 60287-2-1 section 4.2.4.3.3:
        T4 = (1.5/pi) x rho_soil x [ln(2u) - 0.630]

    For all other formations — uses single cable formula IEC 60287-2-1 Eq.9:
        exact=True  -> (rho/2pi) x ln(u + sqrt(u^2-1))   [TB 880 GP8]
        exact=False -> (rho/2pi) x ln(2u)                 [simplified]

    depth      : depth to cable centre (mm)
    De         : cable outer diameter (mm)
    rho_soil   : soil thermal resistivity (K.m/W)
    formation  : 'trefoil', 'trefoil_spaced', 'flat', 'flat_spaced'
    spacing_s  : axial spacing centre-to-centre (mm)
    exact      : use exact formula for non-touching formations
    """
    u = 2.0 * depth / De

    # Check if touching trefoil — cables touching means spacing = De
    touching_trefoil = (
        formation == 'trefoil' and spacing_s <= De + 1.0
    )

    if touching_trefoil:
        # IEC 60287-2-1 section 4.2.4.3.3 — grouped touching trefoil
        T4 = (1.5 / math.pi) * rho_soil * (math.log(2 * u) - 0.630)
    elif exact:
        # TB 880 GP8 exact formula — single cable or spaced
        T4 = (rho_soil / (2 * math.pi)) * math.log(u + math.sqrt(u**2 - 1))
    else:
        # IEC simplified
        T4 = (rho_soil / (2 * math.pi)) * math.log(2 * u)

    return T4, u


def touching_factor(formation, spacing_s, De, apply_factor):
    """
    Return 1.6 when cables are in touching trefoil/flat and the TB 880
    T3 correction is enabled, otherwise 1.0.
    """
    touching = formation in ('trefoil', 'flat') and spacing_s <= De + 1.0
    return 1.6 if (apply_factor and touching) else 1.0