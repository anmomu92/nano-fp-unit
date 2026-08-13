"""
cocotb testbench for b32_adapter.sv (binary16 -> binary32)

Two layers of checking:
  1. Directed tests, one per IEEE-754 category that the DUT has dedicated
     logic for (zero, normal, subnormal, infinity, NaN, fp32 pass-through,
     plus the two boundary/corner subnormal cases). These are the
     "most relevant inputs" and are reported individually so a failure
     immediately tells you which category broke.
  2. An exhaustive sweep: binary16 only has 2^16 = 65536 possible bit
     patterns, so instead of random sampling we can simply check every
     single one against an independent golden model (numpy's IEEE-754
     half<->single conversion) rather than against our own re-derivation
     of the RTL's logic. This is real verification, not the RTL grading
     itself.
"""

import os
import random
from dataclasses import dataclass

import cocotb
import numpy as np
from cocotb.triggers import Timer
from cocotb_coverage.coverage import CoverCross, CoverPoint, coverage_db

SETTLE = Timer(1, unit="ns")  # combinational settle time, DUT has no clock

# debugging
DEBUG_INTERNALS = os.environ.get("DEBUG_INTERNALS", "0") == "1"


# --------
# CLASSES
# -------
@dataclass
class AdapterInputs:
    num_i: int
    format_i: int

    def __str__(self):
        return f"num_i=0x{self.num_i:08x} " f"format_i={self.format_i}"


@dataclass
class AdapterOutputs:
    num_o: int

    def __str__(self):
        return f"num_o=0x{self.num_o:08x} "


# ---------
# FUNCTIONS
# ---------
# synchronous
def golden_reference(inputs: AdapterInputs) -> AdapterOutputs:
    """
    Independent reference model: numpy's IEEE-754 binary16 -> binary32.
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


# asynchronous
async def drive_dut(dut, inputs):
    """
    Drive DUT inputs.
    """
    dut.num_i.value = inputs.num_i
    dut.format_i.value = inputs.format_i

    await SETTLE

    return AdapterOutputs(num_o=int(dut.num_o.value))


async def check(dut, inputs, expected=None, label=""):
    """
    Compare the DUT results against the golden reference.
    """

    got = await drive_dut(dut, inputs)

    if not expected:
        expected = golden_reference(inputs)

    assert got == expected, f"{label}: got {got} expected {expected} [{inputs}]"

    # coverage
    sample(inputs)

    if label:
        dut._log.info(f"PASS {label}")


# ------------
# COVER POINTS
# ------------
@CoverPoint("top.format", xf=lambda t: t.format_i, bins=[0, 1])
def sample(t):
    pass


# --------------
# DIRECTED TESTS
# --------------


@cocotb.test()
async def test_fp16_adapt(dut):
    """
    Walk every IEEE-754 category the converter has dedicated logic for.
    """
    DIRECTED_CASES = [
        # (name, fp16 bits, expected fp32 bits)
        ("positive zero", 0x0000, 0x00000000),
        ("negative zero", 0x8000, 0x80000000),
        ("positive one", 0x3C00, 0x3F800000),
        ("negative two", 0xC000, 0xC0000000),
        ("smallest normal (2^-14)", 0x0400, 0x38800000),
        ("largest normal (~65504)", 0x7BFF, 0x477FE000),
        ("smallest pos subnormal", 0x0001, 0x33800000),
        ("largest subnormal", 0x03FF, 0x387FC000),
        ("mid subnormal (exact pow2)", 0x0200, 0x38000000),
        ("positive infinity", 0x7C00, 0x7F800000),
        ("negative infinity", 0xFC00, 0xFF800000),
        ("quiet NaN", 0x7E00, 0x7FC00000),
        ("quiet NaN, nonzero payload", 0x7E01, 0x7FC02000),
        ("signaling NaN payload", 0x7C01, 0x7F802000),
    ]

    for name, num_i, num_o in DIRECTED_CASES:
        inputs = AdapterInputs(num_i=num_i, format_i=1)
        outputs = AdapterOutputs(num_o=num_o)
        await check(dut, inputs, outputs, label=name)


@cocotb.test()
async def test_fp32_passthrough(dut):
    """
    When format_i is low, the full 32-bit word must pass through unchanged.
    """
    DIRECTED_CASES = [
        ("pi", 0x40490FDB, 0x40490FDB),  # pi
        ("positive zero", 0x00000000, 0x00000000),  # +0
        ("negative zero", 0x80000000, 0x80000000),  # -0
        ("positive infinity", 0x7F800000, 0x7F800000),  # +inf
        ("negative infinity", 0xFF800000, 0xFF800000),  # -inf
        ("NaN with payload", 0x7FC00001, 0x7FC00001),  # NaN with payload
        (
            "Arbitrary",
            0xDEADBEEF,
            0xDEADBEEF,
        ),  # arbitrary bit pattern, must pass through bit-exact
    ]
    for name, num_i, num_o in DIRECTED_CASES:
        inputs = AdapterInputs(num_i=num_i, format_i=0)
        outputs = AdapterOutputs(num_o=num_o)
        await check(
            dut,
            inputs,
            outputs,
            label=name,
        )


# ---------------
# EXHAUSTIVE TEST
# ---------------


@cocotb.test()
async def test_fp16_exhaustive(dut):
    """
    Check every one of the 65536 possible binary16 bit patterns against
    numpy's independent IEEE-754 half<->single conversion.
    """
    for b16 in range(0x10000):
        inputs = AdapterInputs(num_i=b16, format_i=1)
        await check(dut, inputs)

    dut._log.info(
        "PASS exhaustive sweep: all 65536 binary16 patterns match the golden model"
    )

    report_coverage(dut)


# ---------
# DEBUGGING
# ---------
def report_coverage(dut):
    """
    Print every coverpoint with per-bin hit counts

    Set COVERAGE_VERBOSE=1 to also list the hit counts of bins that were covered.
    """

    verbose = os.environ.get("COVERAGE_VERBOSE", "0") == "1"

    # TODO: make a global list with the coverpoints
    coverage = ["top.format"]

    dut._log.info("\n---------- FUNCTIONAL COVERAGE ----------")
    all_missing = []

    for name in coverage:
        cp = coverage_db[name]
        cp_details = cp.detailed_coverage
        missing_bins = [b for b, hits in cp_details.items() if hits == 0]
        flag = "" if not missing_bins else f"  <-- {len(missing_bins)} bins MISSING"

        dut._log.info(
            f"  {name:<22s} {cp.cover_percentage:6.2f}%  "
            f"({cp.coverage}/{cp.size}){flag}"
        )

        for b in missing_bins:
            dut._log.info(f"     MISSING bin: {b!r}")
            all_missing.append(f"{name}={b!r}")
        if verbose:
            for b, hits in cp_details.items():
                if hits:
                    dut._log.info(f"     hit {hits:6d}x : {b!r}")

    # report the total coverage of the testbench
    total = coverage_db["top"].cover_percentage

    dut._log.info(f"  {'TOTAL':<22s} {total:6.2f}%")
    dut._log.info(f"-----------------------------------------\n")

    # export coverage data
    coverage_db.export_to_xml(filename="coverage_functional.xml")

    # notify if 100% was not reached
    assert total == 100.0, (
        f"Functional coverage incomplete: {total:.2f}%"
        f"Uncovered bins ({len(all_missing)}): " + ", ".join(all_missing)
    )
