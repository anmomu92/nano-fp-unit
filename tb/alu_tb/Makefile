# Makefile for the alu cocotb test.
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
SRC_DIR := ${PROJECT_ROOT}/src

VERILOG_SOURCES = ${SRC_DIR}/alu.sv

COCOTB_TOPLEVEL = alu
COCOTB_TEST_MODULES = test_alu

include $(shell cocotb-config --makefiles)/Makefile.sim
