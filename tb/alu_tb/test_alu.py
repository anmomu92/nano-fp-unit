"""
cocotb testbench for alu.sv

DUT performs the arithmetic operation with the two significands.

Outputs:
    res_o - result of the arithmetic operation
    guard_o - guard bit
    round_o - round bit
    sticky_o - sticky bit

Notes:
    - golden_reference model done with AI.
    - the test fails when both mantissas are zero.
        TODO - study why
"""

import random
from dataclasses import dataclass

import cocotb
from cocotb.triggers import Timer
from cocotb_coverage.coverage import CoverCross, CoverPoint, coverage_db
from common.coverage_report import report_coverage

# ---------
# CONSTANTS
# ---------

SETTLE = Timer(1, unit="ns")

MANT_WIDTH = 24
EXT_WIDTH = MANT_WIDTH + 3
FULL_WIDTH = EXT_WIDTH + 1

MANT_MASK = (1 << MANT_WIDTH) - 1
EXT_MASK = (1 << EXT_WIDTH) - 1
FULL_MASK = (1 << FULL_WIDTH) - 1

COVERAGE = [
    # CoverPoints
    "top.sign_a",
    "top.sign_b",
    "top.mant_a",
    "top.mant_b",
    "top.op_code",
    "top.guard",
    "top.round",
    "top.sticky",
    "top.swap",
    "top.grs",
    "top.truth_table",
    "top.cmp",
    # CoverCrosses
    "top.sign_a_x_mant_a",
    "top.sign_b_x_mant_b",
    "top.op_code_x_swap",
]


# ---------------------------------------------------------------------------
# Directed cases — all reachable through exp_diff
# ---------------------------------------------------------------------------
DIRECTED_CASES = [
    (
        "add_pos_pos",  # name
        0,  # sign_a_i
        0,  # sign_b_i
        0x800000,  # mant_a_i
        0x400000,  # mant_b_i
        1,  # op_code_i
        0,  # guard_i
        0,  # round_i
        0,  # sticky_i
        0,  # swap_i
        0xC00000,  # res_o
        0,  # guard_o
        0,  # round_o
        0,  # sticky_o
        0,  # sign_o
        0,  # carry_o
    ),
    (
        "add_carry_out",  # name
        0,  # sign_a_i
        0,  # sign_b_i
        0xFFFFFF,  # mant_a_i
        0x000001,  # mant_b_i
        1,  # op_code_i
        0,  # guard_i
        0,  # round_i
        0,  # sticky_i
        0,  # swap_i
        0x000000,  # res_o
        0,  # guard_o
        0,  # round_o
        0,  # sticky_o
        0,  # sign_o
        1,  # carry_o
    ),
    (
        "sub_a_greater",  # name
        0,  # sign_a_i
        0,  # sign_b_i
        0xC00000,  # mant_a_i
        0x400000,  # mant_b_i
        0,  # op_code_i
        0,  # guard_i
        0,  # round_i
        0,  # sticky_i
        0,  # swap_i
        0x800000,  # res_o
        0,  # guard_o
        0,  # round_o
        0,  # sticky_o
        0,  # sign_o
        0,  # carry_o
    ),
    (
        "sub_b_greater_equal_exp",  # name
        0,  # sign_a_i
        0,  # sign_b_i
        0x800000,  # mant_a_i
        0xC00000,  # mant_b_i
        0,  # op_code_i
        0,  # guard_i
        0,  # round_i
        0,  # sticky_i
        0,  # swap_i
        0x400000,  # res_o
        0,  # guard_o
        0,  # round_o
        0,  # sticky_o
        1,  # sign_o
        0,  # carry_o
    ),
    (
        "sub_equal_gives_zero",  # name
        0,  # sign_a_i
        0,  # sign_b_i
        0x800000,  # mant_a_i
        0x800000,  # mant_b_i
        0,  # op_code_i
        0,  # guard_i
        0,  # round_i
        0,  # sticky_i
        0,  # swap_i
        0x000000,  # res_o
        0,  # guard_o
        0,  # round_o
        0,  # sticky_o
        0,  # sign_o
        0,  # carry_o
    ),
    (
        "add_neg_neg_carry",  # name
        1,  # sign_a_i
        1,  # sign_b_i
        0x800000,  # mant_a_i
        0x800000,  # mant_b_i
        1,  # op_code_i
        0,  # guard_i
        0,  # round_i
        0,  # sticky_i
        0,  # swap_i
        0x000000,  # res_o
        0,  # guard_o
        0,  # round_o
        0,  # sticky_o
        1,  # sign_o
        1,  # carry_o
    ),
    (
        "add_pos_neg_is_sub_mag",  # name
        0,  # sign_a_i
        1,  # sign_b_i
        0x900000,  # mant_a_i
        0x800000,  # mant_b_i
        1,  # op_code_i
        0,  # guard_i
        0,  # round_i
        0,  # sticky_i
        0,  # swap_i
        0x100000,  # res_o
        0,  # guard_o
        0,  # round_o
        0,  # sticky_o
        0,  # sign_o
        0,  # carry_o
    ),
    (
        "sub_pos_neg_is_add_mag",  # name
        0,  # sign_a_i
        1,  # sign_b_i
        0x800000,  # mant_a_i
        0x000001,  # mant_b_i
        0,  # op_code_i
        0,  # guard_i
        0,  # round_i
        0,  # sticky_i
        0,  # swap_i
        0x800001,  # res_o
        0,  # guard_o
        0,  # round_o
        0,  # sticky_o
        0,  # sign_o
        0,  # carry_o
    ),
    (
        "sub_neg_pos_is_add_mag",  # name
        1,  # sign_a_i
        0,  # sign_b_i
        0x800000,  # mant_a_i
        0x000001,  # mant_b_i
        0,  # op_code_i
        0,  # guard_i
        0,  # round_i
        0,  # sticky_i
        0,  # swap_i
        0x800001,  # res_o
        0,  # guard_o
        0,  # round_o
        0,  # sticky_o
        1,  # sign_o
        0,  # carry_o
    ),
    (
        "add_with_grs_passthrough",  # name
        0,  # sign_a_i
        0,  # sign_b_i
        0x800000,  # mant_a_i
        0x000001,  # mant_b_i
        1,  # op_code_i
        1,  # guard_i
        0,  # round_i
        1,  # sticky_i
        0,  # swap_i
        0x800001,  # res_o
        1,  # guard_o
        0,  # round_o
        1,  # sticky_o
        0,  # sign_o
        0,  # carry_o
    ),
    (
        "sub_grs_borrows_from_lsb",  # name
        0,  # sign_a_i
        0,  # sign_b_i
        0x800000,  # mant_a_i
        0x000000,  # mant_b_i
        0,  # op_code_i
        1,  # guard_i
        0,  # round_i
        0,  # sticky_i
        0,  # swap_i
        0x7FFFFF,  # res_o
        1,  # guard_o
        0,  # round_o
        0,  # sticky_o
        0,  # sign_o
        0,  # carry_o
    ),
    (
        "swap_sub_sign_from_b",  # name
        0,  # sign_a_i
        0,  # sign_b_i
        0x800000,  # mant_a_i
        0x400000,  # mant_b_i
        0,  # op_code_i
        0,  # guard_i
        0,  # round_i
        0,  # sticky_i
        1,  # swap_i
        0x400000,  # res_o
        0,  # guard_o
        0,  # round_o
        0,  # sticky_o
        1,  # sign_o
        0,  # carry_o
    ),
    (
        "swap_add_mixed_signs",  # name
        1,  # sign_a_i
        0,  # sign_b_i
        0x900000,  # mant_a_i
        0x480000,  # mant_b_i
        1,  # op_code_i
        0,  # guard_i
        0,  # round_i
        0,  # sticky_i
        1,  # swap_i
        0x480000,  # res_o
        0,  # guard_o
        0,  # round_o
        0,  # sticky_o
        0,  # sign_o
        0,  # carry_o
    ),
]


# ---------------------------------------------------------------------------
# Corner cases — all reachable through exp_diff
# ---------------------------------------------------------------------------
CORNER_CASES = [
    (
        "add_max_max",  # name
        0,  # sign_a_i
        0,  # sign_b_i
        0xFFFFFF,  # mant_a_i
        0xFFFFFF,  # mant_b_i
        1,  # op_code_i
        0,  # guard_i
        0,  # round_i
        0,  # sticky_i
        0,  # swap_i
        0xFFFFFE,  # res_o
        0,  # guard_o
        0,  # round_o
        0,  # sticky_o
        0,  # sign_o
        1,  # carry_o
    ),
    (
        "add_max_plus_shifted_max_grs",  # name
        0,  # sign_a_i
        0,  # sign_b_i
        0xFFFFFF,  # mant_a_i
        0x7FFFFF,  # mant_b_i
        1,  # op_code_i
        1,  # guard_i
        0,  # round_i
        0,  # sticky_i
        0,  # swap_i
        0x7FFFFE,  # res_o
        1,  # guard_o
        0,  # round_o
        0,  # sticky_o
        0,  # sign_o
        1,  # carry_o
    ),
    (
        "sub_max_minus_guard_only",  # name
        0,  # sign_a_i
        0,  # sign_b_i
        0xFFFFFF,  # mant_a_i
        0x000000,  # mant_b_i
        0,  # op_code_i
        1,  # guard_i
        0,  # round_i
        0,  # sticky_i
        0,  # swap_i
        0xFFFFFE,  # res_o
        1,  # guard_o
        0,  # round_o
        0,  # sticky_o
        0,  # sign_o
        0,  # carry_o
    ),
    (
        "sub_equal_exp_b_max",  # name
        0,  # sign_a_i
        0,  # sign_b_i
        0x800000,  # mant_a_i
        0xFFFFFF,  # mant_b_i
        0,  # op_code_i
        0,  # guard_i
        0,  # round_i
        0,  # sticky_i
        0,  # swap_i
        0x7FFFFF,  # res_o
        0,  # guard_o
        0,  # round_o
        0,  # sticky_o
        1,  # sign_o
        0,  # carry_o
    ),
    (
        "sub_sticky_only_borrow_ripple",  # name
        0,  # sign_a_i
        0,  # sign_b_i
        0x800000,  # mant_a_i
        0x000000,  # mant_b_i
        0,  # op_code_i
        0,  # guard_i
        0,  # round_i
        1,  # sticky_i
        0,  # swap_i
        0x7FFFFF,  # res_o
        1,  # guard_o
        1,  # round_o
        1,  # sticky_o
        0,  # sign_o
        0,  # carry_o
    ),
    (
        "add_neg_neg_carry_with_swap",  # name
        1,  # sign_a_i
        1,  # sign_b_i
        0xFFFFFF,  # mant_a_i
        0xFFFFFF,  # mant_b_i
        1,  # op_code_i
        0,  # guard_i
        0,  # round_i
        0,  # sticky_i
        1,  # swap_i
        0xFFFFFE,  # res_o
        0,  # guard_o
        0,  # round_o
        0,  # sticky_o
        1,  # sign_o
        1,  # carry_o
    ),
    (
        "swap_equal_exp_sub",  # name
        0,  # sign_a_i
        0,  # sign_b_i
        0x800000,  # mant_a_i
        0xC00000,  # mant_b_i
        0,  # op_code_i
        0,  # guard_i
        0,  # round_i
        0,  # sticky_i
        1,  # swap_i
        0x400000,  # res_o
        0,  # guard_o
        0,  # round_o
        0,  # sticky_o
        0,  # sign_o
        0,  # carry_o
    ),
]


# ---------------------------------------------------------------------------
# Unreachable cases — inputs that exp_diff can never produce for normalized
# operngs. Still useful to exercise the bare datapath in standalone tests.
# ---------------------------------------------------------------------------
UNREACHABLE_CASES = [
    (
        "sub_b_greater",  # name (mant_a denormalized)
        0,  # sign_a_i
        0,  # sign_b_i
        0x400000,  # mant_a_i
        0xC00000,  # mant_b_i
        0,  # op_code_i
        0,  # guard_i
        0,  # round_i
        0,  # sticky_i
        0,  # swap_i
        0x800000,  # res_o
        0,  # guard_o
        0,  # round_o
        0,  # sticky_o
        1,  # sign_o
        0,  # carry_o
    ),
    (
        "swap_neg_a_plus_pos_b",  # name (b=0 with GRS=000 -> zero operng)
        1,  # sign_a_i
        0,  # sign_b_i
        0x800000,  # mant_a_i
        0x000000,  # mant_b_i
        1,  # op_code_i
        0,  # guard_i
        0,  # round_i
        0,  # sticky_i
        1,  # swap_i
        0x800000,  # res_o
        0,  # guard_o
        0,  # round_o
        0,  # sticky_o
        0,  # sign_o
        0,  # carry_o
    ),
    (
        "all_zeros",  # name (mant_a denormalized)
        0,  # sign_a_i
        0,  # sign_b_i
        0x000000,  # mant_a_i
        0x000000,  # mant_b_i
        0,  # op_code_i
        0,  # guard_i
        0,  # round_i
        0,  # sticky_i
        0,  # swap_i
        0x000000,  # res_o
        0,  # guard_o
        0,  # round_o
        0,  # sticky_o
        0,  # sign_o
        0,  # carry_o
    ),
    (
        "add_max_max_grs_all_ones",  # name (GRS!=0 with shift 0)
        0,  # sign_a_i
        0,  # sign_b_i
        0xFFFFFF,  # mant_a_i
        0xFFFFFF,  # mant_b_i
        1,  # op_code_i
        1,  # guard_i
        1,  # round_i
        1,  # sticky_i
        0,  # swap_i
        0xFFFFFE,  # res_o
        1,  # guard_o
        1,  # round_o
        1,  # sticky_o
        0,  # sign_o
        1,  # carry_o
    ),
    (
        "sub_max_minus_zero",  # name (b=0 with GRS=000)
        0,  # sign_a_i
        0,  # sign_b_i
        0xFFFFFF,  # mant_a_i
        0x000000,  # mant_b_i
        0,  # op_code_i
        0,  # guard_i
        0,  # round_i
        0,  # sticky_i
        0,  # swap_i
        0xFFFFFF,  # res_o
        0,  # guard_o
        0,  # round_o
        0,  # sticky_o
        0,  # sign_o
        0,  # carry_o
    ),
    (
        "sub_zero_minus_max",  # name (mant_a denormalized)
        0,  # sign_a_i
        0,  # sign_b_i
        0x000000,  # mant_a_i
        0xFFFFFF,  # mant_b_i
        0,  # op_code_i
        0,  # guard_i
        0,  # round_i
        0,  # sticky_i
        0,  # swap_i
        0xFFFFFF,  # res_o
        0,  # guard_o
        0,  # round_o
        0,  # sticky_o
        1,  # sign_o
        0,  # carry_o
    ),
    (
        "sub_equal_neg_neg_zero",  # name (both denormalized)
        1,  # sign_a_i
        1,  # sign_b_i
        0x123456,  # mant_a_i
        0x123456,  # mant_b_i
        0,  # op_code_i
        0,  # guard_i
        0,  # round_i
        0,  # sticky_i
        0,  # swap_i
        0x000000,  # res_o
        0,  # guard_o
        0,  # round_o
        0,  # sticky_o
        0,  # sign_o
        0,  # carry_o
    ),
    (
        "sub_equal_only_sticky_differs",  # name (sticky with shift 0)
        0,  # sign_a_i
        0,  # sign_b_i
        0x800000,  # mant_a_i
        0x800000,  # mant_b_i
        0,  # op_code_i
        0,  # guard_i
        0,  # round_i
        1,  # sticky_i
        0,  # swap_i
        0x000000,  # res_o
        0,  # guard_o
        0,  # round_o
        1,  # sticky_o
        1,  # sign_o
        0,  # carry_o
    ),
    (
        "add_zero_plus_max_grs",  # name (mant_a=0, GRS with shift 0)
        0,  # sign_a_i
        0,  # sign_b_i
        0x000000,  # mant_a_i
        0xFFFFFF,  # mant_b_i
        1,  # op_code_i
        1,  # guard_i
        1,  # round_i
        1,  # sticky_i
        0,  # swap_i
        0xFFFFFF,  # res_o
        1,  # guard_o
        1,  # round_o
        1,  # sticky_o
        0,  # sign_o
        0,  # carry_o
    ),
    (
        "add_lsb_plus_lsb",  # name (mant_a denormalized)
        0,  # sign_a_i
        0,  # sign_b_i
        0x000001,  # mant_a_i
        0x000001,  # mant_b_i
        1,  # op_code_i
        0,  # guard_i
        0,  # round_i
        0,  # sticky_i
        0,  # swap_i
        0x000002,  # res_o
        0,  # guard_o
        0,  # round_o
        0,  # sticky_o
        0,  # sign_o
        0,  # carry_o
    ),
    (
        "sub_zero_minus_lsb",  # name (mant_a denormalized)
        0,  # sign_a_i
        0,  # sign_b_i
        0x000000,  # mant_a_i
        0x000001,  # mant_b_i
        0,  # op_code_i
        0,  # guard_i
        0,  # round_i
        0,  # sticky_i
        0,  # swap_i
        0x000001,  # res_o
        0,  # guard_o
        0,  # round_o
        0,  # sticky_o
        1,  # sign_o
        0,  # carry_o
    ),
    (
        "swap_sub_b_greater_in_mant_b",  # name (mant_a denormalized)
        0,  # sign_a_i
        0,  # sign_b_i
        0x400000,  # mant_a_i
        0x800000,  # mant_b_i
        0,  # op_code_i
        0,  # guard_i
        0,  # round_i
        0,  # sticky_i
        1,  # swap_i
        0x400000,  # res_o
        0,  # guard_o
        0,  # round_o
        0,  # sticky_o
        0,  # sign_o
        0,  # carry_o
    ),
]


# -------
# CLASSES
# -------
@dataclass
class AluInputs:
    sign_a_i: int
    sign_b_i: int
    mant_a_i: int
    mant_b_i: int
    op_code_i: int
    guard_i: int
    round_i: int
    sticky_i: int
    swap_i: int

    def __str__(self) -> str:
        return (
            f"\n\tsign_a_i={self.sign_a_i} \n"
            f"\tsign_b_i={self.sign_b_i} \n"
            f"\tmant_a_i=0x{self.mant_a_i:06x} \n"
            f"\tmant_b_i=0x{self.mant_b_i:06x} \n"
            f"\top_code_i={self.op_code_i} \n"
            f"\tguard_i={self.guard_i} \n"
            f"\tround_i={self.round_i} \n"
            f"\tsticky_i={self.sticky_i} \n"
            f"\tswap_i={self.swap_i} \n"
        )


@dataclass
class AluOutputs:
    sign_o: int
    res_o: int
    guard_o: int
    round_o: int
    sticky_o: int
    carry_o: int

    def __str__(self) -> str:
        return (
            f"\n\tsign_o={self.sign_o} \n"
            f"\tres_o=0x{self.res_o:06x} \n"
            f"\tguard_o={self.guard_o} \n"
            f"\tround_o={self.round_o} \n"
            f"\tsticky_o={self.sticky_o} \n"
            f"\tcarry_o={self.carry_o} \n"
        )


# ---------
# FUNCTIONS
# ---------
def golden_reference(inputs):
    """
    Independent golden reference model.
    """
    MANT_MASK = (1 << MANT_WIDTH) - 1

    # extended magnitudes: {mantissa, G, R, S}
    a_ext = (inputs.mant_a_i & MANT_MASK) << 3
    b_ext = (
        ((inputs.mant_b_i & MANT_MASK) << 3)
        | ((inputs.guard_i & 1) << 2)
        | ((inputs.round_i & 1) << 1)
        | (inputs.sticky_i & 1)
    )

    # effective signs of the two original operngs (B's sign flips on subtraction)
    eff_sign_a = inputs.sign_a_i & 1
    eff_sign_b = (inputs.sign_b_i & 1) ^ (1 - (inputs.op_code_i & 1))

    # associate signs with the operng actually sitting on mant_a / mant_b
    if inputs.swap_i:
        sign_first, sign_second = eff_sign_b, eff_sign_a
    else:
        sign_first, sign_second = eff_sign_a, eff_sign_b

    magnitude_add = (inputs.op_code_i ^ inputs.sign_a_i ^ inputs.sign_b_i) & 1

    if magnitude_add:
        total = a_ext + b_ext
        carry = (total >> (MANT_WIDTH + 3)) & 1
        res_ext = total & ((1 << (MANT_WIDTH + 3)) - 1)
        sign = sign_first  # both operngs share this sign
    else:
        carry = 0
        if a_ext >= b_ext:
            res_ext = a_ext - b_ext
            sign = sign_first
        else:
            res_ext = b_ext - a_ext
            sign = sign_second
        if res_ext == 0:
            sign = 0  # x - x = +0 (round-to-nearest)

    return AluOutputs(
        res_o=(res_ext >> 3) & MANT_MASK,
        guard_o=(res_ext >> 2) & 1,
        round_o=(res_ext >> 1) & 1,
        sticky_o=res_ext & 1,
        sign_o=sign,
        carry_o=carry,
    )


async def drive_dut(dut, inputs):
    """
    Drive DUT inputs
    """
    dut.sign_a_i.value = inputs.sign_a_i
    dut.sign_b_i.value = inputs.sign_b_i
    dut.mant_a_i.value = inputs.mant_a_i
    dut.mant_b_i.value = inputs.mant_b_i
    dut.op_code_i.value = inputs.op_code_i
    dut.guard_i.value = inputs.guard_i
    dut.round_i.value = inputs.round_i
    dut.sticky_i.value = inputs.sticky_i
    dut.swap_i.value = inputs.swap_i

    await SETTLE

    return AluOutputs(
        res_o=int(dut.res_o.value),
        guard_o=int(dut.guard_o.value),
        round_o=int(dut.round_o.value),
        sticky_o=int(dut.sticky_o.value),
        sign_o=int(dut.sign_o.value),
        carry_o=int(dut.carry_o.value),
    )


async def check(dut, inputs, expected=None, label=""):
    """
    Check the expected results against the DUT's ones.
    """
    # obtained values from the DUT
    got = await drive_dut(dut, inputs)
    # expected values from golden model
    if not expected:
        expected = golden_reference(inputs)

    carry_raw = int(dut.carry_raw.value)
    mag_add = int(dut.magnitude_add.value)
    op_code = int(dut.op_code_i.value)
    sign_b = int(dut.sign_b_i.value)
    eff_sign_b = int(dut.eff_sign_b.value)

    dut._log.info(f"CARRY_RAW = {carry_raw}")
    dut._log.info(f"MAG_ADD = {mag_add}")
    dut._log.info(f"OP = {op_code}")
    dut._log.info(f"SIGN_B = {sign_b}")
    dut._log.info(f"EFF_SIGN_B = {eff_sign_b}\n")

    assert got == expected, f"{label}:\n got {got} expected {expected} [{inputs}]"

    sample({"i": inputs, "o": expected})

    if label:
        dut._log.info(f"PASS: {label}")


# -------------------
# FUNCTIONAL COVERAGE
# -------------------

# bins
MANT_BINS = [
    "ZERO",
    "CTZ_0",
    "CTZ_1",
    "CTZ_2",
    "CTZ_3_11",
    "CTZ_12_22",
    "CTZ_23",
]

GRS_BINS = [
    "G0R0S0",
    "G0R0S1",
    "G0R1S0",
    "G0R1S1",
    "G1R0S0",
    "G1R0S1",
    "G1R1S0",
    "G1R1S1",
]

# The 8 rows of the truth table, encoded as (op, sign_a, sign_b)
TRUTH_TABLE_BINS = [
    "OP0_SA0_SB0",  # A - B      -> sub magnitudes, sign of greatest
    "OP0_SA0_SB1",  # A - (-B)   -> add magnitudes, sign 0
    "OP0_SA1_SB0",  # (-A) - B   -> add magnitudes, sign 1
    "OP0_SA1_SB1",  # (-A)-(-B)  -> sub magnitudes, sign of greatest
    "OP1_SA0_SB0",  # A + B      -> add magnitudes, sign 0
    "OP1_SA0_SB1",  # A + (-B)   -> sub magnitudes, sign of greatest
    "OP1_SA1_SB0",  # (-A) + B   -> sub magnitudes, sign of greatest
    "OP1_SA1_SB1",  # (-A)+(-B)  -> add magnitudes, sign 1
]

CMP_BINS = ["A_GT_B", "A_EQ_B", "A_LT_B"]


# functions
def classify_mant(mant: int) -> str:
    """
    Categorize the mantissa.
    CTZ_<amount-of-zero-bits> stands for Count of Trailing Zeros.
        - CTZ_1 means that there is one 0 below the first bit set.
    """
    if mant == 0x000000:
        return "ZERO"
    k = (mant & -mant).bit_length() - 1  # this finds the lowest bit set in the mantissa
    if k <= 2:
        return f"CTZ_{k}"
    if k <= 11:
        return "CTZ_3_11"
    if k <= 22:
        return "CTZ_12_22"
    return "CTZ_23"


def classify_grs(g: int, r: int, s: int) -> str:
    return f"G{g}R{r}S{s}"


def classify_truth_row(op: int, sa: int, sb: int) -> str:
    return f"OP{op}_SA{sa}_SB{sb}"


def classify_cmp(inp) -> str:
    """
    Outcome of the magnitude comparison on the extended values
    {mantissa, G, R, S} — the quantity that drives the sign mux
    and the borrow direction in subtract mode.
    mant_a has implicit GRS = 000.
    """
    a_ext = inp.mant_a_i << 3
    b_ext = (inp.mant_b_i << 3) | (inp.guard_i << 2) | (inp.round_i << 1) | inp.sticky_i
    if a_ext > b_ext:
        return "A_GT_B"
    if a_ext == b_ext:
        return "A_EQ_B"
    return "A_LT_B"


# coverpoints
@CoverPoint("top.sign_a", xf=lambda t: t["i"].sign_a_i, bins=[0, 1])
@CoverPoint("top.sign_b", xf=lambda t: t["i"].sign_b_i, bins=[0, 1])
@CoverPoint("top.mant_a", xf=lambda t: classify_mant(t["i"].mant_a_i), bins=MANT_BINS)
@CoverPoint("top.mant_b", xf=lambda t: classify_mant(t["i"].mant_b_i), bins=MANT_BINS)
@CoverPoint("top.op_code", xf=lambda t: t["i"].op_code_i, bins=[0, 1])
@CoverPoint("top.guard", xf=lambda t: t["i"].guard_i, bins=[0, 1])
@CoverPoint("top.round", xf=lambda t: t["i"].round_i, bins=[0, 1])
@CoverPoint("top.sticky", xf=lambda t: t["i"].sticky_i, bins=[0, 1])
@CoverPoint("top.swap", xf=lambda t: t["i"].swap_i, bins=[0, 1])
@CoverPoint(
    "top.grs",
    xf=lambda t: classify_grs(t["o"].guard_o, t["o"].round_o, t["o"].sticky_o),
    bins=GRS_BINS,
)
@CoverPoint("top.cmp", xf=lambda t: classify_cmp(t["i"]), bins=CMP_BINS)
@CoverPoint(
    "top.truth_table",
    xf=lambda t: classify_truth_row(t["i"].op_code_i, t["i"].sign_a_i, t["i"].sign_b_i),
    bins=TRUTH_TABLE_BINS,
)
@CoverCross("top.sign_a_x_mant_a", items=["top.sign_a", "top.mant_a"])
@CoverCross("top.sign_b_x_mant_b", items=["top.sign_b", "top.mant_b"])
@CoverCross("top.mant_x_grs", items=["top.mant_b", "top.grs"])
@CoverCross("top.op_code_x_swap", items=["top.op_code", "top.swap"])
def sample(t):
    pass


# --------------
# DIRECTED TESTS
# --------------
@cocotb.test()
async def test_directed_cases(dut):
    for (
        name,
        sa,
        sb,
        ma,
        mb,
        op,
        g_i,
        r_i,
        s_i,
        swap,
        res,
        g_o,
        r_o,
        s_o,
        s,
        c,
    ) in DIRECTED_CASES:
        inputs = AluInputs(
            sign_a_i=sa,
            sign_b_i=sb,
            mant_a_i=ma,
            mant_b_i=mb,
            op_code_i=op,
            guard_i=g_i,
            round_i=r_i,
            sticky_i=s_i,
            swap_i=swap,
        )
        outputs = AluOutputs(
            res_o=res, guard_o=g_o, round_o=r_o, sticky_o=s_o, sign_o=s, carry_o=c
        )

        await check(dut, inputs, expected=outputs, label=name)


@cocotb.test()
async def test_corner_cases(dut):
    for (
        name,
        sa,
        sb,
        ma,
        mb,
        op,
        g_i,
        r_i,
        s_i,
        swap,
        res,
        g_o,
        r_o,
        s_o,
        s,
        c,
    ) in CORNER_CASES:
        inputs = AluInputs(
            sign_a_i=sa,
            sign_b_i=sb,
            mant_a_i=ma,
            mant_b_i=mb,
            op_code_i=op,
            guard_i=g_i,
            round_i=r_i,
            sticky_i=s_i,
            swap_i=swap,
        )
        outputs = AluOutputs(
            res_o=res, guard_o=g_o, round_o=r_o, sticky_o=s_o, sign_o=s, carry_o=c
        )

        await check(dut, inputs, expected=outputs, label=name)


# -----------------
# Random tests
# -----------------
@cocotb.test()
async def test_random(dut):
    rng = random.Random(0xC0C0BABE)
    MAX_VAL = (1 << MANT_WIDTH) - 1
    NUM_TESTS = 10000
    for i in range(NUM_TESTS):
        for op in (0, 1):
            for sign_a in (0, 1):
                for sign_b in (0, 1):
                    for swap in (0, 1):
                        # mantissa a
                        # uncomment to increase ZERO chance
                        # ma_rng = rng.random()
                        # if ma_rng < 0.1:
                        #     mant_a = 0
                        # else:
                        #     mant_a = rng.randint(0, MAX_VAL)

                        # # mantissa b
                        # mb_rng = rng.random()
                        # if mb_rng < 0.1:
                        #     mant_b = 0
                        # else:
                        #     mant_b = rng.randint(0, MAX_VAL)

                        mant_a = rng.randint(0, MAX_VAL)
                        mant_b = rng.randint(0, MAX_VAL)

                        # grs bits
                        g = rng.randint(0, 1)
                        r = rng.randint(0, 1)
                        s = rng.randint(0, 1)

                        # inputs
                        inputs = AluInputs(
                            sign_a_i=sign_a,
                            sign_b_i=sign_b,
                            mant_a_i=mant_a,
                            mant_b_i=mant_b,
                            op_code_i=op,
                            guard_i=g,
                            round_i=r,
                            sticky_i=s,
                            swap_i=swap,
                        )

                        await check(dut, inputs)

    dut._log.info(f"PASS random: {NUM_TESTS} tests match.")

    report_coverage(dut, COVERAGE)
