# Plasma CPU temperature on J614s

On 27 October the kernel exposed `/sys/class/hwmon/hwmon1/temp1_input`,
labelled `CPU Die Max`, through `macsmc_hwmon`. `sensors` and btop can read it.
The hwmon index can change, so use the device and label rather than assuming
`hwmon1`.

Plasma 6.8.1's running `ksystemstats` service exposes the same reading as
`lmsensors/macsmc_hwmon-isa-0000/temp1`, named `CPU Die Max`, under Hardware
Sensors. A subscribed D-Bus read returned 77.921 °C while
`cpu/all/averageTemperature` returned 0. The KDE CPU plugin's `addSensors()`
only associates `coretemp` and `k10temp` chips with its CPU temperature
objects; the separate lm-sensors plugin exposes `macsmc_hwmon` as a generic
hardware sensor. Thus this is a Plasma classification issue rather than an
unavailable CPU temperature. The CPU Die Max reading is a die-wide maximum,
not per-core or average temperature, so it should not be presented as a
per-core temperature or average.

In a Plasma System Monitor sensor picker or a configurable sensor widget,
select **Hardware Sensors → macsmc_hwmon-isa-0000 → CPU Die Max**. A proper
CPU-category integration would require a targeted ksystemstats change that
preserves its semantics; no KDE package or user configuration was modified.
