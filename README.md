<h1 align="center">Nano FP unit</h1>

<div align="center">

[![GPL-3.0 license](https://img.shields.io/badge/License-GPLv3-blue.svg?style=flat-square)](LICENSE)
[![State](https://img.shields.io/badge/State-active-brightgreen?style=flat-square)]()
[![Wiki](https://img.shields.io/badge/Wiki-documentation-yellow?style=flat-square)](https://github.com/anmomu92/nano-fp-unit/wiki)

</div>

This repository contains the source code of a digital unit that is meant to be compliant with the IEEE 754-2019 Std.

So far, for the proper behavior of the unit, some asumptions must be taken into account:

- Signals connected to the *num* input must be 32-bit wide to avoid zero extensions of the signal.

## Dependencies

- [Icarus Verilog](https://steveicarus.github.io/iverilog/) - Currently, simulations are only supported via icarus verilog.
- [GTKWave](https://gtkwave.github.io/gtkwave/) - It is used to visualize the waveforms of the design.

## Block Diagram

The structure of the design is depicted in the following block diagram:

![Block diagram of the unit.](docs/block-diagram.drawio.png)
