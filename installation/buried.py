"""Direct buried installation — IEC 60287-2-1 Cl.4.2.4

T4 external thermal resistance for buried cables.

Touching trefoil / flat:
  GP8=n (approx): T4 = (1.5/pi)*rho*(ln(2u) - 0.630)
  GP8=y (exact):  T4 = (1.5/pi)*rho*(ln(u+sqrt(u^2-1)) - 0.630)
  where u = 2L/De

TB880 CS0-1 verification:
  L=1000mm, De=75.5mm, rho=1.0, trefoil touching
  u  = 26.490066
  GP8=n: T4 = 1.5946928925  (TB880 IEC approx value)
  GP8=y: T4 = 1.5945226972  (TB880 GP8 exact value)
"""

import math


def touching_factor(formation, spacing_s, De, t3_touching_factor):
    """
    Return T3 touching factor for buried installation.
    1.6 for touching trefoil/flat, 1.0 otherwise.
    IEC 60287-2-1 Cl.4.2.4.3.2
    """
    if not t3_touching_factor:
        return 1.0

    is_touching = (
        (formation in ('trefoil', 'flat')) and
        (abs(spacing_s - De) < 0.5)   # spacing ≈ De means touching
    )
    return 1.6 if is_touching else 1.0


def calc_T4(depth_mm, De_mm, rho_soil, formation, spacing_s, gp8_exact):
    """
    External thermal resistance for directly buried cables.
    IEC 60287-2-1 Cl.4.2.4

    For touching trefoil (metallic sheath, equally loaded):
        u  = 2L/De
        GP8=n: T4 = (1.5/pi)*rho*(ln(2u) - 0.630)
        GP8=y: T4 = (1.5/pi)*rho*(ln(u + sqrt(u^2-1)) - 0.630)

    For single cable or spaced formation:
        GP8=n: T4 = (rho/pi)*(ln(2u) - 0.630)
        GP8=y: T4 = (rho/pi)*(ln(u + sqrt(u^2-1)) - 0.630)

    Returns (T4, u).
    """
    L  = depth_mm * 1e-3    # m
    De = De_mm    * 1e-3    # m
    u  = 2.0 * L / De

    touching = (
        formation in ('trefoil', 'flat') and
        abs(spacing_s - De_mm) < 0.5
    )

    if touching:
        # Touching trefoil or flat — 1.5/pi factor (Goldenberg)
        if gp8_exact:
            T4 = (1.5 / math.pi) * rho_soil * (
                math.log(u + math.sqrt(u**2 - 1.0)) - 0.630
            )
        else:
            T4 = (1.5 / math.pi) * rho_soil * (
                math.log(2.0 * u) - 0.630
            )
    else:
        # Single cable or spaced — 1/pi factor
        if gp8_exact:
            T4 = (rho_soil / math.pi) * (
                math.log(u + math.sqrt(u**2 - 1.0)) - 0.630
            )
        else:
            T4 = (rho_soil / math.pi) * (
                math.log(2.0 * u) - 0.630
            )

    return T4, u