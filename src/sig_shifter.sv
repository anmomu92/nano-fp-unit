// sig_shifter.sv
//
// Parameters:
//  WIDTH - width of the significand without GRS bits
//  MAX_WIDTH - width of the significand with GRS bits
//
// Inputs:
//  sig_i - the un-shifted significand
//  shift_i - number of bit positions to right shift the significand
//
// Outputs:
//  sig_o - the shifted significand

module sig_shifter #(
    parameter int WIDTH = 24,
    parameter int MAX_WIDTH = 27,
    parameter int SHIFT_WIDTH = 8
) (
    input logic [WIDTH-1:0] sig_i,
    input logic shift_i,

    output logic [WIDTH-1:0] sig_o,
    output logic guard_o,
    output logic round_o,
    output logic sticky_o

);

  // We need to hold a number big enough so we can get the GRS bits
  localparam int TOTAL_WIDTH = WIDTH + MAX_WIDTH;

  logic [TOTAL_WIDTH-1:0] result;

  always_comb begin : OUTPUT_LOGIC
    result = sig_i >> shift_i;

    sig_o = result[TOTAL_WIDTH-1:MAX_WIDTH];
    guard_o = result[MAX_WIDTH-1];
    round_o = result[MAX_WIDTH-2];
    sticky_o = |result[MAX_WIDTH-3:0];
  end


endmodule
