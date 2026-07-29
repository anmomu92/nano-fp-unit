"""
cocotb testbench for normalizer.sv
"""

import os
import random
from typing import Any

import cocotb
from cocotb.triggers import Timer
from cocotb_coverage.coverage import CoverCross, CoverPoint, coverage_db

# -----------------------
# VARIABLES AND CONSTANTS
# -----------------------
# environment
DEBUG_INTERNALS = os.environ.get("DEBUG_INTERNALS", "0") == "1"
SWEEP_N = int(os.environ.get("SWEEP_N", "8000"))

# timing
SETTLE = Timer(1, unit="ns")

# widths
MANT_WIDTH = 24
EXP_WIDTH = 8
EXT_WIDTH = MANT_WIDTH + 3
SHIFT_WIDTH = 5

# max widths
MANT_MASK = (1 << MANT_WIDTH) - 1
EXT_MASK = (1 << EXT_WIDTH) - 1
EXP_MASK = (1 << EXP_WIDTH) - 1

# -------------------
# Helping functions
# -------------------


# leading zeros count
def lzc(x, width=MANT_WIDTH):
    for i in range(width):
        if (x >> (width - 1 - i)) & 1:
            return i
    return width


# -----------------------
# Golden reference model
# -----------------------
def golden_reference(mant_i, g, r, s, carry_i, sign_i, zero_i, exp_i):
    # we distinguish the different cases
    carry_case = carry_i  # overflow
    normal_case = (not carry_case) and ((mant_i >> (MANT_WIDTH - 1)) & 1)  # normal

    # for subnormal inputs
    lz_raw = lzc(mant_i)
    headroom = 0 if exp_i == 0 else (exp_i - 1)

    # if exp_i - lzc <= 1
    if lz_raw > headroom:
        lz_use, subnormal = headroom & 0x1F, 1  # subnormal un-normalizable
    else:
        lz_use, subnormal = lz_raw, 0  # subnormal normalizabe

    extended_mant = (mant_i << 3) | (g << 2) | (r << 1) | s
    shifted_mant = (extended_mant << lz_use) & EXT_MASK

    # we make a dictionary for the outputs
    out: dict[str, Any] = dict(sign=sign_i, zero=zero_i, underflow=0, overflow=0)

    # depending on the case, we update the rest of the output values
    if zero_i:
        out.update(mant=0, exp=0, g=0, r=0, s=0)
    elif carry_case:
        out.update(
            mant=(carry_i << (MANT_WIDTH - 1))
            | ((mant_i >> 1) & ((1 << (MANT_WIDTH - 1)) - 1)),
            exp=(exp_i + 1) & EXP_MASK,
            g=mant_i & 1,
            r=g,
            s=(r | s),
            overflow=1 if exp_i >= EXP_MASK - 1 else 0,
        )
    elif normal_case:
        out.update(mant=mant_i, exp=exp_i, g=g, r=r, s=s)
    else:
        out.update(
            mant=(shifted_mant >> 3) & MANT_MASK,
            g=(shifted_mant >> 2) & 1,
            r=(shifted_mant >> 1) & 1,
            s=shifted_mant & 1,
        )
        if subnormal:
            out.update(exp=0, underflow=1)
        else:
            out.update(exp=(exp_i - lz_use) & EXP_MASK)

    out["_internals"] = dict(
        carry_case=int(bool(carry_case)),
        normal_case=int(bool(normal_case)),
        cancel_case=int(not (zero_i or carry_case or normal_case)),
        lz_raw=lz_raw,
        headroom=headroom,
        lz_use=lz_use,
        subnormal=subnormal,
        shifted_mant=shifted_mant,
    )

    return out


def classify_case(mant_i, carry_i, zero_i):
    if zero_i:
        return "zero"
    if carry_i:
        return "carry"
    if (mant_i >> MANT_WIDTH) & 1:
        return "normal"
    return "cancel"


# --------------------
# Functional coverage
# --------------------


@CoverPoint(
    "top.case", xf=lambda t: t["case"], bins=["carry", "normal", "cancel", "zero"]
)
@CoverPoint("top.sign", xf=lambda t: t["sign"], bins=[0, 1])
@CoverPoint("top.underflow", xf=lambda t: t["underflow"], bins=[0, 1])
@CoverPoint("top.overflow", xf=lambda t: t["overflow"], bins=[0, 1])
@CoverPoint(
    "top.grs",
    xf=lambda t: (t["g"], t["r"], t["s"]),
    bins=[(a, b, c) for a in (0, 1) for b in (0, 1) for c in (0, 1)],
)
@CoverPoint(
    "top.exp_region",
    xf=lambda t: t["exp_region"],
    bins=["zero", "low", "mid", "high", "max"],
)
@CoverCross("top.case_x_sign", items=["top.case", "top.sign"])
def sample(t):
    pass


def make_sample(mant_i, g, r, s, carry_i, sign_i, zero_i, exp_i, exp_out, uf, ov):
    # classify the exponent in different regions
    if exp_i == 0:
        region = "zero"
    elif exp_i <= 32:
        region = "low"
    elif exp_i >= EXP_MASK:
        region = "max"
    elif exp_i >= EXP_MASK - 8:
        region = "high"
    else:
        region = "mid"

    return dict(
        case=classify_case(mant_i, carry_i, zero_i),
        sign=sign_i,
        underflow=uf,
        overflow=ov,
        g=g,
        r=r,
        s=s,
        exp_region=region,
    )


async def drive_and_check(
    dut, mant_i, g, r, s, carry_i, sign_i, zero_i, exp_i, label=""
):
    dut.mant_i.value = mant_i & MANT_MASK
    dut.carry_i.value = carry_i
    dut.guard_i.value = g
    dut.round_i.value = r
    dut.sticky_i.value = s
    dut.sign_i.value = sign_i
    dut.zero_i.value = zero_i
    dut.exp_i.value = exp_i & EXP_MASK

    await SETTLE

    expected = golden_reference(mant_i, g, r, s, carry_i, sign_i, zero_i, exp_i)
    context = (
        f"mant=0x{mant_i:06x} grs={g}{r}{s} carry={carry_i} sign={sign_i} "
        f"zero={zero_i} exp={exp_i}"
    )

    # obtained results from DUT
    got = dict(
        mant=int(dut.mant_o.value),
        exp=int(dut.exp_o.value),
        sign=int(dut.sign_o.value),
        g=int(dut.guard_o.value),
        r=int(dut.round_o.value),
        s=int(dut.sticky_o.value),
        zero=int(dut.zero_o.value),
        underflow=int(dut.underflow_o.value),
        overflow=int(dut.overflow_o.value),
    )

    # internal DUT signals
    lz_eff = int(dut.lz_eff.value)
    shifted_mant = int(dut.shifted_mant.value)

    dut._log.info(f"\n\n")

    if DEBUG_INTERNALS:
        gi = expected["_internals"]
        case = (
            "zero"
            if zero_i
            else (
                "carry"
                if gi["carry_case"]
                else "normal_case" if gi["normal_case"] else "cancel"
            )
        )
        dut._log.info(
            f"\nINTERNAL GOLDEN REFERENCE VALUES\t [Context] : {context}\n"
            f"  carry_case = {gi['carry_case']}\n"
            f"  normal_case = {gi['normal_case']}\n"
            f"  cancel_case = {gi['cancel_case']} -> {case:<6s} | "
            f"  lz_raw = {gi['lz_raw']:2d} lz_use = {gi['lz_use']:2d} \n"
            f"  headroom = {gi['headroom']:3d} subnormal = {gi['subnormal']}\n"
        )

        dut._log.info(
            f"\n DUT INTERNAL SIGNALS\n"
            f"  lz_eff = {lz_eff}\n"
            f"  shifted_mant = 0b{shifted_mant:27b}\n"
        )

    for k in expected:
        if k == "_internals":
            continue
        elif k == "mant":
            assert (
                got[k] == expected[k]
            ), f"{k}: got 0x{got[k]:06x} expected 0x{expected[k]:06x}  [{context}]"
        assert (
            got[k] == expected[k]
        ), f"{k}: got {got[k]} expected {expected[k]}  [{context}]"

    # record functional coverage for this stimulus
    sample(
        make_sample(
            mant_i,
            g,
            r,
            s,
            carry_i,
            sign_i,
            zero_i,
            exp_i,
            expected["exp"],
            expected["underflow"],
            expected["overflow"],
        )
    )

    if label:
        dut._log.info(f"PASS {label}")


# ---------------
# Directed cases
# ---------------


@cocotb.test()
async def test_already_normalised(dut):
    await drive_and_check(dut, 0x800000, 0, 0, 0, 0, 0, 0, 127, "1.0 passthrough")
    await drive_and_check(
        dut, 0xFFFFFF, 1, 1, 1, 0, 1, 0, 127, "max mant + GRS passthrough"
    )
    await drive_and_check(
        dut, 0x800000, 1, 0, 1, 0, 0, 1, 127, "min-normal passthrough"
    )


@cocotb.test()
async def test_addition_overflow(dut):
    await drive_and_check(dut, 0x000000, 0, 0, 0, 1, 0, 0, 127, "carry, clean")
    await drive_and_check(dut, 0x000001, 0, 0, 0, 1, 0, 0, 100, "carry, LSB->guard")
    await drive_and_check(dut, 0x000001, 1, 1, 0, 1, 0, 0, 100, "carry, GRS collapse")
    await drive_and_check(dut, 0xFFFFFF, 1, 1, 1, 1, 1, 0, 50, "carry, all ones")


@cocotb.test()
async def test_exponent_overflow(dut):
    await drive_and_check(
        dut, 0x000000, 0, 0, 0, 1, 0, 0, 254, "carry at exp=254 -> overflow"
    )
    await drive_and_check(
        dut, 0x800000, 0, 0, 0, 1, 1, 0, 254, "carry at exp=254 (neg) -> overflow"
    )
    await drive_and_check(
        dut, 0x000000, 0, 0, 0, 1, 0, 0, 253, "carry at exp=253 -> no overflow"
    )


@cocotb.test()
async def test_cancellation(dut):
    await drive_and_check(dut, 0x400000, 0, 0, 0, 0, 0, 0, 127, "1 leading zero")
    await drive_and_check(dut, 0x004000, 0, 0, 0, 0, 0, 0, 127, "9 leading zeros")
    await drive_and_check(dut, 0x000002, 0, 0, 0, 0, 0, 0, 127, "22 leading zeros")
    await drive_and_check(dut, 0x400000, 1, 0, 0, 0, 0, 0, 127, "cancel pulls guard up")


@cocotb.test()
async def test_subnormal_underflow(dut):
    await drive_and_check(
        dut, 0x000001, 0, 0, 0, 0, 0, 0, 5, "underflow, big cancel small exponent"
    )
    await drive_and_check(
        dut, 0x000010, 0, 0, 0, 0, 0, 0, 3, "underflow, exponent runs out"
    )
    await drive_and_check(
        dut, 0x400000, 0, 0, 0, 0, 0, 0, 1, "exp=1, any left shift underflows"
    )
    await drive_and_check(
        dut, 0x000001, 0, 0, 0, 1, 0, 0, 0, "exponent already 0 -> subnormal"
    )


@cocotb.test()
async def test_zero_result(dut):
    await drive_and_check(dut, 0x000000, 0, 0, 0, 0, 0, 1, 127, "+0")
    await drive_and_check(dut, 0x000000, 0, 0, 0, 0, 1, 1, 127, "-0")
    await drive_and_check(dut, 0x123456, 1, 1, 1, 0, 0, 1, 99, "zero flag dominates")


# ----------------
# Randomized test
# ----------------


@cocotb.test()
async def test_random_sweep(dut):
    rng = random.Random(0x4E4F524D)
    num_tests = 8000
    for _ in range(num_tests):
        # cases
        case_rn = rng.random()
        if case_rn < 0.25:  # carry case
            mant = rng.randint(0, MANT_MASK)
            carry = 1
        elif case_rn < 0.5:  # cancellation
            mant = rng.randint(0, (1 << (MANT_WIDTH - 1) - 1))
            carry = 0
        else:  # normal
            mant = rng.randint(0, MANT_MASK)
            carry = rng.randint(0, 1)

        # grs bits
        g = rng.randint(0, 1)
        r = rng.randint(0, 1)
        s = rng.randint(0, 1)

        sign = rng.randint(0, 1)
        zero = 1 if rng.random() < 0.05 else 0
        exp_rn = rng.random()
        if exp_rn < 0.15:
            exp = 0
        elif exp_rn < 0.30:
            exp = rng.randint(1, 32)
        elif exp_rn < 0.45:
            exp = rng.randint(EXP_MASK - 8, EXP_MASK)
        else:
            exp = rng.randint(0, EXP_MASK)

        await drive_and_check(dut, mant, g, r, s, carry, sign, zero, exp)


def report_coverage(dut):
    """Print every coverpoint with per-bin hit counts, flagging cold bins.

    Set COVERAGE_VERBOSE=1 to also list the hit counts of bins that WERE
    covered (useful for spotting bins hit only once or twice, which are
    technically covered but statistically thin).
    """
    verbose = os.environ.get("COVERAGE_VERBOSE", "0") == "1"
    names = [
        "top.case",
        "top.sign",
        "top.underflow",
        "top.overflow",
        "top.grs",
        "top.exp_region",
        "top.case_x_sign",
    ]

    dut._log.info("──────────── FUNCTIONAL COVERAGE ────────────")
    all_missing = []
    for name in names:
        cp = coverage_db[name]
        detail = cp.detailed_coverage  # OrderedDict: bin -> hit count
        missing = [b for b, hits in detail.items() if hits == 0]
        flag = "" if not missing else f"   <-- {len(missing)} MISSING"
        dut._log.info(
            f"  {name:<22s} {cp.cover_percentage:6.2f}%  "
            f"({cp.coverage}/{cp.size} bins){flag}"
        )
        for b in missing:
            dut._log.info(f"        MISSING bin: {b!r}")
            all_missing.append(f"{name}={b!r}")
        if verbose:
            for b, hits in detail.items():
                if hits:
                    dut._log.info(f"        hit {hits:6d}x : {b!r}")

    total = coverage_db["top"].cover_percentage
    dut._log.info(f"  {'TOTAL':<22s} {total:6.2f}%")
    dut._log.info("─────────────────────────────────────────────")

    coverage_db.export_to_xml(filename="coverage_functional.xml")

    # Failure message names the uncovered bins, so the log line that fails
    # tells you what to go fix rather than just quoting a percentage.
    assert total == 100.0, (
        f"Functional coverage incomplete: {total:.2f}%. "
        f"Uncovered bins ({len(all_missing)}): " + ", ".join(all_missing)
    )
