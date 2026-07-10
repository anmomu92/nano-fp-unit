"""
cocotb testbench for sig_shift.sv

DUT aligns the smaller significand and generates GRS bits.

Outputs:
    sig_o - shifted significand
    guard_o, round_o, sticky_o - rounding bits

Golden model:
    independent from RTL design
"""

import random

import cocotb
from cocotb.clock import Timer

SETTLE = Timer(1, unit="ns")
WIDTH = 24
MAX_WIDTH = 27


def golden_reference(significand: int, shift: int):
    shift = min(shift, MAX_SHIFT)

    result = 
