SRCS=src/b32_adapter.sv \
     tb/b32_adapter_tb/top_tb.sv
SRCS_ADAPTER=src/b32_adapter.sv \
	     tb/b32_adapter_tb/top_tb.sv
SRCS_EXP_DIFF=src/exp_diff.sv \
	     tb/exp_diff_tb/top_tb.sv
SRCS_ALU=src/alu.sv \
	     tb/alu_tb/top_tb.sv
EXE_DIR=exe
VCD_DIR=vcd
CC=iverilog

b32_adapter: $(SRCS_ADAPTER)
	$(CC) -g2012 $(SRCS_ADAPTER) -o $(EXE_DIR)/b32_adapter.vvp 
	vvp $(EXE_DIR)/b32_adapter.vvp
	gtkwave $(VCD_DIR)/b32_adapter.vcd

exp_diff: $(SRCS_EXP_DIFF)
	$(CC) -g2012 $(SRCS_EXP_DIFF) -o $(EXE_DIR)/exp_diff.vvp
	vvp $(EXE_DIR)/exp_diff.vvp
	gtkwave $(VCD_DIR)/exp_diff.vcd

alu: $(SRCS_ALU)
	$(CC) -g2012 $(SRCS_ALU) -o $(EXE_DIR)/alu.vvp
	vvp $(EXE_DIR)/alu.vvp
	gtkwave $(VCD_DIR)/alu.vcd
