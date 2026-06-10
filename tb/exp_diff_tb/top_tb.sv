/******************************************************************************
 * File        : top_tb.sv
 * Author      : Antonio Moran
 * Created     : 2026-06-09
 * Last Update : 2026-06-09
 *
 * Description :
 *   Testbench for the exp_diff module
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
  localparam EXP_WIDTH = 8;

  // --------------------------------------------------------------
  // Variables
  // --------------------------------------------------------------
  logic [EXP_WIDTH-1:0] exp_A;
  logic [EXP_WIDTH-1:0] exp_B;
  logic sel;
  logic [EXP_WIDTH-1:0] n;

  // --------------------------------------------------------------
  // Instantiation
  // --------------------------------------------------------------
  exp_diff #(
      .EXP_WIDTH(EXP_WIDTH)
  ) exp_diff_i (
      .exp_A(exp_A),
      .exp_B(exp_B),
      .sel(sel),
      .n(n)
  );

  // --------------------------------------------------------------
  // Initilization
  // --------------------------------------------------------------
  initial begin
    $display("=================================================");
    $display("  Exponent Difference Testbench - SystemVerilog  ");
    $display("=================================================");

    exp_A = 11;
    exp_B = 5;

    #125_000 exp_A = 3;
    exp_B = 7;

    #125_000 exp_A = 2;
    exp_B = 2;

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
