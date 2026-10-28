# Development

This guide covers the historical SD-card workflow. For current package builds
and checks, see the [package guide](../packages/README.md).

## Source layout

| Path | Responsibility |
| --- | --- |
| `Makefile`, `scripts/` | POSIX make and shell entry points |
| `sdboot/` | Current image, UEFI bridge, rootfs, packages and enrollment |
| `lib/` | Shared hardware, firmware, disk validation and source helpers |
| `patches/` | Pinned upstream backports and local platform changes |
| `packages/` | Kernel/configuration, GRUB and paru recipes |
| `tests/` | Python regressions and executable C/shell fixtures |
| `docs/evidence/` | Curated, dated native/source evidence receipts |

Build inside the Linux runtime; do not compile kernel working trees on the
case-insensitive macOS filesystem. The named Linux work volume is shared by
build stages and protected by a lock. Run kernel/package stages sequentially,
not concurrent `make` invocations against that volume.

## Inputs and provenance

- `sources.lock.json` pins Wallace, Linux, m1n1, rootfs signatures and key
  hardware backports.
- `sdboot/loader.py` pins Asahi U-Boot and validates its resolved configuration.
- `packages/grub-m4rch/source.json` pins GRUB and its ARM64 high-memory fix.
- `packages/paru-m4rch/source.json` pins paru's libalpm-compatible source.
- `lib/firmware.py` verifies the Apple restore/firmware extraction inputs.
- Generated package locks and manifests record resolved packages, source
  hashes, configuration and output hashes under `out/sdboot/`.

This is input pinning and output verification, not a claim of byte-identical
filesystem images. Filesystem metadata, keyring creation and builder package
resolution have their own nondeterminism. Preserve locks and relevant cached
signed archives when reproducing a native result after rolling mirrors move.

Generated images/packages contain extracted firmware and stay local.
Machine-specific boot state and raw diagnostic logs also stay in ignored
`out/`. Publish source and reviewed evidence rather than build directories.

## Validate the layer you changed

```sh
make check       # Python regressions and shell syntax
make verify      # existing artifact/configuration/hash checks
make smoke       # disposable QEMU UEFI → SD GRUB → Linux test
```

Source tests include compiled fixtures for MMIO sequencing, retry cleanup,
NVMe handoff and GRUB high-address allocation. They exercise guarded code
paths without proving how physical firmware responds. The smoke test checks
packages/modules, first-boot growth, persistence, signed package operations
and shutdown in a VM. It does not test Apple policy, the native U-Boot bridge,
the SD reader or physical peripherals.

For native changes, retain a known-good matching kernel/configuration kit,
the enrolled loader and its complete local state. Record the running kernel,
package versions, actual live DT, device identity and logs. A registered
driver, root hub or exposed sysfs attribute is weaker evidence than usable
hardware. Capture failure paths and regression checks as well as success.

## Contributions

Keep hardware changes small and explain the triggering failure, upstream
basis, exact local adaptation and validation limits. Preserve patch authors,
license notices and source hashes. Never infer an M4 Pro register sequence,
capacity ratio or firmware behavior solely from a similarly named base-M4
device. The [USB provenance](usb-patchset-provenance.md) shows the expected
distinction between upstream code and platform integration.

The repository contains AI-assisted code and source-derived adaptations; it
is **not clean-room research**. Claims of upstream authorship or support must
follow the retained sources. See [third-party attribution](../THIRD_PARTY.md)
and [licensing scope](../LICENSE).

Before sharing diagnostics, review them for credentials, network details and
device identifiers. Do not include personalized Apple tickets, owner records,
private keys or raw restore/firmware archives in a source submission.

SourceHut's [September 2026 policy change](https://sourcehut.org/blog/2026-08-27-tos-changes-and-llms/)
restricts original AI-assisted content, with case-by-case exceptions. This
project contains substantial agent-authored code and documentation; a local
SourceHut remote is not confirmation that hosting it there is permitted.
