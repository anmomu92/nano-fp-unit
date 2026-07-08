"""
Runner for the b32_adapter.sv cocotb testbench.

Usage:
    python3 run_tests.py

Requires: cocotb, a Verilog simulator on PATH (default: Icarus Verilog).
"""

import os
from pathlib import Path

from cocotb_tools.runner import get_runner

SIM = os.getenv("SIM", "icarus")


def main():
    proj_path = Path(__file__).resolve().parent
    sources = [proj_path / "b32_adapter.sv"]

    runner = get_runner(SIM)
    runner.build(
        sources=sources,
        hdl_toplevel="b32_adapter",
        always=True,
        timescale=("1ns", "1ps"),
    )
    runner.test(
        hdl_toplevel="b32_adapter",
        test_module="test_adapter",
    )


if __name__ == "__main__":
    main()
