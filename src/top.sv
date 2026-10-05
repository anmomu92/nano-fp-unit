module top #(
    parameter int WIDTH = 32,
    parameter int MANT_WIDTH = 24,
    parameter int EXP_WIDTH = 8,
    parameter int SHIFT_WIDTH = 8
) (
    // inputs
    input logic clk_i,   // crear un proceso secuencial que registre las entradas
    input logic rst_n_i,
    // input logic start_i
    // input logic finish_i

    input logic [WIDTH-1:0] num_a_i,
    input logic [WIDTH-1:0] num_b_i,

    input logic [1:0] format_a_i,
    input logic [1:0] format_b_i,

    input logic op_code_i,
    input logic [2:0] round_mode_i,

    // outputs
    output logic [WIDTH-1:0] result_o,
    output logic overflow_o,
    output logic underflow_o,
    output logic inexact_o,
    output logic zero_o
);
  // ----------------
  // INTERNAL SIGNALS
  // ----------------
  // adapted numbers
  logic [WIDTH-1:0] b32_num_a;
  logic [WIDTH-1:0] b32_num_b;

  // number fields
  // operands
  logic sign_a;
  logic sign_b;
  logic [EXP_WIDTH-1:0] exp_a;
  logic [EXP_WIDTH-1:0] exp_b;
  logic [EXP_WIDTH-1:0] exp_big;  // it holds the bigger exponent
  logic [MANT_WIDTH-1:0] shifted_mant;
  logic [MANT_WIDTH-1:0] unshifted_mant;
  logic [MANT_WIDTH-1:0] untouched_mant;

  // result
  logic alu_sign_norm, norm_sign_round, sign_round;
  logic [EXP_WIDTH-1:0] norm_exp_round, exp_round;
  logic [MANT_WIDTH-1:0] alu_mant_norm, norm_mant_round;
  logic [MANT_WIDTH-2:0] norm_frac;

  // GRS bits
  logic shift_guard_alu, alu_guard_norm, norm_guard_round;
  logic shift_round_alu, alu_round_norm, norm_round_round;
  logic shift_sticky_alu, alu_sticky_norm, norm_sticky_round;

  // flags
  logic alu_overflow_norm, norm_overflow_round;
  logic alu_underflow_norm, norm_underflow_round;
  logic alu_zero_norm, norm_zero_round;

  // other
  logic swap;  // 0=A, 1=B
  logic [SHIFT_WIDTH-1:0] shift;  // number of bit positions to shift
  logic implicit_a;  // implicit bit a
  logic implicit_b;  // implicit bit b

  // ----------------------
  // CONTINUOUS ASSIGNMENTS
  // ----------------------
  assign sign_a = b32_num_a[WIDTH-1];
  assign sign_b = b32_num_b[WIDTH-1];
  assign exp_a = b32_num_a[WIDTH-2:23];
  assign exp_b = b32_num_b[WIDTH-2:23];
  assign implicit_a = (exp_a) ? 1'b1 : 1'b0;
  assign implicit_b = (exp_b) ? 1'b1 : 1'b0;
  assign exp_big = (exp_a > exp_b) ? exp_a : exp_b;

  // -------------------
  // COMBINATIONAL LOGIC
  // -------------------
  always_comb begin : MANTISSA_SELECTION
    if (swap) begin
      unshifted_mant = {implicit_b, b32_num_b[22:0]};
      untouched_mant = {implicit_a, b32_num_a[22:0]};
    end else begin
      unshifted_mant = {implicit_a, b32_num_a[22:0]};
      untouched_mant = {implicit_b, b32_num_b[22:0]};
    end
  end

  // ---------------------
  // MODULE INSTANTIATIONS
  // ---------------------
  b32_adapter #(
      .WIDTH(WIDTH)
  ) b32_adapter_a_inst (
      .num_i(num_a_i),
      .format_i(format_a_i),
      .num_o(b32_num_a)
  );

  b32_adapter #(
      .WIDTH(WIDTH)
  ) b32_adapter_b_inst (
      .num_i(num_b_i),
      .format_i(format_b_i),
      .num_o(b32_num_b)
  );

  exp_diff #(
      .EXP_WIDTH(EXP_WIDTH)
  ) exp_diff_inst (
      .exp_a_i(exp_a),
      .exp_b_i(exp_b),
      .swap_o (swap),
      .shift_o(shift)
  );

  mant_shift #(
      .MANT_WIDTH(MANT_WIDTH)
  ) mant_shift_inst (
      .mant_i  (unshifted_mant),
      .shift_i (shift),
      .mant_o  (shifted_mant),
      .guard_o (shift_guard_alu),
      .round_o (shift_round_alu),
      .sticky_o(shift_sticky_alu)
  );

  alu #(
      .MANT_WIDTH(MANT_WIDTH)
  ) alu_inst (
      // inputs
      .sign_a_i(sign_a),
      .sign_b_i(sign_b),
      .mant_a_i(untouched_mant),
      .mant_b_i(shifted_mant),

      .guard_i (shift_guard_alu),
      .round_i (shift_round_alu),
      .sticky_i(shift_sticky_alu),

      .swap_i(swap),
      .op_code_i(op_code_i),

      // outputs
      .sign_o  (alu_sign_norm),
      .mant_o  (alu_mant_norm),
      .guard_o (alu_guard_norm),
      .round_o (alu_round_norm),
      .sticky_o(alu_sticky_norm),
      .carry_o (alu_overflow_norm),
      .zero_o  (alu_zero_norm)
  );

  normalizer #(
      .MANT_WIDTH(MANT_WIDTH),
      .EXP_WIDTH (EXP_WIDTH)
  ) normalizer_inst (
      // inputs
      .sign_i(alu_sign_norm),
      .exp_i(exp_big),  // TODO - I may need to recalculate the exponent in the ALU module
      .mant_i(alu_mant_norm),

      .guard_i (alu_guard_norm),
      .round_i (alu_round_norm),
      .sticky_i(alu_sticky_norm),

      .carry_i(alu_overflow_norm),  // TODO - rename the carry flag in ALU and normalizer modules
      .zero_i (alu_zero_norm),

      // outputs
      .sign_o(norm_sign_round),
      .exp_o (norm_exp_round),
      .mant_o(norm_mant_round),

      .guard_o (norm_guard_round),
      .round_o (norm_round_round),
      .sticky_o(norm_sticky_round),

      .overflow_o(norm_overflow_round),
      .underflow_o(norm_underflow_round),
      .zero_o(zero_o)
  );

  rounder #(
      .MANT_WIDTH(MANT_WIDTH),
      .EXP_WIDTH (EXP_WIDTH)
  ) rounder_inst (
      // inputs
      .sign_i(norm_sign_round),
      .exp_i (norm_exp_round),
      .mant_i(norm_mant_round),

      .guard_i (norm_guard_round),
      .round_i (norm_round_round),
      .sticky_i(norm_sticky_round),

      .overflow_i(norm_overflow_round),  // TODO - rename the carry flag in ALU module
      .underflow_i(norm_underflow_round),  // TODO - include flag in ALU module
      .zero_i(zero_o),

      .round_mode_i(round_mode_i),

      // outputs
      // TODO - revise if sign and exponent have to be connected to the output interface
      .sign_o(sign_round),
      .exp_o(exp_round),
      .frac_o(norm_frac),  // TODO - revise why is this needed
      .result_o(result_o),

      // TODO - include zero flag here and in the rounder module
      .overflow_o (overflow_o),
      .underflow_o(underflow_o),
      .inexact_o  (inexact_o)
  );

endmodule
