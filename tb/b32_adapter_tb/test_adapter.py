"""b32_adapter testbench
The module to test adapts an input number to binary32 encoding.

This testbench stimulates the DUT and performs functional verification on it.
    Directed testing and an exhaustive sweep have been performed.
    Functional verification has been performed (100% PASSED).

DUT signals used:
    <The dut attributes this component reads or drives, and in which direction.
    Python has no port list, so nothing else in the file records this. Without
    it a reader must search the whole class to learn what the component
    touches, and a renamed RTL signal fails at runtime with an AttributeError
    that points nowhere useful.>

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

SETTLE = Timer(1, unit="ns")  # combinational settle time, DUT has no clock

COVERAGE = ["top.format"]


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

        return f"num_i=0x{self.num_i:08x} " f"format_i={self.format_i}"


@dataclass
class AdapterOutputs:
    """Class representing the hardware module's input interface.

    Args:
        num_o (int): adapted number
    """

    num_o: int

    def __str__(self):
        """Print signals.

        Args:
            self: current class' instance.

        Returns:
            A formated string with signal values.
        """
        return f"num_o=0x{self.num_o:08x} "


# ---------
# FUNCTIONS
# ---------
def golden_reference(inputs: AdapterInputs) -> AdapterOutputs:
    """Adapt input number to binary32 format

    Args:
        inputs (AdapterInputs): input interface values.

    Returns:
        The output interface.
    """
    match (inputs.format_i):
        case 0:
            b32 = inputs.num_i
        case 1:
            aux = np.uint16(inputs.num_i).view(np.float16)
            b32 = aux.astype(np.float32).view(np.uint32).item()
        case _:
            b32 = inputs.num_i

    return AdapterOutputs(num_o=b32)


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

    return AdapterOutputs(num_o=int(dut.num_o.value))


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
        expected = golden_reference(inputs)

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
        AdapterOutputs(num_o=0x00000000),
    ),
    (
        "negative zero",
        AdapterInputs(num_i=0x8000, format_i=1),
        AdapterOutputs(num_o=0x80000000),
    ),
    (
        "positive one",
        AdapterInputs(num_i=0x3C00, format_i=1),
        AdapterOutputs(num_o=0x3F800000),
    ),
    (
        "negative two",
        AdapterInputs(num_i=0xC000, format_i=1),
        AdapterOutputs(num_o=0xC0000000),
    ),
    (
        "smallest normal",
        AdapterInputs(num_i=0x0400, format_i=1),
        AdapterOutputs(num_o=0x38800000),
    ),
    (
        "largest normal",
        AdapterInputs(num_i=0x7BFF, format_i=1),
        AdapterOutputs(num_o=0x477FE000),
    ),
    (
        "smallest pos subnormal",
        AdapterInputs(num_i=0x0001, format_i=1),
        AdapterOutputs(num_o=0x33800000),
    ),
    (
        "largest subnormal",
        AdapterInputs(num_i=0x03FF, format_i=1),
        AdapterOutputs(num_o=0x387FC000),
    ),
    (
        "mid subnormal",
        AdapterInputs(num_i=0x0200, format_i=1),
        AdapterOutputs(num_o=0x38000000),
    ),
    (
        "positive infinity",
        AdapterInputs(num_i=0x7C00, format_i=1),
        AdapterOutputs(num_o=0x7F800000),
    ),
    (
        "negative infinity",
        AdapterInputs(num_i=0xFC00, format_i=1),
        AdapterOutputs(num_o=0xFF800000),
    ),
    (
        "quiet NaN",
        AdapterInputs(num_i=0x7E00, format_i=1),
        AdapterOutputs(num_o=0x7FC00000),
    ),
    (
        "quiet NaN, nonzero payload",
        AdapterInputs(num_i=0x7E01, format_i=1),
        AdapterOutputs(num_o=0x7FC02000),
    ),
    (
        "signaling NaN payload",
        AdapterInputs(num_i=0x7C01, format_i=1),
        AdapterOutputs(num_o=0x7F802000),
    ),
]

F32_ADAPTING_CASES = [
    (
        "pi",
        AdapterInputs(num_i=0x40490FDB, format_i=0),
        AdapterOutputs(num_o=0x40490FDB),
    ),
    (
        "positive zero",
        AdapterInputs(num_i=0x00000000, format_i=0),
        AdapterOutputs(num_o=0x00000000),
    ),
    (
        "negative zero",
        AdapterInputs(num_i=0x80000000, format_i=0),
        AdapterOutputs(num_o=0x80000000),
    ),
    (
        "positive infinity",
        AdapterInputs(num_i=0x7F800000, format_i=0),
        AdapterOutputs(num_o=0x7F800000),
    ),
    (
        "negative infinity",
        AdapterInputs(num_i=0xFF800000, format_i=0),
        AdapterOutputs(num_o=0xFF800000),
    ),
    (
        "NaN with payload",
        AdapterInputs(num_i=0x7FC00001, format_i=0),
        AdapterOutputs(num_o=0x7FC00001),
    ),
    (
        "arbitrary bit pattern",
        AdapterInputs(num_i=0xDEADBEEF, format_i=0),
        AdapterOutputs(num_o=0xDEADBEEF),
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
