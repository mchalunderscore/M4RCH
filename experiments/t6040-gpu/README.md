# T6040 GPU bring-up

Baseline: Gravity Linux's G16G/T8132 implementation. First target is a correct
G16S platform contract and identification, then firmware boot and a render
node, then headless rendering. Desktop acceleration follows those milestones.

`contract.py` decodes captured macOS IODeviceTree/IOService plists, retains both
clusters' voltage/frequency rows and derives per-cluster high/low ladders using
the published loader algorithm. Raw voltages are retained without asserting
units or inventing power calibration. It does not access GPU hardware.

`collect.py --output NEW_DIRECTORY` runs as root in Linux and captures the boot
FDT, selected GPU/reservation metadata, kernel config/notes and logs. It reads
an ADT phram device only if already exposed as an MTD named `adt`; it never
loads a driver, reads `/dev/mem`, writes MMIO or starts firmware. Raw captures
stay private in ignored output directories.

`load-adt.py` uses the exact-kernel ADT helper to expose only loader-reserved
System RAM as a read-only sysfs file. It validates build ID and kit checksums,
captures the metadata, then unloads the module. `adt.py` decodes that metadata.
The helper was built with W=1 and verified vermagic; native loading remains
pending. No GPU state changes or new enrollment are needed for this capture.

`patches/gravity-t6040-identify-only.patch` applies to the pinned Gravity source
in `sources.json`. It adds a distinct T6040 match, bounds identification mapping
to the four published ID-register offsets, defaults to probe-only and refuses
T6040 firmware execution even when probe_only=0. T6040 returns before T8132
power/MCC/firmware builders. Patch application was verified; a complete Rust
module build and native register reads are not yet verified. This patch is not
applied to the maintained kernel. Its register layout still needs native
qualification and a valid powered Linux platform node before a manual trial.

Known differences:

| Input | T8132 implementation | This T6040 capture |
| --- | --- | --- |
| Generation / variant | G16G | G16S |
| Cluster / enabled masks | 1 / 0x3ff | 2 / 0x3db, 0x3db; 16 enabled cores |
| Performance tables | One table | Two independent 16-row tables |
| Voltage groups | Eleven | Eleven in each table |
| SGX register span | Identification maps 64 MiB | macOS translates about 55.3 MiB |
| Firmware | Exact mBoot-18000.161.10 check | Linux loader's actual version still to capture |
| Mesa generation 16 | Asserts variant G | Needs explicit S support and layout audit |

Current macOS firmware is not the Linux boot stub's firmware. Live physical
reservations must come from that Linux boot, not be copied from a macOS capture.
Hardcoded T8132 MCC registers, power limits/calibration, firmware object layouts
and single-cluster submission topology require individual review. No chip-ID
spoofing or blanket firmware-version bypass.

The original identification patch uses public Gravity/Asahi sources and
observed metadata, and retains GPL-2.0-only provenance. Later GPU ABI and
[register mapping](../../docs/gpu-register-map.md) research includes Apple
firmware/driver binary analysis and is not clean-room work. Raw binaries and
disassembly remain private in ignored output. Existing USB work has separate
provenance; this is not a repository-wide clean-room claim.
