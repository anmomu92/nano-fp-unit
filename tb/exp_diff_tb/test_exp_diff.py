"""
cocotb testbench for exp_diff.sv

DUT takes two exponents and computes the following:
    - sel_o:    selection line that indicates which exponent is smaller (0=A, 1=B)
    - shift_o:  the exponent difference
"""

import random
from dataclasses import dataclass

import cocotb
from cocotb.triggers import Timer
from cocotb_coverage.coverage import CoverCross, CoverPoint, coverage_db
from common.coverage_report import report_coverage

SETTLE = Timer(1, unit="ns")

MAX_SHIFT = 27


# -------
# CLASSES
# -------
@dataclass
class ExpDiffInputs:
    exp_a_i: int
    exp_b_i: int

    def __str__(self):
        return f"exp_a_i={self.exp_a_i} " f"exp_b_i={self.exp_b_i}"


@dataclass
class ExpDiffOutputs:
    sel_o: int
    shift_o: int

    def __str__(self):
        return f"sel_o={self.sel_o} " f"shift_o={self.shift_o}"


# ------------------------
# AUXILIARY FUNCTIONS
# ------------------------
# synchronous
def golden_reference(inputs: ExpDiffInputs) -> ExpDiffOutputs:
    """Independent reference model"""
    diff = inputs.exp_a_i - inputs.exp_b_i

    if diff >= 0:
        sel = 1
        if diff > 27:
            shift = MAX_SHIFT
        else:
            shift = diff
    else:
        sel = 0
        if diff < -27:
            shift = MAX_SHIFT
        else:
            shift = -diff

    return ExpDiffOutputs(sel_o=sel, shift_o=shift)


# asynchronous
async def drive_dut(dut, inputs):
    """
    Drive DUT inputs.
    """
    dut.exp_a_i.value = inputs.exp_a_i
    dut.exp_b_i.value = inputs.exp_b_i

    await SETTLE

    return ExpDiffOutputs(sel_o=int(dut.sel_o.value), shift_o=int(dut.shift_o.value))


async def check(dut, inputs, expected=None, label=""):
    """
    Compare the DUT outputs with the expected outputs.
    """

    got = await drive_dut(dut, inputs)
    if not expected:
        expected = golden_reference(inputs)

    assert got == expected, f"{label}: got {got} expected {expected} [{inputs}]"

    # coverage
    # sample(inputs)

    if label:
        dut._log.info(f"PASS {label}")


# ------------
# COVER POINTS
# ------------
# @CoverPoint("top")


# --------------
# DIRECTED TESTS
# --------------


@cocotb.test()
async def test_directed(dut):

    DIRECTED_CASES = [
        ("equal exponents (zero_diff)", 0x00, 0x00, 1, 0),
        ("equal exponents, mid value", 0x7F, 0x7F, 1, 0),
        ("A one greater than B", 0x80, 0x7F, 1, 1),
        ("B one greater than A", 0x7F, 0x80, 0, 1),
        ("A much greater, within maximum shift", 0x40, 0x30, 1, 16),
        ("B much greater, within maximum shift", 0x30, 0x40, 0, 16),
        ("A greater, at maximum shift", 0x40 + MAX_SHIFT, 0x40, 1, MAX_SHIFT),
        ("A greater, one past maximum shift", 0x40 + MAX_SHIFT + 1, 0x40, 1, MAX_SHIFT),
        ("B greater, at maximum shift", 0x40, 0x40 + MAX_SHIFT, 0, MAX_SHIFT),
        ("B greater, one past maximum shift", 0x40, 0x40 + MAX_SHIFT + 1, 0, MAX_SHIFT),
        ("max possible difference (A>>B)", 0xFF, 0x00, 1, MAX_SHIFT),
        ("max possible difference (B>>A)", 0x00, 0xFF, 0, MAX_SHIFT),
        ("both zero (double subnormal)", 0x00, 0x00, 1, 0),
        ("both max (double inf/NaN)", 0xFF, 0xFF, 1, 0),
    ]

    for name, exp_a_i, exp_b_i, sel_o, shift_o in DIRECTED_CASES:
        inputs = ExpDiffInputs(exp_a_i=exp_a_i, exp_b_i=exp_b_i)
        outputs = ExpDiffOutputs(sel_o=sel_o, shift_o=shift_o)
        await check(dut, inputs, outputs, label=name)


# ---------------
# EXHAUSTIVE TEST
# ---------------


@cocotb.test()
async def test_exhaustive_exponent_space(dut):
    mismatches = 0
    for exp_a in range(256):
        for exp_b in range(256):
            inputs = ExpDiffInputs(exp_a_i=exp_a, exp_b_i=exp_b)
            await check(dut, inputs)

    dut._log.info(
        "PASS exhaustive sweep: all 65536 (exp_a, exp_b) pairs match the golden model"
    )
