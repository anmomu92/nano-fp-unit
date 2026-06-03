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
    EXP_WIDTH = 8
)(
    input logic [EXP_WIDTH-1:0] exp_A,
    input logic [EXP_WIDTH-1:0] exp_B,
    output logic sel,
    output logic [EXP_WIDTH-1:0] n
);

logic [EXP_WIDTH-1:0] diff;

always_comb begin : OUTPUT_LOGIC
    diff = exp_A - exp_B;

    if(diff < 0) begin
	sel = 0;	// select exponent A
	n = -diff;
    end
    else begin
	sel = 1;	// select exponent B
	n = diff;
    end
end

endmodule
