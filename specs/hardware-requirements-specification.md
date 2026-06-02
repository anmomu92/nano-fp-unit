# Hardware Requirements Specification

## Ámbito

El siguiente módulo se enmarca dentro de un diseño mayor, que consta de una serie de componentes encaminados a formar una ruta de datos basada en RISC-V. Se espera que la inclusión de esta unidad de cálculo en punto flotante sea el primer paso para dotar a la ruta de datos donde se integre de capacidades para llevar a cabo este tipo de cálculos.

## Requerimientos funcionales

| Req ID | Descripción | Verificado |
| --- | --- | --- |
| FP01 | Aceptar formato entero de entrada | N |
| FP02 | Aceptar formato *binary16* de entrada | N |
| FP03 | Aceptar formato *binary16* de entrada | N |
| FP04 | Convertir formatos a *binary32* | N |
| FP05 | Operaciones de suma y resta en punto flotante | N |
| FP06 | Normalizar el resultado | N |
| FP07 | Redondeo del resultado siguiendo el modo de redondeo *RoundTiesToEven* | N |
