# Makefile for the exp_diff cocotb test.
#
# Usage:
# 	make
# 	make SIM=verilator
# 	make WAVES=1
# 	make clean

SIM ?= icarus
COVERAGE_VERBOSE ?= 0
TOPLEVEL_LANG ?= verilog

THIS_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
PROJECT_ROOT := $(abspath $(THIS_DIR)/../..)
SRC_DIR := $(PROJECT_ROOT)/src

export PYTHONPATH := $(THIS_DIR)/..:$(PYTHONPATH)

VERILOG_SOURCES := $(SRC_DIR)/exp_diff.sv

COCOTB_TOPLEVEL = exp_diff
COCOTB_TEST_MODULES = test_exp_diff

include $(shell cocotb-config --makefiles)/Makefile.sim
