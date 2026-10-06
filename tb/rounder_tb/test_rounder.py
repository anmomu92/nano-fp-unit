"""
cocotb testbench for the rounder.sv module
"""

import os
import random
from dataclasses import dataclass
from enum import Enum

import cocotb
from cocotb.triggers import Timer
from cocotb_coverage.coverage import CoverCross, CoverPoint, coverage_db
from common.coverage_report import report_coverage

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

# coverage
COVERAGE = [
    "top.mode",
    "top.flags",
    "top.sign",
    "top.grs",
    "top.inexact",
    "top.overflow",
    "top.underflow",
    "top.mode_x_sign",
    "top.mode_x_flags",
    "top.mode_x_ovf",
    "top.sign_x_flags",
]


# -------
# CLASSES
# -------
# RISC-V frm
class RoundMode(Enum):
    RNE = 0
    RTZ = 1
    RDN = 2
    RUP = 3
    RMM = 4


@dataclass
class RoundInputs:
    sign_i: int
    exp_i: int
    mant_i: int
    guard_i: int
    round_i: int
    sticky_i: int
    round_mode_i: int
    overflow_i: int = 0
    underflow_i: int = 0
    zero_i: int = 0

    def __str__(self) -> str:
        return (
            f"\n\tsign_i={self.sign_i} \n"
            f"\texp_i=0x{self.exp_i:02x} \n"
            f"\tmant_i=0x{self.mant_i:06x} \n"
            f"\tguard_i={self.guard_i} \n"
            f"\tround_i={self.round_i} \n"
            f"\tsticky_i={self.sticky_i} \n"
            f"\tround_mode_i={self.round_mode_i} \n"
            f"\toverflow_i={self.overflow_i} \n"
            f"\tunderflow_i={self.underflow_i} \n"
            f"\tzero_i={self.zero_i} \n"
        )


@dataclass
class RoundOutputs:
    sign_o: int
    exp_o: int
    frac_o: int
    result_o: int
    overflow_o: int
    underflow_o: int
    inexact_o: int

    def __str__(self) -> str:
        return (
            f"\n\tsign_o={self.sign_o} \n"
            f"\texp_o=0x{self.exp_o:02x} \n"
            f"\tfrac_o=0x{self.frac_o:06x} \n"
            f"\tresult_o=0x{self.result_o:08x} \n"
            f"\toverflow_o={self.overflow_o} \n"
            f"\tunderflow_o={self.underflow_o} \n"
            f"\tinexact_o={self.inexact_o} \n"
        )


# ---------
# FUNCTIONS
# ---------


# ROUNDING_DECISION
#
# Description - calculates the bit that will decide in which direction to round up the fraction
def rounding_decision(mode, sign, g, r, s, lsb):
    """Decide how to round a number.

    Arguments:
    mode -- the rounding mode
    sign -- the sign of the number
    g -- the guard bit
    r -- the round bit
    s -- the sticky bit
    lsb -- the least significant bit of the number

    Returns:
    The round up decision.
    """
    match mode:
        case RoundMode.RNE.value:
            round_up = g & (r | s | lsb)
        case RoundMode.RTZ.value:
            round_up = 0
        case RoundMode.RDN.value:
            round_up = sign & (g | r | s)
        case RoundMode.RUP.value:
            round_up = (1 - sign) & (g | r | s)
        case RoundMode.RMM.value:
            round_up = g
        case _:
            round_up = g & (r | s | lsb)

    return round_up


def golden_reference(inputs: RoundInputs) -> RoundOutputs:
    """Round a number following the IEEE 754 Std.

    Arguments:
    inputs -- input interface

    Returns:
    The output interface
    """
    frac = inputs.mant_i & FRAC_MASK
    lsb = inputs.mant_i & 1

    round_up = rounding_decision(
        inputs.round_mode_i,
        inputs.sign_i,
        inputs.guard_i,
        inputs.round_i,
        inputs.sticky_i,
        lsb,
    )

    if inputs.overflow_i:
        round_up = 0

    exp_frac = (inputs.exp_i << FRAC_WIDTH) | frac
    exp_frac_r = exp_frac + round_up

    exp_r = (exp_frac_r >> FRAC_WIDTH) & EXP_MASK
    exp_f = 0
    frac_r = exp_frac_r & FRAC_MASK
    frac_f = 0

    ovf_raw = inputs.overflow_i | (exp_r == EXP_MASK)

    # adjust exponent and fraction after incoming flags
    if inputs.zero_i:
        exp_f, frac_f, inexact = 0, 0, 0
    else:
        if ovf_raw:
            match inputs.round_mode_i:
                case RoundMode.RTZ.value:
                    exp_f = EXP_MAX_NORM
                    frac_f = FRAC_MASK
                case RoundMode.RDN.value:
                    if inputs.sign_i:  # if negative, -infinity
                        exp_f = EXP_MASK
                        frac_f = 0
                    else:
                        exp_f = EXP_MAX_NORM
                        frac_f = FRAC_MASK
                case RoundMode.RUP.value:
                    if not inputs.sign_i:  # if positive, +infinity
                        exp_f = EXP_MASK
                        frac_f = 0
                    else:
                        exp_f = EXP_MAX_NORM
                        frac_f = FRAC_MASK
                case _:
                    exp_f = exp_r
                    frac_f = frac_r
        else:
            exp_f, frac_f = exp_r, frac_r

    ovf_f = 1 if (ovf_raw and not inputs.zero_i) else 0
    # inexact is raised in the following cases:
    #   - any of the GRS is set
    #   - the ovf flag is one
    inexact = (
        ovf_f
        or ((inputs.guard_i | inputs.round_i | inputs.sticky_i) & 1)
        and not inputs.zero_i
    )
    uf_f = 1 if (exp_f == 0 and not inputs.zero_i and inexact) else 0
    res_f = (inputs.sign_i << (RES_WIDTH - 1)) | (exp_f << FRAC_WIDTH) | frac_f

    return RoundOutputs(
        sign_o=inputs.sign_i,
        exp_o=exp_f,
        frac_o=frac_f,
        result_o=res_f,
        overflow_o=ovf_f,
        underflow_o=uf_f,
        inexact_o=inexact,
    )

    """
    out: dict[str, Any] = dict(
        sign_o=sign_i,
        exp_o=exp_f,
        frac_o=frac_f,
        result_o=res_f,
        ovf_o=ovf_f,
        uf_o=uf_f,
        inexact_o=inexact,
        round_up_o=round_up,
    )

    out["_internals"] = dict(
        frac=frac,
        round_up=round_up,
        ovf_raw=ovf_raw,
        exp_frac=exp_frac,
        exp_frac_r=exp_frac_r,
        exp_r=exp_r,
        exp_f=exp_f,
        frac_r=frac_r,
        frac_f=frac_f,
    )
    """


# -------------------
# Functional coverage
# -------------------

INPUT_FLAG_BINS = ["zero", "overflow", "no flag"]
ROUND_MODE_BINS = [
    RoundMode.RNE.value,
    RoundMode.RTZ.value,
    RoundMode.RDN.value,
    RoundMode.RUP.value,
    RoundMode.RMM.value,
]
ROUND_DECISION_BINS = ["round up", "round down"]


# classification functions
def classify_in_flags(zero: int, ovf_i: int = 0) -> str:
    """Classify input flags in bing"""
    if zero:
        return "zero"
    if ovf_i:
        return "overflow"
    return "no flag"


def classify_round_decision(inputs: RoundInputs) -> str:
    if rounding_decision(
        inputs.round_mode_i,
        inputs.sign_i,
        inputs.guard_i,
        inputs.round_i,
        inputs.sticky_i,
        inputs.mant_i & 1,
    ):
        return "round up"
    else:
        return "round down"


# coverpoints
@CoverPoint(
    "top.mode",
    xf=lambda t: t["i"].round_mode_i,
    bins=ROUND_MODE_BINS,
)
@CoverPoint(
    "top.flags",
    xf=lambda t: classify_in_flags(t["i"].zero_i, t["i"].overflow_i),
    bins=INPUT_FLAG_BINS,
)
@CoverPoint("top.sign", xf=lambda t: t["i"].sign_i, bins=[0, 1])
@CoverPoint(
    "top.grs",
    xf=lambda t: (t["i"].guard_i, t["i"].round_i, t["i"].sticky_i),
    bins=[(a, b, c) for a in (0, 1) for b in (0, 1) for c in (0, 1)],
)
@CoverPoint("top.inexact", xf=lambda t: t["o"].inexact_o, bins=[0, 1])
@CoverPoint("top.overflow", xf=lambda t: t["o"].overflow_o, bins=[0, 1])
@CoverPoint("top.underflow", xf=lambda t: t["o"].underflow_o, bins=[0, 1])
@CoverCross("top.mode_x_sign", items=["top.mode", "top.sign"])
@CoverCross("top.mode_x_flags", items=["top.mode", "top.flags"])
@CoverCross("top.mode_x_ovf", items=["top.mode", "top.overflow"])
@CoverCross("top.sign_x_flags", items=["top.sign", "top.flags"])
def sample(t):
    pass


# ------
# DRIVER
# ------


async def drive_dut(
    dut,
    inputs,
) -> RoundOutputs:

    dut.mant_i.value = inputs.mant_i
    dut.exp_i.value = inputs.exp_i
    dut.sign_i.value = inputs.sign_i
    dut.guard_i.value = inputs.guard_i
    dut.round_i.value = inputs.round_i
    dut.sticky_i.value = inputs.sticky_i
    dut.overflow_i.value = inputs.overflow_i
    dut.underflow_i.value = inputs.underflow_i
    dut.zero_i.value = inputs.zero_i
    dut.round_mode_i.value = inputs.round_mode_i

    await SETTLE

    return RoundOutputs(
        sign_o=int(dut.sign_o.value),
        exp_o=int(dut.exp_o.value),
        frac_o=int(dut.frac_o.value),
        result_o=int(dut.result_o.value),
        overflow_o=int(dut.overflow_o),
        underflow_o=int(dut.underflow_o),
        inexact_o=int(dut.inexact_o),
    )


async def check(dut, inputs, expected=None, label=""):

    got = await drive_dut(dut, inputs)
    if expected == None:
        expected = golden_reference(inputs)

    assert got == expected, f"{label} got {got} expected {expected} [{inputs}]"

    # record functional coverage for this stimulus
    sample({"i": inputs, "o": got})

    if label:
        dut._log.info(f"PASS {label}")


# --------------
# DIRECTED TESTS
# --------------

# cases
BASIC_ROUNDING_CASES = [
    (
        "exact_no_rounding",
        RoundInputs(
            sign_i=0,
            exp_i=0x7F,
            mant_i=0x800000,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            overflow_i=0,
            underflow_i=0,
            zero_i=0,
            round_mode_i=0b000,  # RNE
        ),
        RoundOutputs(
            sign_o=0,
            exp_o=0x7F,
            frac_o=0x000000,
            result_o=0x3F800000,
            overflow_o=0,
            underflow_o=0,
            inexact_o=0,
        ),
    ),
    (
        "rne_below_half_round_down",
        RoundInputs(
            sign_i=0,
            exp_i=0x7F,
            mant_i=0x800001,
            guard_i=0,
            round_i=1,
            sticky_i=1,
            overflow_i=0,
            underflow_i=0,
            zero_i=0,
            round_mode_i=0b000,  # RNE
        ),
        RoundOutputs(
            sign_o=0,
            exp_o=0x7F,
            frac_o=0x000001,
            result_o=0x3F800001,
            overflow_o=0,
            underflow_o=0,
            inexact_o=1,
        ),
    ),
    (
        "rne_above_half_round_up",
        RoundInputs(
            sign_i=0,
            exp_i=0x7F,
            mant_i=0x800001,
            guard_i=1,
            round_i=1,
            sticky_i=0,
            overflow_i=0,
            underflow_i=0,
            zero_i=0,
            round_mode_i=0b000,  # RNE
        ),
        RoundOutputs(
            sign_o=0,
            exp_o=0x7F,
            frac_o=0x000002,
            result_o=0x3F800002,
            overflow_o=0,
            underflow_o=0,
            inexact_o=1,
        ),
    ),
    (
        "rne_tie_lsb_even_stays",
        RoundInputs(
            sign_i=0,
            exp_i=0x7F,
            mant_i=0x800002,
            guard_i=1,
            round_i=0,
            sticky_i=0,
            overflow_i=0,
            underflow_i=0,
            zero_i=0,
            round_mode_i=0b000,  # RNE
        ),
        RoundOutputs(
            sign_o=0,
            exp_o=0x7F,
            frac_o=0x000002,
            result_o=0x3F800002,
            overflow_o=0,
            underflow_o=0,
            inexact_o=1,
        ),
    ),
    (
        "rne_tie_lsb_odd_rounds_up",
        RoundInputs(
            sign_i=0,
            exp_i=0x7F,
            mant_i=0x800003,
            guard_i=1,
            round_i=0,
            sticky_i=0,
            overflow_i=0,
            underflow_i=0,
            zero_i=0,
            round_mode_i=0b000,  # RNE
        ),
        RoundOutputs(
            sign_o=0,
            exp_o=0x7F,
            frac_o=0x000004,
            result_o=0x3F800004,
            overflow_o=0,
            underflow_o=0,
            inexact_o=1,
        ),
    ),
]

ROUND_MODE_CASES = [
    (
        "rtz_truncates",
        RoundInputs(
            sign_i=0,
            exp_i=0x7F,
            mant_i=0x800001,
            guard_i=1,
            round_i=1,
            sticky_i=1,
            overflow_i=0,
            underflow_i=0,
            zero_i=0,
            round_mode_i=0b001,  # RTZ
        ),
        RoundOutputs(
            sign_o=0,
            exp_o=0x7F,
            frac_o=0x000001,
            result_o=0x3F800001,
            overflow_o=0,
            underflow_o=0,
            inexact_o=1,
        ),
    ),
    (
        "rdn_positive_truncates",
        RoundInputs(
            sign_i=0,
            exp_i=0x7F,
            mant_i=0x800001,
            guard_i=1,
            round_i=0,
            sticky_i=0,
            overflow_i=0,
            underflow_i=0,
            zero_i=0,
            round_mode_i=0b010,  # RDN
        ),
        RoundOutputs(
            sign_o=0,
            exp_o=0x7F,
            frac_o=0x000001,
            result_o=0x3F800001,
            overflow_o=0,
            underflow_o=0,
            inexact_o=1,
        ),
    ),
    (
        "rdn_negative_rounds_up_magnitude",
        RoundInputs(
            sign_i=1,
            exp_i=0x7F,
            mant_i=0x800001,
            guard_i=0,
            round_i=0,
            sticky_i=1,
            overflow_i=0,
            underflow_i=0,
            zero_i=0,
            round_mode_i=0b010,  # RDN
        ),
        RoundOutputs(
            sign_o=1,
            exp_o=0x7F,
            frac_o=0x000002,
            result_o=0xBF800002,
            overflow_o=0,
            underflow_o=0,
            inexact_o=1,
        ),
    ),
    (
        "rup_positive_rounds_up_magnitude",
        RoundInputs(
            sign_i=0,
            exp_i=0x7F,
            mant_i=0x800001,
            guard_i=0,
            round_i=0,
            sticky_i=1,
            overflow_i=0,
            underflow_i=0,
            zero_i=0,
            round_mode_i=0b011,  # RUP
        ),
        RoundOutputs(
            sign_o=0,
            exp_o=0x7F,
            frac_o=0x000002,
            result_o=0x3F800002,
            overflow_o=0,
            underflow_o=0,
            inexact_o=1,
        ),
    ),
    (
        "rup_negative_truncates",
        RoundInputs(
            sign_i=1,
            exp_i=0x7F,
            mant_i=0x800001,
            guard_i=1,
            round_i=0,
            sticky_i=0,
            overflow_i=0,
            underflow_i=0,
            zero_i=0,
            round_mode_i=0b011,  # RUP
        ),
        RoundOutputs(
            sign_o=1,
            exp_o=0x7F,
            frac_o=0x000001,
            result_o=0xBF800001,
            overflow_o=0,
            underflow_o=0,
            inexact_o=1,
        ),
    ),
    (
        "rmm_tie_rounds_away",
        RoundInputs(
            sign_i=0,
            exp_i=0x7F,
            mant_i=0x800002,
            guard_i=1,
            round_i=0,
            sticky_i=0,
            overflow_i=0,
            underflow_i=0,
            zero_i=0,
            round_mode_i=0b100,  # RMM
        ),
        RoundOutputs(
            sign_o=0,
            exp_o=0x7F,
            frac_o=0x000003,
            result_o=0x3F800003,
            overflow_o=0,
            underflow_o=0,
            inexact_o=1,
        ),
    ),
]

MANTISSA_CARRY_CASES = [
    (
        "carry_increments_exponent",
        RoundInputs(
            sign_i=0,
            exp_i=0x7F,
            mant_i=0xFFFFFF,
            guard_i=1,
            round_i=0,
            sticky_i=1,
            overflow_i=0,
            underflow_i=0,
            zero_i=0,
            round_mode_i=0b000,  # RNE
        ),
        RoundOutputs(
            sign_o=0,
            exp_o=0x80,
            frac_o=0x000000,
            result_o=0x40000000,
            overflow_o=0,
            underflow_o=0,
            inexact_o=1,
        ),
    ),
    (
        "carry_causes_overflow_rne",
        RoundInputs(
            sign_i=0,
            exp_i=0xFE,
            mant_i=0xFFFFFF,
            guard_i=1,
            round_i=0,
            sticky_i=0,
            overflow_i=0,
            underflow_i=0,
            zero_i=0,
            round_mode_i=0b000,  # RNE
        ),
        RoundOutputs(
            sign_o=0,
            exp_o=0xFF,
            frac_o=0x000000,
            result_o=0x7F800000,
            overflow_o=1,
            underflow_o=0,
            inexact_o=1,
        ),
    ),
    (
        "max_finite_rtz_no_overflow",
        RoundInputs(
            sign_i=0,
            exp_i=0xFE,
            mant_i=0xFFFFFF,
            guard_i=1,
            round_i=1,
            sticky_i=1,
            overflow_i=0,
            underflow_i=0,
            zero_i=0,
            round_mode_i=0b001,  # RTZ
        ),
        RoundOutputs(
            sign_o=0,
            exp_o=0xFE,
            frac_o=0x7FFFFF,
            result_o=0x7F7FFFFF,
            overflow_o=0,
            underflow_o=0,
            inexact_o=1,
        ),
    ),
]

OVERFLOW_CASES = [
    (
        "overflow_in_rne_positive_inf",
        RoundInputs(
            sign_i=0,
            exp_i=0xFF,
            mant_i=0x800000,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            overflow_i=1,
            underflow_i=0,
            zero_i=0,
            round_mode_i=0b000,  # RNE
        ),
        RoundOutputs(
            sign_o=0,
            exp_o=0xFF,
            frac_o=0x000000,
            result_o=0x7F800000,
            overflow_o=1,
            underflow_o=0,
            inexact_o=1,
        ),
    ),
    (
        "overflow_in_rtz_positive_max_finite",
        RoundInputs(
            sign_i=0,
            exp_i=0xFF,
            mant_i=0x800000,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            overflow_i=1,
            underflow_i=0,
            zero_i=0,
            round_mode_i=0b001,  # RTZ
        ),
        RoundOutputs(
            sign_o=0,
            exp_o=0xFE,
            frac_o=0x7FFFFF,
            result_o=0x7F7FFFFF,
            overflow_o=1,
            underflow_o=0,
            inexact_o=1,
        ),
    ),
    (
        "overflow_in_rdn_positive_max_finite",
        RoundInputs(
            sign_i=0,
            exp_i=0xFF,
            mant_i=0x800000,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            overflow_i=1,
            underflow_i=0,
            zero_i=0,
            round_mode_i=0b010,  # RDN
        ),
        RoundOutputs(
            sign_o=0,
            exp_o=0xFE,
            frac_o=0x7FFFFF,
            result_o=0x7F7FFFFF,
            overflow_o=1,
            underflow_o=0,
            inexact_o=1,
        ),
    ),
    (
        "overflow_in_rdn_negative_inf",
        RoundInputs(
            sign_i=1,
            exp_i=0xFF,
            mant_i=0x800000,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            overflow_i=1,
            underflow_i=0,
            zero_i=0,
            round_mode_i=0b010,  # RDN
        ),
        RoundOutputs(
            sign_o=1,
            exp_o=0xFF,
            frac_o=0x000000,
            result_o=0xFF800000,
            overflow_o=1,
            underflow_o=0,
            inexact_o=1,
        ),
    ),
    (
        "overflow_in_rup_positive_inf",
        RoundInputs(
            sign_i=0,
            exp_i=0xFF,
            mant_i=0x800000,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            overflow_i=1,
            underflow_i=0,
            zero_i=0,
            round_mode_i=0b011,  # RUP
        ),
        RoundOutputs(
            sign_o=0,
            exp_o=0xFF,
            frac_o=0x000000,
            result_o=0x7F800000,
            overflow_o=1,
            underflow_o=0,
            inexact_o=1,
        ),
    ),
    (
        "overflow_in_rup_negative_max_finite",
        RoundInputs(
            sign_i=1,
            exp_i=0xFF,
            mant_i=0x800000,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            overflow_i=1,
            underflow_i=0,
            zero_i=0,
            round_mode_i=0b011,  # RUP
        ),
        RoundOutputs(
            sign_o=1,
            exp_o=0xFE,
            frac_o=0x7FFFFF,
            result_o=0xFF7FFFFF,
            overflow_o=1,
            underflow_o=0,
            inexact_o=1,
        ),
    ),
]

ZERO_CASES = [
    (
        "positive_zero",
        RoundInputs(
            sign_i=0,
            exp_i=0x00,
            mant_i=0x000000,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            overflow_i=0,
            underflow_i=0,
            zero_i=1,
            round_mode_i=0b000,  # RNE
        ),
        RoundOutputs(
            sign_o=0,
            exp_o=0x00,
            frac_o=0x000000,
            result_o=0x00000000,
            overflow_o=0,
            underflow_o=0,
            inexact_o=0,
        ),
    ),
    (
        "negative_zero",
        RoundInputs(
            sign_i=1,
            exp_i=0x00,
            mant_i=0x000000,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            overflow_i=0,
            underflow_i=0,
            zero_i=1,
            round_mode_i=0b000,  # RNE
        ),
        RoundOutputs(
            sign_o=1,
            exp_o=0x00,
            frac_o=0x000000,
            result_o=0x80000000,
            overflow_o=0,
            underflow_o=0,
            inexact_o=0,
        ),
    ),
]

SUBNORMAL_CASES = [
    (
        "subnormal_exact_no_underflow_flag",
        RoundInputs(
            sign_i=0,
            exp_i=0x00,
            mant_i=0x000100,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            overflow_i=0,
            underflow_i=1,
            zero_i=0,
            round_mode_i=0b000,  # RNE
        ),
        RoundOutputs(
            sign_o=0,
            exp_o=0x00,
            frac_o=0x000100,
            result_o=0x00000100,
            overflow_o=0,
            underflow_o=0,
            inexact_o=0,
        ),
    ),
    (
        "subnormal_inexact_round_up",
        RoundInputs(
            sign_i=0,
            exp_i=0x00,
            mant_i=0x000101,
            guard_i=1,
            round_i=1,
            sticky_i=0,
            overflow_i=0,
            underflow_i=1,
            zero_i=0,
            round_mode_i=0b000,  # RNE
        ),
        RoundOutputs(
            sign_o=0,
            exp_o=0x00,
            frac_o=0x000102,
            result_o=0x00000102,
            overflow_o=0,
            underflow_o=1,
            inexact_o=1,
        ),
    ),
    (
        # tininess detected AFTER rounding -> underflow_o=0
        # (if your design detects tininess BEFORE rounding, expect underflow_o=1)
        "subnormal_rounds_to_min_normal",
        RoundInputs(
            sign_i=0,
            exp_i=0x00,
            mant_i=0x7FFFFF,
            guard_i=1,
            round_i=1,
            sticky_i=0,
            overflow_i=0,
            underflow_i=1,
            zero_i=0,
            round_mode_i=0b000,  # RNE
        ),
        RoundOutputs(
            sign_o=0,
            exp_o=0x01,
            frac_o=0x000000,
            result_o=0x00800000,
            overflow_o=0,
            underflow_o=0,
            inexact_o=1,
        ),
    ),
]

ALL_CASES = (
    BASIC_ROUNDING_CASES
    + ROUND_MODE_CASES
    + MANTISSA_CARRY_CASES
    + OVERFLOW_CASES
    + ZERO_CASES
    + SUBNORMAL_CASES
)


async def run_cases(dut, cases):
    for label, inputs, outputs in cases:
        await check(dut, inputs, outputs, label)


@cocotb.test()
async def test_basic_rounding(dut):
    """Round-to-nearest-even: exact, below/above half, and ties to even."""
    await run_cases(dut, BASIC_ROUNDING_CASES)


@cocotb.test()
async def test_round_modes(dut):
    """RTZ, RDN, RUP and RMM behaviour for positive and negative operands."""
    await run_cases(dut, ROUND_MODE_CASES)


@cocotb.test()
async def test_mantissa_carry(dut):
    """Rounding carry out of the mantissa increments the exponent or overflows."""
    await run_cases(dut, MANTISSA_CARRY_CASES)


@cocotb.test()
async def test_overflow(dut):
    """Incoming overflow: infinity or max finite depending on mode and sign."""
    await run_cases(dut, OVERFLOW_CASES)


@cocotb.test()
async def test_zero(dut):
    """Zero input: signed zero out, no flags raised."""
    await run_cases(dut, ZERO_CASES)


@cocotb.test()
async def test_subnormal(dut):
    """Tiny results: underflow only when inexact, rounding up to min normal."""
    await run_cases(dut, SUBNORMAL_CASES)


@cocotb.test()
async def test_all_cases(dut):
    """Run every directed case back to back."""
    await run_cases(dut, ALL_CASES)


# ---------------
# RANDOMIZED TEST
# ---------------
@cocotb.test()
async def random_test(dut):
    rng = random.Random(0xCACABACA)
    num_tests = 80000
    for _ in range(num_tests):
        for sign in (0, 1):
            for g in (0, 1):
                for r in (0, 1):
                    for s in (0, 1):
                        mode_rnd = rng.randint(0, len(RoundMode) - 1)

                        # define probabilities for different exponent values
                        case = rng.random()
                        if case < 0.2:
                            # if exponent is 0, mantissa's MSB cannot be 1 (exp=0 means subnormal, that is, the implicit bit is 0)
                            exp_rnd = 0
                            mant_rnd = 0
                            ovf = 0
                            uf = 1
                        elif case < 0.4:
                            # if exponent is 0, mantissa's MSB cannot be 1 (exp=0 means subnormal, that is, the implicit bit is 0)
                            exp_rnd = 0
                            mant_rnd = rng.randint(1, 0x7FFFFF)
                            ovf = 0
                            uf = 1
                        elif case < 0.6:
                            exp_rnd = rng.randint(0x01, 0xFE)
                            mant_rnd = rng.randint(0, MANT_MASK)
                            ovf = 0
                            uf = 0
                        else:
                            # if exponent is 0xFF, mantissa's MSB cannot be 0 (exp=0xFF means infiniy, that is, the implicit bit is 0)
                            # Also, it indicates the number overflowed in the previous module, so the overflow_i flag has to be forced
                            exp_rnd = EXP_MASK
                            mant_rnd = rng.randint(0x800000, MANT_MASK)
                            ovf = 1
                            uf = 0

                        # if overflow input is 1, that means the exponent has the reserved maximum value
                        if mant_rnd == 0:
                            zero_rnd = 1 if rng.random() <= 0.8 else 0
                        else:
                            zero_rnd = 0

                        inputs = RoundInputs(
                            sign_i=sign,
                            exp_i=exp_rnd,
                            mant_i=mant_rnd,
                            guard_i=g,
                            round_i=r,
                            sticky_i=s,
                            overflow_i=ovf,
                            underflow_i=uf,
                            zero_i=zero_rnd,
                            round_mode_i=mode_rnd,
                        )

                        await check(dut, inputs)

    report_coverage(dut, COVERAGE)
