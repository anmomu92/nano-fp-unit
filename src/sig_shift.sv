// mant_shifter.sv
//
// Parameters:
//  WIDTH - width of the mantissa without GRS bits
//  MAX_WIDTH - width of the mantissa with GRS bits
//
// Inputs:
//  mant_i - the un-shifted mantissa
//  shift_i - number of bit positions to right shift the mantissa
//
// Outputs:
//  mant_o - the shifted mantissa

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
