# Makefile for the adapter (binary16 -> binary32) cocotb testbench.
#
# Layout this Makefile assumes:
#   <project_root>/src/b32_adapter.sv
#   <project_root>/tb/adapter/Makefile        <- this file
#   <project_root>/tb/adapter/test_adapter.py
#
# Usage (run from this directory, tb/adapter/):
#   make                 # build + run with the default simulator (Icarus Verilog)
#   make SIM=verilator   # run with a different cocotb-supported simulator
#   make WAVES=1         # dump a waveform (sim_build/adapter.fst / .vcd)
#   make clean           # remove build/sim artifacts

SIM ?= icarus
TOPLEVEL_LANG ?= verilog

# Resolve paths relative to this Makefile's own location, so `make` behaves
# the same whether invoked from tb/adapter/ directly or via
# `make -C tb/adapter` from elsewhere (e.g. a CI job or a root Makefile).
THIS_DIR     := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
PROJECT_ROOT := $(abspath $(THIS_DIR)/../..)
SRC_DIR      := $(PROJECT_ROOT)/src

VERILOG_SOURCES = $(SRC_DIR)/b32_adapter.sv

# Name of the top-level module to instantiate, and the Python file
# (without .py) containing the @cocotb.test() functions.
COCOTB_TOPLEVEL     = b32_adapter 
COCOTB_TEST_MODULES = test_adapter

include $(shell cocotb-config --makefiles)/Makefile.sim
