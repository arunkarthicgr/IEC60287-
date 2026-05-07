"""Free air installation — IEC 60287-2-1 Cl.2.2.1 / Cl.4.2.1

Verified against TB880 Case Study 0-4:
  630mm² Cu, 132kV, trefoil free, solar H=1000, θa=25°C → 990.94 A  ✓
Verified against Gunnerz TREFOIL AIR:
  185mm² Al, 33kV, trefoil free, no solar, θa=40°C → 385 A  ✓

CORRECT FORMULAS:

1. Heat dissipation coefficient:
       h = Z / (De*)^g + E      [W/(m² K^(5/4))]
       De* in METRES, g from IEC Table 2

2. T4 external thermal resistance:
       T4 = 1 / (π × De* × h × x)
       where x = (θj - θa)^(1/4)  — cable outer surface above ambient

3. Inner iteration for x at each outer step:
       x_new^5 = [Wc(1+λ1+λ2) + Wd + σ De* H] / (π De* h)
       i.e. x_new = { [Wtotal] / (π De* h) }^(1/5)
       where Wtotal is total heat per metre (updated each inner step using T4=1/(pi*De*h*x))

   This is derived from the heat balance:
       π De* h (θj-θa)^(5/4) = Wtotal
       x^5 = Wtotal / (π De* h)

4. Ampacity at each inner step:
       T4     = 1/(π De* h x)
       solar  = σ De* H T4
       Etop   = Δθ - Wd(0.5T1 + n(T3+T4)) - solar
       Ebot   = R T1 + nR(1+λ1+λ2)(T3+T4)
       I      = sqrt(Etop/Ebot)
       Wc     = I² R

TB880 CS0-4 verification:
   h    = 0.96/(0.0755^0.20) + 1.25 = 2.859466134  ✓
   x    = 2.601954174                               ✓
   T4   = 1/(π×0.0755×2.8595×2.601954) = 0.56665  ✓
   I    = 990.9416 A                                ✓
"""

import math


# ── IEC 60287-2-1 Table 2 — Z, E, g constants ────────────────────────────────
ZEG_TABLE = {
    ('single',          'wall'):  (0.21, 0.60, 0.020),
    ('single',          'free'):  (0.21, 0.60, 0.020),
    ('trefoil',         'wall'):  (0.62, 1.25, 0.200),
    ('trefoil',         'free'):  (0.96, 1.25, 0.200),
    ('trefoil_spaced',  'wall'):  (0.62, 1.25, 0.200),
    ('trefoil_spaced',  'free'):  (0.96, 1.25, 0.200),
    ('flat',            'wall'):  (1.42, 1.25, 0.200),
    ('flat',            'free'):  (2.50, 1.25, 0.200),
    ('flat_spaced',     'wall'):  (0.62, 1.25, 0.200),
    ('flat_spaced',     'free'):  (0.96, 1.25, 0.200),
}


def get_ZEg(formation, mounting):
    """Return (Z, E, g) from IEC 60287-2-1 Table 2."""
    return ZEG_TABLE.get((formation, mounting), (0.96, 1.25, 0.200))


def calc_h(Z, E, g, De_m):
    """
    Heat dissipation coefficient  IEC 60287-2-1 Cl.4.2.1.1

        h = Z / (De*)^g + E      [W/(m² K^(5/4))]

    De_m : cable outer diameter in METRES
    g    : exponent from IEC Table 2

    TB880 CS0-4: h = 0.96/(0.0755^0.20) + 1.25 = 2.859466134  ✓
    """
    return Z / (De_m ** g) + E


def solve_x_inner(De_m, h, R_ac, lam1, lam2, T1, T3, Wd,
                  Dtheta, sigma, H_solar, solar, n=1,
                  tol=1e-10, max_iter=100):
    """
    Inner iteration for x = (θj - θa)^(1/4) at a given outer lam1.

    Heat balance:
        π De* h (θj-θa)^(5/4) = Wc(1+λ1+λ2) + Wd + σ De* H
        x^5 = Wtotal / (π De* h)

    At each inner step:
        T4      = 1/(π De* h x)
        solar   = σ De* H T4    (if solar enabled)
        Etop    = Δθ - Wd(0.5T1 + n(T3+T4)) - solar
        Ebot    = R T1 + nR(1+λ1+λ2)(T3+T4)
        I       = sqrt(Etop/Ebot)
        Wc      = I² R
        Wtotal  = Wc(1+λ1+λ2) + Wd + σ De* H
        x_new   = (Wtotal/(π De* h))^(1/5)

    TB880 CS0-4: x converges to 2.601954174, T4=0.5666548  ✓
    Gunnerz air: x converges to ~2.375, T4=1.000  ✓

    Returns (x, T4, I, Wc, solar_heat, iters).
    """
    piDeh = math.pi * De_m * h
    sigma_De_H = sigma * De_m * H_solar if solar else 0.0

    # Starting guess: x = 2.0
    x = 2.0

    for i in range(max_iter):
        T4 = 1.0 / (piDeh * x)
        solar_heat = sigma_De_H * T4

        Etop = Dtheta - Wd * (0.5*T1 + n*(T3+T4)) - solar_heat
        Ebot = R_ac*T1 + n*R_ac*(1+lam1+lam2)*(T3+T4)
        I    = math.sqrt(max(0.0, Etop / Ebot))
        Wc   = I**2 * R_ac

        # Total heat dissipated per metre
        Wtotal = Wc*(1+lam1+lam2) + Wd + sigma_De_H

        # Update x from heat balance: x = (Wtotal/(pi*De*h))^(1/5)
        x_new = (Wtotal / piDeh) ** 0.2

        if abs(x_new - x) < tol:
            x = x_new
            # Recompute T4, I at converged x
            T4 = 1.0 / (piDeh * x)
            solar_heat = sigma_De_H * T4
            Etop = Dtheta - Wd*(0.5*T1 + n*(T3+T4)) - solar_heat
            Ebot = R_ac*T1 + n*R_ac*(1+lam1+lam2)*(T3+T4)
            I    = math.sqrt(max(0.0, Etop / Ebot))
            Wc   = I**2 * R_ac
            break
        x = x_new

    return x, T4, I, Wc, solar_heat, i+1