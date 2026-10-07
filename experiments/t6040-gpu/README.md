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
The helper was built with W=1 and verified vermagic; native read-only capture succeeded on the exact maintained build. No GPU state changes or new enrollment are needed for this capture.

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
| Firmware | Exact mBoot-18000.161.10 check | Linux stage two is mBoot-18000.121.3 |
| Mesa generation 16 | Asserts variant G | Needs explicit S support and layout audit |

Current macOS firmware is not the Linux boot stub's firmware. Live physical
reservations must come from that Linux boot, not be copied from a macOS capture.
Hardcoded T8132 MCC registers, power limits/calibration, firmware object layouts
and single-cluster submission topology require individual review. No chip-ID
spoofing or blanket firmware-version bypass.

Public Gravity/Asahi sources and observed metadata are the inputs to this work;
no Apple source, firmware disassembly or binary-derived control code is used.
Derived kernel patch retains GPL-2.0-only provenance. Existing project USB work
has separate provenance; this is not a repository-wide clean-room claim.

## Native contract and offline builds (2026-10-06)

The Linux boot ADT was captured using the guarded helper, which unloaded
afterward. Its unrelated duplicate cpu-debug-interface siblings exposed a
parser assumption: adt.py now retains both and rejects duplicated contract
nodes. Both captured GPU performance tables exactly match the macOS evidence.
The boot firmware is mBoot-18000.121.3, not the accepted .161.10 build; the exact
firmware barrier is retained. GPU physical handoff regions are outside usable
Linux RAM, but the required named GPU resources/alias are missing. No GPU MMIO
was performed. WFI remains enabled.

Three further patches are kept separate from the image recipe:

- gravity-linux-t6040-metadata.patch: distinct metadata profile and generic
  per-cluster ladder decoder plus guarded identification. Six Rust tests pass.
- gravity-bootloader-t6040-metadata.patch: preserve live reservations, raw tables
  and version metadata, leave the GPU node disabled; actual loader object builds.
- gravity-mesa-t6040-metadata.patch: explicit S discovery/topology check, rejecting
  unqualified S layouts before G16G initialization; C model tests pass.

The pinned Gravity 7.1.13+ vmlinux and GPU .ko build successfully with warnings;
Mesa shared Gallium/GBM/EGL libraries build into a private workspace prefix.
These are not matched to the maintained 7.1.3-m4rch kernel and must not be
loaded into it. Neither the loader nor desktop Mesa was replaced. The original
identification-only patch remains an earlier candidate; its application receipt
does not describe the expanded metadata patch.

Rebuild instructions and the successful offline config are in REPRODUCE.md
and configs/gravity-offline.config.

Reviewed build receipts: docs/evidence/2026-10-06-gpu-native-build.json. Full
captures/binaries/logs stay in ignored out/gpu-native-20261006 on this Linux
checkout. Run make check for parser and compiled metadata regression tests.

Next: integrate into the exact maintained source/config, qualify SGX power and
Linux DT/IRQ/mailbox resources, then test native identification in a separate
matched kernel. Firmware ABI comparison precedes startup or rendering. Keep
Git changes on separate branches and exchange exact commits. Set any eventual
trial GRUB entry as default before reboot: the owner cannot use its keyboard.

## Expanded offline graph and mapping trial (2026-10-07)

`plan-init-graph.py` records17 objects and16 pointer edges. The root+c0 target
has an unknown extent and receives no reservation in that plan. Known minimum
extents now require18 pages; both status_b and power need two.

`assemble-init-graph.py` takes a JSON manifest containing `base` and `templates`
(object name to binary path relative to the manifest). Every template must be
explicit, including the unknown target. It preserves non-pointer bytes and
relocates only the documented/qualified edges; its receipt always marks the
result unpublishable. It neither validates opaque contents nor discovers
transitive pointers. `graph-tests.py` checks relocations, preservation, page
separation, missing templates, undersized status data and address bounds.

The completed native trial used18 marker pages plus two tables, reserving one
explicitly unqualified marker page for the unknown target. Its clean retirement
is recorded separately. The subsequently qualified power extent means a rebuilt
probe would use19 marker pages plus two tables. Neither run publishes a graph.
Do not request a reboot solely to repeat arena capacity testing; finish graph
contracts first. The earlier13-page result and current18-page result remain
capacity/retirement evidence only.

The profile-A firmware parser independently confirms two cluster voltage
columns and16 storage slots with0x40 stride. The offline voltage codec takes11
candidate voltage groups and emits full0x400-byte arrays with unused slots
zero. Profile A/B frequency assignment and profile-B semantics remain unknown;
these candidate bytes are not part of the running driver.
