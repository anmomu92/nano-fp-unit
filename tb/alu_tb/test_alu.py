"""
cocotb testbench for alu.sv

DUT performs the arithmetic operation with the two significands.

Outputs:
    res_o - result of the arithmetic operation
    guard_o - guard bit
    round_o - round bit
    sticky_o - sticky bit
"""

import random

import cocotb
from cocotb.clock import Timer

SETTLE = Timer(1, unit="ns")
SIG_WIDTH = 24


def golden_reference(
    sig_a: int,
    sig_b: int,
    op_code: int,
    g: int,
    r: int,
    s: int,
    swap: int,
):
    if swap:
        op_a = sig_b
        op_b = sig_a
    else:
        op_a = sig_a
        op_b = sig_b

    match (op_code):
        case 0:
            res = op_a - op_b
        case 1:
            res = op_a + op_b
        case _:
            res = 0

    return res, g, r, s


async def drive_and_check(dut, sig_a, sig_b, op_code, g, r, s, swap):
    # stimulate the DUT
    dut.sig_a_i.value = sig_a
    dut.sig_b_i.value = sig_b
    dut.op_code_i.value = op_code
    dut.guard_i.value = g
    dut.round_i.value = r
    dut.sticky_i.value = s
    dut.swap_i.value = swap

    await SETTLE

    # expected values
    exp_res, exp_g, exp_r, exp_s = golden_reference(
        sig_a, sig_a, op_code, g, r, s, swap
    )

    # DUT values
    got_res = int(dut.res_o.value)
    got_g = int(dut.guard_o.value)
    got_r = int(dut.round_o.value)
    got_s = int(dut.sticky_o.value)

    # assert results
    val = f"sig_a=0x{sig_a:06x}\nsig_b=0x{sig_b:06x}\nop_code={op_code}\nguard_bit={g}\nround_bit={r}\nsticky_bit={s}\nswap={swap}"

    assert (
        got_res == exp_res
    ), f"res_o: got 0x{got_res:06x} expected 0x{exp_res:06x}  [{val}]"

    assert got_g == exp_g, f"guard_o: got {got_g} expected {exp_g}  [{val}]"
    assert got_r == exp_r, f"round_o: got {got_r} expected {exp_r}  [{val}]"
    assert got_s == exp_s, f"sticky_o: got {got_s} expected {exp_s}  [{val}]"


# -----------------
# Random tests
# -----------------
@cocotb.test()
async def test_random(dut):
    rand = random.Random(0xC0C0BABE)
    MAX_VAL = (1 << SIG_WIDTH) - 1
    NUM_TESTS = 5000
    for i in range(NUM_TESTS):
        for op in [0, 1]:
            for sw in [0, 1]:
                sig_a = rand.randint(0, MAX_VAL)
                sig_b = rand.randint(0, MAX_VAL)
                g = rand.randint(0, 1)
                r = rand.randint(0, 1)
                s = rand.randint(0, 1)
                await drive_and_check(dut, sig_a, sig_b, op, g, r, s, sw)

    dut._log.info(f"PASS random: {NUM_TESTS} tests match.")
