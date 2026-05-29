"""
IEC 60287 Ampacity Calculator — REST API
=========================================
Wraps the existing core/ and installation/ modules as a FastAPI endpoint.
Your calculation code is NOT modified — only input_parser.py (CLI) is replaced
by this JSON-based request handler.

Usage:
    pip install fastapi uvicorn
    uvicorn api:app --reload --port 8000

POST /calculate/ampacity
    → returns ampacity results for Buried + Duct + Free Air in one call

GET  /health
    → returns API status

Docs:
    http://localhost:8000/docs   (Swagger UI — auto-generated)
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Literal
import math
import traceback

# ── Import your existing modules (unchanged) ─────────────────────────────────
# These paths assume api.py sits at the project root, same level as core/ etc.
from core.cable     import dc_resistance, ac_resistance, electrical_params
from core.losses    import dielectric_losses, sheath_setup, armour_loss
from core.thermal   import thermal_resistances
from core.ampacity  import iterate_buried, iterate_duct, iterate_air

app = FastAPI(
    title="IEC 60287 Ampacity Calculator API",
    description="""
REST API for IEC 60287 cable ampacity calculations.
Supports Direct Buried, Duct, and Free Air installations in a single request.

### Variable Cable Constructions Supported
- Standard Cu/Al wire or tape screen
- With Al laminated foil (`has_foil: true`)
- With armour — SWA, STA, AWA (`armour_type`)
- With outer semiconducting layer (`has_outer_sc: true`)
- Milliken conductors (`cond_type: milliken_*`)
- Solar radiation for free air (`solar: true`)
    """,
    version="1.0.0",
)

# Allow all origins — tighten this for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# REQUEST SCHEMA
# All fields match keys used in input_parser.py → c dict exactly.
# Optional fields are only needed for specific cable construction cases.
# =============================================================================

class AmpacityRequest(BaseModel):

    # ── Project info ──────────────────────────────────────────────────────
    project:    str = Field(default="API Project",    description="Project name")
    doc_no:     str = Field(default="API-001",         description="Document number")
    engineer:   str = Field(default="Engineer",        description="Engineer name")
    cable_desc: str = Field(default="MV/HV Ampacity",  description="Cable description")

    # ── Conductor ─────────────────────────────────────────────────────────
    cond_mat:   Literal["Al", "Cu"] = Field(default="Al",  description="Conductor material")
    cond_size:  int                 = Field(..., description="Conductor size mm² — e.g. 185, 240, 300, 400, 630")
    cond_type:  Literal[
        "stranded", "stranded_compact", "solid",
        "milliken", "milliken_uni", "milliken_insulated"
    ] = Field(default="stranded", description="Conductor type — controls ks/kp")

    Dc:        float = Field(..., description="Conductor diameter mm")
    Dc_sc:     float = Field(..., description="Conductor screen outer diameter mm")
    theta_max: int   = Field(default=90, description="Max conductor temperature degC")

    # ── Insulation ────────────────────────────────────────────────────────
    ins_mat: Literal["XLPE", "XLPE_filled", "EPR", "PILC"] = Field(
        default="XLPE", description="Insulation material")
    Di:    float = Field(..., description="Insulation outer diameter mm")
    Di_sc: float = Field(..., description="Insulation screen outer diameter mm")
    t_ins: float = Field(..., description="Insulation thickness mm")
    eps_r: float = Field(default=2.5,   description="Relative permittivity")
    tan_d: float = Field(default=0.001, description="Loss tangent tan(delta)")

    # ── Screen / Sheath ───────────────────────────────────────────────────
    screen_type: Literal["Cu_tape", "Cu_wire", "Pb", "Al"] = Field(
        default="Cu_tape", description="Screen/sheath type")
    ds: float = Field(..., description="Mean screen diameter mm")
    ts: float = Field(default=0.10,  description="Screen thickness mm")
    As: float = Field(default=50.0,  description="Screen area mm² (0 = calc from ts)")

    # Cu wire screen extras — only needed when screen_type = Cu_wire
    ns:      Optional[int]   = Field(default=0,     description="Number of screen wires [Cu_wire only]")
    ds_wire: Optional[float] = Field(default=None,  description="Screen wire diameter mm [Cu_wire only]")
    Ls:      Optional[float] = Field(default=240.0, description="Wire lay length mm [Cu_wire only]")

    rho_s_user: float = Field(default=0.0, description="Screen resistivity ohm.m — 0 = IEC default")
    rho_sc:     float = Field(default=2.5, description="Semicon screen thermal resistivity K.m/W")
    rho_tape:   float = Field(default=6.0, description="Bedding tape thermal resistivity K.m/W")
    D_tuws:     Optional[float] = Field(default=None, description="OD over tape under wire screen mm")

    # ── CASE: Al Laminated Foil ───────────────────────────────────────────
    # Set has_foil=true and provide the fields below for HV cables with foil
    has_foil: bool          = Field(default=False, description="Has Al laminated foil?")
    t_fl:     Optional[float] = Field(default=0.0,  description="Foil thickness mm [has_foil only]")
    D_fl:     Optional[float] = Field(default=0.0,  description="Foil outer diameter mm [has_foil only]")
    D_owt:    Optional[float] = Field(default=0.0,  description="OD of tape over wire screen mm [has_foil only]")
    rho_wb:   Optional[float] = Field(default=12.0, description="Water blocking tape K.m/W [has_foil only]")

    # ── CASE: Armour ──────────────────────────────────────────────────────
    # Set armour_type to SWA/STA/AWA and provide da, na, Da
    armour_type: Literal["none", "SWA", "STA", "AWA"] = Field(
        default="none", description="Armour type")
    da: Optional[float] = Field(default=0.0, description="Armour wire diameter mm [armour only]")
    na: Optional[int]   = Field(default=0,   description="Number of armour wires [armour only]")
    Da: Optional[float] = Field(default=0.0, description="Mean armour diameter mm [armour only]")

    # ── Oversheath ────────────────────────────────────────────────────────
    osh_mat: Literal["PVC", "PE", "HDPE", "LSOH"] = Field(
        default="PVC", description="Oversheath material")
    t_osh: float = Field(default=3.2, description="Oversheath thickness mm")
    De:    float = Field(..., description="Cable outer diameter mm")

    # ── CASE: Outer Semiconducting Layer ─────────────────────────────────
    has_outer_sc: bool          = Field(default=False, description="Has outer semiconducting layer?")
    De_1:         Optional[float] = Field(default=None, description="OD without outer semicon mm [has_outer_sc only]")
    t_osh_sc:     Optional[float] = Field(default=0.5,  description="Outer semicon thickness mm [has_outer_sc only]")
    rho_osh_sc:   Optional[float] = Field(default=2.5,  description="Outer semicon K.m/W [has_outer_sc only]")

    # ── System ────────────────────────────────────────────────────────────
    U_rated:   float                              = Field(default=33.0, description="Rated voltage kV line-to-line")
    U0:        Optional[float]                    = Field(default=None, description="Line-to-earth voltage kV — auto-calculated if not given")
    freq:      Literal[50, 60]                    = Field(default=50,   description="Frequency Hz")
    bonding:   Literal["solid", "single", "cross"] = Field(default="solid",   description="Sheath bonding type")
    formation: Literal["trefoil", "trefoil_spaced", "flat", "flat_spaced"] = Field(
        default="trefoil", description="Cable formation")

    # ── Direct Buried ─────────────────────────────────────────────────────
    depth:     int   = Field(default=1000, description="Burial depth to cable centre mm")
    spacing_s: float = Field(...,          description="Centre-to-centre cable spacing mm")
    theta_amb: int   = Field(default=30,   description="Ambient ground temperature degC")
    rho_soil:  float = Field(default=1.2,  description="Soil thermal resistivity K.m/W")

    # ── Duct ──────────────────────────────────────────────────────────────
    duct_mat:       Literal["HDPE", "PE", "PVC", "fibre_cement", "concrete"] = Field(
        default="HDPE", description="Duct material")
    duct_Do:        float         = Field(default=110.0, description="Duct outer diameter mm")
    duct_t:         float         = Field(default=5.0,   description="Duct wall thickness mm")
    duct_touching:  bool          = Field(default=True,  description="Are ducts touching?")
    duct_spacing:   Optional[float] = Field(default=None, description="Duct centre-to-centre spacing mm (if not touching)")

    # ── Free Air ──────────────────────────────────────────────────────────
    theta_amb_air: int                    = Field(default=40,   description="Ambient air temperature degC")
    air_mounting:  Literal["free", "wall"] = Field(default="free", description="Cable mounting in air")

    # CASE: Solar radiation
    solar:       bool  = Field(default=False, description="Include solar radiation?")
    solar_H:     float = Field(default=0.0,   description="Solar intensity W/m² [solar only]")
    solar_sigma: float = Field(default=0.4,   description="Surface absorption coefficient [solar only]")
    wind:        bool  = Field(default=False, description="Include forced convection?")
    wind_speed:  float = Field(default=0.0,   description="Wind speed m/s [wind only]")

    # ── TB880 Options ─────────────────────────────────────────────────────
    tb880_gp2_round_down: bool = Field(default=True, description="GP2: round ampacity DOWN?")
    tb880_gp6_eddy:       bool = Field(default=True, description="GP6: always calculate eddy losses?")
    tb880_gp7_wd:         bool = Field(default=True, description="GP7: always calculate dielectric losses?")
    tb880_gp8_exact_t4:   bool = Field(default=True, description="GP8: use exact T4 formula?")
    t3_touching_factor:   bool = Field(default=True, description="Apply 1.6x T3 for touching trefoil buried?")

    # ── Output ────────────────────────────────────────────────────────────
    generate_pdf: bool = Field(default=False, description="Generate PDF report?")
    pdf_name:     str  = Field(default="",    description="PDF filename (auto if empty)")


# =============================================================================
# RESPONSE SCHEMA
# =============================================================================

class InstallationResult(BaseModel):
    ampacity_exact:   float
    ampacity_rounded: int
    mva:              float
    lambda1:          float
    lambda1_circ:     float
    lambda1_eddy:     float
    lambda2:          float
    T1:               float
    T2:               float
    T3:               float
    T4:               float
    theta_conductor:  float
    theta_sheath:     float
    theta_surface:    float
    Wc_W_per_m:       float
    Ws_W_per_m:       float
    converged:        bool
    iterations:       int


class SharedResults(BaseModel):
    R0_20_ohm_per_m:      float
    R0_max_ohm_per_m:     float
    Rac_buried_ohm_per_m: float
    Rac_duct_ohm_per_m:   float
    lam2_armour:          float
    Wd_W_per_m:           float
    capacitance_nF_per_m: float
    T1_K_m_per_W:         float


class AmpacityResponse(BaseModel):
    status:   str
    buried:   InstallationResult
    duct:     InstallationResult
    air:      InstallationResult
    shared:   SharedResults
    pdf_path: Optional[str] = None


# =============================================================================
# HELPERS
# =============================================================================

def build_c_dict(req: AmpacityRequest) -> dict:
    """
    Convert the Pydantic request model → the c dict your existing code expects.
    Mirrors what input_parser.py builds via CLI prompts.
    """
    c = req.dict()

    # Auto-derived fields
    c['U0']      = req.U0 if req.U0 else round(req.U_rated / math.sqrt(3), 3)
    c['duct_Di'] = round(req.duct_Do - 2 * req.duct_t, 2)
    c['D_tuws']  = req.D_tuws if req.D_tuws else round(req.Di_sc + 1.0, 1)

    # Wire screen defaults for non-Cu_wire types
    if req.screen_type != 'Cu_wire':
        c['ns']      = 0
        c['ds_wire'] = req.ts
        c['Ls']      = 0.0
    else:
        c['ds_wire'] = req.ds_wire if req.ds_wire else req.ts

    # Duct spacing
    c['duct_spacing'] = (
        req.duct_spacing
        if (not req.duct_touching and req.duct_spacing)
        else req.duct_Do
    )

    # Armour defaults
    if req.armour_type == 'none':
        c['da'] = 0.0; c['na'] = 0; c['Da'] = 0.0

    # Outer semicon defaults
    if not req.has_outer_sc:
        c['De_1']       = req.De
        c['t_osh_sc']   = 0.0
        c['rho_osh_sc'] = 2.5

    # Al foil defaults
    if not req.has_foil:
        c['t_fl']  = 0.0; c['D_fl']  = 0.0
        c['D_owt'] = 0.0; c['rho_wb'] = 12.0

    # PDF name
    if not c['pdf_name']:
        c['pdf_name'] = (
            f"Ampacity_{req.cond_size}mm2_{req.cond_mat}_{req.U_rated:.0f}kV.pdf"
        )

    return c


def run_calculation(c: dict):
    """Run the full IEC 60287 pipeline — calls your existing modules."""
    r = {}
    log = []; log_bur = []; log_dct = []; log_air = []

    dc_resistance(c, r, log)
    ac_resistance(c, r, log)
    dielectric_losses(c, r, log)
    sheath_setup(c, r, log)
    armour_loss(c, r, log)
    thermal_resistances(c, r, log)
    electrical_params(c, r, log)

    rb = iterate_buried(c, r, log_bur)
    rd = iterate_duct(c, r, log_dct)
    ra = iterate_air(c, r, log_air)

    return r, rb, rd, ra, log, log_bur, log_dct, log_air


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/health")
def health_check():
    return {
        "status":  "ok",
        "api":     "IEC 60287 Ampacity Calculator",
        "version": "1.0.0",
    }


@app.post("/calculate/ampacity", response_model=AmpacityResponse)
def calculate_ampacity(req: AmpacityRequest):
    """
    Calculate cable ampacity per IEC 60287 for Buried + Duct + Free Air.

    **Variable construction cases** — set these flags + extra fields:
    - `has_foil: true` → Al laminated foil (provide t_fl, D_fl, D_owt, rho_wb)
    - `armour_type: "SWA"` → armoured (provide da, na, Da)
    - `has_outer_sc: true` → outer semicon (provide De_1, t_osh_sc, rho_osh_sc)
    - `cond_type: "milliken"` → Milliken HV conductor
    - `solar: true` → solar radiation for free air (provide solar_H, solar_sigma)
    """
    try:
        c = build_c_dict(req)
        r, rb, rd, ra, log, log_b, log_d, log_a = run_calculation(c)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error":   str(e),
                "trace":   traceback.format_exc(),
                "message": "Calculation failed — check input parameters.",
            },
        )

    # Optional PDF
    pdf_path = None
    if req.generate_pdf:
        try:
            from utils.report_generator import generate_pdf
            pdf_path = generate_pdf(c, r, rb, rd, ra, log, log_b, log_d, log_a,
                                    c['pdf_name'])
        except Exception as e:
            pdf_path = f"PDF generation failed: {e}"

    lam2 = r.get('lam2', 0.0)

    def make_result(rx: dict) -> InstallationResult:
        return InstallationResult(
            ampacity_exact   = rx['I'],
            ampacity_rounded = rx['I_rounded'],
            mva              = rx['MVA'],
            lambda1          = rx['lam1'],
            lambda1_circ     = rx['lam1p'],
            lambda1_eddy     = rx['lam1pp'],
            lambda2          = lam2,
            T1               = rx['T1'],
            T2               = rx.get('T2', 0.0),
            T3               = rx['T3'],
            T4               = rx['T4'],
            theta_conductor  = rx['theta_c_calc'],
            theta_sheath     = rx['theta_s'],
            theta_surface    = rx['theta_j'],
            Wc_W_per_m       = rx['Wc'],
            Ws_W_per_m       = rx['Ws'],
            converged        = rx['converged'],
            iterations       = rx['iters'],
        )

    return AmpacityResponse(
        status  = "success",
        buried  = make_result(rb),
        duct    = make_result(rd),
        air     = make_result(ra),
        shared  = SharedResults(
            R0_20_ohm_per_m       = r['R0_20'],
            R0_max_ohm_per_m      = r['R0_max'],
            Rac_buried_ohm_per_m  = r['R_max'],
            Rac_duct_ohm_per_m    = r['R_max_duct'],
            lam2_armour           = lam2,
            Wd_W_per_m            = r['Wd'],
            capacitance_nF_per_m  = r['C'] * 1e9,
            T1_K_m_per_W          = r['T1_buried'],
        ),
        pdf_path = pdf_path,
    )