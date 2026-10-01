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
    zero_o: int

    def __str__(self) -> str:
        return (
            f"\n\tsign_o={self.sign_o} \n"
            f"\tres_o=0x{self.res_o:06x} \n"
            f"\tguard_o={self.guard_o} \n"
            f"\tround_o={self.round_o} \n"
            f"\tsticky_o={self.sticky_o} \n"
            f"\tcarry_o={self.carry_o} \n"
            f"\tzero_o={self.zero_o} \n"
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

    if (
        ((res_ext >> 3) & MANT_MASK)
        or ((res_ext >> 2) & 1)
        or ((res_ext >> 1) & 1)
        or (res_ext & 1)
        or carry
    ):
        zero = 0
    else:
        zero = 1

    return AluOutputs(
        res_o=(res_ext >> 3) & MANT_MASK,
        guard_o=(res_ext >> 2) & 1,
        round_o=(res_ext >> 1) & 1,
        sticky_o=res_ext & 1,
        sign_o=sign,
        carry_o=carry,
        zero_o=zero,
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
        zero_o=int(dut.zero_o.value),
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

    # carry_raw = int(dut.carry_raw.value)
    # mag_add = int(dut.magnitude_add.value)
    # op_code = int(dut.op_code_i.value)
    # sign_b = int(dut.sign_b_i.value)
    # eff_sign_b = int(dut.eff_sign_b.value)

    # dut._log.info(f"CARRY_RAW = {carry_raw}")
    # dut._log.info(f"MAG_ADD = {mag_add}")
    # dut._log.info(f"OP = {op_code}")
    # dut._log.info(f"SIGN_B = {sign_b}")
    # dut._log.info(f"EFF_SIGN_B = {eff_sign_b}\n")

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
# ---------------------------------------------------------------------------
# Directed cases — all reachable through exp_diff
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Directed cases — all reachable through exp_diff
# ---------------------------------------------------------------------------
DIRECTED_CASES = [
    (
        "add_pos_pos",
        AluInputs(
            sign_a_i=0,
            sign_b_i=0,
            mant_a_i=0x800000,
            mant_b_i=0x400000,
            op_code_i=1,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=0,
            res_o=0xC00000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            carry_o=0,
            zero_o=0,
        ),
    ),
    (
        "add_carry_out",
        AluInputs(
            sign_a_i=0,
            sign_b_i=0,
            mant_a_i=0xFFFFFF,
            mant_b_i=0x000001,
            op_code_i=1,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=0,
            res_o=0x000000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            carry_o=1,
            zero_o=0,
        ),
    ),
    (
        "sub_a_greater",
        AluInputs(
            sign_a_i=0,
            sign_b_i=0,
            mant_a_i=0xC00000,
            mant_b_i=0x400000,
            op_code_i=0,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=0,
            res_o=0x800000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            carry_o=0,
            zero_o=0,
        ),
    ),
    (
        "sub_b_greater_equal_exp",
        AluInputs(
            sign_a_i=0,
            sign_b_i=0,
            mant_a_i=0x800000,
            mant_b_i=0xC00000,
            op_code_i=0,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=1,
            res_o=0x400000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            carry_o=0,
            zero_o=0,
        ),
    ),
    (
        "sub_equal_gives_zero",
        AluInputs(
            sign_a_i=0,
            sign_b_i=0,
            mant_a_i=0x800000,
            mant_b_i=0x800000,
            op_code_i=0,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=0,
            res_o=0x000000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            carry_o=0,
            zero_o=1,
        ),
    ),
    (
        "add_neg_neg_carry",
        AluInputs(
            sign_a_i=1,
            sign_b_i=1,
            mant_a_i=0x800000,
            mant_b_i=0x800000,
            op_code_i=1,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=1,
            res_o=0x000000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            carry_o=1,
            zero_o=0,
        ),
    ),
    (
        "add_pos_neg_is_sub_mag",
        AluInputs(
            sign_a_i=0,
            sign_b_i=1,
            mant_a_i=0x900000,
            mant_b_i=0x800000,
            op_code_i=1,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=0,
            res_o=0x100000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            carry_o=0,
            zero_o=0,
        ),
    ),
    (
        "sub_pos_neg_is_add_mag",
        AluInputs(
            sign_a_i=0,
            sign_b_i=1,
            mant_a_i=0x800000,
            mant_b_i=0x000001,
            op_code_i=0,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=0,
            res_o=0x800001,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            carry_o=0,
            zero_o=0,
        ),
    ),
    (
        "sub_neg_pos_is_add_mag",
        AluInputs(
            sign_a_i=1,
            sign_b_i=0,
            mant_a_i=0x800000,
            mant_b_i=0x000001,
            op_code_i=0,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=1,
            res_o=0x800001,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            carry_o=0,
            zero_o=0,
        ),
    ),
    (
        "add_with_grs_passthrough",
        AluInputs(
            sign_a_i=0,
            sign_b_i=0,
            mant_a_i=0x800000,
            mant_b_i=0x000001,
            op_code_i=1,
            guard_i=1,
            round_i=0,
            sticky_i=1,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=0,
            res_o=0x800001,
            guard_o=1,
            round_o=0,
            sticky_o=1,
            carry_o=0,
            zero_o=0,
        ),
    ),
    (
        "sub_grs_borrows_from_lsb",
        AluInputs(
            sign_a_i=0,
            sign_b_i=0,
            mant_a_i=0x800000,
            mant_b_i=0x000000,
            op_code_i=0,
            guard_i=1,
            round_i=0,
            sticky_i=0,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=0,
            res_o=0x7FFFFF,
            guard_o=1,
            round_o=0,
            sticky_o=0,
            carry_o=0,
            zero_o=0,
        ),
    ),
    (
        "swap_sub_sign_from_b",
        AluInputs(
            sign_a_i=0,
            sign_b_i=0,
            mant_a_i=0x800000,
            mant_b_i=0x400000,
            op_code_i=0,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            swap_i=1,
        ),
        AluOutputs(
            sign_o=1,
            res_o=0x400000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            carry_o=0,
            zero_o=0,
        ),
    ),
    (
        "swap_add_mixed_signs",
        AluInputs(
            sign_a_i=1,
            sign_b_i=0,
            mant_a_i=0x900000,
            mant_b_i=0x480000,
            op_code_i=1,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            swap_i=1,
        ),
        AluOutputs(
            sign_o=0,
            res_o=0x480000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            carry_o=0,
            zero_o=0,
        ),
    ),
]


# ---------------------------------------------------------------------------
# Corner cases — all reachable through exp_diff
# ---------------------------------------------------------------------------
CORNER_CASES = [
    (
        "add_max_max",
        AluInputs(
            sign_a_i=0,
            sign_b_i=0,
            mant_a_i=0xFFFFFF,
            mant_b_i=0xFFFFFF,
            op_code_i=1,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=0,
            res_o=0xFFFFFE,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            carry_o=1,
            zero_o=0,
        ),
    ),
    (
        "add_max_plus_shifted_max_grs",
        AluInputs(
            sign_a_i=0,
            sign_b_i=0,
            mant_a_i=0xFFFFFF,
            mant_b_i=0x7FFFFF,
            op_code_i=1,
            guard_i=1,
            round_i=0,
            sticky_i=0,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=0,
            res_o=0x7FFFFE,
            guard_o=1,
            round_o=0,
            sticky_o=0,
            carry_o=1,
            zero_o=0,
        ),
    ),
    (
        "sub_max_minus_guard_only",
        AluInputs(
            sign_a_i=0,
            sign_b_i=0,
            mant_a_i=0xFFFFFF,
            mant_b_i=0x000000,
            op_code_i=0,
            guard_i=1,
            round_i=0,
            sticky_i=0,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=0,
            res_o=0xFFFFFE,
            guard_o=1,
            round_o=0,
            sticky_o=0,
            carry_o=0,
            zero_o=0,
        ),
    ),
    (
        "sub_equal_exp_b_max",
        AluInputs(
            sign_a_i=0,
            sign_b_i=0,
            mant_a_i=0x800000,
            mant_b_i=0xFFFFFF,
            op_code_i=0,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=1,
            res_o=0x7FFFFF,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            carry_o=0,
            zero_o=0,
        ),
    ),
    (
        "sub_sticky_only_borrow_ripple",
        AluInputs(
            sign_a_i=0,
            sign_b_i=0,
            mant_a_i=0x800000,
            mant_b_i=0x000000,
            op_code_i=0,
            guard_i=0,
            round_i=0,
            sticky_i=1,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=0,
            res_o=0x7FFFFF,
            guard_o=1,
            round_o=1,
            sticky_o=1,
            carry_o=0,
            zero_o=0,
        ),
    ),
    (
        "add_neg_neg_carry_with_swap",
        AluInputs(
            sign_a_i=1,
            sign_b_i=1,
            mant_a_i=0xFFFFFF,
            mant_b_i=0xFFFFFF,
            op_code_i=1,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            swap_i=1,
        ),
        AluOutputs(
            sign_o=1,
            res_o=0xFFFFFE,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            carry_o=1,
            zero_o=0,
        ),
    ),
    (
        "swap_equal_exp_sub",
        AluInputs(
            sign_a_i=0,
            sign_b_i=0,
            mant_a_i=0x800000,
            mant_b_i=0xC00000,
            op_code_i=0,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            swap_i=1,
        ),
        AluOutputs(
            sign_o=0,
            res_o=0x400000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            carry_o=0,
            zero_o=0,
        ),
    ),
]


# ---------------------------------------------------------------------------
# Unreachable cases — inputs that exp_diff can never produce for normalized
# operands. Still useful to exercise the bare datapath in standalone tests.
# ---------------------------------------------------------------------------
UNREACHABLE_CASES = [
    (
        "sub_b_greater",  # mant_a denormalized
        AluInputs(
            sign_a_i=0,
            sign_b_i=0,
            mant_a_i=0x400000,
            mant_b_i=0xC00000,
            op_code_i=0,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=1,
            res_o=0x800000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            carry_o=0,
            zero_o=0,
        ),
    ),
    (
        "swap_neg_a_plus_pos_b",  # b=0 with GRS=000 -> zero operng
        AluInputs(
            sign_a_i=1,
            sign_b_i=0,
            mant_a_i=0x800000,
            mant_b_i=0x000000,
            op_code_i=1,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            swap_i=1,
        ),
        AluOutputs(
            sign_o=0,
            res_o=0x800000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            carry_o=0,
            zero_o=0,
        ),
    ),
    (
        "all_zeros",  # mant_a denormalized
        AluInputs(
            sign_a_i=0,
            sign_b_i=0,
            mant_a_i=0x000000,
            mant_b_i=0x000000,
            op_code_i=0,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=0,
            res_o=0x000000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            carry_o=0,
            zero_o=1,
        ),
    ),
    (
        "add_max_max_grs_all_ones",  # GRS!=0 with shift 0
        AluInputs(
            sign_a_i=0,
            sign_b_i=0,
            mant_a_i=0xFFFFFF,
            mant_b_i=0xFFFFFF,
            op_code_i=1,
            guard_i=1,
            round_i=1,
            sticky_i=1,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=0,
            res_o=0xFFFFFE,
            guard_o=1,
            round_o=1,
            sticky_o=1,
            carry_o=1,
            zero_o=0,
        ),
    ),
    (
        "sub_max_minus_zero",  # b=0 with GRS=000
        AluInputs(
            sign_a_i=0,
            sign_b_i=0,
            mant_a_i=0xFFFFFF,
            mant_b_i=0x000000,
            op_code_i=0,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=0,
            res_o=0xFFFFFF,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            carry_o=0,
            zero_o=0,
        ),
    ),
    (
        "sub_zero_minus_max",  # mant_a denormalized
        AluInputs(
            sign_a_i=0,
            sign_b_i=0,
            mant_a_i=0x000000,
            mant_b_i=0xFFFFFF,
            op_code_i=0,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=1,
            res_o=0xFFFFFF,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            carry_o=0,
            zero_o=0,
        ),
    ),
    (
        "sub_equal_neg_neg_zero",  # both denormalized
        AluInputs(
            sign_a_i=1,
            sign_b_i=1,
            mant_a_i=0x123456,
            mant_b_i=0x123456,
            op_code_i=0,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=0,
            res_o=0x000000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            carry_o=0,
            zero_o=1,
        ),
    ),
    (
        "sub_equal_only_sticky_differs",  # sticky with shift 0
        AluInputs(
            sign_a_i=0,
            sign_b_i=0,
            mant_a_i=0x800000,
            mant_b_i=0x800000,
            op_code_i=0,
            guard_i=0,
            round_i=0,
            sticky_i=1,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=1,
            res_o=0x000000,
            guard_o=0,
            round_o=0,
            sticky_o=1,
            carry_o=0,
            zero_o=0,
        ),
    ),
    (
        "add_zero_plus_max_grs",  # mant_a=0, GRS with shift 0
        AluInputs(
            sign_a_i=0,
            sign_b_i=0,
            mant_a_i=0x000000,
            mant_b_i=0xFFFFFF,
            op_code_i=1,
            guard_i=1,
            round_i=1,
            sticky_i=1,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=0,
            res_o=0xFFFFFF,
            guard_o=1,
            round_o=1,
            sticky_o=1,
            carry_o=0,
            zero_o=0,
        ),
    ),
    (
        "add_lsb_plus_lsb",  # mant_a denormalized
        AluInputs(
            sign_a_i=0,
            sign_b_i=0,
            mant_a_i=0x000001,
            mant_b_i=0x000001,
            op_code_i=1,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=0,
            res_o=0x000002,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            carry_o=0,
            zero_o=0,
        ),
    ),
    (
        "sub_zero_minus_lsb",  # mant_a denormalized
        AluInputs(
            sign_a_i=0,
            sign_b_i=0,
            mant_a_i=0x000000,
            mant_b_i=0x000001,
            op_code_i=0,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            swap_i=0,
        ),
        AluOutputs(
            sign_o=1,
            res_o=0x000001,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            carry_o=0,
            zero_o=0,
        ),
    ),
    (
        "swap_sub_b_greater_in_mant_b",  # mant_a denormalized
        AluInputs(
            sign_a_i=0,
            sign_b_i=0,
            mant_a_i=0x400000,
            mant_b_i=0x800000,
            op_code_i=0,
            guard_i=0,
            round_i=0,
            sticky_i=0,
            swap_i=1,
        ),
        AluOutputs(
            sign_o=0,
            res_o=0x400000,
            guard_o=0,
            round_o=0,
            sticky_o=0,
            carry_o=0,
            zero_o=0,
        ),
    ),
]

ALL_CASES = DIRECTED_CASES + CORNER_CASES + UNREACHABLE_CASES


async def run_cases(dut, cases):
    for label, inputs, outputs in cases:
        await check(dut, inputs, outputs, label)


@cocotb.test()
async def test_direct_cases(dut):
    """Test all direct cases.

    Args:
        dut: handle to the design under test.
    """
    await run_cases(dut, ALL_CASES)


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
