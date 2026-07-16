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

import cocotb
import numpy as np
from cocotb.clock import Timer

SETTLE = Timer(1, unit="ns")  # combinational settle time, DUT has no clock


def f16_bits_to_f32_bits_golden(bits16: int) -> int:
    """Independent reference model: numpy's IEEE-754 binary16 -> binary32."""
    h = np.uint16(bits16).view(np.float16)
    f = h.astype(np.float32)
    return int(f.view(np.uint32))


async def drive_and_check(dut, num_bits, num_is_fp16, expected, case_name):
    """Drive operand A with num_bits (right-justified) and tag, check num_o."""
    dut.num_i.value = num_bits & 0xFFFF_FFFF
    dut.num_is_fp16.value = num_is_fp16
    # Keep operand B parked at a known, unrelated value so we also catch
    # any accidental cross-talk between the A and B datapaths.
    dut.b_i.value = 0x0000_3C00  # fp16 1.0, inert
    dut.b_is_fp16.value = 1
    await SETTLE

    got = int(dut.num_o.value)
    assert got == expected, (
        f"{case_name}: num_i=0x{num_bits & 0xFFFF:04x} -> got 0x{got:08x}, "
        f"expected 0x{expected:08x}"
    )
    dut._log.info(f"PASS {case_name:<22s} 0x{num_bits & 0xFFFF:04x} -> 0x{got:08x}")


# ---------------------------------------------------------------------------
# Directed tests: the "most relevant" inputs, one IEEE-754 category each.
# ---------------------------------------------------------------------------

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


@cocotb.test()
async def test_directed_categories(dut):
    """Walk every IEEE-754 category the converter has dedicated logic for."""
    for name, bits16, expected32 in DIRECTED_CASES:
        await drive_and_check(
            dut, bits16, num_is_fp16=1, expected=expected32, case_name=name
        )


@cocotb.test()
async def test_fp32_passthrough(dut):
    """When num_is_fp16 is low, the full 32-bit word must pass through unchanged."""
    passthrough_values = [
        0x40490FDB,  # pi
        0x00000000,  # +0
        0x80000000,  # -0
        0x7F800000,  # +inf
        0xFF800000,  # -inf
        0x7FC00001,  # NaN with payload
        0xDEADBEEF,  # arbitrary bit pattern, must pass through bit-exact
    ]
    for val in passthrough_values:
        await drive_and_check(
            dut,
            val,
            num_is_fp16=0,
            expected=val,
            case_name=f"fp32 passthrough 0x{val:08x}",
        )


@cocotb.test()
async def test_both_operands_independently(dut):
    """A and B must convert independently and simultaneously, including
    mixed formats (A as fp16, B as fp32 passthrough, and vice versa)."""

    async def check_pair(num_bits, num_fmt16, exp_a, b_bits, b_fmt16, exp_b, name):
        dut.num_i.value = num_bits & 0xFFFF_FFFF
        dut.num_is_fp16.value = num_fmt16
        dut.b_i.value = b_bits & 0xFFFF_FFFF
        dut.b_is_fp16.value = b_fmt16
        await SETTLE
        got_a = int(dut.num_o.value)
        got_b = int(dut.b_o.value)
        assert got_a == exp_a, f"{name}: num_o got 0x{got_a:08x} expected 0x{exp_a:08x}"
        assert got_b == exp_b, f"{name}: b_o got 0x{got_b:08x} expected 0x{exp_b:08x}"
        dut._log.info(f"PASS {name:<28s} num_o=0x{got_a:08x} b_o=0x{got_b:08x}")

    # Both fp16, different values
    await check_pair(
        0x3C00, 1, 0x3F800000, 0xC000, 1, 0xC0000000, "both fp16 (1.0, -2.0)"
    )
    # A fp16, B fp32 passthrough
    await check_pair(
        0x3C00, 1, 0x3F800000, 0x40490FDB, 0, 0x40490FDB, "A=fp16 1.0, B=fp32 pi"
    )
    # A fp32 passthrough, B fp16
    await check_pair(
        0x3F000000, 0, 0x3F000000, 0x3C00, 1, 0x3F800000, "A=fp32 0.5, B=fp16 1.0"
    )
    # Both fp32 passthrough
    await check_pair(
        0xAABBCCDD, 0, 0xAABBCCDD, 0x11223344, 0, 0x11223344, "both fp32 passthrough"
    )


# ---------------------------------------------------------------------------
# Exhaustive sweep against an independent golden model.
# binary16 has only 65536 possible bit patterns, so full coverage is cheap
# and strictly stronger than random sampling.
# ---------------------------------------------------------------------------


@cocotb.test()
async def test_exhaustive_fp16_space(dut):
    """Check every one of the 65536 possible binary16 bit patterns against
    numpy's independent IEEE-754 half<->single conversion."""
    mismatches = []
    for bits16 in range(0x10000):
        expected = f16_bits_to_f32_bits_golden(bits16)
        dut.num_i.value = bits16
        dut.num_is_fp16.value = 1
        await SETTLE
        got = int(dut.num_o.value)
        if got != expected:
            mismatches.append((bits16, got, expected))
            if len(mismatches) >= 20:
                break  # don't flood the log if something is systematically wrong

    if mismatches:
        detail = ", ".join(
            f"0x{b:04x}: got 0x{g:08x} exp 0x{e:08x}" for b, g, e in mismatches
        )
        assert (
            False
        ), f"{len(mismatches)} mismatch(es) found (first {len(mismatches)} shown): {detail}"

    dut._log.info(
        "PASS exhaustive sweep: all 65536 binary16 patterns match the golden model"
    )
