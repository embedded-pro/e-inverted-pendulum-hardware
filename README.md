# e-inverted-pendulum-hardware

Hardware for the [e-inverted-pendulum](https://github.com/embedded-pro/e-inverted-pendulum) self-balancing robot: a single 4-layer PCB that is also the robot's chassis. It carries an STM32WB55RG (BLE), a DRV8711 driving two brushed DC gearmotors with ABZ encoders, an MPU-6500 IMU, SPI flash and a 3S LiPo power path. Built and assembled at JLCPCB.

Status: planning. See [docs/plan.md](docs/plan.md) for the decisions, the JLCPCB part selection, and the schematic, simulation and layout phases.

Design rules come from the `hardware-design` skills in [claude-hardware-skills](https://github.com/gabrielfrasantos/claude-hardware-skills).
