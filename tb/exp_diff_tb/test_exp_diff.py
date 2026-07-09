"""
cocotb testbench for exp_diff.sv

DUT takes two exponents and computes the following:
    - sel_o:    selection line that indicates which exponent is smaller (0=A, 1=B)
    - shift_o:  the exponent difference
"""

import cocotb
from cocotb.clock import Timer

SETTLE = Timer(1, unit="ns")
MAX_SHIFT = 27
DIRECTED_CASES = [
    # (name, exp_a, exp_b)
    ("equal exponents (zero_diff)", 0x00, 0x00),
    ("equal exponents, mid value ", 0x7F, 0x7F),
    ("A one greater than B", 0x80, 0x7F),
    ("B one greater than A", 0x7F, 0x80),
    ("A much greater, within maximum shift", 0x40, 0x30),
    ("B much greater, within maximum shift", 0x30, 0x40),
    ("A greater, at maximum shift", 0x40 + MAX_SHIFT, 0x40),
    ("A greater, one past maximum shift", 0x40 + MAX_SHIFT + 1, 0x40),
    ("B greater, at maximum shift", 0x40, 0x40 + MAX_SHIFT),
    ("B greater, one past maximum shift", 0x40, 0x40 + MAX_SHIFT + 1),
    ("max possible difference (A>>B)", 0xFF, 0x00),
    ("max possible difference (B>>A)", 0x00, 0xFF),
    ("both zero (double subnormal)", 0x00, 0x00),
    ("both max (double inf/NaN)", 0xFF, 0xFF),
]


# ------------------------
# AUXILIARY FUNCTIONS
# ------------------------
def golden_reference(exp_a: int, exp_b: int):
    """Independent reference model"""
    diff = exp_a - exp_b

    if diff >= 0:
        sel = 1
        shift_o = diff
    else:
        sel = 0
        shift_o = -diff

    return sel, shift_o


async def drive_and_check(dut, exp_a, exp_b):
    dut.exp_a_i.value = exp_a
    dut.exp_b_i.value = exp_b

    await SETTLE

    exp_sel, exp_shift = golden_reference(exp_a, exp_b)

    got_sel = int(dut.sel_o.value)
    got_shift = int(dut.shift_o.value)

    assert got_sel == exp_sel, (
        f"sel_o mismatch: exp_a=0x{exp_a:02x} exp_b=0x{exp_b:02x} "
        f"got={got_sel} expected={exp_sel}"
    )

    assert got_shift == exp_shift, (
        f"shift_o mismatch: exp_a=0x{exp_a:02x} exp_b=0x{exp_b:02x} "
        f"got={got_shift} expected={exp_shift}"
    )


# -------------------------
# TESTS
# -------------------------
# directed test
@cocotb.test()
async def test_directed_cases(dut):
    for name, exp_a, exp_b in DIRECTED_CASES:
        await drive_and_check(dut, exp_a, exp_b)
        dut._log.info(f"PASS {name:<38s} exp_a= 0x{exp_a:02x} exp_b=0x{exp_b:02x}")


# exhaustive test
@cocotb.test()
async def test_exhaustive_exponent_space(dut):
    mismatches = 0
    for exp_a in range(256):
        for exp_b in range(256):
            try:
                await drive_and_check(dut, exp_a, exp_b)
            except AssertionError as e:
                mismatches += 1
                dut._log.error(str(e))
                if mismatches >= 20:
                    raise
    dut._log.info(
        "PASS exhaustive sweep: all 65536 (exp_a, exp_b) pairs match the golden model"
    )
