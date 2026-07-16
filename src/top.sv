module top #(
    parameter int WIDTH = 32,
    parameter int MANT_WIDTH = 24,
    parameter int EXP_WIDTH = 8
) (
    // inputs
    input logic clk_i,
    input logic rst_n_i,

    input logic [WIDTH-1:0] num_a_i,
    input logic [WIDTH-1:0] num_b_i,
    input logic [1:0] format_a_i,
    input logic [1:0] format_b_i,
    input logic op_code_i
);

  // internal signals
  logic [WIDTH-1:0] b32_num_a;
  logic [WIDTH-1:0] b32_num_b;

  logic sign_a;
  logic sign_b;
  logic sign_res;

  logic [EXP_WIDTH-1:0] exp_a;
  logic [EXP_WIDTH-1:0] exp_b;

  logic [MANT_WIDTH-1:0] shifted_mant;
  logic [MANT_WIDTH-1:0] unshifted_mant;
  logic [MANT_WIDTH-1:0] untouched_mant;
  logic [MANT_WIDTH-1:0] mant_res;

  logic guard_bit_pre, guard_bit_post;
  logic round_bit_pre, round_bit_post;
  logic sticky_bit_pre, sticky_bit_post;

  logic sel;  // 0=A, 1=B
  logic shift;  // number of bit positions to shift

  logic carry_res;

  // continuous assignments
  assign sign_a = b32_num_a[WIDTH-1];
  assign sign_b = b32_num_b[WIDTH-1];
  assign exp_a  = b32_num_a[WIDTH-2:23];
  assign exp_b  = b32_num_b[WIDTH-2:23];

  // combinational logic
  always_comb begin : MANTISSA_SELECTION
    if (sel) begin
      unshifted_mant = {1'b1, b32_num_b[22:0]};
      untouched_mant = {1'b1, b32_num_a[22:0]};
    end else begin
      unshifted_mant = {1'b1, b32_num_a[22:0]};
      untouched_mant = {1'b1, b32_num_b[22:0]};
    end
  end

  // module instantiations
  b32_adapter #(
      .WIDTH(WIDTH)
  ) b32_adapter_a_inst (
      .num_i (num_a_i),
      .format(format_a_i),
      .num_o (b32_num_a)
  );

  b32_adapter #(
      .WIDTH(WIDTH)
  ) b32_adapter_b_inst (
      .num_i (num_b_i),
      .format(format_b_i),
      .num_o (b32_num_b)
  );

  exp_diff #(
      .EXP_WIDTH(EXP_WIDTH)
  ) exp_diff_inst (
      .exp_a_i(exp_a),
      .exp_b_i(exp_b),
      .sel_o  (sel),
      .shift_o(shift)
      // TODO .swap()
  );

  mant_shift #(
      .MANT_WIDTH(MANT_WIDTH)
  ) mant_shift_inst (
      .mant_i  (unshifted_mant),
      .shift_i (shift),
      .mant_o  (shifted_mant),
      .guard_o (guard_bit_pre),
      .round_o (round_bit_pre),
      .sticky_o(sticky_bit_pre)
  );

  alu #(
      .MANT_WIDTH(MANT_WIDTH)
  ) alu_inst (
      .sign_a_i(sign_a),
      .sign_b_i(sign_b),
      .mant_a_i(untouched_mant),
      .mant_b_i(shifted_mant),
      .op_code_i(op_code_i),
      .guard_i(guard_bit_pre),
      .round_i(round_bit_pre),
      .sticky_i(sticky_bit_pre),
      .swap_i(swap),
      .res_o(res_mant),
      .guard_o(guard_bit_post),
      .round_o(round_bit_post),
      .sticky_o(sticky_bit_post),
      .sign_o(sign_res),
      .carry_o(carry_res)
  );


endmodule
