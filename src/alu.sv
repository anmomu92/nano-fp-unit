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
 *   clk      - clock signal
 *   rst_n    - active low reset signal
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
    WIDTH = 23
) (
    input clk,
    input rst_n,

    input [WIDTH-1:0] sig_A,
    input [WIDTH-1:0] sig_B,
    input [3:0] op_code,

    output logic [30:0] res
);

  always_ff @(posedge clk) begin : CLK_LOGIC
    if (!rst_n) begin
      res <= 0;
    end
  end

  always_comb begin : OUTPUT_LOGIC

  end

endmodule
