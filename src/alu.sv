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
 *   sig_A    - exponent of number A
 *   sig_B    - exponent of number B
 *   op_code  - operation code
 *   res      - result of the operation
 *
 * Notes :
 *   - Synthesizable
 *
 * License :
 *   GPL-3.0 License
 ******************************************************************************/

module alu #(
    WIDTH = 30
) (
    input logic [WIDTH-1:0] sig_A,
    input logic [WIDTH-1:0] sig_B,
    input logic op_code,

    output logic [WIDTH-1:0] res
);

  always_comb begin : OUTPUT_LOGIC
    unique case (op_code)
      1'b0: res = sig_A - sig_B;
      1'b1: res = sig_A + sig_B;
      default: res = 0;
    endcase
  end

endmodule
