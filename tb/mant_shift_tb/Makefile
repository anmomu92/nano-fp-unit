# Makefile for the sig_shift cocotb test.
#
# Usage:
# 	make
# 	make SIM=verilator
# 	make WAVES=1
# 	make clean

SIM ?= icarus
TOPLEVEL_LANG ?= verilog

THIS_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
PROJECT_ROOT := $(abspath $(THIS_DIR)/../..)
SRC_DIR := $(PROJECT_ROOT)/src

VERILOG_SOURCES = $(SRC_DIR)/mant_shift.sv

COCOTB_TOPLEVEL = mant_shift
COCOTB_TEST_MODULES = test_mant_shift

include $(shell cocotb-config --makefiles)/Makefile.sim
