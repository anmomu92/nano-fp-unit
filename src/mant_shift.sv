//=============================================================================
// File        : mant_shift.sv
// Module      : mant_shift
// Project     : nano-fp-unit
// Author      : Antonio Moran Munoz, UCLM
// Created     : 2026-07-10
//-----------------------------------------------------------------------------
// Purpose
//   To right shift the lower operand.
//
// Specification
//   No formal spec exists.
//-----------------------------------------------------------------------------
// Parameters
//   MANT_WIDTH          : the width in bits of the mantissa. Default: 24
//   MAX_SHIFT           : the limit for the right shift.     Default: 27
//   SHIFT_WIDTH         : the width of the shifting.         Default: 8
//-----------------------------------------------------------------------------
// Interface
//
//   mant_i       : in  24    mantissa to shift
//   shift_i      : in  8     amount of shift in bits
//
//   mant_o       : out 24    resulting mantissa
//   guard_o      : out 1     guard bit
//   round_o      : out 1     round bit
//   sticky_o     : out 1     sticky bit
//-----------------------------------------------------------------------------
// Protocol
//   No interface protocol is used for data.
//
// Timing
//   Latency         : none
//   Throughput      : none
//   Back-pressure   : none
//
// Clock domains
//   None
//-----------------------------------------------------------------------------
// Implementation notes
//   Combinational logic and continuous assignments
//
//   The result logic followd the following truth table
//
//   operation | sign_a | sign_b | equation                            | sign_result
//   ----------|--------|--------|-------------------------------------|-----------------
//   0         | 0      | 0      | A - B -> substract magnitudes       | greatest operand
//   0         | 0      | 1      | A - (-B) -> add magnitudes          | 0
//   0         | 1      | 0      | (-A) - B -> add magnitudes          | 1
//   0         | 1      | 1      | (-A) - (-B) -> substract magnitudes | greatest operand
//   1         | 0      | 0      | A + B -> add magnitudes             | 0
//   1         | 0      | 1      | A + (-B) -> substract magnitudes    | greatest operand
//   1         | 1      | 0      | (-A) + B -> substract magnitudes    | greatest operand
//   1         | 1      | 1      | (-A) + (-B) -> add magnitudes       | 1
//
//   magnitude_add = operation ^ sign_a ^ sign_b
//
// Assumptions and limitations
//   None
//
// Known issues
//   None
//-----------------------------------------------------------------------------
// Verification status
//   The testbench is located under the tb/alu directory.
//   Directed tests passed.
//   Functional coverage complete: 100% - Last measurement: 2026-09-29
//
// Synthesis / implementation status
//   Not synthesized yet.
//-----------------------------------------------------------------------------
// Dependencies
//   No dependencies.
//-----------------------------------------------------------------------------
// Revision history
//   2026-07-10     Antonio Moran Munoz     Initial commit.
//-----------------------------------------------------------------------------
// GPL-3.0 License - UCLM
//=============================================================================

module mant_shift #(
    parameter int MANT_WIDTH  = 24,
    parameter int MAX_SHIFT   = 27,
    parameter int SHIFT_WIDTH = 8
) (
    input logic [ MANT_WIDTH-1:0] mant_i,
    input logic [SHIFT_WIDTH-1:0] shift_i,

    output logic [MANT_WIDTH-1:0] mant_o,
    output logic guard_o,
    output logic round_o,
    output logic sticky_o
);

  // We need to hold a number big enough so we can get the GRS bits
  localparam int TOTAL_WIDTH = MANT_WIDTH + MAX_SHIFT;

  // We have to pad the number with 0s to the right so, when we right-shift it,
  // we can set the GRS bits accordingly
  logic [TOTAL_WIDTH-1:0] padded;
  logic [TOTAL_WIDTH-1:0] result;

  logic [SHIFT_WIDTH-1:0] effective_shift;

  // shift_i might be greater than MAX_SHIFT.
  // to avoid shifting so many positions, we have to
  // trim the value to MAX_SHIFT in those cases.
  always_comb begin : EFFECTIVE_SHIFT
    if (shift_i > MAX_SHIFT) effective_shift = 'd27;
    else effective_shift = shift_i;
  end

  always_comb begin : OUTPUT_LOGIC
    padded   = {mant_i, {MAX_SHIFT{1'b0}}};
    result   = padded >> shift_i;

    mant_o   = result[TOTAL_WIDTH-1:MAX_SHIFT];
    guard_o  = result[MAX_SHIFT-1];
    round_o  = result[MAX_SHIFT-2];
    sticky_o = |result[MAX_SHIFT-3:0];
  end

endmodule
