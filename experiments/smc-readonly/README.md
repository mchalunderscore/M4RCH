# Read-only SMC diagnostic

A temporary J614s module, built for the exact accepted `7.1.3-m4rch` kernel.
It calls the existing locked SMC metadata/read APIs for twelve fixed CPU/fan
keys. Output gives boot-time timestamp, metadata status, size, type, flags,
read status and raw bytes. The debugfs file is root-readable, with no write
handler, arbitrary key selection, SMC enumeration or fan-control operation.

`run.sh` checks checksums, running GNU build ID and installed provenance,
loads the module, captures thirty samples alongside hwmon and unloads it.
It creates a new private output directory and applies no workload. Mount
normal debugfs first if absent. Do not force-load on a mismatched kernel,
unbind/unload SMC, or turn off kernel protections to run this diagnostic.
Loading this external module adds the normal out-of-tree kernel taint.
A forced kill/power loss can bypass cleanup; reboot clears the module.

Compare raw bytes and type with the macOS receipt. `flt ` is a little-endian
IEEE float here; temperatures use °C and fan values RPM. Preserve error/short
read records. Interpret F0Md/F1Md values without writing them. A frozen raw
reply points below hwmon, but does not alone identify the firmware cause.

The capture validates every fixed key record, including status, exact reply
length and type. It preserves raw failures/short reads/timeouts before stopping;
a successful debugfs `cat` alone is insufficient. Valid zero floats are accepted.

Optional `--samples 720` captures about twelve minutes at a monotonic one-second
cadence, alongside adjacent policy readings. Default remains30samples. These
are sequential snapshots; timing/duration checks are not a hardware watchdog.
