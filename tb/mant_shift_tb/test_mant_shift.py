"""
cocotb testbench for mant_shift.sv

DUT aligns the smaller mantissa and generates GRS bits.

Outputs:
    mant_o - shifted mantissa
    guard_o, round_o, sticky_o - rounding bits

Golden model:
    independent from RTL design
"""

import random
from dataclasses import dataclass

import cocotb
from cocotb.triggers import Timer
from cocotb_coverage.coverage import CoverCross, CoverPoint
from common.coverage_report import report_coverage

# from common.coverage_report import report_coverage

# ---------
# CONSTANTS
# ---------
SETTLE = Timer(1, unit="ns")
MANT_WIDTH = 24
MAX_SHIFT = 27
DIRECTED_CASES = [
    # (name, mant, shift, expected_out, G, R, S)
    ("zero shift", 0x800000, 0, 0x800000, 0, 0, 0),
    ("one shift (G=0)", 0x800000, 1, 0x400000, 0, 0, 0),
    ("one shift (G=1)", 0x800001, 1, 0x400000, 1, 0, 0),
    ("two shift (R=0)", 0x800000, 2, 0x200000, 0, 0, 0),
    ("two shift (R=1 only)", 0x800001, 2, 0x200000, 0, 1, 0),
    ("two shift (G=1,R=1)", 0x800003, 2, 0x200000, 1, 1, 0),
    ("three shift (S=0)", 0x800000, 3, 0x100000, 0, 0, 0),
    ("three shift (S=1 only)", 0x800001, 3, 0x100000, 0, 0, 1),
    ("three shift (G=R=S=1)", 0x80000F, 3, 0x100001, 1, 1, 1),
]

CORNER_CASES = [
    # zero mantissa: nothing to round, all flags must stay clear
    ("mant zero", 0x000000, 5, 0x000000, 0, 0, 0),
    # all ones: max ripple through the shifter
    ("all ones, shift 1", 0xFFFFFF, 1, 0x7FFFFF, 1, 0, 0),
    ("all ones, shift 3", 0xFFFFFF, 3, 0x1FFFFF, 1, 1, 1),
    # last shift where any bit survives in the result
    ("shift 23 (LSB alive)", 0x800000, 23, 0x000001, 0, 0, 0),
    # hidden bit falls into G: result is 0 but the value is NOT zero
    ("shift 24 (hidden->G)", 0x800000, 24, 0x000000, 1, 0, 0),
    ("shift 25 (hidden->R)", 0x800000, 25, 0x000000, 0, 1, 0),
    ("shift 26 (hidden->S)", 0x800000, 26, 0x000000, 0, 0, 1),
    # exact tie vs. tie broken by a far-away bit -> different rounding downstream
    ("tie at shift 24", 0x800000, 24, 0x000000, 1, 0, 0),
    ("tie broken by LSB", 0x800001, 24, 0x000000, 1, 0, 1),
    # sticky must be an OR of everything below R, not just one bit
    ("sticky from deep bit", 0x800004, 5, 0x040000, 0, 0, 1),
    ("alternating pattern", 0xAAAAAA, 5, 0x055555, 0, 1, 1),
    # subnormal-style operand: no hidden bit set
    ("no hidden bit", 0x000003, 1, 0x000001, 1, 0, 0),
    # saturation region: shift beyond the datapath width
    ("max shift", 0x800000, 31, 0x000000, 0, 0, 1),
    ("max shift, all ones", 0xFFFFFF, 31, 0x000000, 0, 0, 1),
]
COVERAGE = [
    "top.mant",
    "top.shift",
    "top.guard",
    "top.round",
    "top.sticky",
    "top.mant_x_shift",
]


# -------
# CLASSES
# -------
@dataclass
class MantShiftInputs:
    mant_i: int
    shift_i: int


@dataclass
class MantShiftOutputs:
    mant_o: int
    guard_o: int
    round_o: int
    sticky_o: int


# ---------
# FUNCTIONS
# ---------
# synchronous
def golden_reference(inputs: MantShiftInputs) -> MantShiftOutputs:
    """
    Independent reference model
    """

    # check that the received shift does not surpass the maximum
    shift = min(inputs.shift_i, MAX_SHIFT)

    wide = MANT_WIDTH + MAX_SHIFT

    padded = inputs.mant_i << MAX_SHIFT  # this is done so data is not lost
    result_shift = padded >> shift

    mask_wide = (1 << wide) - 1
    result_shift &= mask_wide

    shifted_mant = (result_shift >> MAX_SHIFT) & ((1 << MANT_WIDTH) - 1)
    guard_bit = (result_shift >> (MAX_SHIFT - 1)) & 1
    round_bit = (result_shift >> (MAX_SHIFT - 2)) & 1
    remainder_bits = result_shift & ((1 << MAX_SHIFT - 2) - 1)
    sticky_bit = 1 if remainder_bits != 0 else 0

    return MantShiftOutputs(
        mant_o=shifted_mant, guard_o=guard_bit, round_o=round_bit, sticky_o=sticky_bit
    )


# synchronous
async def drive_dut(dut, inputs):
    """
    Drive DUT inputs.
    """
    dut.mant_i.value = inputs.mant_i
    dut.shift_i.value = inputs.shift_i

    await SETTLE

    return MantShiftOutputs(
        mant_o=int(dut.mant_o.value),
        guard_o=int(dut.guard_o.value),
        round_o=int(dut.round_o.value),
        sticky_o=int(dut.sticky_o.value),
    )


async def check(dut, inputs, expected=None, label=""):
    """
    Compare the obtained and expected results.
    """

    got = await drive_dut(dut, inputs)
    if not expected:
        expected = golden_reference(inputs)

    assert got == expected, f"{label} got {got} expected {expected} [{inputs}]"

    sample({"i": inputs, "o": expected})

    if label:
        dut._log.info(f"PASS {label}")


# --------
# COVERAGE
# --------
MANT_BINS = [
    "ZERO",
    "B01",
    "B10",
    "B11",
    "B100",
    "B00",
    "ALL_ONES",
]

SHIFT_BINS = [
    "LOW (0-3)",
    "MID (4-23)",
    "HIGH (24-27)",
    "SATURATION",
]


def classify_mant(mant: int) -> str:
    if mant == 0x000000:
        return "ZERO"
    if mant == 0xFFFFFF:
        return "ALL_ONES"
    lsb = mant & 0x4
    if lsb == 0x1:
        return "GUARD"
    if lsb == 0x2:
        return "ROUND"
    if lsb == 0x3:
        return "STICKY"
    if lsb == 0x4:
        return "B100"
    return "B00"


def classify_shift(shift: int) -> str:
    if shift >= 0 and shift <= 3:
        return "LOW (0-3)"
    if shift >= 4 and shift <= 23:
        return "MID (4-23)"
    if shift >= 24 and shift <= 27:
        return "HIGH (24-27)"
    return "SATURATION"


@CoverPoint("top.mant", xf=lambda t: classify_mant(t["i"].mant_i), bins=MANT_BINS)
@CoverPoint("top.shift", xf=lambda t: classify_shift(t["i"].shift_i), bins=SHIFT_BINS)
@CoverPoint("top.guard", xf=lambda t: t["o"].guard_o, bins=[0, 1])
@CoverPoint("top.round", xf=lambda t: t["o"].round_o, bins=[0, 1])
@CoverPoint("top.sticky", xf=lambda t: t["o"].sticky_o, bins=[0, 1])
@CoverCross("top.mant_x_shift", items=["top.mant", "top.shift"])
def sample(t):
    pass


# --------------
# DIRECTED TESTS
# --------------
@cocotb.test()
async def test_direct_cases(dut):
    for name, mant_i, shift_i, mant_o, g_o, r_o, s_o in DIRECTED_CASES:
        inputs = MantShiftInputs(mant_i=mant_i, shift_i=shift_i)
        outputs = MantShiftOutputs(
            mant_o=mant_o,
            guard_o=g_o,
            round_o=r_o,
            sticky_o=s_o,
        )
        await check(dut, inputs, outputs, name)


@cocotb.test()
async def test_corner_cases(dut):
    for name, mant_i, shift_i, mant_o, g_o, r_o, s_o in CORNER_CASES:
        inputs = MantShiftInputs(mant_i=mant_i, shift_i=shift_i)
        outputs = MantShiftOutputs(
            mant_o=mant_o,
            guard_o=g_o,
            round_o=r_o,
            sticky_o=s_o,
        )
        await check(dut, inputs, outputs, name)


@cocotb.test()
async def test_all_shifts(dut):
    for shift in range(MAX_SHIFT + 1):
        inputs = MantShiftInputs(mant_i=0xFFFFFF, shift_i=shift)
        await check(dut, inputs)

    dut._log.info(f"PASS all_shifts.")


# --------------
# Random tests
# --------------
@cocotb.test()
async def test_random(dut):
    rng = random.Random(0xC0C0BABE)
    MAX_VAL = (1 << MANT_WIDTH) - 1
    NUM_TESTS = 10000
    for _ in range(NUM_TESTS):
        rmant = rng.random()
        if rmant < 0.2:
            mant = rng.choice([0x000000, 0x800000])
        elif rmant < 0.4:
            mant = rng.choice([0x000001, 0x800001])
        elif rmant < 0.6:
            mant = rng.randint(0, MAX_VAL)
        else:
            mant = rng.randint(0, MAX_VAL)
        shift = rng.randint(0, MAX_SHIFT)
        inputs = MantShiftInputs(mant_i=mant, shift_i=shift)
        await check(dut, inputs)

    dut._log.info(f"PASS random: {NUM_TESTS} tests match.")

    report_coverage(dut, COVERAGE)
