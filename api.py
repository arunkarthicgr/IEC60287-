"""
IEC 60287 Ampacity Calculator — REST API
=========================================
FastAPI wrapper around the existing calculation engine.

Handles all cable construction cases:
  - Standard (Cu tape / Cu wire screen)
  - With Al laminated foil (HV cables)            → include 'al_foil' block
  - With armour (SWA/STA/AWA)                     → include 'armour'  block
  - With outer semiconducting layer over oversheath
  - Milliken / segmented conductors
  - Solid / single / cross bonding

Install:
    pip install fastapi uvicorn pydantic

Run:
    uvicorn api:app --host 0.0.0.0 --port 8000 --reload

Company JavaScript software connects via:
    POST http://your-server:8000/calculate
    Content-Type: application/json

Schema tolerance:
    Each model uses ConfigDict(extra='ignore'), so unknown fields in the
    request body (e.g. '_comment', client metadata, future additions) are
    silently dropped during validation instead of returning 422. This keeps
    the contract loose enough for the JS team to attach their own metadata
    without breaking the call.
"""

from __future__ import annotations
from typing import Optional, Literal
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ConfigDict

# ─── Import your existing engine (adjust path if needed) ─────────────────────
import sys, os
sys.path.insert(0, os.path.dirname(__file__))   # add project root to path

from core.cable      import dc_resistance, ac_resistance, electrical_params
from core.losses     import dielectric_losses, sheath_setup, armour_loss
from core.thermal    import thermal_resistances
from core.ampacity   import iterate_buried, iterate_air, iterate_duct


# =============================================================================
# Base model — every nested block inherits this so unknown keys are tolerated
# =============================================================================

class TolerantModel(BaseModel):
    """
    Pydantic base that ignores unknown fields.
    Lets the JS team attach metadata like '_comment', '_client_id', etc.
    without the API returning 422 Unprocessable Entity.
    """
    model_config = ConfigDict(extra='ignore')


# =============================================================================
# INPUT SCHEMA — covers ALL cable construction cases
# =============================================================================

class ConductorInput(TolerantModel):
    mat:        Literal["Al", "Cu"]           = Field("Al",  description="Conductor material")
    size_mm2:   int                            = Field(185,   description="Conductor size in mm²")
    type:       Literal[
        "stranded", "stranded_compact", "solid",
        "milliken", "milliken_uni", "milliken_insulated"
    ]                                          = Field("stranded", description="Conductor type (affects ks, kp)")
    Dc_mm:      float                          = Field(15.9,  description="Conductor diameter (mm)")
    Dc_sc_mm:   float                          = Field(17.6,  description="Conductor screen OD (mm)")
    theta_max:  float                          = Field(90.0,  description="Max conductor temperature (°C)")


class InsulationInput(TolerantModel):
    material:   Literal["XLPE", "XLPE_filled", "EPR", "PILC"] = Field("XLPE")
    Di_mm:      float  = Field(35.9,  description="Insulation OD (mm)")
    Di_sc_mm:   float  = Field(37.6,  description="Insulation screen OD (mm)")
    t_ins_mm:   float  = Field(9.19,  description="Insulation thickness (mm)")
    eps_r:      float  = Field(2.5,   description="Relative permittivity")
    tan_d:      float  = Field(0.004, description="Loss tangent")


class ScreenInput(TolerantModel):
    type:         Literal["Cu_tape", "Cu_wire", "Pb", "Al"] = Field("Cu_tape")
    ds_mm:        float  = Field(38.0,  description="Mean screen diameter (mm)")
    ts_mm:        float  = Field(0.10,  description="Screen thickness (mm)")
    As_mm2:       float  = Field(50.0,  description="Screen area mm² (0 = calc from ts)")
    rho_s_user:   float  = Field(0.0,   description="Screen resistivity ohm.m (0 = IEC default)")
    rho_sc:       float  = Field(2.5,   description="Semiconducting screen thermal resistivity K.m/W")
    rho_tape:     float  = Field(6.0,   description="Bedding tape thermal resistivity K.m/W")
    D_tuws_mm:    float  = Field(39.3,  description="OD of tape under wire screen (mm)")

    # Cu wire screen extras (only needed when type = 'Cu_wire')
    ns:           int    = Field(0,     description="Number of screen wires (Cu_wire only)")
    ds_wire_mm:   float  = Field(0.9,   description="Screen wire diameter mm (Cu_wire only)")
    Ls_mm:        float  = Field(240.0, description="Lay length mm (Cu_wire only)")


class AlFoilInput(TolerantModel):
    """
    CASE: Al laminated foil — present on HV cables.
    Include this block ONLY when the cable has an Al foil between
    the wire screen and the oversheath.
    """
    t_fl_mm:    float = Field(0.2,  description="Foil thickness (mm)")
    D_fl_mm:    float = Field(39.5, description="Foil OD (mm)")
    D_owt_mm:   float = Field(38.6, description="OD of tape over wire screen (mm)")
    rho_wb:     float = Field(12.0, description="Water blocking tape thermal resistivity K.m/W")


class ArmourInput(TolerantModel):
    """
    CASE: Armoured cable — include when armour is present.
    """
    type: Literal["SWA", "STA", "AWA"] = Field("SWA")
    da_mm: float = Field(3.0,  description="Armour wire diameter (mm)")
    na:    int   = Field(24,   description="Number of armour wires")
    Da_mm: float = Field(60.0, description="Mean armour diameter (mm)")


class OversheathInput(TolerantModel):
    material:     Literal["PVC", "PE", "HDPE", "LSOH"] = Field("PVC")
    t_osh_mm:     float = Field(3.2,  description="Oversheath thickness (mm)")
    De_mm:        float = Field(44.0, description="Cable outer diameter (mm)")

    # CASE: outer semiconducting layer over oversheath
    has_outer_sc: bool  = Field(False, description="Cable has outer semicon layer")
    De_1_mm:      float = Field(0.0,   description="OD without outer semicon (mm)")
    rho_osh_sc:   float = Field(2.5,   description="Outer semicon thermal resistivity K.m/W")


class SystemInput(TolerantModel):
    U_rated_kV:  float  = Field(33.0,  description="Rated line-to-line voltage (kV)")
    U0_kV:       float  = Field(19.053, description="Line-to-earth voltage (kV)")
    freq_Hz:     Literal[50, 60]       = Field(50)
    bonding:     Literal["solid", "single", "cross"] = Field("solid")
    formation:   Literal["trefoil", "trefoil_spaced", "flat", "flat_spaced"] = Field("trefoil")


class BuriedInput(TolerantModel):
    depth_mm:    int   = Field(1000, description="Depth to cable centre (mm)")
    spacing_mm:  float = Field(44.0, description="Axial centre-to-centre spacing (mm)")
    theta_amb:   float = Field(30.0, description="Ambient ground temp (°C)")
    rho_soil:    float = Field(1.2,  description="Soil thermal resistivity K.m/W")


class DuctInput(TolerantModel):
    material:       Literal["HDPE", "PE", "PVC", "fibre_cement", "concrete"] = Field("HDPE")
    Do_mm:          float = Field(110.0, description="Duct outer diameter (mm)")
    t_duct_mm:      float = Field(5.0,   description="Duct wall thickness (mm)")
    touching:       bool  = Field(True,  description="Are ducts touching?")
    duct_spacing_mm: float = Field(0.0,  description="Centre-to-centre duct spacing if not touching (mm)")


class AirInput(TolerantModel):
    theta_amb_air: float  = Field(40.0, description="Ambient air temperature (°C)")
    mounting:      Literal["free", "wall"] = Field("free")
    solar:         bool   = Field(False)
    solar_H:       float  = Field(1000.0, description="Solar intensity W/m²")
    solar_sigma:   float  = Field(0.4,    description="Surface absorption factor")
    wind:          bool   = Field(False)
    wind_speed_ms: float  = Field(1.0)


class TB880Options(TolerantModel):
    gp2_round_down:   bool = Field(True,  description="Round ampacity DOWN (GP2)")
    gp6_eddy:         bool = Field(True,  description="Always calculate eddy current losses (GP6)")
    gp7_wd:           bool = Field(True,  description="Always calculate dielectric losses (GP7)")
    gp8_exact_t4:     bool = Field(True,  description="Use exact T4 formula (GP8)")
    t3_touching:      bool = Field(True,  description="Apply 1.6x T3 factor for touching trefoil")


class AmpacityRequest(TolerantModel):
    """
    Full API request.
    Fields marked Optional are for specific cable construction cases:
      - al_foil:  cables with Al laminated foil layer (HV cables)
      - armour:   armoured cables (SWA/STA/AWA)
    Unknown top-level fields are ignored (e.g. '_comment', client metadata).
    """
    # Metadata
    project:    str = Field("MY PROJECT")
    doc_no:     str = Field("DOC-001")
    engineer:   str = Field("Engineer")

    # Cable construction (required)
    conductor:   ConductorInput
    insulation:  InsulationInput
    screen:      ScreenInput
    oversheath:  OversheathInput
    system:      SystemInput

    # Optional construction cases
    al_foil:     Optional[AlFoilInput]  = Field(None, description="Include for cables with Al laminated foil")
    armour:      Optional[ArmourInput]  = Field(None, description="Include for armoured cables")

    # Installation conditions
    buried:      BuriedInput
    duct:        DuctInput
    air:         AirInput

    # Calculation options
    tb880:       TB880Options = TB880Options()


# =============================================================================
# RESPONSE SCHEMA
# =============================================================================

class InstallationResult(BaseModel):
    ampacity_A:      float
    ampacity_rounded: int
    MVA:             float
    lam1:            float
    lam1_circ:       float
    lam1_eddy:       float
    lam2:            float
    Wc_W_per_m:      float
    Ws_W_per_m:      float
    Wa_W_per_m:      float
    theta_conductor: float
    theta_sheath:    float
    theta_surface:   float
    T1:              float
    T2:              float
    T3:              float
    T4:              float
    converged:       bool
    iterations:      int


class AmpacityResponse(BaseModel):
    project:    str
    doc_no:     str
    cable_desc: str
    buried:     InstallationResult
    duct:       InstallationResult
    air:        InstallationResult
    # Shared cable parameters
    R0_20:      float
    R_ac:       float
    Wd:         float
    C_nF_per_m: float


# =============================================================================
# INPUT CONVERTER: API schema → engine dict 'c'
# =============================================================================

def build_c(req: AmpacityRequest) -> dict:
    """Convert Pydantic request model to the engine's flat 'c' dict."""
    cond = req.conductor
    ins  = req.insulation
    scr  = req.screen
    osh  = req.oversheath
    sys_ = req.system
    bur  = req.buried
    dct  = req.duct
    air  = req.air
    tb   = req.tb880

    has_foil   = req.al_foil is not None
    has_armour = req.armour  is not None

    c = {
        # Project
        'project':    req.project,
        'doc_no':     req.doc_no,
        'engineer':   req.engineer,
        'cable_desc': f"{cond.size_mm2}mm² {cond.mat} {ins.material} {sys_.U_rated_kV:.0f}kV",

        # Conductor
        'cond_mat':   cond.mat,
        'cond_size':  cond.size_mm2,
        'cond_type':  cond.type,
        'Dc':         cond.Dc_mm,
        'Dc_sc':      cond.Dc_sc_mm,
        'theta_max':  cond.theta_max,

        # Insulation
        'ins_mat':    ins.material,
        'Di':         ins.Di_mm,
        'Di_sc':      ins.Di_sc_mm,
        't_ins':      ins.t_ins_mm,
        'eps_r':      ins.eps_r,
        'tan_d':      ins.tan_d,

        # Screen
        'screen_type': scr.type,
        'ds':          scr.ds_mm,
        'ts':          scr.ts_mm,
        'As':          scr.As_mm2,
        'rho_s_user':  scr.rho_s_user,
        'rho_sc':      scr.rho_sc,
        'rho_tape':    scr.rho_tape,
        'D_tuws':      scr.D_tuws_mm,
        'ns':          scr.ns,
        'ds_wire':     scr.ds_wire_mm,
        'Ls':          scr.Ls_mm,

        # Al foil case
        'has_foil':    has_foil,
        't_fl':        req.al_foil.t_fl_mm   if has_foil else 0.0,
        'D_fl':        req.al_foil.D_fl_mm   if has_foil else 0.0,
        'D_owt':       req.al_foil.D_owt_mm  if has_foil else 0.0,
        'rho_wb':      req.al_foil.rho_wb    if has_foil else 12.0,

        # Armour case
        'armour_type': req.armour.type   if has_armour else 'none',
        'da':          req.armour.da_mm  if has_armour else 0.0,
        'na':          req.armour.na     if has_armour else 0,
        'Da':          req.armour.Da_mm  if has_armour else 0.0,

        # Oversheath
        'osh_mat':       osh.material,
        't_osh':         osh.t_osh_mm,
        'De':            osh.De_mm,
        'has_outer_sc':  osh.has_outer_sc,
        'De_1':          osh.De_1_mm if osh.has_outer_sc else osh.De_mm,
        'rho_osh_sc':    osh.rho_osh_sc,

        # System
        'U_rated':    sys_.U_rated_kV,
        'U0':         sys_.U0_kV,
        'freq':       sys_.freq_Hz,
        'bonding':    sys_.bonding,
        'formation':  sys_.formation,

        # Buried
        'depth':      bur.depth_mm,
        'spacing_s':  bur.spacing_mm,
        'theta_amb':  bur.theta_amb,
        'rho_soil':   bur.rho_soil,

        # Duct
        'duct_mat':      dct.material,
        'duct_Do':       dct.Do_mm,
        'duct_t':        dct.t_duct_mm,
        'duct_Di':       round(dct.Do_mm - 2 * dct.t_duct_mm, 2),
        'duct_touching': dct.touching,
        'duct_spacing':  dct.duct_spacing_mm if not dct.touching else dct.Do_mm,
        'cables_per_duct': 1,

        # Air
        'theta_amb_air': air.theta_amb_air,
        'air_mounting':  air.mounting,
        'solar':         air.solar,
        'solar_H':       air.solar_H,
        'solar_sigma':   air.solar_sigma,
        'wind':          air.wind,
        'wind_speed':    air.wind_speed_ms,

        # TB880
        'tb880_gp2_round_down':  tb.gp2_round_down,
        'tb880_gp6_eddy':        tb.gp6_eddy,
        'tb880_gp7_wd':          tb.gp7_wd,
        'tb880_gp8_exact_t4':    tb.gp8_exact_t4,
        't3_touching_factor':    tb.t3_touching,

        # PDF (not used in API mode)
        'pdf_name': 'api_output.pdf',
    }
    return c


def _to_result(res: dict, lam2: float) -> InstallationResult:
    return InstallationResult(
        ampacity_A=       res['I'],
        ampacity_rounded= res['I_rounded'],
        MVA=              res['MVA'],
        lam1=             res['lam1'],
        lam1_circ=        res['lam1p'],
        lam1_eddy=        res['lam1pp'],
        lam2=             lam2,
        Wc_W_per_m=       res['Wc'],
        Ws_W_per_m=       res['Ws'],
        Wa_W_per_m=       res['Wa'],
        theta_conductor=  res['theta_c_calc'],
        theta_sheath=     res['theta_s'],
        theta_surface=    res['theta_j'],
        T1=               res['T1'],
        T2=               res.get('T2', 0.0),
        T3=               res['T3'],
        T4=               res['T4'],
        converged=        res['converged'],
        iterations=       res['iters'],
    )


# =============================================================================
# APP
# =============================================================================

app = FastAPI(
    title="IEC 60287 Ampacity API",
    description="REST API for MV/HV cable ampacity calculations per IEC 60287 / CIGRE TB 880",
    version="1.0.0",
)


@app.post("/calculate", response_model=AmpacityResponse)
def calculate(req: AmpacityRequest):
    """
    Run ampacity calculation for all three installation types in one call:
    - Direct buried
    - In duct
    - Free air
    """
    try:
        c   = build_c(req)
        r   = {}
        log = []

        # Run engine — same sequence as main.py
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

        lam2 = r.get('lam2', 0.0)

        return AmpacityResponse(
            project=    c['project'],
            doc_no=     c['doc_no'],
            cable_desc= c['cable_desc'],
            buried=     _to_result(rb, lam2),
            duct=       _to_result(rd, lam2),
            air=        _to_result(ra, lam2),
            R0_20=      r['R0_20'],
            R_ac=       r['R_max'],
            Wd=         r['Wd'],
            C_nF_per_m= r['C'] * 1e9,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok", "engine": "IEC 60287 / CIGRE TB 880"}
