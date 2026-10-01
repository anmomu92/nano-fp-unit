//=============================================================================
// File        : rounder.sv
// Module      : rounder
// Project     : nano-fp-unit
// Author      : Antonio Moran Munoz, UCLM
// Created     : 2026-07-31
//-----------------------------------------------------------------------------
// Purpose
//   To round the result of the operation as defined in the IEEE-754 Std.
//
// Specification
//   No formal spec exists.
//-----------------------------------------------------------------------------
// Parameters
//   MANT_WIDTH          : the width in bits of the mantissa. Default: 24
//   EXP_WIDTH           : the width in bits of the exponent. Default: 8
//-----------------------------------------------------------------------------
// Interface
//   sign_i       : in  1     sign of the number to round
//   exp_i        : in  8     exponent of the number to round
//   mant_i       : in  24    mantissa of the number to round
//   guard_i      : in  1     guard bit
//   round_i      : in  1     round bit
//   sticky_i     : in  1     sticky bit 
//   overflow_i   : in  1     overflow flag before rounding
//   underflow_i  : in  1     underflow flag bejore rounding
//   zero_i       : in  1     zero flag
//   round_mode_i : in  3     rounding mode
//     000: RNE     Round to Nearest, ties to Even (default).
//     001: RTZ     Round towards Zero.
//     010: RDN     Round Down (towards $-\infty$).
//     011: RUP     Round Up (towards $+\infty$).
//     100: RMM     Round to Nearest, ties to Max Magnitude.
//
//   sign_o       : in  1     sign of the rounded number
//   exp_o        : in  8     exponent of the rounded number
//   frac_o       : in  23    fraction of the rounded number
//   result_o     : in  32    rounded number
//   overflow_o   : in  1     overflow flag after rounding
//   underflow_o  : in  1     underflow flag after rounding
//   inexact_o    : in  1     zero flag after
//-----------------------------------------------------------------------------
// Protocol
//   No interface protocol is used for data.
//
// Timing
//   Latency         : none
//   Throughput      : none
//   Back-pressure   : none
//
// Clock domains
//   None
//-----------------------------------------------------------------------------
// Implementation notes
//   Combinational logic and continuous assignments
//
// Assumptions and limitations
//   None
//
// Known issues
//   None
//-----------------------------------------------------------------------------
// Verification status
//   The testbench is located under the tb/alu directory.
//   Directed tests passed.
//   Functional coverage incomplete: 100% - Last measurement: 2026-09-29
//
// Synthesis / implementation status
//   Not synthesized yet.
//-----------------------------------------------------------------------------
// Dependencies
//   No dependencies.
//-----------------------------------------------------------------------------
// Revision history
//   2026-06-11     Antonio Moran Munoz     Initial commit.
//-----------------------------------------------------------------------------
// GPL-3.0 License - UCLM
//=============================================================================

module rounder #(
    parameter int MANT_WIDTH = 24,
    parameter int EXP_WIDTH  = 8
) (
    // ------
    // INPUTS
    // ------
    // number to round
    input logic sign_i,
    input logic [EXP_WIDTH-1:0] exp_i,
    input logic [MANT_WIDTH-1:0] mant_i,

    // GRS bits
    input logic guard_i,
    input logic round_i,
    input logic sticky_i,

    // status flags
    input logic overflow_i,
    input logic underflow_i,
    input logic zero_i,

    // round mode
    input logic [2:0] round_mode_i,

    // -------
    // OUTPUTS
    // -------
    // rounded number
    output logic sign_o,
    output logic [EXP_WIDTH-1:0] exp_o,
    output logic [MANT_WIDTH-2:0] frac_o,
    output logic [EXP_WIDTH+MANT_WIDTH-1:0] result_o,

    // status flags
    output logic overflow_o,
    output logic underflow_o,
    output logic inexact_o

);

  // ----------------
  // LOCAL PARAMETERS
  // ----------------
  localparam int FRAC_WIDTH = MANT_WIDTH - 1;
  localparam int EXT_WIDTH = EXP_WIDTH + FRAC_WIDTH;

  // possible values for exponent and fractions
  localparam logic [EXP_WIDTH-1:0] EXP_ALL1 = {EXP_WIDTH{1'b1}};
  localparam logic [EXP_WIDTH-1:0] EXP_MAX_NORM = EXP_ALL1 - 1'b1;
  localparam logic [FRAC_WIDTH-1:0] FRAC_ALL1 = {FRAC_WIDTH{1'b1}};

  // round-mode (it follows RISC_V frm)
  //   RNE (000): Round to Nearest, ties to Even (default).
  //   RTZ (001): Round towards Zero.
  //   RDN (010): Round Down (towards $-\infty$).
  //   RUP (011): Round Up (towards $+\infty$).
  //   RMM (100): Round to Nearest, ties to Max Magnitude.
  localparam logic [2:0] RNE = 3'b000;
  localparam logic [2:0] RTZ = 3'b001;
  localparam logic [2:0] RDN = 3'b010;
  localparam logic [2:0] RUP = 3'b011;
  localparam logic [2:0] RMM = 3'b100;

  // ----------------
  // INTERNAL SIGNALS
  // ----------------
  logic round_up;
  // '_r' means rounded - this signals hold the rounded result
  // '_f' means final- this signals hold the final value of the result
  logic [EXP_WIDTH-1:0] exp_r;
  logic [EXP_WIDTH-1:0] exp_f;
  logic [FRAC_WIDTH-1:0] frac_r;
  logic [FRAC_WIDTH-1:0] frac_f;

  // {exponent, fraction}
  // we do this so an overflow in the fraction updates directly the exponent
  logic [EXT_WIDTH-1:0] exp_frac;
  logic [EXT_WIDTH-1:0] exp_frac_r;

  // overflow handling
  logic overflow_raw;
  logic [EXP_WIDTH-1:0] exp_ovf;
  logic [FRAC_WIDTH-1:0] frac_ovf;


  // ----------------------
  // CONTINUOUS ASSIGNMENTS
  // ----------------------
  assign exp_frac = {exp_i[EXP_WIDTH-1:0], mant_i[FRAC_WIDTH-1:0]};
  assign exp_frac_r = exp_frac + (round_up & ~overflow_i);

  assign exp_r = exp_frac_r[EXT_WIDTH-1:FRAC_WIDTH];
  assign frac_r = exp_frac_r[FRAC_WIDTH-1:0];

  // two situations for overflow:
  //   - Situation 1: the overflow ocurred in the normalization stage
  //   (overflow_i == 1)
  //   - Situation 2: the overflow ocurs during rounding (rounded exponent is
  //   all 1s)
  assign overflow_raw = overflow_i | (exp_r == EXP_ALL1);

  // -------------------
  // COMBINATIONAL LOGIC
  // -------------------
  // ROUNDING_DECISION
  //
  // Description - calculates the bit that decides if we round up or down
  always_comb begin : ROUNDING_DECISION
    case (round_mode_i)
      RNE: round_up = guard_i & (round_i | sticky_i | mant_i[0]);
      RTZ: round_up = 0;
      RDN: round_up = sign_i & (guard_i | round_i | sticky_i);
      RUP: round_up = !sign_i & (guard_i | round_i | sticky_i);
      RMM: round_up = guard_i;
      default: round_up = guard_i & (guard_i | sticky_i | mant_i[0]);
    endcase
  end

  // OVERFLOW_HANDLING
  // Description - calculates is used to handle overflow in different
  // rounding modes according to RISC-V
  always_comb begin : OVERFLOW_HANDLING
    if (overflow_raw) begin
      case (round_mode_i)
        RTZ: begin
          exp_ovf  = EXP_MAX_NORM;
          frac_ovf = FRAC_ALL1;
        end
        RDN: begin
          exp_ovf  = sign_i ? EXP_ALL1 : EXP_MAX_NORM;
          frac_ovf = sign_i ? '0 : FRAC_ALL1;
        end
        RUP: begin
          exp_ovf  = sign_i ? EXP_MAX_NORM : EXP_ALL1;
          frac_ovf = sign_i ? FRAC_ALL1 : '0;
        end
        default: begin
          exp_ovf  = EXP_ALL1;
          frac_ovf = frac_r;
        end
      endcase
    end else begin
      exp_ovf  = exp_r;
      frac_ovf = frac_r;
    end
  end

  always_comb begin : OUTPUT_LOGIC
    if (zero_i) begin
      exp_f = '0;
      frac_f = '0;
      overflow_o = '0;
    end else begin
      exp_f = exp_ovf;
      frac_f = frac_ovf;
      overflow_o = overflow_raw;
    end

    sign_o = sign_i;
    exp_o = exp_f;
    frac_o = frac_f;
    result_o = {sign_i, exp_f, frac_f};

    // flags
    overflow_o = overflow_raw & ~zero_i;
    inexact_o = (overflow_o) ? 1'b1 : (guard_i | round_i | sticky_i) & ~zero_i;
    underflow_o = (exp_f == '0) & ~zero_i & inexact_o;
  end

endmodule
