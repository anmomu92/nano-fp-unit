/******************************************************************************
 * File        : top_tb.sv
 * Author      : Antonio Moran
 * Created     : 2026-06-11
 * Last Update : 2026-06-11
 *
 * Description :
 *   Testbench for the alu module
 *
 * Notes :
 *   - Non-synthesizable
 *
 * License :
 *   GPL-3.0 License
 ******************************************************************************/

`timescale 1ns / 1ps

module top_tb;

  // --------------------------------------------------------------
  // Parameters
  // --------------------------------------------------------------
  localparam WIDTH = 30;

  // --------------------------------------------------------------
  // Variables
  // --------------------------------------------------------------
  logic [WIDTH-1:0] sig_A;
  logic [WIDTH-1:0] sig_B;
  logic op_code;
  logic [WIDTH-1:0] res;

  // --------------------------------------------------------------
  // Instantiation
  // --------------------------------------------------------------
  exp_diff #(
      .WIDTH(WIDTH)
  ) exp_diff_i (
      .sig_A(sig_A),
      .sig_B(sig_B),
      .op_code(op_code),
      .res(res)
  );

  // --------------------------------------------------------------
  // Initilization
  // --------------------------------------------------------------
  initial begin
    $display("=================================================");
    $display("  ALU Testbench - SystemVerilog  ");
    $display("=================================================");

    sig_A = 30'h0000FFFF;
    sig_B = 30'h3FFF0000;

    #125_000 sig_A = 30'h0000FFFF;
    sig_B = 30'h3FFFFFFF;


    #125_000 sig_A = 30'h0000421F;
    sig_B = 30'h001A08CB;


  end

  // --------------------------------------------------------------
  // Timeout Watchdog
  // --------------------------------------------------------------
  initial begin
    #500_000;
    $display("[TIMEOUT] Simulation exceeded time limit.");
    $finish();
  end

  // --------------------------------------------------------------
  // Waveform dump
  // --------------------------------------------------------------
  initial begin
    $dumpfile("vcd/exp_diff.vcd");
    $dumpvars(0, top_tb);
  end

endmodule
