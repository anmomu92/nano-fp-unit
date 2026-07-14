"""
cocotb testbench for sig_shift.sv

DUT aligns the smaller significand and generates GRS bits.

Outputs:
    sig_o - shifted significand
    guard_o, round_o, sticky_o - rounding bits

Golden model:
    independent from RTL design
"""

import random

import cocotb
from cocotb.clock import Timer

SETTLE = Timer(1, unit="ns")
SIG_WIDTH = 24
MAX_SHIFT = 27
DIRECTED_CASES = [
    # (name, sig, shift)
    ("zero shift", 0x800000, 0),
    ("one shift (G=0)", 0x800000, 1),
    ("one shift (G=1)", 0x800001, 1),
    ("two shift (R=0)", 0x800000, 1),
    ("two shift (R=1)", 0x800003, 1),
    ("three shift (S=0)", 0x800000, 1),
    ("three shift (S=1)", 0x80000F, 1),
]


def golden_reference(significand: int, shift: int):
    shift = min(shift, MAX_SHIFT)

    wide = SIG_WIDTH + MAX_SHIFT

    padded = significand << MAX_SHIFT  # this is done so data is not lost
    result_shift = padded >> shift

    mask_wide = (1 << wide) - 1
    result_shift &= mask_wide

    shifted_sig = (result_shift >> MAX_SHIFT) & ((1 << SIG_WIDTH) - 1)
    guard_bit = (result_shift >> (MAX_SHIFT - 1)) & 1
    round_bit = (result_shift >> (MAX_SHIFT - 2)) & 1
    remainder_bits = result_shift & ((1 << MAX_SHIFT - 2) - 1)
    sticky_bit = 1 if remainder_bits != 0 else 0

    return shifted_sig, guard_bit, round_bit, sticky_bit


async def drive_and_check(dut, sig, shift, label=""):
    dut.sig_i.value = sig
    dut.shift_i.value = shift

    await SETTLE

    # expected values
    exp_shifted, exp_g, exp_r, exp_s = golden_reference(sig, shift)

    # dut values
    got_shifted = int(dut.sig_o.value)
    got_g = int(dut.guard_o.value)
    got_r = int(dut.round_o.value)
    got_s = int(dut.sticky_o.value)

    # assert results
    val = f"sig=0x{sig:06x} shift=0x{shift:06x}"
    assert (
        got_shifted == exp_shifted
    ), f"sig_o: got 0x{got_shifted:06x} expected 0x{exp_shifted:06x}  [{val}]"
    assert got_g == exp_g, f"guard_o: got {got_g} expected {exp_g}  [{val}]"
    assert got_r == exp_r, f"round_o: got {got_r} expected {exp_r}  [{val}]"
    assert got_s == exp_s, f"sticky_o: got {got_s} expected {exp_s}  [{val}]"

    if label:
        dut._log.info(f"PASS {label}")


# ---------------
# Directed tests
# ---------------
@cocotb.test()
async def test_direct_cases(dut):
    for name, sig, shift in DIRECTED_CASES:
        await drive_and_check(dut, sig, shift, name)


@cocotb.test()
async def test_all_shifts(dut):
    for shift in range(MAX_SHIFT + 1):
        await drive_and_check(dut, 0xFFFFFF, shift, f"all shifts")


# --------------
# Random tests
# --------------
@cocotb.test()
async def test_random(dut):
    rand = random.Random(0xC0C0BABE)
    MAX_VAL = (1 << SIG_WIDTH) - 1
    NUM_TESTS = 5000
    for i in range(NUM_TESTS):
        sig = rand.randint(0, MAX_VAL)
        shift = rand.randint(0, MAX_SHIFT)
        await drive_and_check(dut, sig, shift)

    dut._log.info(f"PASS random: {NUM_TESTS} tests match.")
