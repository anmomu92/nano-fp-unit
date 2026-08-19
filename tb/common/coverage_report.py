import os

from cocotb_coverage.coverage import coverage_db


def report_coverage(dut, coverage):
    """
    Print every coverpoint with per-bin hit counts

    Set COVERAGE_VERBOSE=1 to also list the hit counts of bins that were covered.
    """

    verbose = os.environ.get("COVERAGE_VERBOSE", "0") == "1"

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
            all_missing.append(f"\n\t{name}={b!r}")
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
        f"Functional coverage incomplete: {total:.2f}%\n"
        f"Uncovered bins ({len(all_missing)}): " + "".join(all_missing)
    )
