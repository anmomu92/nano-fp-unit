"""
top testbench for the rounder.sv module
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


@dataclass
class FpuInputs:
    num_a_i: int
    num_b_i: int
    format_a_i: int
    format_b_i: int
    op_code_i: int
    round_mode_i: int

    def __str__(self) -> str:
        return (
            f"\n\tnum_a_i={self.num_a_i:08x} \n"
            f"\tnum_b_i={self.num_b_i:08x} \n"
            f"\tformat_a_i=0x{self.format_a_i} \n"
            f"\tformat_b_i=0x{self.format_b_i} \n"
            f"\top_code_i={self.op_code_i} \n"
            f"\tround_mode_i={self.round_mode_i} \n"
        )


@dataclass
class FpuOutputs:
    result_o: int
    overflow_o: int
    underflow_o: int
    inexact_o: int
    zero_o: int

    def __str__(self) -> str:
        return (
            f"\n\tresult_o=0x{self.result_o:08x} \n"
            f"\toverflow_o={self.overflow_o} \n"
            f"\tunderflow_o={self.underflow_o} \n"
            f"\tinexact_o={self.inexact_o} \n"
            f"\tzero_o={self.zero_o} \n"
        )


# ---------
# FUNCTIONS
# ---------

# def golden_reference(inputs: RoundInputs) -> RoundOutputs:
#    """Round a number following the IEEE 754 Std.
#
#    Arguments:
#    inputs -- input interface
#
#    Returns:
#    The output interface
#    """
#    frac = inputs.mant_i & FRAC_MASK
#    lsb = inputs.mant_i & 1
#
#    round_up = rounding_decision(
#        inputs.round_mode_i,
#        inputs.sign_i,
#        inputs.guard_i,
#        inputs.round_i,
#        inputs.sticky_i,
#        lsb,
#    )
#
#    if inputs.overflow_i:
#        round_up = 0
#
#    exp_frac = (inputs.exp_i << FRAC_WIDTH) | frac
#    exp_frac_r = exp_frac + round_up
#
#    exp_r = (exp_frac_r >> FRAC_WIDTH) & EXP_MASK
#    exp_f = 0
#    frac_r = exp_frac_r & FRAC_MASK
#    frac_f = 0
#
#    ovf_raw = inputs.overflow_i | (exp_r == EXP_MASK)
#
#    # adjust exponent and fraction after incoming flags
#    if inputs.zero_i:
#        exp_f, frac_f, inexact = 0, 0, 0
#    else:
#        if ovf_raw:
#            match inputs.round_mode_i:
#                case RoundMode.RTZ.value:
#                    exp_f = EXP_MAX_NORM
#                    frac_f = FRAC_MASK
#                case RoundMode.RDN.value:
#                    if inputs.sign_i:  # if negative, -infinity
#                        exp_f = EXP_MASK
#                        frac_f = 0
#                    else:
#                        exp_f = EXP_MAX_NORM
#                        frac_f = FRAC_MASK
#                case RoundMode.RUP.value:
#                    if not inputs.sign_i:  # if positive, +infinity
#                        exp_f = EXP_MASK
#                        frac_f = 0
#                    else:
#                        exp_f = EXP_MAX_NORM
#                        frac_f = FRAC_MASK
#                case _:
#                    exp_f = exp_r
#                    frac_f = frac_r
#        else:
#            exp_f, frac_f = exp_r, frac_r
#
#    ovf_f = 1 if (ovf_raw and not inputs.zero_i) else 0
#    # inexact is raised in the following cases:
#    #   - any of the GRS is set
#    #   - the ovf flag is one
#    inexact = (
#        ovf_f
#        or ((inputs.guard_i | inputs.round_i | inputs.sticky_i) & 1)
#        and not inputs.zero_i
#    )
#    uf_f = 1 if (exp_f == 0 and not inputs.zero_i and inexact) else 0
#    res_f = (inputs.sign_i << (RES_WIDTH - 1)) | (exp_f << FRAC_WIDTH) | frac_f
#
#    return RoundOutputs(
#        sign_o=inputs.sign_i,
#        exp_o=exp_f,
#        frac_o=frac_f,
#        result_o=res_f,
#        overflow_o=ovf_f,
#        underflow_o=uf_f,
#        inexact_o=inexact,
#    )
#
#    """
#    out: dict[str, Any] = dict(
#        sign_o=sign_i,
#        exp_o=exp_f,
#        frac_o=frac_f,
#        result_o=res_f,
#        ovf_o=ovf_f,
#        uf_o=uf_f,
#        inexact_o=inexact,
#        round_up_o=round_up,
#    )
#
#    out["_internals"] = dict(
#        frac=frac,
#        round_up=round_up,
#        ovf_raw=ovf_raw,
#        exp_frac=exp_frac,
#        exp_frac_r=exp_frac_r,
#        exp_r=exp_r,
#        exp_f=exp_f,
#        frac_r=frac_r,
#        frac_f=frac_f,
#    )
#    """
#
#
## -------------------
## Functional coverage
## -------------------
#
# INPUT_FLAG_BINS = ["zero", "overflow", "no flag"]
# ROUND_MODE_BINS = [
#    RoundMode.RNE.value,
#    RoundMode.RTZ.value,
#    RoundMode.RDN.value,
#    RoundMode.RUP.value,
#    RoundMode.RMM.value,
# ]
# ROUND_DECISION_BINS = ["round up", "round down"]
#
#
## classification functions
# def classify_in_flags(zero: int, ovf_i: int = 0) -> str:
#    """Classify input flags in bing"""
#    if zero:
#        return "zero"
#    if ovf_i:
#        return "overflow"
#    return "no flag"
#
#
# def classify_round_decision(inputs: RoundInputs) -> str:
#    if rounding_decision(
#        inputs.round_mode_i,
#        inputs.sign_i,
#        inputs.guard_i,
#        inputs.round_i,
#        inputs.sticky_i,
#        inputs.mant_i & 1,
#    ):
#        return "round up"
#    else:
#        return "round down"
#
#
## coverpoints
# @CoverPoint(
#    "top.mode",
#    xf=lambda t: t["i"].round_mode_i,
#    bins=ROUND_MODE_BINS,
# )
# @CoverPoint(
#    "top.flags",
#    xf=lambda t: classify_in_flags(t["i"].zero_i, t["i"].overflow_i),
#    bins=INPUT_FLAG_BINS,
# )
# @CoverPoint("top.sign", xf=lambda t: t["i"].sign_i, bins=[0, 1])
# @CoverPoint(
#    "top.grs",
#    xf=lambda t: (t["i"].guard_i, t["i"].round_i, t["i"].sticky_i),
#    bins=[(a, b, c) for a in (0, 1) for b in (0, 1) for c in (0, 1)],
# )
# @CoverPoint("top.inexact", xf=lambda t: t["o"].inexact_o, bins=[0, 1])
# @CoverPoint("top.overflow", xf=lambda t: t["o"].overflow_o, bins=[0, 1])
# @CoverPoint("top.underflow", xf=lambda t: t["o"].underflow_o, bins=[0, 1])
# @CoverCross("top.mode_x_sign", items=["top.mode", "top.sign"])
# @CoverCross("top.mode_x_flags", items=["top.mode", "top.flags"])
# @CoverCross("top.mode_x_ovf", items=["top.mode", "top.overflow"])
# @CoverCross("top.sign_x_flags", items=["top.sign", "top.flags"])
# def sample(t):
#    pass
#

# ------
# DRIVER
# ------


async def drive_dut(
    dut,
    inputs,
) -> FpuOutputs:

    dut.num_a_i.value = inputs.num_a_i
    dut.num_b_i.value = inputs.num_b_i
    dut.format_a_i.value = inputs.format_a_i
    dut.format_b_i.value = inputs.format_b_i
    dut.op_code_i.value = inputs.op_code_i
    dut.round_mode_i.value = inputs.round_mode_i

    await SETTLE

    return FpuOutputs(
        result_o=int(dut.result_o.value),
        overflow_o=int(dut.overflow_o.value),
        underflow_o=int(dut.underflow_o.value),
        inexact_o=int(dut.inexact_o.value),
        zero_o=int(dut.zero_o.value),
    )


async def check(dut, inputs, expected=None, label=""):

    got = await drive_dut(dut, inputs)
    #    if expected == None:
    #        expected = golden_reference(inputs)

    assert got == expected, f"{label}\n got {got} expected {expected} [{inputs}]"

    # record functional coverage for this stimulus
    # sample({"i": inputs, "o": got})

    if label:
        dut._log.info(f"PASS {label}")


# --------------
# DIRECTED TESTS
# --------------

F32_BASIC_CASES = [
    (
        "1.0 + 1.0 = 2.0",
        FpuInputs(
            num_a_i=0x3F800000,
            num_b_i=0x3F800000,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=0,
        ),
        FpuOutputs(
            result_o=0x40000000, overflow_o=0, underflow_o=0, inexact_o=0, zero_o=0
        ),
    ),
    (
        "1.0 + 2.0 = 3.0",
        FpuInputs(
            num_a_i=0x3F800000,
            num_b_i=0x40000000,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=0,
        ),
        FpuOutputs(
            result_o=0x40400000, overflow_o=0, underflow_o=0, inexact_o=0, zero_o=0
        ),
    ),
    (
        "-1.0 + 0.5 = -0.5 (sign of larger magnitude)",
        FpuInputs(
            num_a_i=0xBF800000,
            num_b_i=0x3F000000,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=0,
        ),
        FpuOutputs(
            result_o=0xBF000000, overflow_o=0, underflow_o=0, inexact_o=0, zero_o=0
        ),
    ),
    (
        "1.0000001 - 1.0 = 2^-23 (massive cancellation, renormalization)",
        FpuInputs(
            num_a_i=0x3F800001,
            num_b_i=0x3F800000,
            format_a_i=0,
            format_b_i=0,
            op_code_i=0,
            round_mode_i=0,
        ),
        FpuOutputs(
            result_o=0x34000000, overflow_o=0, underflow_o=0, inexact_o=0, zero_o=0
        ),
    ),
]

F32_SIGNED_ZERO_CASES = [
    (
        "1.0 - 1.0 = +0 (exact cancellation, RNE)",
        FpuInputs(
            num_a_i=0x3F800000,
            num_b_i=0x3F800000,
            format_a_i=0,
            format_b_i=0,
            op_code_i=0,
            round_mode_i=0,
        ),
        FpuOutputs(
            result_o=0x00000000, overflow_o=0, underflow_o=0, inexact_o=0, zero_o=1
        ),
    ),
    (
        "★ 1.0 - 1.0 = -0 (exact cancellation, RDN)",
        FpuInputs(
            num_a_i=0x3F800000,
            num_b_i=0x3F800000,
            format_a_i=0,
            format_b_i=0,
            op_code_i=0,
            round_mode_i=2,
        ),
        FpuOutputs(
            result_o=0x80000000, overflow_o=0, underflow_o=0, inexact_o=0, zero_o=1
        ),
    ),
    (
        "+0 + -0 = +0 (RNE)",
        FpuInputs(
            num_a_i=0x00000000,
            num_b_i=0x80000000,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=0,
        ),
        FpuOutputs(
            result_o=0x00000000, overflow_o=0, underflow_o=0, inexact_o=0, zero_o=1
        ),
    ),
    (
        "★ +0 + -0 = -0 (RDN)",
        FpuInputs(
            num_a_i=0x00000000,
            num_b_i=0x80000000,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=2,
        ),
        FpuOutputs(
            result_o=0x80000000, overflow_o=0, underflow_o=0, inexact_o=0, zero_o=1
        ),
    ),
    (
        "-0 + -0 = -0",
        FpuInputs(
            num_a_i=0x80000000,
            num_b_i=0x80000000,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=0,
        ),
        FpuOutputs(
            result_o=0x80000000, overflow_o=0, underflow_o=0, inexact_o=0, zero_o=1
        ),
    ),
]

F32_ROUNDING_CASES = [
    (
        "0.1 + 0.2 = 0.3 (inexact)",
        FpuInputs(
            num_a_i=0x3DCCCCCD,
            num_b_i=0x3E4CCCCD,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=0,
        ),
        FpuOutputs(
            result_o=0x3E99999A, overflow_o=0, underflow_o=0, inexact_o=1, zero_o=0
        ),
    ),
    (
        "2^24 + 1 = 2^24 (tie, RNE rounds to even)",
        FpuInputs(
            num_a_i=0x4B800000,
            num_b_i=0x3F800000,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=0,
        ),
        FpuOutputs(
            result_o=0x4B800000, overflow_o=0, underflow_o=0, inexact_o=1, zero_o=0
        ),
    ),
    (
        "★ 2^24 + 1 = 2^24 + 2 (tie, RMM rounds away from zero)",
        FpuInputs(
            num_a_i=0x4B800000,
            num_b_i=0x3F800000,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=4,
        ),
        FpuOutputs(
            result_o=0x4B800001, overflow_o=0, underflow_o=0, inexact_o=1, zero_o=0
        ),
    ),
    (
        "1.0 + 2^-25 = 1.0 (below half ulp, absorbed, RNE)",
        FpuInputs(
            num_a_i=0x3F800000,
            num_b_i=0x33000000,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=0,
        ),
        FpuOutputs(
            result_o=0x3F800000, overflow_o=0, underflow_o=0, inexact_o=1, zero_o=0
        ),
    ),
    (
        "★ 1.0 + 2^-25 = 1+2^-23 (sticky bit, RUP rounds up)",
        FpuInputs(
            num_a_i=0x3F800000,
            num_b_i=0x33000000,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=3,
        ),
        FpuOutputs(
            result_o=0x3F800001, overflow_o=0, underflow_o=0, inexact_o=1, zero_o=0
        ),
    ),
    (
        "★ -1.0 + -2^-25 = -(1+2^-23) (sticky bit, RDN rounds toward -inf)",
        FpuInputs(
            num_a_i=0xBF800000,
            num_b_i=0xB3000000,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=2,
        ),
        FpuOutputs(
            result_o=0xBF800001, overflow_o=0, underflow_o=0, inexact_o=1, zero_o=0
        ),
    ),
    (
        "1.0 + 2^-24 = 1.0 (exact tie, RNE even stays)",
        FpuInputs(
            num_a_i=0x3F800000,
            num_b_i=0x33800000,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=0,
        ),
        FpuOutputs(
            result_o=0x3F800000, overflow_o=0, underflow_o=0, inexact_o=1, zero_o=0
        ),
    ),
    (
        "★ 1.0 + 2^-24 = 1+2^-23 (exact tie, RMM rounds away)",
        FpuInputs(
            num_a_i=0x3F800000,
            num_b_i=0x33800000,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=4,
        ),
        FpuOutputs(
            result_o=0x3F800001, overflow_o=0, underflow_o=0, inexact_o=1, zero_o=0
        ),
    ),
    (
        "(1+2^-23) + 2^-24 RNE (exact tie, odd rounds up)",
        FpuInputs(
            num_a_i=0x3F800001,
            num_b_i=0x33800000,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=0,
        ),
        FpuOutputs(
            result_o=0x3F800002, overflow_o=0, underflow_o=0, inexact_o=1, zero_o=0
        ),
    ),
    (
        "(1+2^-23) + 2^-24 RTZ (truncated)",
        FpuInputs(
            num_a_i=0x3F800001,
            num_b_i=0x33800000,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=1,
        ),
        FpuOutputs(
            result_o=0x3F800001, overflow_o=0, underflow_o=0, inexact_o=1, zero_o=0
        ),
    ),
    (
        "1.0 - 2^-25 RNE (tie across binade, rounds to 1.0)",
        FpuInputs(
            num_a_i=0x3F800000,
            num_b_i=0x33000000,
            format_a_i=0,
            format_b_i=0,
            op_code_i=0,
            round_mode_i=0,
        ),
        FpuOutputs(
            result_o=0x3F800000, overflow_o=0, underflow_o=0, inexact_o=1, zero_o=0
        ),
    ),
    (
        "1.0 - 2^-25 RTZ (largest value below 1.0)",
        FpuInputs(
            num_a_i=0x3F800000,
            num_b_i=0x33000000,
            format_a_i=0,
            format_b_i=0,
            op_code_i=0,
            round_mode_i=1,
        ),
        FpuOutputs(
            result_o=0x3F7FFFFF, overflow_o=0, underflow_o=0, inexact_o=1, zero_o=0
        ),
    ),
]

F32_OVERFLOW_CASES = [
    (
        "MAX + MAX = +inf (RNE overflow)",
        FpuInputs(
            num_a_i=0x7F7FFFFF,
            num_b_i=0x7F7FFFFF,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=0,
        ),
        FpuOutputs(
            result_o=0x7F800000, overflow_o=1, underflow_o=0, inexact_o=1, zero_o=0
        ),
    ),
    (
        "MAX + MAX = MAX (RTZ overflow)",
        FpuInputs(
            num_a_i=0x7F7FFFFF,
            num_b_i=0x7F7FFFFF,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=1,
        ),
        FpuOutputs(
            result_o=0x7F7FFFFF, overflow_o=1, underflow_o=0, inexact_o=1, zero_o=0
        ),
    ),
    (
        "★ MAX + MAX = MAX (RDN overflow, positive)",
        FpuInputs(
            num_a_i=0x7F7FFFFF,
            num_b_i=0x7F7FFFFF,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=2,
        ),
        FpuOutputs(
            result_o=0x7F7FFFFF, overflow_o=1, underflow_o=0, inexact_o=1, zero_o=0
        ),
    ),
    (
        "★ -MAX + -MAX = -inf (RDN overflow, negative)",
        FpuInputs(
            num_a_i=0xFF7FFFFF,
            num_b_i=0xFF7FFFFF,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=2,
        ),
        FpuOutputs(
            result_o=0xFF800000, overflow_o=1, underflow_o=0, inexact_o=1, zero_o=0
        ),
    ),
    (
        "★ MAX + MAX = +inf (RUP overflow, positive)",
        FpuInputs(
            num_a_i=0x7F7FFFFF,
            num_b_i=0x7F7FFFFF,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=3,
        ),
        FpuOutputs(
            result_o=0x7F800000, overflow_o=1, underflow_o=0, inexact_o=1, zero_o=0
        ),
    ),
    (
        "★ -MAX + -MAX = -MAX (RUP overflow, negative)",
        FpuInputs(
            num_a_i=0xFF7FFFFF,
            num_b_i=0xFF7FFFFF,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=3,
        ),
        FpuOutputs(
            result_o=0xFF7FFFFF, overflow_o=1, underflow_o=0, inexact_o=1, zero_o=0
        ),
    ),
]

F32_SUBNORMAL_CASES = [
    (
        "min subnormal + min subnormal (exact, no underflow flag)",
        FpuInputs(
            num_a_i=0x00000001,
            num_b_i=0x00000001,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=0,
        ),
        FpuOutputs(
            result_o=0x00000002, overflow_o=0, underflow_o=0, inexact_o=0, zero_o=0
        ),
    ),
    (
        "max subnormal + min subnormal = min normal",
        FpuInputs(
            num_a_i=0x007FFFFF,
            num_b_i=0x00000001,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=0,
        ),
        FpuOutputs(
            result_o=0x00800000, overflow_o=0, underflow_o=0, inexact_o=0, zero_o=0
        ),
    ),
    (
        "min normal - min subnormal = max subnormal",
        FpuInputs(
            num_a_i=0x00800000,
            num_b_i=0x00000001,
            format_a_i=0,
            format_b_i=0,
            op_code_i=0,
            round_mode_i=0,
        ),
        FpuOutputs(
            result_o=0x007FFFFF, overflow_o=0, underflow_o=0, inexact_o=0, zero_o=0
        ),
    ),
]

F32_SPECIAL_VALUE_CASES = [
    (
        "+inf + 1.0 = +inf (no flags)",
        FpuInputs(
            num_a_i=0x7F800000,
            num_b_i=0x3F800000,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=0,
        ),
        FpuOutputs(
            result_o=0x7F800000, overflow_o=0, underflow_o=0, inexact_o=0, zero_o=0
        ),
    ),
    (
        "+inf - +inf = qNaN (invalid)",
        FpuInputs(
            num_a_i=0x7F800000,
            num_b_i=0x7F800000,
            format_a_i=0,
            format_b_i=0,
            op_code_i=0,
            round_mode_i=0,
        ),
        FpuOutputs(
            result_o=0x7FC00000, overflow_o=0, underflow_o=0, inexact_o=0, zero_o=0
        ),
    ),
    (
        "qNaN + 1.0 = qNaN (propagation)",
        FpuInputs(
            num_a_i=0x7FC00000,
            num_b_i=0x3F800000,
            format_a_i=0,
            format_b_i=0,
            op_code_i=1,
            round_mode_i=0,
        ),
        FpuOutputs(
            result_o=0x7FC00000, overflow_o=0, underflow_o=0, inexact_o=0, zero_o=0
        ),
    ),
]

ALL_CASES = (
    F32_BASIC_CASES
    + F32_SIGNED_ZERO_CASES
    + F32_ROUNDING_CASES
    + F32_OVERFLOW_CASES
    + F32_SUBNORMAL_CASES
    + F32_SPECIAL_VALUE_CASES
)


async def run_cases(dut, cases):
    for label, inputs, outputs in cases:
        await check(dut, inputs, outputs, label)


@cocotb.test()
async def test_all_cases(dut):
    """Run every directed case back to back."""
    await run_cases(dut, ALL_CASES)
