//=============================================================================
// File        : b32_adapter.sv
// Module      : b32_adapter
// Project     : nano-fp-unit
// Author      : Antonio Moran Munoz, UCLM
// Created     : 2026-06-02
//-----------------------------------------------------------------------------
// Purpose
//   To adapt a number to *binary32* encoding as defined in the IEEE-754 Std,
//   regardless of the incoming format.
//
// Specification
//   No formal spec exists.
//-----------------------------------------------------------------------------
// Parameters
//   WIDTH          : the width in bits of the adapted number.  Default: 32
//   PRECISION      : the precision of the format.              Default: 24
//   EXP_WIDTH      : the width in bits of the exponent.        Default: 8
//-----------------------------------------------------------------------------
// Interface
//   - num_i     : in  32     number to adapt.
//   - format_i  : in  2      format of the input number.
//     0 : binary32
//     1 : binary16
//
//   - num_o     : out 32     adapted number.
//   - zero_o    : out 1      zero flag.
//   - infty_o   : out 1      infinity flag.
//   - nan_o     : out 1      not a number (NaN) flag.
//   - sub_o     : out 1      subnormal flag.
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
//   A combinational block calls the corresponding function depending on the
//   input format of the number. So far, only the b16 to b32 function is
//   implemented.
//
//   A function to count the number of leading zeros of the number.
//
// Assumptions and limitations
//   None
//
// Known issues
//   None
//
//-----------------------------------------------------------------------------
// Verification status
//   The testbench is located under the tb/b32_adapter directory.
//   Not tested
//
// Synthesis / implementation status
//   Not synthesized yet.
//-----------------------------------------------------------------------------
// Dependencies
//   No dependencies.
//-----------------------------------------------------------------------------
// Revision history
//   2026-06-02     Antonio Moran Munoz     Initial commit.
//   2026-10-06     Antonio Moran Munoz     Added number type indentification.
//-----------------------------------------------------------------------------
// GPL-3.0 License - UCLM
//=============================================================================

//
// Widening binary16 -> binary32 is always EXACT (no rounding is ever
// required), so this stage is purely combinational re-biasing / padding
// logic, plus re-normalization for binary16 subnormals (which become
// normal binary32 numbers because binary32 has a much wider exponent
// range).
//
// binary16 : 1 sign (S) | 5 exponent (E) (bias 15)  | 10 significand (T)
// binary32 : 1 sign (S) | 8 exponent (E) (bias 127) | 23 significand (T)
//
// We can have different cases depending on the values of the operand:
//   E16 == 0,  T16 == 0   -> signed zero
//   E16 == 0,  T16 != 0   -> subnormal - we have to normalize the number
//   E16 == 31, T16 == 0   -> signed infinity
//   E16 == 31, T16 != 0   -> NaN (payload left-justified into man32,
//                                 preserving the quiet/signaling bit)
//   1 <= E16 <= 30        -> normal number, exponent re-biased by +112
//=============================================================================

module b32_adapter #(
    WIDTH = 32,
    PRECISION = 24,
    EXP_WIDTH = 8
) (
    input logic [WIDTH-1:0] num_i,
    input logic [1:0] format_i,  // maybe define an enum in a package

    output logic [WIDTH-1:0] num_o,
    output logic zero_o,
    output logic infty_o,
    output logic nan_o,
    output logic sub_o
);
  localparam int TRAIL_WIDTH = PRECISION - 1;

  // ---------
  // VARIABLES
  // ---------
  logic [  EXP_WIDTH-1:0] exp;
  logic [TRAIL_WIDTH-1:0] trail;

  // ----------------------
  // CONTINUOUS ASSIGNMENTS
  // ----------------------
  assign exp   = num_o[WIDTH-2:TRAIL_WIDTH];
  assign trail = num_o[TRAIL_WIDTH-1:0];

  // ---------
  // FUNCTIONS
  // ---------
  //-------------------------------------------------------------------
  // Leading-zero count
  // This function takes a t16 and counts the number of leading zeros
  // This is done to normalize subnormal numbers.
  //-------------------------------------------------------------------
  // TODO - move function to a package as it is used in several modules
  //-------------------------------------------------------------------
  function automatic logic [3:0] lzc(input logic [9:0] t16);
    integer       i;
    logic         one;
    logic   [3:0] cnt;
    begin
      one = 1'b0;
      cnt = 4'd0;

      for (i = 9; i >= 0; i--) begin
        if (!one) begin
          if (t16[i])
            // a 1 is found
            one = 1'b1;
          else
            // increase the zero count
            cnt = cnt + 1'b1;
        end
      end

      lzc = cnt;
    end
  endfunction

  //
  function automatic logic [WIDTH-1:0] b16_to_b32(input logic [15:0] b16_i);
    // local signals
    logic s;
    logic [4:0] e16;
    logic [9:0] t16;
    logic [7:0] e32;
    logic [22:0] t32;
    logic [3:0] lz;  // leading zeros
    logic [9:0] shifted_t16;

    begin
      // extract number fields
      s   = b16_i[15];
      e16 = b16_i[14:10];
      t16 = b16_i[9:0];

      case (e16)
        5'd0:
        if (t16 == 10'd0) begin
          // signed zero number
          e32 = 8'd0;
          t32 = 23'd0;
        end else begin
          // subnormal number
          e32 = 8'd0;
          lz = lzc(t16);
          shifted_t16 = t16 << lz;

          e32 = 8'd112 - {4'd0, lz};
          t32 = {shifted_t16[8:0], 14'd0};
        end
        5'd31:
        if (t16 == 10'd0) begin
          // infinity
          e32 = 8'd255;
          t32 = 23'd0;
        end else begin
          // NaN
          e32 = 8'd255;
          t32 = {t16, 13'd0};
        end
        default: // normal number
        begin
          e32 = {3'd0, e16} + 8'd112;  // re-bias the exponent
          t32 = {t16, 13'd0};
        end
      endcase

      b16_to_b32 = {s, e32, t32};
    end
  endfunction

  // -------------------
  // COMBINATIONAL LOGIC
  // -------------------

  // See Clause 3.4 from IEEE 754-2019 Std.
  always_comb begin : NUMBER_TYPE
    zero_o  = 1'b0;
    nan_o   = 1'b0;
    infty_o = 1'b0;

    // NaN
    // TODO - use d1 to distinguish between qNaN and sNaN
    if ((exp == 2 ^ (EXP_WIDTH) - 1) && trail) begin
      nan_o = 1'b1;
    end

    // infinity
    if ((exp == 2 ^ (EXP_WIDTH) - 1) && ~trail) begin
      infty_o = 1'b0;
    end

    // infinity
    if (~exp && ~trail) begin
      zero_o = 1'b0;
    end

    // subnormal
    if (~exp && trail) begin
      sub_o = 1'b0;
    end
  end

  always_comb begin : OUTPUT_LOGIC
    // we distinguish different input format_is (so far, only b16)
    case (format_i)
      2'd1: begin
        num_o = b16_to_b32(num_i[15:0]);  // b16 -> b32
      end
      default: begin  // b32 -> b32
        num_o = num_i;
      end
    endcase
  end

endmodule
