//=============================================================================
// File        : exp_diff.sv
// Module      : exp_diff
// Project     : nano-fp-unit
// Author      : Antonio Moran Munoz, UCLM
// Created     : 2026-06-03
//-----------------------------------------------------------------------------
// Purpose
//   To compare the operands and select the lower one.
//
// Specification
//   No formal spec exists.
//-----------------------------------------------------------------------------
// Parameters
//   EXP_WIDTH          : the width in bits of the exponents. Default: 8
//-----------------------------------------------------------------------------
// Interface
//
//   exp_a_i     : in  8      exponent of operand a
//   exp_b_i     : in  8      exponent of operand b
//
//   swap_o       : out 1     flag to indicate a swap in the operands
//   shift_o      : out 8     number of bits to right shift the lower number
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
// Assumptions and limitations
//   None
//
// Known issues
//   None
//-----------------------------------------------------------------------------
// Verification status
//   The testbench is located under the tb/exp_diff directory.
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
//   2026-06-03     Antonio Moran Munoz     Initial commit.
//-----------------------------------------------------------------------------
// GPL-3.0 License - UCLM
//=============================================================================

module exp_diff #(
    parameter int EXP_WIDTH = 8
) (
    input logic [EXP_WIDTH-1:0] exp_a_i,
    input logic [EXP_WIDTH-1:0] exp_b_i,
    output logic swap_o,
    output logic [EXP_WIDTH-1:0] shift_o
);

  localparam MAX_SHIFT = 27;

  logic [EXP_WIDTH-1:0] diff;

  always_comb begin : OUTPUT_LOGIC
    swap_o = (exp_a_i >= exp_b_i) ? 0 : 1;

    if (swap_o) begin
      // exponent A is bigger, shift exponent B
      diff = exp_b_i - exp_a_i;
    end else begin
      // exponent B is bigger, shift exponent A
      diff = exp_a_i - exp_b_i;
    end

    if (diff > MAX_SHIFT) shift_o = MAX_SHIFT;
    else shift_o = diff;
  end

endmodule
