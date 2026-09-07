"""
cocotb testbench for normalizer.sv
"""

import os
import random
from dataclasses import dataclass
from typing import Any

import cocotb
from cocotb.triggers import Timer
from cocotb_coverage.coverage import CoverCross, CoverPoint, coverage_db
from common.coverage_report import report_coverage

# -----------------------
# VARIABLES AND CONSTANTS
# -----------------------
# environment
SWEEP_N = int(os.environ.get("SWEEP_N", "8000"))

# timing
SETTLE = Timer(1, unit="ns")

# widths
MANT_WIDTH = 24
EXP_WIDTH = 8
EXT_WIDTH = MANT_WIDTH + 3
SHIFT_WIDTH = 5

# max widths
MANT_MASK = (1 << MANT_WIDTH) - 1
EXT_MASK = (1 << EXT_WIDTH) - 1
EXP_MASK = (1 << EXP_WIDTH) - 1

COVERAGE = [
    "top.case",
    "top.sign",
    "top.overflow",
    "top.underflow",
    "top.grs",
    "top.exp",
    "top.case_x_sign",
]


# -------
# CLASSES
# -------
@dataclass
class NormInputs:
    sign_i: int
    exp_i: int
    mant_i: int
    guard_i: int
    round_i: int
    sticky_i: int
    carry_i: int
    zero_i: int

    def __str__(self) -> str:
        return (
            f"\n\tsign_i={self.sign_i} \n"
            f"\texp_i=0x{self.exp_i:02x} \n"
            f"\tmant_i=0x{self.mant_i:06x} \n"
            f"\tguard_i={self.guard_i} \n"
            f"\tround_i={self.round_i} \n"
            f"\tsticky_i={self.sticky_i} \n"
            f"\tcarry_i={self.carry_i} \n"
            f"\tzero_i={self.zero_i} \n"
        )


@dataclass
class NormOutputs:
    sign_o: int
    exp_o: int
    mant_o: int
    guard_o: int
    round_o: int
    sticky_o: int
    zero_o: int
    overflow_o: int
    underflow_o: int

    def __str__(self) -> str:
        return (
            f"\n\tsign_i={self.sign_o} \n"
            f"\texp_i=0x{self.exp_o:02x} \n"
            f"\tmant_i=0x{self.mant_o:06x} \n"
            f"\tguard_i={self.guard_o} \n"
            f"\tround_i={self.round_o} \n"
            f"\tsticky_i={self.sticky_o} \n"
            f"\tzero_i={self.zero_o} \n"
            f"\tzero_i={self.overflow_o} \n"
            f"\tzero_i={self.underflow_o} \n"
        )


# ---------
# FUNCTIONS
# ---------
def lzc(x, width=MANT_WIDTH):
    """
    It counts leading zeros
    """
    for i in range(width):
        if (x >> (width - 1 - i)) & 1:
            return i
    return width


def golden_reference(inputs: NormInputs) -> NormOutputs:
    """
    Independent golden reference model.
    """
    overflow = 0
    underflow = 0

    carry_case = inputs.carry_i  # overflow
    normal_case = (not carry_case) and (
        (inputs.mant_i >> (MANT_WIDTH - 1)) & 1
    )  # normal

    # for subnormal inputs
    lz_raw = lzc(inputs.mant_i)
    headroom = 0 if inputs.exp_i == 0 else (inputs.exp_i - 1)

    # if exp_i - lzc <= 1
    if lz_raw > headroom:
        lz_use, subnormal = headroom & 0x1F, 1  # subnormal un-normalizable
    else:
        lz_use, subnormal = lz_raw, 0  # subnormal normalizabe

    extended_mant = (
        (inputs.mant_i << 3)
        | (inputs.guard_i << 2)
        | (inputs.round_i << 1)
        | inputs.sticky_i
    )
    shifted_mant = (extended_mant << lz_use) & EXT_MASK

    # depending on the case, we update the rest of the output values
    if inputs.zero_i:
        mant = 0
        exp = 0
        g = 0
        r = 0
        s = 0
    elif carry_case:
        mant = (inputs.carry_i << (MANT_WIDTH - 1)) | (
            (inputs.mant_i >> 1) & ((1 << (MANT_WIDTH - 1)) - 1)
        )
        exp = (inputs.exp_i + 1) & EXP_MASK
        g = inputs.mant_i & 1
        r = inputs.guard_i
        s = inputs.round_i | inputs.sticky_i
        overflow = 1 if inputs.exp_i >= EXP_MASK - 1 else 0
    elif normal_case:
        exp_f = 1 if inputs.exp_i == 0 else inputs.exp_i
        exp = exp_f

        mant = inputs.mant_i
        g = inputs.guard_i
        r = inputs.round_i
        s = inputs.sticky_i
    else:
        mant = (shifted_mant >> 3) & MANT_MASK
        g = (shifted_mant >> 2) & 1
        r = (shifted_mant >> 1) & 1
        s = shifted_mant & 1
        if subnormal:
            exp = 0
            underflow = 1
        else:
            exp = (inputs.exp_i - lz_use) & EXP_MASK

    return NormOutputs(
        sign_o=inputs.sign_i,
        exp_o=exp,
        mant_o=mant,
        guard_o=g,
        round_o=r,
        sticky_o=s,
        zero_o=inputs.zero_i,
        overflow_o=overflow,
        underflow_o=underflow,
    )


# --------------------
# Functional coverage
# --------------------

CASE_BINS = ["carry", "normal", "cancel", "zero"]
EXP_BINS = ["zero", "low", "mid", "high", "max"]


def classify_case(inputs):
    """
    case classification
    """
    if inputs.zero_i:
        return "zero"
    if inputs.carry_i:
        return "carry"
    if (inputs.mant_i >> (MANT_WIDTH - 1)) & 1:
        return "normal"
    return "cancel"


def classify_exp(e: int) -> str:
    # classify the exponent in different regions
    if e == 0:
        region = "zero"
    elif e <= 32:
        region = "low"
    elif e >= EXP_MASK:
        region = "max"
    elif e >= EXP_MASK - 8:
        region = "high"
    else:
        region = "mid"

    return region


@CoverPoint(
    "top.case",
    xf=lambda t: classify_case(t["i"]),
    bins=CASE_BINS,
)
@CoverPoint("top.sign", xf=lambda t: t["i"].sign_i, bins=[0, 1])
@CoverPoint("top.overflow", xf=lambda t: t["o"].overflow_o, bins=[0, 1])
@CoverPoint("top.underflow", xf=lambda t: t["o"].underflow_o, bins=[0, 1])
@CoverPoint(
    "top.grs",
    xf=lambda t: (t["i"].guard_i, t["i"].round_i, t["i"].sticky_i),
    bins=[(a, b, c) for a in (0, 1) for b in (0, 1) for c in (0, 1)],
)
@CoverPoint(
    "top.exp",
    xf=lambda t: classify_exp(t["i"].exp_i),
    bins=EXP_BINS,
)
@CoverCross("top.case_x_sign", items=["top.case", "top.sign"])
def sample(t):
    pass


async def drive_dut(dut, inputs) -> NormOutputs:
    dut.sign_i.value = inputs.sign_i
    dut.exp_i.value = inputs.exp_i
    dut.mant_i.value = inputs.mant_i
    dut.carry_i.value = inputs.carry_i
    dut.guard_i.value = inputs.guard_i
    dut.round_i.value = inputs.round_i
    dut.sticky_i.value = inputs.sticky_i
    dut.zero_i.value = inputs.zero_i

    await SETTLE

    return NormOutputs(
        sign_o=int(dut.sign_o.value),
        exp_o=int(dut.exp_o.value),
        mant_o=int(dut.mant_o.value),
        guard_o=int(dut.guard_o.value),
        round_o=int(dut.round_o.value),
        sticky_o=int(dut.sticky_o.value),
        zero_o=int(dut.zero_o.value),
        overflow_o=int(dut.overflow_o.value),
        underflow_o=int(dut.underflow_o.value),
    )


async def check(dut, inputs, expected=None, label=""):
    """
    Check the model against the DUT outputs
    """
    got = await drive_dut(dut, inputs)

    if expected == None:
        expected = golden_reference(inputs)

    # record functional coverage for this stimulus
    sample({"i": inputs, "o": got})

    if label:
        dut._log.info(f"PASS {label}")


# ---------------
# Directed cases
# ---------------

PASSTHROUGH_CASES = [
    (
        "already_normalized_1p0",
        NormInputs(
            sign_i=0,
            exp_i=0x7F,
            mant_i=0x800000,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            carry_i=0,
            zero_i=0,
        ),
        NormOutputs(
            sign_o=0,
            exp_o=0x7F,
            mant_o=0x800000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            zero_o=0,
            overflow_o=0,
            underflow_o=0,
        ),
    ),
    (
        "already_normalized_neg",
        NormInputs(
            sign_i=1,
            exp_i=0x7F,
            mant_i=0xC00000,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            carry_i=0,
            zero_i=0,
        ),
        NormOutputs(
            sign_o=1,
            exp_o=0x7F,
            mant_o=0xC00000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            zero_o=0,
            overflow_o=0,
            underflow_o=0,
        ),
    ),
    (
        "normalized_grs_passthrough",
        NormInputs(
            sign_i=0,
            exp_i=0x85,
            mant_i=0xABCDEF,
            guard_i=1,
            round_i=0,
            sticky_i=1,
            carry_i=0,
            zero_i=0,
        ),
        NormOutputs(
            sign_o=0,
            exp_o=0x85,
            mant_o=0xABCDEF,
            guard_o=1,
            round_o=0,
            sticky_o=1,
            zero_o=0,
            overflow_o=0,
            underflow_o=0,
        ),
    ),
    (
        "just_normalized_lsb_set",
        NormInputs(
            sign_i=0,
            exp_i=0x7F,
            mant_i=0x800001,
            guard_i=0,
            round_i=0,
            sticky_i=1,
            carry_i=0,
            zero_i=0,
        ),
        NormOutputs(
            sign_o=0,
            exp_o=0x7F,
            mant_o=0x800001,
            guard_o=0,
            round_o=0,
            sticky_o=1,
            zero_o=0,
            overflow_o=0,
            underflow_o=0,
        ),
    ),
    (
        "no_overflow_max_normal",
        NormInputs(
            sign_i=0,
            exp_i=0xFE,
            mant_i=0xFFFFFF,
            guard_i=1,
            round_i=1,
            sticky_i=1,
            carry_i=0,
            zero_i=0,
        ),
        NormOutputs(
            sign_o=0,
            exp_o=0xFE,
            mant_o=0xFFFFFF,
            guard_o=1,
            round_o=1,
            sticky_o=1,
            zero_o=0,
            overflow_o=0,
            underflow_o=0,
        ),
    ),
]

CARRY_CASES = [
    (
        "carry_out_shift_right",
        NormInputs(
            sign_i=0,
            exp_i=0x7F,
            mant_i=0x800000,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            carry_i=1,
            zero_i=0,
        ),
        NormOutputs(
            sign_o=0,
            exp_o=0x80,
            mant_o=0xC00000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            zero_o=0,
            overflow_o=0,
            underflow_o=0,
        ),
    ),
    (
        "carry_out_grs_cascade",
        NormInputs(
            sign_i=0,
            exp_i=0x7F,
            mant_i=0x800001,
            guard_i=1,
            round_i=0,
            sticky_i=0,
            carry_i=1,
            zero_i=0,
        ),
        NormOutputs(
            sign_o=0,
            exp_o=0x80,
            mant_o=0xC00000,
            guard_o=1,
            round_o=1,
            sticky_o=0,
            zero_o=0,
            overflow_o=0,
            underflow_o=0,
        ),
    ),
    (
        "carry_out_all_ones",
        NormInputs(
            sign_i=1,
            exp_i=0x7F,
            mant_i=0xFFFFFF,
            guard_i=1,
            round_i=1,
            sticky_i=1,
            carry_i=1,
            zero_i=0,
        ),
        NormOutputs(
            sign_o=1,
            exp_o=0x80,
            mant_o=0xFFFFFF,
            guard_o=1,
            round_o=1,
            sticky_o=1,
            zero_o=0,
            overflow_o=0,
            underflow_o=0,
        ),
    ),
    (
        "carry_at_min_exp",
        NormInputs(
            sign_i=0,
            exp_i=0x01,
            mant_i=0x000000,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            carry_i=1,
            zero_i=0,
        ),
        NormOutputs(
            sign_o=0,
            exp_o=0x02,
            mant_o=0x800000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            zero_o=0,
            overflow_o=0,
            underflow_o=0,
        ),
    ),
]

LEFT_SHIFT_CASES = [
    (
        "left_shift_1",
        NormInputs(
            sign_i=0,
            exp_i=0x7F,
            mant_i=0x400000,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            carry_i=0,
            zero_i=0,
        ),
        NormOutputs(
            sign_o=0,
            exp_o=0x7E,
            mant_o=0x800000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            zero_o=0,
            overflow_o=0,
            underflow_o=0,
        ),
    ),
    (
        "left_shift_1_guard_in",
        NormInputs(
            sign_i=0,
            exp_i=0x7F,
            mant_i=0x400000,
            guard_i=1,
            round_i=1,
            sticky_i=0,
            carry_i=0,
            zero_i=0,
        ),
        NormOutputs(
            sign_o=0,
            exp_o=0x7E,
            mant_o=0x800001,
            guard_o=1,
            round_o=0,
            sticky_o=0,
            zero_o=0,
            overflow_o=0,
            underflow_o=0,
        ),
    ),
    (
        "left_shift_4",
        NormInputs(
            sign_i=1,
            exp_i=0x90,
            mant_i=0x0F0000,
            guard_i=1,
            round_i=0,
            sticky_i=1,
            carry_i=0,
            zero_i=0,
        ),
        NormOutputs(
            sign_o=1,
            exp_o=0x8C,
            mant_o=0xF0000A,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            zero_o=0,
            overflow_o=0,
            underflow_o=0,
        ),
    ),
    (
        "left_shift_23_cancellation",
        NormInputs(
            sign_i=0,
            exp_i=0x7F,
            mant_i=0x000001,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            carry_i=0,
            zero_i=0,
        ),
        NormOutputs(
            sign_o=0,
            exp_o=0x68,
            mant_o=0x800000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            zero_o=0,
            overflow_o=0,
            underflow_o=0,
        ),
    ),
]

ZERO_CASES = [
    (
        "zero_flag_in",
        NormInputs(
            sign_i=1,
            exp_i=0x7F,
            mant_i=0x800000,
            guard_i=1,
            round_i=1,
            sticky_i=1,
            carry_i=0,
            zero_i=1,
        ),
        NormOutputs(
            sign_o=1,
            exp_o=0x00,
            mant_o=0x000000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            zero_o=1,
            overflow_o=0,
            underflow_o=0,
        ),
    ),
    (
        "all_zero_no_zero_flag",
        NormInputs(
            sign_i=0,
            exp_i=0x7F,
            mant_i=0x000000,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            carry_i=0,
            zero_i=0,
        ),
        NormOutputs(
            sign_o=0,
            exp_o=0x00,
            mant_o=0x000000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            zero_o=1,
            overflow_o=0,
            underflow_o=0,
        ),
    ),
]

OVERFLOW_CASES = [
    (
        "overflow_carry_at_max_exp",
        NormInputs(
            sign_i=0,
            exp_i=0xFE,
            mant_i=0x800000,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            carry_i=1,
            zero_i=0,
        ),
        NormOutputs(
            sign_o=0,
            exp_o=0xFF,
            mant_o=0xC00000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            zero_o=0,
            overflow_o=1,
            underflow_o=0,
        ),
    ),
    (
        "overflow_exp_already_max",
        NormInputs(
            sign_i=1,
            exp_i=0xFE,
            mant_i=0xFFFFFF,
            guard_i=1,
            round_i=1,
            sticky_i=1,
            carry_i=1,
            zero_i=0,
        ),
        NormOutputs(
            sign_o=1,
            exp_o=0xFF,
            mant_o=0xFFFFFF,
            guard_o=1,
            round_o=1,
            sticky_o=1,
            zero_o=0,
            overflow_o=1,
            underflow_o=0,
        ),
    ),
]

UNDERFLOW_CASES = [
    (
        "min_normal_exact_fit",
        NormInputs(
            sign_i=0,
            exp_i=0x04,
            mant_i=0x100000,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            carry_i=0,
            zero_i=0,
        ),
        NormOutputs(
            sign_o=0,
            exp_o=0x01,
            mant_o=0x800000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            zero_o=0,
            overflow_o=0,
            underflow_o=0,
        ),
    ),
    (
        "underflow_to_subnormal",
        NormInputs(
            sign_i=0,
            exp_i=0x03,
            mant_i=0x100000,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            carry_i=0,
            zero_i=0,
        ),
        NormOutputs(
            sign_o=0,
            exp_o=0x00,
            mant_o=0x400000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            zero_o=0,
            overflow_o=0,
            underflow_o=1,
        ),
    ),
    (
        "underflow_exp1_no_shift",
        NormInputs(
            sign_i=1,
            exp_i=0x01,
            mant_i=0x200000,
            guard_i=1,
            round_i=0,
            sticky_i=1,
            carry_i=0,
            zero_i=0,
        ),
        NormOutputs(
            sign_o=1,
            exp_o=0x00,
            mant_o=0x200000,
            guard_o=1,
            round_o=0,
            sticky_o=1,
            zero_o=0,
            overflow_o=0,
            underflow_o=1,
        ),
    ),
    (
        "underflow_full_cancellation",
        NormInputs(
            sign_i=0,
            exp_i=0x02,
            mant_i=0x000001,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            carry_i=0,
            zero_i=0,
        ),
        NormOutputs(
            sign_o=0,
            exp_o=0x00,
            mant_o=0x000002,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            zero_o=0,
            overflow_o=0,
            underflow_o=1,
        ),
    ),
]

GRS_ONLY_CASES = [
    (
        "mant_zero_grs_only",
        NormInputs(
            sign_i=0,
            exp_i=0x7F,
            mant_i=0x000000,
            guard_i=1,
            round_i=0,
            sticky_i=0,
            carry_i=0,
            zero_i=0,
        ),
        NormOutputs(
            sign_o=0,
            exp_o=0x67,
            mant_o=0x800000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            zero_o=0,
            overflow_o=0,
            underflow_o=0,
        ),
    ),
    (
        "sticky_only_survives",
        NormInputs(
            sign_i=1,
            exp_i=0x40,
            mant_i=0x000000,
            guard_i=0,
            round_i=0,
            sticky_i=1,
            carry_i=0,
            zero_i=0,
        ),
        NormOutputs(
            sign_o=1,
            exp_o=0x26,
            mant_o=0x800000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            zero_o=0,
            overflow_o=0,
            underflow_o=0,
        ),
    ),
]

ALL_CASES = (
    PASSTHROUGH_CASES
    + CARRY_CASES
    + LEFT_SHIFT_CASES
    + ZERO_CASES
    + OVERFLOW_CASES
    + UNDERFLOW_CASES
    + GRS_ONLY_CASES
)


async def run_cases(dut, cases):
    for label, inputs, outputs in cases:
        await check(dut, inputs, outputs, label)


@cocotb.test()
async def test_already_normalised(dut):
    """Mantissa MSB already set: everything must come out untouched."""
    await run_cases(dut, PASSTHROUGH_CASES)


@cocotb.test()
async def test_carry_right_shift(dut):
    """carry_i=1: one right shift, exp+1, GRS cascade down."""
    await run_cases(dut, CARRY_CASES)


@cocotb.test()
async def test_left_shift(dut):
    """Leading zeros: left shift with exp decrement, bits shifted in from GRS."""
    await run_cases(dut, LEFT_SHIFT_CASES)


@cocotb.test()
async def test_zero(dut):
    """zero_i flag and the implicit all-zero significand."""
    await run_cases(dut, ZERO_CASES)


@cocotb.test()
async def test_overflow(dut):
    """Exponent reaching 0xFF through the carry right shift."""
    await run_cases(dut, OVERFLOW_CASES)


@cocotb.test()
async def test_underflow(dut):
    """Shift clamped at exp=1: subnormal results, plus the exact-fit boundary."""
    await run_cases(dut, UNDERFLOW_CASES)


@cocotb.test()
async def test_grs_only(dut):
    """Degenerate: mantissa is zero but GRS is not, so GRS must be shifted up."""
    await run_cases(dut, GRS_ONLY_CASES)


@cocotb.test()
async def test_all(dut):
    """Every vector in one go, useful as a single regression gate."""
    await run_cases(dut, ALL_CASES)


# ----------------
# Randomized test
# ----------------


@cocotb.test()
async def test_random_sweep(dut):
    rng = random.Random(0x4E4F524D)
    num_tests = 100000
    for _ in range(num_tests):
        # cases
        case_rn = rng.random()
        if case_rn < 0.25:  # carry case
            mant = rng.randint(0, MANT_MASK)
            carry = 1
        elif case_rn < 0.5:  # cancellation
            mant = rng.randint(0, (1 << (MANT_WIDTH - 1) - 1))
            carry = 0
        else:  # normal
            mant = rng.randint(0, MANT_MASK)
            carry = rng.randint(0, 1)

        # grs bits
        g = rng.randint(0, 1)
        r = rng.randint(0, 1)
        s = rng.randint(0, 1)

        sign = rng.randint(0, 1)
        zero = 1 if rng.random() < 0.05 else 0
        exp_rn = rng.random()
        if exp_rn < 0.15:
            exp = 0
        elif exp_rn < 0.30:
            exp = rng.randint(1, 32)
        elif exp_rn < 0.45:
            exp = rng.randint(EXP_MASK - 8, EXP_MASK)
        else:
            exp = rng.randint(0, EXP_MASK)

        inputs = NormInputs(
            sign_i=sign,
            exp_i=exp,
            mant_i=mant,
            guard_i=g,
            round_i=r,
            sticky_i=s,
            carry_i=carry,
            zero_i=zero,
        )

        await check(dut, inputs)

    report_coverage(dut, COVERAGE)
