# Documentation

| Guide | Purpose |
| --- | --- |
| [Bootloader alignment](bootloader-alignment.md) | Gravity-based stage 2, build and rollback |
| [Split internal boot](split-boot.md) | Enrolled stage 1 and replaceable ESP boot.bin |
| [Setup](setup.md) | First installation, building, flashing, enrollment and updates |
| [Hardware](hardware.md) | Tested devices, limits and useful native checks |
| [Architecture](architecture.md) | Internal loader, SD UEFI files, packages and boot policy |
| [Development](development.md) | Source pins, validation and contribution workflow |
| [CPU experiments](cpu-performance.md) | Controlled placement and clock/cooling captures |
| [Left USB trial](left-usb-trial.md) | Both-left USB2 candidate, driver dependency and rollback |
| [USB patch provenance](usb-patchset-provenance.md) | Upstream basis and local USB adaptations |

The [native-agent instructions](native-agent-instructions.md) and
[follow-up](native-agent-followup.md) are operational handoff files for the
current test installation and are included in `make cpu-tools` kits. Verify
live devices and settings before applying them to another installation.
The current [HANDOVER.md](../HANDOVER.md) describes the first opt-in T6040 idle
trial, with separate GRUB images and macOS-accessible selection rollback.
The accepted clock diagnostic and its rollback remain available.

Curated evidence receipts are retained in [evidence/](evidence/):

- [Initial CPU/source audit](evidence/2026-10-05-cpu-performance.json).
- [Accepted left USB, capacity and cooling return](evidence/2026-10-05-native-round4.json).
- [macOS SMC freshness comparison](evidence/2026-10-05-macos-smc-freshness.json).
- [SMC key availability](evidence/2026-10-05-j614s-smc-keys.json).
- [Native placement and desktop return](evidence/2026-10-05-native-return.json).

Raw captures, generated packages, images and machine-specific enrollment
state are local `out/` artifacts and are excluded from the source repository.

- [Apple boot-stub upgrade](stub-upgrade.md): isolated 25G83 preparation and GPU ABI reference.

- [NVMe root migration](nvme-root.md): storage layout, qualification and fallback plan.
