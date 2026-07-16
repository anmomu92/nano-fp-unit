/******************************************************************************
 * File        : alu.sv
 * Author      : Antonio Moran
 * Created     : 2026-06-10
 * Last Update : 2026-06-10
 *
 * Description :
 *   This module performs arithmetic-logic operations with the significands.
 *
 *   It receives two exponents and calculates their difference.
 *
 * Truth table
 *
     * operation | sign_a | sign_b | equation | sign_result
     * 0 | 0 | 0 | A - B -> substract magnitudes | greatest operand
     * 0 | 0 | 1 | A - (-B) -> add magnitudes | 0
     * 0 | 1 | 0 | (-A) - B -> add magnitudes | 1
     * 0 | 1 | 1 | (-A) - (-B) -> substract magnitudes | greatest operand
     * 1 | 0 | 0 | A + B -> add magnitudes | 0
     * 1 | 0 | 1 | A + (-B) -> substract magnitudes | greatest operand
     * 1 | 1 | 0 | (-A) + B -> substract magnitudes | greatest operand
     * 1 | 1 | 1 | (-A) + (-B) -> add magnitudes | 1
     *
     * effective_add  = operation ^ sign_a ^ sign_b
     *
 *
 * Parameters :
 *   - MANT_WIDTH - width of the significands.
 *
 * Interface :
 *   mant_a_i    - exponent of number A
 *   mant_b_i    - exponent of number B
 *   op_code_i  - operation code
 *   res_o      - result of the operation
 *
 * Notes :
 *   - Not tested
 *   - We assume the smaller number (the shifted one) comes through mant_b
 *   signal
 *
 * License :
 *   GPL-3.0 License
 ******************************************************************************/

module alu #(
    parameter int MANT_WIDTH = 24
) (
    // inputs
    input logic sign_a_i,
    input logic sign_b_i,
    input logic [MANT_WIDTH-1:0] mant_a_i,  // this is the unshifted significand
    input logic [MANT_WIDTH-1:0] mant_b_i,  // this is the shifted significand

    input logic op_code_i,

    input logic guard_i,
    input logic round_i,
    input logic sticky_i,

    input logic swap_i,  // indicates if operands were swapped during exp_diff

    // outputs
    output logic [MANT_WIDTH-1:0] res_o,
    output logic guard_o,
    output logic round_o,
    output logic sticky_o,

    output logic sign_o,

    output logic carry_o
);

  // local parameters
  localparam int EXT_WIDTH = MANT_WIDTH + 3;  // significand width + grs bits
  localparam int FULL_WIDTH = EXT_WIDTH + 1;  // carry bit + extended width

  // internal signals
  logic magnitude_add;  // this signal indicates if the magnitudes have to be added, regardless of the operation type
  logic [EXT_WIDTH-1:0] op_a;
  logic [EXT_WIDTH-1:0] op_b;
  logic [FULL_WIDTH-1:0] raw_sum;  // the result of the operation has to include the carry bit

  logic carry_raw;
  logic [EXT_WIDTH-1:0] sum;  // this signal carries the sum of the operation
  logic [EXT_WIDTH-1:0] abs_value;  // this signal carries the absolute value of the result

  // continuous assignments
  assign carry_raw = raw_sum[EXT_WIDTH];
  assign sum = raw_sum[EXT_WIDTH-1:0];
  assign magnitude_add = op_type_i ^ sign_a_i ^ sign_b_i;

  assign carry_o = magnitude_add && carry_raw;
  assign res_o = abs_value[EXT_WIDTH-1:3];  // remove grs bits
  assign guard_o = abs_value[2];
  assign round_o = abs_value[1];
  assign sticky_o = abs_value[0];

  // The lower operand is always going to enter through the mant_b_i signal. So
  // if we want to substract the greater operand from it, we need to swap them
  // We do not need to swap the signs because they are not swapped previously
  always_comb begin : SWAP_OPERANDS
    if (swap_i) begin
      op_a = {mant_b_i, guard_i, round_i, sticky_i};
      op_b = {mant_a_i, 3'b0};
    end else begin
      op_a = {mant_a_i, 3'b000};
      op_b = {mant_b_i, guard_i, round_i, sticky_i};
    end
  end

  always_comb begin : OPERATION
    unique case (magnitude_add)
      1'b0: begin  // substraction (2's complement)
        raw_sum = {1'b0, op_a} - {1'b0, ~op_b} + {{EXT_WIDTH{1'b0}}, 1'b1};
        sign_o = swap_i; // if there was a swap, it means that the greater value was substracted from the lower one
      end
      1'b1: begin  // addition
        raw_sum = {1'b0, op_a} + {1'b0, op_b};
      end
      default: res_o = 0;
    endcase
  end

  always_comb begin : ABSOLUTE_VALUE
    if (!carry_raw && !magnitude_add) abs_value = ~sum + {{EXT_WIDTH - 1{1'b0}}, 1'b1};
    else abs_value = sum;
  end

  always_comb begin : MANT_VALUE
    if (magnitude_add) sign_result_o = sign_a_i;
    else sign_result_o = carry_raw ? sign_a_i : sign_shifted;
  end

endmodule
