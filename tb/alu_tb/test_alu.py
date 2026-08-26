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
"""

import random
from dataclasses import dataclass

import cocotb
from cocotb.triggers import Timer

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

# directed cases
DIRECTED_CASES = [
    # name,                      sa, sb, mant_a,   mant_b,   op, g, r, s, swap,  res,      g, r, s, sign, carry
    ("add_pos_pos", 0, 0, 0x800000, 0x400000, 1, 0, 0, 0, 0, 0xC00000, 0, 0, 0, 0, 0),
    ("add_carry_out", 0, 0, 0xFFFFFF, 0x000001, 1, 0, 0, 0, 0, 0x000000, 0, 0, 0, 0, 1),
    ("sub_a_greater", 0, 0, 0xC00000, 0x400000, 0, 0, 0, 0, 0, 0x800000, 0, 0, 0, 0, 0),
    (
        "sub_b_greater_equal_exp",
        0,
        0,
        0x800000,
        0xC00000,
        0,
        0,
        0,
        0,
        0,
        0x400000,
        0,
        0,
        0,
        1,
        0,
    ),
    (
        "sub_equal_gives_zero",
        0,
        0,
        0x800000,
        0x800000,
        0,
        0,
        0,
        0,
        0,
        0x000000,
        0,
        0,
        0,
        0,
        0,
    ),
    (
        "add_neg_neg_carry",
        1,
        1,
        0x800000,
        0x800000,
        1,
        0,
        0,
        0,
        0,
        0x000000,
        0,
        0,
        0,
        1,
        1,
    ),
    (
        "add_pos_neg_is_sub_mag",
        0,
        1,
        0x900000,
        0x800000,
        1,
        0,
        0,
        0,
        0,
        0x100000,
        0,
        0,
        0,
        0,
        0,
    ),
    (
        "sub_pos_neg_is_add_mag",
        0,
        1,
        0x800000,
        0x000001,
        0,
        0,
        0,
        0,
        0,
        0x800001,
        0,
        0,
        0,
        0,
        0,
    ),
    (
        "sub_neg_pos_is_add_mag",
        1,
        0,
        0x800000,
        0x000001,
        0,
        0,
        0,
        0,
        0,
        0x800001,
        0,
        0,
        0,
        1,
        0,
    ),
    (
        "add_with_grs_passthrough",
        0,
        0,
        0x800000,
        0x000001,
        1,
        1,
        0,
        1,
        0,
        0x800001,
        1,
        0,
        1,
        0,
        0,
    ),
    (
        "sub_grs_borrows_from_lsb",
        0,
        0,
        0x800000,
        0x000000,
        0,
        1,
        0,
        0,
        0,
        0x7FFFFF,
        1,
        0,
        0,
        0,
        0,
    ),
    (
        "swap_sub_sign_from_b",
        0,
        0,
        0x800000,
        0x400000,
        0,
        0,
        0,
        0,
        1,
        0x400000,
        0,
        0,
        0,
        1,
        0,
    ),
    (
        "swap_add_mixed_signs",
        1,
        0,
        0x900000,
        0x480000,
        1,
        0,
        0,
        0,
        1,
        0x480000,
        0,
        0,
        0,
        0,
        0,
    ),
]

# corner cases
CORNER_CASES = [
    # name,                           sa, sb, mant_a,   mant_b,   op, g, r, s, swap,  res,      g, r, s, sign, carry
    ("add_max_max", 0, 0, 0xFFFFFF, 0xFFFFFF, 1, 0, 0, 0, 0, 0xFFFFFE, 0, 0, 0, 0, 1),
    (
        "add_max_plus_shifted_max_grs",
        0,
        0,
        0xFFFFFF,
        0x7FFFFF,
        1,
        1,
        0,
        0,
        0,
        0x7FFFFE,
        1,
        0,
        0,
        0,
        1,
    ),
    (
        "sub_max_minus_guard_only",
        0,
        0,
        0xFFFFFF,
        0x000000,
        0,
        1,
        0,
        0,
        0,
        0xFFFFFE,
        1,
        0,
        0,
        0,
        0,
    ),
    (
        "sub_equal_exp_b_max",
        0,
        0,
        0x800000,
        0xFFFFFF,
        0,
        0,
        0,
        0,
        0,
        0x7FFFFF,
        0,
        0,
        0,
        1,
        0,
    ),
    (
        "sub_sticky_only_borrow_ripple",
        0,
        0,
        0x800000,
        0x000000,
        0,
        0,
        0,
        1,
        0,
        0x7FFFFF,
        1,
        1,
        1,
        0,
        0,
    ),
    (
        "add_neg_neg_carry_with_swap",
        1,
        1,
        0xFFFFFF,
        0xFFFFFF,
        1,
        0,
        0,
        0,
        1,
        0xFFFFFE,
        0,
        0,
        0,
        1,
        1,
    ),
    (
        "swap_equal_exp_sub",
        0,
        0,
        0x800000,
        0xC00000,
        0,
        0,
        0,
        0,
        1,
        0x400000,
        0,
        0,
        0,
        0,
        0,
    ),
]

# unreachable cases
UNREACHABLE_CASES = [
    # name,                           sa, sb, mant_a,   mant_b,   op, g, r, s, swap,  res,      g, r, s, sign, carry
    (
        "sub_b_greater",
        0,
        0,
        0x400000,
        0xC00000,
        0,
        0,
        0,
        0,
        0,
        0x800000,
        0,
        0,
        0,
        1,
        0,
    ),  # mant_a denormalized
    (
        "swap_neg_a_plus_pos_b",
        1,
        0,
        0x800000,
        0x000000,
        1,
        0,
        0,
        0,
        1,
        0x800000,
        0,
        0,
        0,
        0,
        0,
    ),  # b=0 with GRS=000 -> zero operand
    (
        "all_zeros",
        0,
        0,
        0x000000,
        0x000000,
        0,
        0,
        0,
        0,
        0,
        0x000000,
        0,
        0,
        0,
        0,
        0,
    ),  # mant_a denormalized
    (
        "add_max_max_grs_all_ones",
        0,
        0,
        0xFFFFFF,
        0xFFFFFF,
        1,
        1,
        1,
        1,
        0,
        0xFFFFFE,
        1,
        1,
        1,
        0,
        1,
    ),  # GRS!=0 with shift 0
    (
        "sub_max_minus_zero",
        0,
        0,
        0xFFFFFF,
        0x000000,
        0,
        0,
        0,
        0,
        0,
        0xFFFFFF,
        0,
        0,
        0,
        0,
        0,
    ),  # b=0 with GRS=000
    (
        "sub_zero_minus_max",
        0,
        0,
        0x000000,
        0xFFFFFF,
        0,
        0,
        0,
        0,
        0,
        0xFFFFFF,
        0,
        0,
        0,
        1,
        0,
    ),  # mant_a denormalized
    (
        "sub_equal_neg_neg_zero",
        1,
        1,
        0x123456,
        0x123456,
        0,
        0,
        0,
        0,
        0,
        0x000000,
        0,
        0,
        0,
        0,
        0,
    ),  # both denormalized
    (
        "sub_equal_only_sticky_differs",
        0,
        0,
        0x800000,
        0x800000,
        0,
        0,
        0,
        1,
        0,
        0x000000,
        0,
        0,
        1,
        1,
        0,
    ),  # sticky with shift 0
    (
        "add_zero_plus_max_grs",
        0,
        0,
        0x000000,
        0xFFFFFF,
        1,
        1,
        1,
        1,
        0,
        0xFFFFFF,
        1,
        1,
        1,
        0,
        0,
    ),  # mant_a=0, GRS with shift 0
    (
        "add_lsb_plus_lsb",
        0,
        0,
        0x000001,
        0x000001,
        1,
        0,
        0,
        0,
        0,
        0x000002,
        0,
        0,
        0,
        0,
        0,
    ),  # mant_a denormalized
    (
        "sub_zero_minus_lsb",
        0,
        0,
        0x000000,
        0x000001,
        0,
        0,
        0,
        0,
        0,
        0x000001,
        0,
        0,
        0,
        1,
        0,
    ),  # mant_a denormalized
    (
        "swap_sub_b_greater_in_mant_b",
        0,
        0,
        0x400000,
        0x800000,
        0,
        0,
        0,
        0,
        1,
        0x400000,
        0,
        0,
        0,
        0,
        0,
    ),  # mant_a denormalized
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
        | ((inputs.rount_i & 1) << 1)
        | (inputs.sticky_i & 1)
    )

    # effective signs of the two original operands (B's sign flips on subtraction)
    eff_sign_a = inputs.sign_a_i & 1
    eff_sign_b = (inputs.sign_b_i & 1) ^ (1 - (inputs.op_code_i & 1))

    # associate signs with the operand actually sitting on mant_a / mant_b
    if inputs.swap_i:
        sign_first, sign_second = eff_sign_b, eff_sign_a
    else:
        sign_first, sign_second = eff_sign_a, eff_sign_b

    magnitude_add = (inputs.op_code_i ^ inputs.sign_a_i ^ inputs.sign_b_i) & 1

    if magnitude_add:
        total = a_ext + b_ext
        carry = (total >> (MANT_WIDTH + 3)) & 1
        res_ext = total & ((1 << (MANT_WIDTH + 3)) - 1)
        sign = sign_first  # both operands share this sign
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

    op_a = int(dut.op_a.value)
    op_b = int(dut.op_b.value)
    raw_value = int(dut.raw_sum.value)
    abs_value = int(dut.abs_value.value)

    dut._log.info(f"\nRAW_VALUE - 0x{raw_value:08x}")
    dut._log.info(f"RAW_VALUE - 0b{raw_value:28b}")
    dut._log.info(f"ABS_VALUE - 0x{abs_value:08x}")
    dut._log.info(f"ABS_VALUE - 0b{abs_value:28b}")
    dut._log.info(f"OP_A      - 0b{op_a:28b}")
    dut._log.info(f"OP_B      - 0b{op_b:28b}")

    assert got == expected, f"{label}:\n got {got} expected {expected} [{inputs}]"


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


# -----------------
# Random tests
# -----------------
# @cocotb.test()
# async def test_random(dut):
#    rand = random.Random(0xC0C0BABE)
#    MAX_VAL = (1 << MANT_WIDTH) - 1
#    NUM_TESTS = 5000
#    for i in range(NUM_TESTS):
#        for op in [0, 1]:
#            for sw in [0, 1]:
#                sig_a = rand.randint(0, MAX_VAL)
#                sig_b = rand.randint(0, MAX_VAL)
#                g = rand.randint(0, 1)
#                r = rand.randint(0, 1)
#                s = rand.randint(0, 1)
#                await drive_and_check(dut, sig_a, sig_b, op, g, r, s, sw)
#
#    dut._log.info(f"PASS random: {NUM_TESTS} tests match.")
