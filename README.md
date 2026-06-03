# Nano FP unit

This unit is meant to perform IEEE 754-2019 arithmetic operations.

So far, for the proper behavior of the unit, some asumptions must be taken into account:

- Signals connected to the *num* input must be 32-bit wide to avoid zero extensions of the signal.

![Block diagram of the unit.](block-diagram.drawio.png)

## Features

> [!WARNING]
> 
> The 16 bits from the *binary16* format have to be in the lower half of the 32-bit wide *num* input.

[ x ] *binary16* to *binary32* adaptation.
