# Nano FP unit

This unit is meant to perform IEEE 754-2019 arithmetic operations.

So far, for the proper behavior of the unit, some asumptions must be taken into account:

- Signals connected to the *num* input must be 32-bit wide to avoid zero extensions of the signal.

## Dependencies

- [Icarus Verilog](https://steveicarus.github.io/iverilog/) - Currently, simulations are only supported via icarus verilog.
- [GTKWave](https://gtkwave.github.io/gtkwave/) - It is used to visualize the waveforms of the design.

## Block Diagram

![Block diagram of the unit.](block-diagram.drawio.png)
## Simulations

> [!NOTE]
> 
> So far, the testbenches are very simple and just test very basic cases.

Within the `tb` directory there is one subdirectory for each of the modules implemented in `src`. In order to launch a given simulation, just run the following command from the root repository:

```bash
make <module-name>
```

Where `<module-name>` is the name of the module you want to test. Currently, the following modules are implemented:

- `b32_adapter`
- `exp_diff`
- `alu`

#### Example

If you want to simulate the `alu.sv` module, run `make alu` from the root of the repository.

## Features

> [!WARNING]
> 
> The 16 bits from the *binary16* format have to be in the lower half of the 32-bit wide *num* input.

- [x] *binary16* to *binary32* adaptation.
