"""
cocotb testbench for the rounder.sv module
"""

import random
from enum import Enum

import cocotb
from cocotb.triggers import Timer
from cocotb_coverage.coverage import CoverCross, CoverPoint, coverage_db

# ---------
# CONSTANTS
# ---------
# timer
SETTLE = Timer(1, unit="ns")

# widths
MANT_WIDTH = 24
EXP_WIDTH = 8
FRAC_WIDTH = MANT_WIDTH - 1
EXT_WIDTH = EXP_WIDTH + FRAC_WIDTH
RES_WIDTH = EXP_WIDTH + MANT_WIDTH

# masks
MANT_MASK = (1 << MANT_WIDTH) - 1
EXP_MASK = (1 << EXP_WIDTH) - 1
FRAC_MASK = (1 << FRAC_WIDTH) - 1

# values
EXP_MAX_NORM = EXP_MASK - 1


# RISC-V frm
class RoundMode(Enum):
    RNE = 0
    RTZ = 1
    RDN = 2
    RUP = 3
    RMM = 4


# ---------
# FUNCTIONS
# ---------
# ROUNDING_DECISION
#
# Description - calculates the bit that will decide in which direction to round up the fraction
def rounding_decision(mode, sign, g, r, s, lsb):
    match mode:
        case RoundMode.RNE:
            round_up = g & (r | s | lsb)
        case RoundMode.RTZ:
            round_up = 0
        case RoundMode.RDN:
            round_up = sign & (g | r | s)
        case RoundMode.RUP:
            round_up = ~sign & (g | r | s)
        case RoundMode.RMM:
            round_up = g
        case _:
            round_up = g & (r | s | lsb)

    return round_up


def golden_reference(
    mant_i,
    exp_i,
    sign_i,
    g_i,
    r_i,
    s_i,
    ovf_i,
    uf_i,
    z_i,
    rm_i,
):
    frac = mant_i & FRAC_MASK
    lsb = mant_i & 1

    round_up = rounding_decision(rm_i, sign_i, g_i, r_i, s_i, lsb)

    exp_frac = (exp_i << FRAC_WIDTH) | frac
    exp_frac_r = ((exp_i << FRAC_WIDTH) | frac) + round_up

    exp_r = (exp_frac_r >> FRAC_WIDTH) & EXP_MASK
    exp_f = 0
    frac_r = exp_frac_r & FRAC_WIDTH
    frac_f = 0

    inexact = (g_i | r_i | s_i) & 1
    ovf_raw = ovf_i | (exp_r == EXP_MASK)

    # adjust exponent and fraction after overflow in different rounding modes
    if ovf_raw:
        match rm_i:
            case RoundMode.RTZ:
                exp_f = EXP_MAX_NORM
                frac_f = FRAC_MASK
            case RoundMode.RDN:
                if sign_i:  # if negative, -infinity
                    exp_f = EXP_MASK
                    frac_f = 0
                else:
                    exp_f = EXP_MAX_NORM
                    frac_f = FRAC_MASK
            case RoundMode.RUP:
                if not sign_i:  # if positive, +infinity
                    exp_f = EXP_MASK
                    frac_f = 0
                else:
                    exp_f = EXP_MAX_NORM
                    frac_f = FRAC_MASK
            case _:
                exp_f = exp_r
                frac_f = frac_r

    if z_i:
        exp_f, frac_f, inexact = 0, 0, 0
    else:
        exp_f, frac_f = exp_r, frac_r

    ovf_f = ovf_raw and not z_i
    uf_f = 1 if (exp_f == 0 and not z_i and inexact) else 0
    res_f = (sign_i << RES_WIDTH) | (exp_f << FRAC_WIDTH) | frac_f

    return dict(
        sign=sign_i,
        exp=exp_f,
        frac=frac_f,
        res=res_f,
        ovf=ovf_f,
        uf=uf_f,
        inexact=inexact,
        round_up=round_up,
    )


# coverage functions
def classify(mant, exp, sign, g, r, s, mode, zero, gold):
    if zero:
        return "zero"
    if gold["round_up"] and (mant & FRAC_MASK) == FRAC_MASK:
        if exp == 0:
            return "subnormal_promote"
        return "mantissa_overflow"
    if gold["overflow"]:
        return "overflow"
    if gold["round_up"]:
        return "round_up"
    return "no_round"


@CoverPoint(
    "top.mode",
    xf=lambda t: t["mode"],
    bins=[RoundMode.RNE, RoundMode.RTZ, RoundMode.RDN, RoundMode.RUP, RoundMode.RMM],
)
@CoverPoint(
    "top.scenario",
    xf=lambda t: t["scenario"],
    bins=[
        "no_round",
        "round_up",
        "mant_overflow",
        "subnormal_promote",
        "overflow",
        "zero",
    ],
)
@CoverPoint("top.sign", xf=lambda t: t["sign"], bins=[0, 1])
@CoverPoint(
    "top.grs",
    xf=lambda t: (t["g"], t["r"], t["s"]),
    bins=[(a, b, c) for a in (0, 1) for b in (0, 1) for c in (0, 1)],
)
@CoverPoint("top.inexact", xf=lambda t: t["inexact"], bins=[0, 1])
@CoverPoint("top.overflow", xf=lambda t: t["overflow"], bins=[0, 1])
@CoverPoint("top.underflow", xf=lambda t: t["underflow"], bins=[0, 1])
def sample(t):
    pass


# ------
# DRIVER
# ------


async def drive_and_check(dut, mant, exp, sign, g, r, s, ovf, uf, zero, mode, label=""):

    dut.mant_i.value = mant
    dut.exp_i.value = exp
    dut.sign_i.value = sign
    dut.guard_i.value = g
    dut.round_i.value = r
    dut.sticky_i.value = s
    dut.overflow_i.value = ovf
    dut.underflow_i.value = uf
    dut.zero_i.value = zero
    dut.round_mode_i.value = mode

    await SETTLE

    exp = golden_reference(mant, exp, sign, g, r, s, ovf, uf, zero, mode)
    context = (
        f"mant: 0x{mant:06x} exp: 0x{exp:02x} sign: {sign}"
        f"g: {g} r: {r} s: {s}"
        f"ovf: {ovf} uf: {uf} zero: {zero}"
        f"mode: {mode}"
    )

    got = dict(
        sign=dut.sign_o.value,
        exp=dut.exp_o.value,
        frac=dut.frac_o.value,
        res=dut.result_o.value,
        ovf=dut.overflow_o.value,
        uf=dut.underflow_o.value,
        inexact=dut.inexact_o.value,
    )

    for k in ("sign", "exp", "frac", "res", "ovf", "uf", "inexact"):
        assert got[k] == exp[k], f"{k}: got {got[k]} expected {exp[k]}  [{context}]"

    # for coverage
    sample(
        dict(mode=mode, scenario=classify(mant, exp, sign, g, r, s, mode, zero, exp))
    )

    if label:
        dut._log.info(f"PASS {label}")


# --------------
# DIRECTED TESTS
# --------------
@cocotb.test()
async def test_rne(dut):
    await drive_and_check(
        dut, 0x800000, 0xF0, 1, 1, 0, 0, 0, 0, RoundMode.RNE, "round up"
    )
    await drive_and_check(dut, 0x800000, 0xF0, 1, 0, 0, 0, 0, 0, RoundMode.RNE, "tie")
    await drive_and_check(
        dut, 0x800000, 0xF0, 1, 0, 0, 0, 0, 0, RoundMode.RNE, "tie with even lsb"
    )
    await drive_and_check(
        dut, 0x800001, 0xF0, 1, 0, 0, 0, 0, 0, RoundMode.RNE, "tie with odd lsb"
    )
