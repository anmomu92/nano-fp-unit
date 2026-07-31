// ----------------------------------------------
// normalizer.sv
//
// Author: Antonio Morán Muñoz (anmomu92)
//
// -- Three situations
//
// 1. Overflow - carry_i == 1
//    exponent - we have to add 1 to it, so we have to check if the resulting
//    exponent reaches the reserved value 255. If it does, we have to set the
//    overflow flag.
//    mantissa - we have to right shift it by 1, so GRS bits have to be
//    recomputed.
// 2. Normalised - carry_i == 0 && mant_i[MANT_WIDTH-1] == 1
//    exponent - stays the same.
//    mantissa - stays the same.
// 3. Underflow (subnorm. num.) - carry_i == 0 && mant_i[MANT_WIDTH-1] == 0
//    exponent - we have to substract as many times as leading zeros there are
//    in the mantissa, so we have to check if the exponent reaches the
//    reserved zero value.
//    mantissa - we have to left shift it as many times as leading zeros it
//    has.
//    underflow flag - if exponent is zero and there are still leading zeros
//    in the mantissa, we have to set the underflow flag
//

module normalizer #(
    parameter int MANT_WIDTH = 24,
    parameter int EXP_WIDTH  = 8
) (
    // --------
    // inputs
    // --------
    input logic [MANT_WIDTH-1:0] mant_i,
    input logic [EXP_WIDTH-1:0] exp_i,
    input logic sign_i,

    // rounding bits
    input logic guard_i,
    input logic round_i,
    input logic sticky_i,

    // carry bit
    input logic carry_i,

    input logic zero_i,

    // --------
    // outputs
    // --------
    output logic [MANT_WIDTH-1:0] mant_o,
    output logic [EXP_WIDTH-1:0] exp_o,
    output logic sign_o,

    // rounding bits
    output logic guard_o,
    output logic round_o,
    output logic sticky_o,

    // status bits
    output logic zero_o,
    output logic underflow_o,
    output logic overflow_o
);

  // ----------------
  // LOCAL PARAMETERS
  // ----------------
  localparam int EXT_WIDTH = MANT_WIDTH + 3;
  localparam int SHIFT_WIDTH = $clog2(
      MANT_WIDTH + 1
  );  // it holds the number of bits to shift depending on the width of the mantissa
  localparam logic [EXP_WIDTH-1:0] EXP_MAX = {EXP_WIDTH{1'b1}};

  // ----------------
  // INTERNAL SIGNALS
  // ----------------

  // subnormal-related signals
  logic [EXT_WIDTH-1:0] extended_mant;
  logic [EXT_WIDTH-1:0] shifted_mant;
  logic [SHIFT_WIDTH-1:0] lz_raw;
  logic [SHIFT_WIDTH-1:0] lz_eff;
  logic [EXP_WIDTH-1:0] headroom;
  logic subnormal_result;

  // case-related signals
  logic carry_case;
  logic normal_case;


  // ---------
  // FUNCTIONS
  // ---------

  // LEADING-ZERO COUNT FUNCTION
  //
  // - Description: it traverses the input from MSB to LSB increasing a counter
  // for every 0 bit until it encounters a 1 bit.
  //
  // - Inputs:
  //    mant - the mantissa whose leading zero bits we want to count.
  //
  // - Outputs:
  //    lzc - the number of leading zeros of the mantissa.
  function automatic logic [SHIFT_WIDTH-1:0] lzc(input logic [MANT_WIDTH-1:0] mant);
    integer i;
    logic one;
    logic [SHIFT_WIDTH-1:0] cnt;
    begin
      one = 1'b0;
      cnt = '0;

      for (i = MANT_WIDTH - 1; i >= 0; i--) begin
        if (!one) begin
          if (mant[i]) begin
            one = 1'b1;
          end else begin
            cnt = cnt + 1'b1;
          end
        end
      end
      lzc = cnt;
    end
  endfunction

  // ----------------------
  // CONTINUOUS ASSIGNMENTS
  // ----------------------
  // subnormal
  assign extended_mant = {
    mant_i[MANT_WIDTH-1:0], guard_i, round_i, sticky_i
  };  // merge all signals into one
  assign shifted_mant = extended_mant << lz_eff;

  // cases
  assign carry_case = carry_i;
  assign normal_case = ~carry_i & mant_i[MANT_WIDTH-1];

  // -------------------
  // COMBINATORIAL LOGIC
  // -------------------

  // The exponent cannot be substracted to a value lower than 0 because it
  // would wrap to 255, therefore: exponent - lzc >= 1
  // Doing an arithmetic rearrangement we get the following formula:
  // lzc <= exponent - 1, we give exponent - 1 the name of headroom
  always_comb begin : SUBNORMAL_CASE
    lz_raw   = lzc(mant_i[MANT_WIDTH-1:0]);
    headroom = (exp_i == '0) ? '0 : (exp_i - 1'b1);

    if ({{(EXP_WIDTH - SHIFT_WIDTH) {1'b0}}, lz_raw} <= headroom) begin
      // the result of the normalization will be subnormal
      lz_eff = lz_raw;
      subnormal_result = 1'b0;
    end else begin
      // the result of the normalization will be normal
      lz_eff = headroom[SHIFT_WIDTH-1:0];
      subnormal_result = 1'b1;
    end
  end

  always_comb begin : OUTPUT_LOGIC
    sign_o = sign_i;
    zero_o = zero_i;
    overflow_o = 1'b0;
    underflow_o = 1'b0;

    if (zero_i) begin
      mant_o = 0;
      exp_o = 0;

      // GRS bits
      guard_o = 0;
      round_o = 0;
      sticky_o = 0;
    end else if (carry_case) begin  // overflow
      mant_o = {carry_i, mant_i[MANT_WIDTH-1:1]};
      exp_o = exp_i + 1'b1;

      // GRS bits
      guard_o = mant_i[0];
      round_o = guard_i;
      sticky_o = round_i | sticky_i;

      // check if exponent overflows
      if (exp_i >= (EXP_MAX - 1'b1)) overflow_o = 1'b1;
    end else begin
      if (normal_case) begin  // normal
        mant_o = mant_i[MANT_WIDTH-1:0];
        // there may be cases where 
        exp_o = (exp_i == '0) ? {{(EXP_WIDTH - 1) {1'b0}}, 1'b1} : exp_i[EXP_WIDTH-1:0];

        // GRS bits
        guard_o = guard_i;
        round_o = round_i;
        sticky_o = sticky_i;
      end else begin  // underflow
        mant_o = shifted_mant[EXT_WIDTH-1:3];
        exp_o = exp_i - lz_eff;

        // GRS bits
        guard_o = shifted_mant[2];
        round_o = shifted_mant[1];
        sticky_o = shifted_mant[0];

        if (subnormal_result) begin
          exp_o = '0;
          underflow_o = 1'b1;
        end else begin
          exp_o = exp_i - {{(EXP_WIDTH - SHIFT_WIDTH) {1'b0}}, lz_eff};
          underflow_o = 1'b0;
        end
      end
    end
  end

endmodule
