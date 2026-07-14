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
 * Parameters :
 *   - WIDTH - width of the significands.
 *
 * Interface :
 *   sig_a_i    - exponent of number A
 *   sig_b_i    - exponent of number B
 *   op_code_i  - operation code
 *   res_o      - result of the operation
 *
 * Notes :
 *   - Not tested
 *   - We assume the smaller number (the shifted one) comes through sig_b
 *   signal
 *   - We have to calculate the sign bit in the exp_diff module (it equals the
 *   sign of the larger operand)
 *
 * License :
 *   GPL-3.0 License
 ******************************************************************************/

module alu #(
    SIG_WIDTH = 24
) (
    input logic [SIG_WIDTH-1:0] sig_a_i,
    input logic [SIG_WIDTH-1:0] sig_b_i,
    input logic op_code_i,
    input logic guard_i,
    input logic round_i,
    input logic sticky_i,

    input logic swap_i,  // indicates if operands were swapped during exp_diff

    output logic [WIDTH-1:0] res_o,
    output logic guard_o,
    output logic round_o,
    output logic sticky_o
);

  logic [  SIG_WIDTH:0] aux;
  logic [SIG_WIDTH-1:0] op_a;
  logic [SIG_WIDTH-1:0] op_b;

  always_comb begin : SWAP_OPERANDS
    if (swap_i) begin
      op_a = sig_b_i;
      op_b = sig_a_i;
    end else begin
      op_a = sig_a_i;
      op_b = sig_b_i;
    end
  end

  always_comb begin : OUTPUT_LOGIC
    unique case (op_code)
      1'b0: begin  // substraction
        aux = {1'b0, op_a} - {1'b0, op_b};

      end
      1'b1: begin  // addition
        aux = {1'b0, op_a} + {1'b0, op_b};
      end
      default: res = 0;
    endcase
  end

endmodule
