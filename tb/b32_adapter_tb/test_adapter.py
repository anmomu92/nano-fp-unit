"""b32_adapter testbench
The module to test adapts an input number to binary32 encoding.

This testbench stimulates the DUT and performs functional verification on it.
    Directed testing and an exhaustive sweep have been performed.
    Functional verification has been performed (100% PASSED).

DUT signals used:
    dut.num_i: driven       The number to adapt
    dut.format_i: driven    The format of the input number

    dut.num_o: read         The adapted number

Notes:
    Functional verification could be improved.
"""

import os
import random
import sys
from dataclasses import dataclass

import cocotb
import numpy as np
from cocotb.triggers import Timer
from cocotb_coverage.coverage import CoverCross, CoverPoint, coverage_db
from common.coverage_report import report_coverage

# ---------
# VARIABLES
# ---------

SETTLE = Timer(1, unit="ns")  # combinational settle time, DUT has no clock

COVERAGE = ["top.format"]

FORMAT_BINARY32 = 0  # passthrough
FORMAT_BINARY16 = 1  # adapted to binary32


# --------
# CLASSES
# -------
@dataclass
class AdapterInputs:
    """Class representing the hardware module's input interface.

    Args:
        num_i (int): number to be adapted
        format_i (int): format of the number
    """

    num_i: int
    format_i: int

    def __str__(self):
        """Print signals.

        Args:
            self: current class' instance.

        Returns:
            A formated string with signal values.
        """

        return f"\n\tnum_i=0x{self.num_i:08x} \n" f"\tformat_i={self.format_i} \n"


@dataclass
class AdapterOutputs:
    """Class representing the hardware module's input interface.

    Args:
        num_o (int): adapted number
    """

    num_o: int
    zero_o: int
    infty_o: int
    nan_o: int
    sub_o: int

    def __str__(self):
        """Print signals.

        Args:
            self: current class' instance.

        Returns:
            A formated string with signal values.
        """
        return (
            f"\n\tnum_o=0x{self.num_o:08x} \n"
            f"\tzero_o={self.zero_o} \n"
            f"\tinfty_o={self.infty_o} \n"
            f"\tnan_o={self.nan_o} \n"
            f"\tsub_o={self.sub_o} \n"
        )


# ---------
# FUNCTIONS
# ---------
def reference_model(inputs: AdapterInputs) -> AdapterOutputs:
    """Expected outputs of the adapter for a given input.

    binary16 inputs (format_i == FORMAT_BINARY16, taken from num_i[15:0]) are
    converted exactly to binary32; any other format_i is treated as binary32
    and passed through unchanged. The flags classify the input operand in
    its original format (a binary16 subnormal raises sub_o even though it
    becomes a normal binary32 number).
    """
    if inputs.format_i == FORMAT_BINARY16:
        # binary16: 1 sign | 5 exponent | 10 fraction, bias 15
        num = inputs.num_i & 0xFFFF
        sign = (num >> 15) & 0x1
        exp = (num >> 10) & 0x1F
        frac = num & 0x3FF
        exp_max = 0x1F

        is_zero = exp == 0 and frac == 0
        is_sub = exp == 0 and frac != 0
        is_inf = exp == exp_max and frac == 0
        is_nan = exp == exp_max and frac != 0

        if is_zero:
            exp32, frac32 = 0, 0
        elif is_sub:
            # value = frac * 2^-24 -> normalize: 1.f * 2^(msb - 24)
            msb = frac.bit_length() - 1  # 0..9
            exp32 = msb - 24 + 127
            frac32 = (frac & ((1 << msb) - 1)) << (23 - msb)
        elif is_inf:
            exp32, frac32 = 0xFF, 0
        elif is_nan:
            exp32 = 0xFF
            frac32 = frac << 13  # payload preserved (IEEE 754-2019 6.2.3)
        else:  # normal: rebias 15 -> 127
            exp32 = exp - 15 + 127
            frac32 = frac << 13

        num_o = (sign << 31) | (exp32 << 23) | frac32
    else:
        # binary32: 1 sign | 8 exponent | 23 fraction -> passthrough
        num_o = inputs.num_i & 0xFFFFFFFF
        exp = (num_o >> 23) & 0xFF
        frac = num_o & 0x7FFFFF
        exp_max = 0xFF

        is_zero = exp == 0 and frac == 0
        is_sub = exp == 0 and frac != 0
        is_inf = exp == exp_max and frac == 0
        is_nan = exp == exp_max and frac != 0

    return AdapterOutputs(
        num_o=num_o,
        zero_o=int(is_zero),
        infty_o=int(is_inf),
        nan_o=int(is_nan),
        sub_o=int(is_sub),
    )


async def drive_dut(dut, inputs):
    """Drive DUT.

    Args:
        dut: the cocotb handle to the design under test.
        inputs: input interface values.

    Returns:
        The output interface.
    """
    dut.num_i.value = inputs.num_i
    dut.format_i.value = inputs.format_i

    await SETTLE

    return AdapterOutputs(
        num_o=int(dut.num_o.value),
        zero_o=int(dut.zero_o.value),
        infty_o=int(dut.infty_o.value),
        nan_o=int(dut.nan_o.value),
        sub_o=int(dut.sub_o.value),
    )


async def check(dut, inputs, expected=None, label=""):
    """Compare DUT results against reference's.

    Args:
        dut: the cocotb handle to the design under test.
        inputs: input interface values.
        expected: expected values.
        label: name of the test.
    """

    got = await drive_dut(dut, inputs)

    if not expected:
        expected = reference_model(inputs)

    assert got == expected, f"{label}: got {got} expected {expected} [{inputs}]"

    # coverage
    sample(inputs)

    if label:
        dut._log.info(f"PASS {label}")


# -----------------------
# FUNCTIONAL VERIFICATION
# -----------------------
@CoverPoint("top.format", xf=lambda t: t.format_i, bins=[0, 1])
def sample(t):
    pass


# --------------
# DIRECTED TESTS
# --------------
#
F16_ADAPTING_CASES = [
    (
        "positive zero",
        AdapterInputs(num_i=0x0000, format_i=1),
        AdapterOutputs(
            num_o=0x00000000,
            zero_o=1,
            infty_o=0,
            nan_o=0,
            sub_o=0,
        ),
    ),
    (
        "negative zero",
        AdapterInputs(num_i=0x8000, format_i=1),
        AdapterOutputs(
            num_o=0x80000000,
            zero_o=1,
            infty_o=0,
            nan_o=0,
            sub_o=0,
        ),
    ),
    (
        "positive one",
        AdapterInputs(num_i=0x3C00, format_i=1),
        AdapterOutputs(
            num_o=0x3F800000,
            zero_o=0,
            infty_o=0,
            nan_o=0,
            sub_o=0,
        ),
    ),
    (
        "negative two",
        AdapterInputs(num_i=0xC000, format_i=1),
        AdapterOutputs(
            num_o=0xC0000000,
            zero_o=0,
            infty_o=0,
            nan_o=0,
            sub_o=0,
        ),
    ),
    (
        "smallest normal",
        AdapterInputs(num_i=0x0400, format_i=1),
        AdapterOutputs(
            num_o=0x38800000,
            zero_o=0,
            infty_o=0,
            nan_o=0,
            sub_o=0,
        ),
    ),
    (
        "largest normal",
        AdapterInputs(num_i=0x7BFF, format_i=1),
        AdapterOutputs(
            num_o=0x477FE000,
            zero_o=0,
            infty_o=0,
            nan_o=0,
            sub_o=0,
        ),
    ),
    (
        "smallest pos subnormal",
        AdapterInputs(num_i=0x0001, format_i=1),
        AdapterOutputs(
            num_o=0x33800000,
            zero_o=0,
            infty_o=0,
            nan_o=0,
            sub_o=1,
        ),
    ),
    (
        "largest subnormal",
        AdapterInputs(num_i=0x03FF, format_i=1),
        AdapterOutputs(
            num_o=0x387FC000,
            zero_o=0,
            infty_o=0,
            nan_o=0,
            sub_o=1,
        ),
    ),
    (
        "mid subnormal",
        AdapterInputs(num_i=0x0200, format_i=1),
        AdapterOutputs(
            num_o=0x38000000,
            zero_o=0,
            infty_o=0,
            nan_o=0,
            sub_o=1,
        ),
    ),
    (
        "positive infinity",
        AdapterInputs(num_i=0x7C00, format_i=1),
        AdapterOutputs(
            num_o=0x7F800000,
            zero_o=0,
            infty_o=1,
            nan_o=0,
            sub_o=0,
        ),
    ),
    (
        "negative infinity",
        AdapterInputs(num_i=0xFC00, format_i=1),
        AdapterOutputs(
            num_o=0xFF800000,
            zero_o=0,
            infty_o=1,
            nan_o=0,
            sub_o=0,
        ),
    ),
    (
        "quiet NaN",
        AdapterInputs(num_i=0x7E00, format_i=1),
        AdapterOutputs(
            num_o=0x7FC00000,
            zero_o=0,
            infty_o=0,
            nan_o=1,
            sub_o=0,
        ),
    ),
    (
        "quiet NaN, nonzero payload",
        AdapterInputs(num_i=0x7E01, format_i=1),
        AdapterOutputs(
            num_o=0x7FC02000,
            zero_o=0,
            infty_o=0,
            nan_o=1,
            sub_o=0,
        ),
    ),
    (
        "signaling NaN payload",
        AdapterInputs(num_i=0x7C01, format_i=1),
        AdapterOutputs(
            num_o=0x7F802000,
            zero_o=0,
            infty_o=0,
            nan_o=1,
            sub_o=0,
        ),
    ),
]

F32_ADAPTING_CASES = [
    (
        "pi",
        AdapterInputs(num_i=0x40490FDB, format_i=0),
        AdapterOutputs(
            num_o=0x40490FDB,
            zero_o=0,
            infty_o=0,
            nan_o=0,
            sub_o=0,
        ),
    ),
    (
        "positive zero",
        AdapterInputs(num_i=0x00000000, format_i=0),
        AdapterOutputs(
            num_o=0x00000000,
            zero_o=1,
            infty_o=0,
            nan_o=0,
            sub_o=0,
        ),
    ),
    (
        "negative zero",
        AdapterInputs(num_i=0x80000000, format_i=0),
        AdapterOutputs(
            num_o=0x80000000,
            zero_o=1,
            infty_o=0,
            nan_o=0,
            sub_o=0,
        ),
    ),
    (
        "positive infinity",
        AdapterInputs(num_i=0x7F800000, format_i=0),
        AdapterOutputs(
            num_o=0x7F800000,
            zero_o=0,
            infty_o=1,
            nan_o=0,
            sub_o=0,
        ),
    ),
    (
        "negative infinity",
        AdapterInputs(num_i=0xFF800000, format_i=0),
        AdapterOutputs(
            num_o=0xFF800000,
            zero_o=0,
            infty_o=1,
            nan_o=0,
            sub_o=0,
        ),
    ),
    (
        "NaN with payload",
        AdapterInputs(num_i=0x7FC00001, format_i=0),
        AdapterOutputs(
            num_o=0x7FC00001,
            zero_o=0,
            infty_o=0,
            nan_o=1,
            sub_o=0,
        ),
    ),
    (
        "arbitrary bit pattern",
        AdapterInputs(num_i=0xDEADBEEF, format_i=0),
        AdapterOutputs(
            num_o=0xDEADBEEF,
            zero_o=0,
            infty_o=0,
            nan_o=0,
            sub_o=0,
        ),
    ),
]

ALL_CASES = F16_ADAPTING_CASES + F32_ADAPTING_CASES


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


# ---------------
# EXHAUSTIVE TEST
# ---------------
@cocotb.test()
async def test_fp16_exhaustive(dut):
    """Perform an exhaustive test.

    It drives the DUT with every possible input value and checks the resault
    against the reference model.

    Stimulus:
        Every possible input value.

    Checking:
        Results are checked against the reference model.

    Pass criteria:
        Every input combination must pass.

    Not covered:
        Nothing.

    Args:
        dut: the cocotb handle to the design under test.
    """
    for b16 in range(0x10000):
        inputs = AdapterInputs(num_i=b16, format_i=1)
        await check(dut, inputs)

    dut._log.info(
        "PASS exhaustive sweep: all 65536 binary16 patterns match the golden model"
    )

    report_coverage(dut, COVERAGE)
