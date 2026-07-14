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

module sig_shift #(
    parameter int SIG_WIDTH   = 24,
    parameter int MAX_SHIFT   = 27,
    parameter int SHIFT_WIDTH = 8
) (
    input logic [  SIG_WIDTH-1:0] sig_i,
    input logic [SHIFT_WIDTH-1:0] shift_i,

    output logic [SIG_WIDTH-1:0] sig_o,
    output logic guard_o,
    output logic round_o,
    output logic sticky_o

);

  // We need to hold a number big enough so we can get the GRS bits
  localparam int TOTAL_WIDTH = SIG_WIDTH + MAX_SHIFT;

  // We have to pad the number with 0s to the right so, when we right-shift it,
  // we can set the GRS bits accordingly
  logic [TOTAL_WIDTH-1:0] padded;
  logic [TOTAL_WIDTH-1:0] result;

  always_comb begin : OUTPUT_LOGIC
    padded = {sig_i, {MAX_SHIFT{1'b0}}};
    result = padded >> shift_i;

    sig_o = result[TOTAL_WIDTH-1:MAX_SHIFT];
    guard_o = result[MAX_SHIFT-1];
    round_o = result[MAX_SHIFT-2];
    sticky_o = |result[MAX_SHIFT-3:0];
  end


endmodule
