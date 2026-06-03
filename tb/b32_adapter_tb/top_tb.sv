`timescale 1ns/1ps

module top_tb;

    // Parameters
    localparam int WIDTH = 32;
    localparam int CLK_PERIOD = 10;

    // Variables
    logic clk = 0;
    logic rst = 1;

    logic [WIDTH-1:0] num = 32'b0000_0000_0000_0000_1011_1011_0100_1000; // b32 -> 1100_0101_1010_0100_0000_0000_0000_0000
    logic [1:0] format = 2'b01;
    logic [3:0] round_mode = 0;
    logic [3:0] op_type = 0;

    // --------------------------------------------------------------
    // Clock
    // --------------------------------------------------------------
    always #(CLK_PERIOD/2) clk = ~clk;

    // Module instantiation
    b32_adapter #(
	.WIDTH(WIDTH)
    ) b32_adapter_i (
	.clk(clk),
	.rst_n(rst),
	.num(num),
	.format(format),
	.round_mode(round_mode),
	.op_type(op_type)
    );

    // --------------------------------------------------------------
    // Initialization
    // --------------------------------------------------------------
    initial begin
	$display("====================================================");
	$display("  Adapter Testbench  –  SystemVerilog");
	$display("====================================================");

	// reset the design
	#1 rst = 0;
	#1 rst = 1;
    end
    
    // --------------------------------------------------------------
    // Timeout watchdog
    // --------------------------------------------------------------
    initial begin
	#500_000;
	$display("[TIMEOUT] Simulation exceeded time limit.");
	$finish;
    end

    // --------------------------------------------------------------
    // Waveform dump (comment out if not needed)
    // --------------------------------------------------------------
    initial begin
	$dumpfile("vcd/b32_adapter.vcd");
	$dumpvars(0, top_tb);
    end


endmodule
