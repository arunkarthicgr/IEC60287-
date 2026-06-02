"""
test_api_vs_cli.py
==================
Verifies the REST API returns identical results to the CLI engine.

Usage:
    # 1. In one terminal, start the API server:
    uvicorn api:app --host 127.0.0.1 --port 8000

    # 2. In another terminal, run this script:
    python test_api_vs_cli.py

What it does:
    1. Calls the engine DIRECTLY (same way main.py does) → "CLI baseline"
    2. POSTs the same inputs to the API → "API result"
    3. Compares every numeric output side by side
    4. Reports PASS/FAIL for each installation type

Expected outcome:
    - Solid bonding case: identical to ~1e-9 precision (bit-identical)
    - All special cases (foil, armour, single/cross bonding): API runs without errors
"""

import json
import sys
import os
import math
import requests

# Add project root so we can import engine modules directly
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# ─── Import the engine the same way main.py does ─────────────────────────────
from core.cable     import dc_resistance, ac_resistance, electrical_params
from core.losses    import dielectric_losses, sheath_setup, armour_loss
from core.thermal   import thermal_resistances
from core.ampacity  import iterate_buried, iterate_duct, iterate_air


API_URL = "http://127.0.0.1:8000/calculate"

# Tolerance for floating-point comparison (engine and API run same code)
TOL_ABS = 1e-9
TOL_REL = 1e-6


# =============================================================================
# 1. Direct engine call — produces the "ground truth" CLI baseline
# =============================================================================

def run_engine_direct(c: dict) -> dict:
    """Run the engine exactly like main.py does. Returns dict of results."""
    r = {}
    log = []
    dc_resistance(c, r, log)
    ac_resistance(c, r, log)
    dielectric_losses(c, r, log)
    sheath_setup(c, r, log)
    armour_loss(c, r, log)
    thermal_resistances(c, r, log)

    rb = iterate_buried(c, r, [])
    rd = iterate_duct(c, r, [])
    ra = iterate_air(c, r, [])

    r['lam1'] = rb['lam1']
    electrical_params(c, r, log)

    return {'r': r, 'buried': rb, 'duct': rd, 'air': ra}


# =============================================================================
# 2. Build the same 'c' dict from a JSON payload
#    (This mirrors build_c() inside api.py)
# =============================================================================

def build_c_from_json(payload: dict) -> dict:
    """Replicates api.build_c() so we can call the engine directly with same inputs."""
    cond = payload['conductor']
    ins  = payload['insulation']
    scr  = payload['screen']
    osh  = payload['oversheath']
    sys_ = payload['system']
    bur  = payload['buried']
    dct  = payload['duct']
    air  = payload['air']
    tb   = payload['tb880']

    has_foil   = 'al_foil' in payload and payload['al_foil'] is not None
    has_armour = 'armour'  in payload and payload['armour']  is not None

    c = {
        'project':    payload.get('project', 'TEST'),
        'doc_no':     payload.get('doc_no', 'TEST-001'),
        'engineer':   payload.get('engineer', 'tester'),
        'cable_desc': f"{cond['size_mm2']}mm² {cond['mat']} {ins['material']} {sys_['U_rated_kV']:.0f}kV",

        # Conductor
        'cond_mat':   cond['mat'],
        'cond_size':  cond['size_mm2'],
        'cond_type':  cond['type'],
        'Dc':         cond['Dc_mm'],
        'Dc_sc':      cond['Dc_sc_mm'],
        'theta_max':  cond['theta_max'],

        # Insulation
        'ins_mat':    ins['material'],
        'Di':         ins['Di_mm'],
        'Di_sc':      ins['Di_sc_mm'],
        't_ins':      ins['t_ins_mm'],
        'eps_r':      ins['eps_r'],
        'tan_d':      ins['tan_d'],

        # Screen
        'screen_type': scr['type'],
        'ds':          scr['ds_mm'],
        'ts':          scr['ts_mm'],
        'As':          scr['As_mm2'],
        'rho_s_user':  scr['rho_s_user'],
        'rho_sc':      scr['rho_sc'],
        'rho_tape':    scr['rho_tape'],
        'D_tuws':      scr['D_tuws_mm'],
        'ns':          scr['ns'],
        'ds_wire':     scr['ds_wire_mm'],
        'Ls':          scr['Ls_mm'],

        # Al foil case
        'has_foil':    has_foil,
        't_fl':        payload['al_foil']['t_fl_mm']   if has_foil else 0.0,
        'D_fl':        payload['al_foil']['D_fl_mm']   if has_foil else 0.0,
        'D_owt':       payload['al_foil']['D_owt_mm']  if has_foil else 0.0,
        'rho_wb':      payload['al_foil']['rho_wb']    if has_foil else 12.0,

        # Armour case
        'armour_type': payload['armour']['type']   if has_armour else 'none',
        'da':          payload['armour']['da_mm']  if has_armour else 0.0,
        'na':          payload['armour']['na']     if has_armour else 0,
        'Da':          payload['armour']['Da_mm']  if has_armour else 0.0,

        # Oversheath
        'osh_mat':       osh['material'],
        't_osh':         osh['t_osh_mm'],
        'De':            osh['De_mm'],
        'has_outer_sc':  osh['has_outer_sc'],
        'De_1':          osh['De_1_mm'] if osh['has_outer_sc'] else osh['De_mm'],
        'rho_osh_sc':    osh['rho_osh_sc'],

        # System
        'U_rated':    sys_['U_rated_kV'],
        'U0':         sys_['U0_kV'],
        'freq':       sys_['freq_Hz'],
        'bonding':    sys_['bonding'],
        'formation':  sys_['formation'],

        # Buried
        'depth':      bur['depth_mm'],
        'spacing_s':  bur['spacing_mm'],
        'theta_amb':  bur['theta_amb'],
        'rho_soil':   bur['rho_soil'],

        # Duct
        'duct_mat':      dct['material'],
        'duct_Do':       dct['Do_mm'],
        'duct_t':        dct['t_duct_mm'],
        'duct_Di':       round(dct['Do_mm'] - 2 * dct['t_duct_mm'], 2),
        'duct_touching': dct['touching'],
        'duct_spacing':  dct['duct_spacing_mm'] if not dct['touching'] else dct['Do_mm'],
        'cables_per_duct': 1,

        # Air
        'theta_amb_air': air['theta_amb_air'],
        'air_mounting':  air['mounting'],
        'solar':         air['solar'],
        'solar_H':       air['solar_H'],
        'solar_sigma':   air['solar_sigma'],
        'wind':          air['wind'],
        'wind_speed':    air['wind_speed_ms'],

        # TB880
        'tb880_gp2_round_down':  tb['gp2_round_down'],
        'tb880_gp6_eddy':        tb['gp6_eddy'],
        'tb880_gp7_wd':          tb['gp7_wd'],
        'tb880_gp8_exact_t4':    tb['gp8_exact_t4'],
        't3_touching_factor':    tb['t3_touching'],

        'pdf_name': 'test.pdf',
    }
    return c


# =============================================================================
# 3. Comparison helper
# =============================================================================

def close(a: float, b: float) -> bool:
    """Compare floats with both absolute and relative tolerance."""
    if a is None or b is None:
        return a == b
    if math.isnan(a) and math.isnan(b):
        return True
    if abs(a - b) <= TOL_ABS:
        return True
    if abs(a) > 0 and abs(a - b) / abs(a) <= TOL_REL:
        return True
    return False


def compare_installation(label: str, cli_res: dict, api_res: dict) -> bool:
    """Compare one installation (buried/duct/air) field by field."""
    # Map CLI engine keys to API response keys
    field_map = [
        ('I',            'ampacity_A'),
        ('I_rounded',    'ampacity_rounded'),
        ('MVA',          'MVA'),
        ('lam1',         'lam1'),
        ('lam1p',        'lam1_circ'),
        ('lam1pp',       'lam1_eddy'),
        ('Wc',           'Wc_W_per_m'),
        ('Ws',           'Ws_W_per_m'),
        ('Wa',           'Wa_W_per_m'),
        ('theta_c_calc', 'theta_conductor'),
        ('theta_s',      'theta_sheath'),
        ('theta_j',      'theta_surface'),
        ('T1',           'T1'),
        ('T3',           'T3'),
        ('T4',           'T4'),
    ]

    all_pass = True
    print(f"\n  ── {label} ────────────────────────────────────────────")
    print(f"  {'Field':<22}{'CLI':>16}{'API':>16}{'Status':>10}")
    print(f"  {'-'*22}{'-'*16}{'-'*16}{'-'*10}")

    for cli_key, api_key in field_map:
        cli_val = cli_res.get(cli_key)
        api_val = api_res.get(api_key)
        ok = close(cli_val, api_val)
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        cli_str = f"{cli_val:.6g}" if isinstance(cli_val, (int, float)) else str(cli_val)
        api_str = f"{api_val:.6g}" if isinstance(api_val, (int, float)) else str(api_val)
        print(f"  {api_key:<22}{cli_str:>16}{api_str:>16}{status:>10}")

    return all_pass


# =============================================================================
# 4. Run one test
# =============================================================================

def run_test(name: str, payload: dict) -> bool:
    print("=" * 70)
    print(f"  TEST CASE: {name}")
    print("=" * 70)

    # CLI baseline (direct engine call)
    try:
        c = build_c_from_json(payload)
        cli = run_engine_direct(c)
    except Exception as e:
        print(f"  ✗ CLI engine call failed: {e}")
        return False

    # API call
    try:
        response = requests.post(API_URL, json=payload, timeout=15)
        if response.status_code != 200:
            print(f"  ✗ API returned HTTP {response.status_code}")
            print(f"    Response: {response.text}")
            return False
        api = response.json()
    except requests.exceptions.ConnectionError:
        print(f"  ✗ Could not reach API at {API_URL}")
        print(f"    Did you start the server? Run: uvicorn api:app --port 8000")
        return False
    except Exception as e:
        print(f"  ✗ API call failed: {e}")
        return False

    # Compare each installation
    pass_b = compare_installation("BURIED", cli['buried'], api['buried'])
    pass_d = compare_installation("DUCT",   cli['duct'],   api['duct'])
    pass_a = compare_installation("AIR",    cli['air'],    api['air'])

    overall = pass_b and pass_d and pass_a
    print(f"\n  RESULT: {'PASS ✓' if overall else 'FAIL ✗'}")
    print()
    return overall


# =============================================================================
# 5. Define test cases
# =============================================================================

# Baseline: 185mm² Al 33kV trefoil — matches Project GUNNERZ sheet
BASELINE = {
    "project": "TEST GUNNERZ",
    "doc_no": "TEST-001",
    "engineer": "tester",
    "conductor":  {"mat":"Al","size_mm2":185,"type":"stranded_compact","Dc_mm":15.9,"Dc_sc_mm":17.6,"theta_max":90},
    "insulation": {"material":"XLPE","Di_mm":35.9,"Di_sc_mm":37.6,"t_ins_mm":9.19,"eps_r":2.5,"tan_d":0.004},
    "screen":     {"type":"Cu_tape","ds_mm":38.0,"ts_mm":0.10,"As_mm2":50.0,"rho_s_user":0.0,
                   "rho_sc":2.5,"rho_tape":6.0,"D_tuws_mm":38.6,"ns":0,"ds_wire_mm":0.0,"Ls_mm":0.0},
    "oversheath": {"material":"PVC","t_osh_mm":3.2,"De_mm":44.0,"has_outer_sc":False,"De_1_mm":0.0,"rho_osh_sc":2.5},
    "system":     {"U_rated_kV":33.0,"U0_kV":19.053,"freq_Hz":50,"bonding":"solid","formation":"trefoil"},
    "buried":     {"depth_mm":1200,"spacing_mm":44.0,"theta_amb":30.0,"rho_soil":1.2},
    "duct":       {"material":"PE","Do_mm":160.0,"t_duct_mm":5.0,"touching":True,"duct_spacing_mm":0.0},
    "air":        {"theta_amb_air":40.0,"mounting":"free","solar":False,"solar_H":1000.0,"solar_sigma":0.4,
                   "wind":False,"wind_speed_ms":0.0},
    "tb880":      {"gp2_round_down":True,"gp6_eddy":True,"gp7_wd":True,"gp8_exact_t4":True,"t3_touching":True},
}


def make_test(name, modifications):
    """Create a test case by modifying the baseline."""
    import copy
    p = copy.deepcopy(BASELINE)
    for path, value in modifications.items():
        keys = path.split('.')
        target = p
        for k in keys[:-1]:
            target = target[k]
        target[keys[-1]] = value
    return name, p


TEST_CASES = [
    # Case 1: Solid bonding baseline — MUST be bit-identical
    ("Case 1: Standard 185mm² Al 33kV (solid bonding)", BASELINE),

    # Case 2: Single-point bonding (the fix we made — lam1' should be 0)
    make_test("Case 2: Same cable but single-point bonded",
              {"system.bonding": "single"}),

    # Case 3: Cross bonding (same fix — lam1' should be 0)
    make_test("Case 3: Same cable but cross bonded",
              {"system.bonding": "cross"}),

    # Case 4: With Al foil (HV case)
    ("Case 4: Same cable WITH Al foil added", {
        **BASELINE,
        "al_foil": {"t_fl_mm": 0.2, "D_fl_mm": 39.5, "D_owt_mm": 38.6, "rho_wb": 12.0}
    }),

    # Case 5: With armour
    ("Case 5: Same cable WITH SWA armour added", {
        **BASELINE,
        "armour": {"type": "SWA", "da_mm": 3.0, "na": 24, "Da_mm": 50.0}
    }),

    # Case 6: Spaced trefoil (different formation)
    make_test("Case 6: Trefoil_spaced formation",
              {"system.formation": "trefoil_spaced",
               "buried.spacing_mm": 88.0}),
]


# =============================================================================
# 6. Run all tests
# =============================================================================

if __name__ == "__main__":
    print("\n" + "█" * 70)
    print("  IEC 60287 — API vs CLI verification suite")
    print("█" * 70 + "\n")

    # Sanity check API is running
    try:
        h = requests.get("http://127.0.0.1:8000/health", timeout=3)
        print(f"  API health: {h.json()}\n")
    except Exception:
        print("  ✗ API is not running.")
        print("    Start it first: uvicorn api:app --host 127.0.0.1 --port 8000")
        sys.exit(1)

    results = []
    for name, payload in TEST_CASES:
        ok = run_test(name, payload)
        results.append((name, ok))

    print("\n" + "█" * 70)
    print("  SUMMARY")
    print("█" * 70)
    for name, ok in results:
        symbol = "✓" if ok else "✗"
        print(f"  {symbol} {name}")

    n_pass = sum(1 for _, ok in results if ok)
    print(f"\n  {n_pass} / {len(results)} test cases passed")

    sys.exit(0 if n_pass == len(results) else 1)
