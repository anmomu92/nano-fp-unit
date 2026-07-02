//=============================================================================
// b32_adapter.sv
//
// IEEE-754 binary16 -> binary32.
//
// The operand is carried on a 32-bit bus together with a format signal:
//   - tag == 1 : the operand is encoded as binary16 in bus[15:0]
//                (bus[31:16] is don't-care / ignored)
//   - tag == 0 : the operand is already encoded as binary32 on the full bus
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
    WIDTH = 32
) (
    input logic [WIDTH-1:0] num_i,
    input logic [1:0] format,  // maybe define an enum in a package
    input logic [3:0] op_type,
    input logic [3:0] round_mode,

    output logic [WIDTH-1:0] num_o
);

  // Functions

  //-------------------------------------------------------------------
  // Leading-zero count
  // This function takes a t16 and counts the number of leading zeros
  // This is done to normalize subnormal numbers.
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
          if (x[i])
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


  // Combinational Logic
  always_comb begin : OUTPUT_LOGIC
    // we distinguish different input formats (so far, only b16)
    case (format)
      2'd1: begin
        num_o = b16_to_b32(num_i[15:0]);  // b16 -> b32
      end
      default: begin  // b32 -> b32
        num_o = num_i;
      end
    endcase
  end

endmodule
