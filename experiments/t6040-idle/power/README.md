# Idle power comparison

`compare.py` runs enabled/disabled/disabled/enabled in one boot, checking the kit's
build receipt and saved-WFI controls. Each phase settles60s and measures180s.
It records battery telemetry, activity, sensors and idle counters; success restores
enabled, failure leaves disabled. No clock/fan/voltage controls are touched.

`analyse.py CAPTURE` produces JSON summaries. Battery estimates follow the Linux
[power_supply ABI](https://docs.kernel.org/power/power_supply_class.html); only
reported discharge samples are used. Whole-machine estimates are uncalibrated.
Constant readings, charging, workload differences and stale sensors limit claims.

Use the generated HANDOVER for the exact kernel, card commands and rollback.
