# Makefile for the normalizer cocotb testbench + coverage.
#
#   make            # functional test + functional-coverage %   (Icarus + cocotb-coverage)
#   make coverage   # RTL line/toggle coverage %                (standalone Verilator)
#   make clean      # remove all build/sim/coverage artifacts
#   make DEBUG_INTERNALS=1
#   make WAVES=1
#
# Two independent notions of "coverage" are reported:
#   • functional (scenario) coverage — from the cocotb testbench, prints a
#     per-point table and a TOTAL %; written to coverage_functional.xml.
#   • RTL line/toggle coverage — from Verilator instrumentation of the SV.
#
# A standalone Verilator flow is used for RTL coverage because cocotb 2.0's
# built-in Verilator support requires Verilator >= 5.036.

SIM ?= icarus
TOPLEVEL_LANG ?= verilog

.DEFAULT_GOAL := sim   # plain `make` runs the cocotb sim, not the coverage target

THIS_DIR     := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
PROJECT_ROOT := $(abspath $(THIS_DIR)/../..)
SRC_DIR      := $(PROJECT_ROOT)/src

VERILOG_SOURCES     = $(SRC_DIR)/normalizer.sv
COCOTB_TOPLEVEL     = normalizer
COCOTB_TEST_MODULES = test_normalizer

DEBUG_INTERNALS ?= 0
export DEBUG_INTERNALS

.PHONY: coverage
coverage:
	@./run_coverage.sh

# Extend cocotb's clean with our coverage artifacts.
.PHONY: clean_cov
clean_cov:
	rm -rf obj_dir coverage.dat coverage_annotated coverage_functional.xml
clean:: clean_cov

include $(shell cocotb-config --makefiles)/Makefile.sim
