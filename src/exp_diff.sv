/******************************************************************************
 * File        : exp_diff.sv
 * Author      : Antonio Moran
 * Created     : 2026-06-03
 * Last Update : 2026-06-03
 *
 * Description :
 *   Exponent difference calculator.
 *
 *   It receives two exponents and calculates their difference.
 *
 * Parameters :
 *   EXP_WIDTH    - width of the exponents
 *
 * Interface :
 *   exp_A        - exponent of number A
 *   exp_B        - exponent of number B
 *   sel          - signal to select the lower number
 *   n            - number of bit positions to shift the lower number
 *
 * Notes :
 *   - Synthesizable
 *   - Pure combinatorial logic. No need for a clock
 *
 * License :
 *   GPL-3.0 License
 ******************************************************************************/

module exp_diff #(
    parameter int EXP_WIDTH = 8
) (
    input logic [EXP_WIDTH-1:0] exp_a_i,
    input logic [EXP_WIDTH-1:0] exp_b_i,
    output logic swap_o,
    output logic [EXP_WIDTH-1:0] shift_o
);

  localparam MAX_SHIFT = 27;

  logic [EXP_WIDTH-1:0] diff;

  always_comb begin : OUTPUT_LOGIC
    swap_o = (exp_a_i >= exp_b_i) ? 0 : 1;

    if (swap_o) begin
      // exponent A is bigger, shift exponent B
      diff = exp_b_i - exp_a_i;
    end else begin
      // exponent B is bigger, shift exponent A
      diff = exp_a_i - exp_b_i;
    end

    if (diff > MAX_SHIFT) shift_o = MAX_SHIFT;
    else shift_o = diff;
  end

endmodule
