"""
cocotb testbench for the rounder.sv module
"""

import os
import random
from enum import Enum

import cocotb
from cocotb.triggers import Timer
from cocotb_coverage.coverage import CoverCross, CoverPoint, coverage_db

# ---------
# CONSTANTS
# ---------
# timer
SETTLE = Timer(1, unit="ns")

# widths
MANT_WIDTH = 24
EXP_WIDTH = 8
FRAC_WIDTH = MANT_WIDTH - 1
EXT_WIDTH = EXP_WIDTH + FRAC_WIDTH
RES_WIDTH = EXP_WIDTH + MANT_WIDTH

# masks
MANT_MASK = (1 << MANT_WIDTH) - 1
EXP_MASK = (1 << EXP_WIDTH) - 1
FRAC_MASK = (1 << FRAC_WIDTH) - 1

# values
EXP_MAX_NORM = EXP_MASK - 1

# debugging
DEBUG_INTERNALS = os.environ.get("DEBUG_INTERNALS", "0") == "1"


# RISC-V frm
class RoundMode(Enum):
    RNE = 0
    RTZ = 1
    RDN = 2
    RUP = 3
    RMM = 4


# ---------
# FUNCTIONS
# ---------
# ROUNDING_DECISION
#
# Description - calculates the bit that will decide in which direction to round up the fraction
def rounding_decision(mode, sign, g, r, s, lsb):
    match mode:
        case RoundMode.RNE.value:
            round_up = g & (r | s | lsb)
        case RoundMode.RTZ.value:
            round_up = 0
        case RoundMode.RDN.value:
            round_up = sign & (g | r | s)
        case RoundMode.RUP.value:
            round_up = (1 - sign) & (g | r | s)
        case RoundMode.RMM.value:
            round_up = g
        case _:
            round_up = g & (r | s | lsb)

    return round_up


def golden_reference(
    mant_i,
    exp_i,
    sign_i,
    g_i,
    r_i,
    s_i,
    rm_i,
    ovf_i=0,
    uf_i=0,
    z_i=0,
):
    frac = mant_i & FRAC_MASK
    lsb = mant_i & 1

    round_up = rounding_decision(rm_i, sign_i, g_i, r_i, s_i, lsb)

    if ovf_i:
        round_up = 0

    exp_frac = (exp_i << FRAC_WIDTH) | frac
    exp_frac_r = exp_frac + round_up

    exp_r = (exp_frac_r >> FRAC_WIDTH) & EXP_MASK
    exp_f = 0
    frac_r = exp_frac_r & FRAC_MASK
    frac_f = 0

    inexact = (g_i | r_i | s_i) & 1
    ovf_raw = ovf_i | (exp_r == EXP_MASK)

    # adjust exponent and fraction after incoming flags
    if z_i:
        exp_f, frac_f, inexact = 0, 0, 0
    else:
        if ovf_raw:
            match rm_i:
                case RoundMode.RTZ.value:
                    exp_f = EXP_MAX_NORM
                    frac_f = FRAC_MASK
                case RoundMode.RDN.value:
                    if sign_i:  # if negative, -infinity
                        exp_f = EXP_MASK
                        frac_f = 0
                    else:
                        exp_f = EXP_MAX_NORM
                        frac_f = FRAC_MASK
                case RoundMode.RUP.value:
                    if not sign_i:  # if positive, +infinity
                        exp_f = EXP_MASK
                        frac_f = 0
                    else:
                        exp_f = EXP_MAX_NORM
                        frac_f = FRAC_MASK
                case _:
                    exp_f = exp_r
                    frac_f = frac_r
        else:
            exp_f, frac_f = exp_r, frac_r

    ovf_f = ovf_raw and not z_i
    uf_f = 1 if (exp_f == 0 and not z_i and inexact) else 0
    res_f = (sign_i << (RES_WIDTH - 1)) | (exp_f << FRAC_WIDTH) | frac_f

    out: dict[str, Any] = dict(
        sign_o=sign_i,
        exp_o=exp_f,
        frac_o=frac_f,
        res_o=res_f,
        ovf_o=ovf_f,
        uf_o=uf_f,
        inexact_o=inexact,
        round_up_o=round_up,
    )

    out["_internals"] = dict(
        frac=frac,
        round_up=round_up,
        ovf_raw=ovf_raw,
        exp_frac=exp_frac,
        exp_frac_r=exp_frac_r,
        exp_r=exp_r,
        exp_f=exp_f,
        frac_r=frac_r,
        frac_f=frac_f,
    )

    return out


# coverage functions
def classify(mant, exp, sign, g, r, s, mode, zero, gold, ovf_i=0):
    if zero:
        return "zero"
    if ovf_i:
        return "incoming_overflow"
    if gold["round_up_o"] and (mant & FRAC_MASK) == FRAC_MASK:
        if exp == 0:
            return "subnormal_promote"
        return "mantissa_overflow"
    if gold["ovf_o"]:
        return "overflow"
    if gold["round_up_o"]:
        return "round_up"
    return "no_round"


@CoverPoint(
    "top.mode",
    xf=lambda t: t["mode"],
    bins=[
        RoundMode.RNE.value,
        RoundMode.RTZ.value,
        RoundMode.RDN.value,
        RoundMode.RUP.value,
        RoundMode.RMM.value,
    ],
)
@CoverPoint(
    "top.scenario",
    xf=lambda t: t["scenario"],
    bins=[
        "no_round",
        "round_up",
        "mantissa_overflow",
        "subnormal_promote",
        "overflow",
        "zero",
    ],
)
@CoverPoint("top.sign", xf=lambda t: t["sign"], bins=[0, 1])
@CoverPoint(
    "top.grs",
    xf=lambda t: (t["g"], t["r"], t["s"]),
    bins=[(a, b, c) for a in (0, 1) for b in (0, 1) for c in (0, 1)],
)
@CoverPoint("top.inexact", xf=lambda t: t["inexact"], bins=[0, 1])
@CoverPoint("top.overflow", xf=lambda t: t["overflow"], bins=[0, 1])
@CoverPoint("top.underflow", xf=lambda t: t["underflow"], bins=[0, 1])
@CoverPoint("top.overflow_in", xf=lambda t: t["ovf_i"], bins=[0, 1])
@CoverCross("top.overflow_x_mode", items=["top.overflow", "top.mode"])
@CoverCross("top.mode_x_sign", items=["top.mode", "top.sign"])
@CoverCross("top.ovfin_x_mode", items=["top.overflow_in", "top.mode"])
@CoverCross("top.ovfin_x_sign", items=["top.overflow_in", "top.sign"])
def sample(t):
    pass


# ------
# DRIVER
# ------


async def drive_and_check(
    dut,
    mant_i,
    exp_i,
    sign_i,
    g_i,
    r_i,
    s_i,
    mode_i,
    ovf_i=0,
    uf_i=0,
    zero_i=0,
    label="",
):

    dut.mant_i.value = mant_i
    dut.exp_i.value = exp_i
    dut.sign_i.value = sign_i
    dut.guard_i.value = g_i
    dut.round_i.value = r_i
    dut.sticky_i.value = s_i
    dut.overflow_i.value = ovf_i
    dut.underflow_i.value = uf_i
    dut.zero_i.value = zero_i
    dut.round_mode_i.value = mode_i

    await SETTLE

    expected = golden_reference(
        mant_i, exp_i, sign_i, g_i, r_i, s_i, mode_i, ovf_i, uf_i, zero_i
    )
    context = (
        f"mant:0x{mant_i:06x} exp:0x{exp_i:02x} sign:{sign_i} "
        f"g:{g_i} r:{r_i} s:{s_i} "
        f"ovf:{ovf_i} uf:{uf_i} zero:{zero_i} "
        f"mode:{RoundMode(mode_i)}"
    )

    got = dict(
        sign_o=int(dut.sign_o.value),
        exp_o=int(dut.exp_o.value),
        frac_o=int(dut.frac_o.value),
        res_o=int(dut.result_o.value),
        ovf_o=int(dut.overflow_o.value),
        uf_o=int(dut.underflow_o.value),
        inexact_o=int(dut.inexact_o.value),
    )

    if DEBUG_INTERNALS:
        gi = expected["_internals"]

        dut._log.info(f"\n\n")
        dut._log.info("--- GOLDEN MODEL INTERNAL SIGNALS")
        dut._log.info(f"\n")
        dut._log.info(f"round up = {gi['round_up']}")
        dut._log.info(f"overflow raw = {gi['ovf_raw']}")
        dut._log.info(
            f"exp_frac = 0x{gi['exp_frac']:08x} exp_frac_r = 0x{gi['exp_frac_r']:08x}"
        )
        dut._log.info(f"exp_r = 0x{gi['exp_r']:02x} exp_f = 0x{gi['exp_f']:02x}")
        dut._log.info(
            f"frac = 0x{gi['frac']:06x} frac_r = 0x{gi['frac_r']:06x} frac_f = 0x{gi['frac_f']:06x}"
        )
        dut._log.info(f"\n\n")

    for k in ("sign_o", "exp_o", "frac_o", "res_o", "ovf_o", "uf_o", "inexact_o"):
        if k == "_internals":
            continue
        elif k == "frac_o":
            assert (
                got[k] == expected[k]
            ), f"{k}: got 0x{got[k]:06x} expected 0x{expected[k]:06x}\n  [{context}]"
        elif k == "exp_o":
            assert (
                got[k] == expected[k]
            ), f"{k}: got 0x{got[k]:02x} expected 0x{expected[k]:02x}\n  [{context}]"
        elif k == "res_o":
            assert (
                got[k] == expected[k]
            ), f"{k}: got 0x{got[k]:08x} expected 0x{expected[k]:08x}\n  [{context}]"
        else:
            assert (
                got[k] == expected[k]
            ), f"{k}: got {got[k]} expected {expected[k]}\n  [{context}]"

    # for coverage
    sample(
        dict(
            mode=mode_i,
            scenario=classify(
                mant_i, exp_i, sign_i, g_i, r_i, s_i, mode_i, zero_i, expected, ovf_i
            ),
            sign=sign_i,
            g=g_i,
            r=r_i,
            s=s_i,
            inexact=expected["inexact_o"],
            overflow=expected["ovf_o"],
            underflow=expected["uf_o"],
            ovf_i=ovf_i,
        )
    )

    if label:
        dut._log.info(f"PASS {label}")


# --------------
# DIRECTED TESTS
# --------------
@cocotb.test()
async def test_rne(dut):
    await drive_and_check(
        dut,
        0x800000,
        0xFE,
        0,
        1,
        0,
        0,
        RoundMode.RNE.value,
        0,
        0,
        0,
        "round to infinity",
    )
    await drive_and_check(
        dut,
        0x800000,
        0xF0,
        0,
        1,
        0,
        0,
        RoundMode.RNE.value,
        0,
        0,
        0,
        "tie with even lsb",
    )
    await drive_and_check(
        dut,
        0x800001,
        0xF0,
        0,
        1,
        0,
        0,
        RoundMode.RNE.value,
        0,
        0,
        0,
        "tie with odd lsb",
    )
    # test grs combinations
    for g in [0, 1]:
        for r in [0, 1]:
            for s in [0, 1]:
                await drive_and_check(
                    dut,
                    0x800000,
                    0xF0,
                    0,
                    g,
                    r,
                    s,
                    RoundMode.RNE.value,
                    0,
                    0,
                    0,
                    f"RNE with g:{g} r:{r} s:{s}",
                )


@cocotb.test()
async def test_rtz(dut):
    await drive_and_check(
        dut,
        0x800000,
        0xF0,
        1,
        0,
        0,
        0,
        RoundMode.RTZ.value,
        0,
        0,
        0,
        "round negative number",
    )
    await drive_and_check(
        dut,
        0x800000,
        0xF0,
        0,
        0,
        0,
        0,
        RoundMode.RTZ.value,
        0,
        0,
        0,
        "round positive number",
    )

    # test grs combinations
    for g in [0, 1]:
        for r in [0, 1]:
            for s in [0, 1]:
                await drive_and_check(
                    dut,
                    0x800000,
                    0xF0,
                    0,
                    g,
                    r,
                    s,
                    RoundMode.RTZ.value,
                    0,
                    0,
                    0,
                    f"RTZ with g:{g} r:{r} s:{s}",
                )


@cocotb.test()
async def test_rdn(dut):
    await drive_and_check(
        dut, 0xFFFFFF, 0xFE, 1, 0, 0, 0, RoundMode.RDN.value, 0, 0, 0, "round to -infty"
    )
    await drive_and_check(
        dut,
        0xFFFFFF,
        0xFE,
        0,
        0,
        0,
        0,
        RoundMode.RDN.value,
        0,
        0,
        0,
        "round biggest positive",
    )

    # test grs combinations
    for g in [0, 1]:
        for r in [0, 1]:
            for s in [0, 1]:
                await drive_and_check(
                    dut,
                    0x800000,
                    0xF0,
                    0,
                    g,
                    r,
                    s,
                    RoundMode.RDN.value,
                    0,
                    0,
                    0,
                    f"RDN with g:{g} r:{r} s:{s}",
                )


@cocotb.test()
async def test_rup(dut):
    await drive_and_check(
        dut, 0xFFFFFF, 0xFE, 0, 0, 0, 0, RoundMode.RUP.value, 0, 0, 0, "round to +infty"
    )
    await drive_and_check(
        dut,
        0xFFFFFF,
        0xFE,
        1,
        0,
        0,
        0,
        RoundMode.RUP.value,
        0,
        0,
        0,
        "round biggest negative",
    )

    # test grs combinations
    for g in [0, 1]:
        for r in [0, 1]:
            for s in [0, 1]:
                await drive_and_check(
                    dut,
                    0x800000,
                    0xF0,
                    0,
                    g,
                    r,
                    s,
                    RoundMode.RUP.value,
                    0,
                    0,
                    0,
                    f"RUP with g:{g} r:{r} s:{s}",
                )


@cocotb.test()
async def test_zero_passthrough(dut):
    """zero_i forces zero output, sign preserved, no flags."""
    await drive_and_check(
        dut, 0x000000, 0, 0, 0, 0, 0, RoundMode.RNE.value, zero_i=1, label="+0"
    )
    await drive_and_check(
        dut, 0x000000, 0, 1, 0, 0, 0, RoundMode.RNE.value, zero_i=1, label="-0"
    )
    await drive_and_check(
        dut,
        0x123456,
        99,
        0,
        1,
        1,
        1,
        RoundMode.RDN.value,
        zero_i=1,
        label="zero dominates GRS",
    )


@cocotb.test()
async def test_overflow_flag(dut):
    """This test is only for overflows comming from the normalizer module."""
    for mode in [
        RoundMode.RNE.value,
        RoundMode.RTZ.value,
        RoundMode.RDN.value,
        RoundMode.RUP.value,
        RoundMode.RMM.value,
    ]:
        for sign in [0, 1]:
            await drive_and_check(
                dut,
                0xFFFFFF,
                0xFF,
                sign,
                1,
                0,
                0,
                mode,
                ovf_i=1,
                label=f"incoming overflow: MODE: {mode} sign: {sign}",
            )


# ---------------
# RANDOMIZED TEST
# ---------------
@cocotb.test()
async def random_test(dut):
    rng = random.Random(0xCACABACA)
    num_tests = 80000
    for _ in range(num_tests):
        mant_case = rng.random()
        if mant_case < 0.2:
            mant_rnd = 0
        elif mant_case < 0.5:
            mant_rnd = rng.randint(0x000001, MANT_MASK)
        else:
            mant_rnd = int(0xFFFFFF)

        # define probabilities for different exponent values
        exp_case = rng.random()
        if exp_case < 0.2:
            exp_rnd = 0
        elif exp_case < 0.4:
            exp_rnd = rng.randint(0xFA, 0xFF)
        else:
            exp_rnd = rng.randint(0, EXP_MASK)

        sign_rnd = rng.randint(0, 1)
        g_rnd = rng.randint(0, 1)
        r_rnd = rng.randint(0, 1)
        s_rnd = rng.randint(0, 1)
        mode_rnd = rng.randint(0, len(RoundMode) - 1)

        # ponderated probability of flags
        ovf_rnd = 1 if rng.random() <= 0.2 else 0
        uf_rnd = 1 if rng.random() <= 0.1 else 0
        zero_rnd = 1 if rng.random() <= 0.05 else 0

        # if overflow input is 1, that means the exponent has the reserved maximum value
        if ovf_rnd == 1:
            exp_rnd = EXP_MASK

        await drive_and_check(
            dut,
            mant_rnd,
            exp_rnd,
            sign_rnd,
            g_rnd,
            r_rnd,
            s_rnd,
            mode_rnd,
            ovf_rnd,
            uf_rnd,
            zero_rnd,
        )

    report_coverage(dut)


# ---------
# DEBUGGING
# ---------
def report_coverage(dut):
    """Print every coverpoint with per-bin hit counts

    Set COVERAGE_VERBOSE=1 to also list the hit counts of bins that were covered.
    """

    verbose = os.environ.get("COVERAGE_VERBOSE", "0") == "1"

    # make a list of the different cover points
    names = [
        "top.mode",
        "top.scenario",
        "top.sign",
        "top.grs",
        "top.inexact",
        "top.overflow",
        "top.underflow",
        "top.overflow_in",
        "top.overflow_x_mode",
        "top.mode_x_sign",
        "top.ovfin_x_mode",
        "top.ovfin_x_sign",
    ]

    dut._log.info("---------- FUNCTIONAL COVERAGE ----------")
    all_missing = []
    # get the bins that have not been tested
    for name in names:
        cp = coverage_db[name]
        detail = cp.detailed_coverage
        missing = [b for b, hits in detail.items() if hits == 0]
        flag = "" if not missing else f"   <-- {len(missing)} bins MISSING"
        dut._log.info(
            f"  {name:<22s} {cp.cover_percentage:6.2f}%  "
            f"({cp.coverage}/{cp.size} bins){flag}"
        )
        for b in missing:
            dut._log.info(f"       MISSING bin: {b!r}")
            all_missing.append(f"{name}={b!r}")
        if verbose:
            for b, hits in detail.items():
                if hits:  # print non-missing too
                    dut._log.info(f"       hit {hits:6d}x : {b!r}")

    # report the total coverage of the testbench
    total = coverage_db["top"].cover_percentage
    dut._log.info(f"  {'TOTAL':<22s} {total:6.2f}%")
    dut._log.info("--------------------------------")

    coverage_db.export_to_xml(filename="coverage_functional.xml")

    # notify missing bins if 100% was not covered
    assert total == 100.0, (
        f"Functional coverage incomplete: {total:.2f}%"
        f"Uncovered bins ({len(all_missing)}): " + ", ".join(all_missing)
    )
