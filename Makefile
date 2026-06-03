SRCS=src/b32_adapter.sv \
     tb/b32_adapter_tb/top_tb.sv
SRCS_ADAPTER=src/b32_adapter.sv \
	     tb/b32_adapter_tb/top_tb.sv
EXE_DIR=exe
VCD_DIR=vcd
CC=iverilog

b32_adapter: $(SRCS_ADAPTER)
	$(CC) -g2012 $(SRCS_ADAPTER) -o $(EXE_DIR)/b32_adapter.vvp 
	vvp $(EXE_DIR)/b32_adapter.vvp
	gtkwave $(VCD_DIR)/b32_adapter.vcd
