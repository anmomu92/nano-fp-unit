module b32_adapter #(
    WIDTH = 32
)(
    input wire clk,
    input wire rst_n,

    input logic [WIDTH-1:0] num,
    input logic [1:0] format,    // maybe define an enum in a package
    input logic [3:0] op_type,
    input logic [3:0] round_mode,

    output logic [WIDTH-1:0] fp_num
);

typedef enum {FORWARD, ADAPT} state_e;

state_e cur_state, next_state;

always_ff @(posedge clk) begin : STATE_MEMORY
    if (!rst_n) begin
	fp_num <= 32'1000_0000_0000_0000_0000_0000_0000_0000;	// signed zero
	cur_state <= FORWARD;
    end else begin
	cur_state <= next_state;
    end
end

always_comb begin : NEXT_STATE_LOGIC
    case(cur_state)
	FORWARD: begin
	    if(format)
		next_state = ADAPT;
	ADAPT: next_state = FORWARD;
	default: next_state = FORWARD;
    endcase
end

always_comb begin : OUTPUT_LOGIC
    fp_num <= 32'1000_0000_0000_0000_0000_0000_0000_0000;   // signed zero

    case(cur_state)
	FORWARD: fp_num = num;
	ADAPT: begin
	    case(format)
		2'b01: begin // b16
		    // Normal numbers
		    fp_num[31] = num [15];		// sign bit
		    fp_num[30:23] = num[14:10] + 112;	// change exponent bias
		    fp_num[22:0] = {num[9:0],13'b0};
		end
		2'b10: begin // integer
		    FORWARD: fp_num = num;
		end
		2'b11: begin // TODO
		    FORWARD: fp_num = num;
		end
		default:
		    FORWARD: fp_num = num;
	    endcase
	end
    endcase
end

endmodule
