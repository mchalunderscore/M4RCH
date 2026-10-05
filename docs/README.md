# Documentation

| Guide | Purpose |
| --- | --- |
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
The current [HANDOVER.md](../HANDOVER.md) sets the USB2/idle/scheduling work
and the return-evidence protocol; the kit includes its read-only collector.

Curated evidence receipts are retained in [evidence/](evidence/):

- [Initial CPU/source audit](evidence/2026-10-05-cpu-performance.json).
- [SMC key availability](evidence/2026-10-05-j614s-smc-keys.json).
- [Native placement and desktop return](evidence/2026-10-05-native-return.json).

Raw captures, generated packages, images and machine-specific enrollment
state are local `out/` artifacts and are excluded from the source repository.
