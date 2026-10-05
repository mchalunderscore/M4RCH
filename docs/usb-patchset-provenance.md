# USB2 patchset provenance

Audited **2026-10-05** for J614s / T6040. The working stack is **not textbook
clean-room**, and its publication review is incomplete. This is not a finding
of infringement or a guarantee that publication is legally safe.
This USB-focused audit does not clear other components: the trackpad fix and
Bootability investigation also involved proprietary binary analysis. See the
[repository-wide review boundaries](../THIRD_PARTY.md#reverse-engineering-scope).

## Provenance

The base is [damsleth/linux e9d2237c](https://github.com/damsleth/linux/tree/e9d2237cd064e6d086d938cd9c85e0c963cf7291),
with [Wallace 55f116dd](https://github.com/damsleth/wallace/tree/55f116dd0e0f28d1412c6be728a101f7d861c473)
USB patches and imported community SPMI fixes. Licensed open-source reuse is
ordinary Linux development when terms and attribution are preserved. The
separate concern is proprietary-driver reverse engineering:

- Wallace's PHY initialization explicitly mirrors a decoded
  `AppleT6040TypeCPhy` register sequence.
- [experimental-usb2-phy-reset.patch](../patches/experimental-usb2-phy-reset.patch)
  derives shutdown operations, delays and ordering from static analysis of that
  Apple component. Implementation and binary analysis occurred together.
- [architecture.md](architecture.md#usb2) explains the Linux callback-order
  correction. The patch contains Linux C rather than an
  embedded Apple binary; that alone does not resolve provenance.

[Gravity's USB2 cold-boot fix](https://github.com/GravityLinux/linux/commit/bc148def8924e43245c353c52ced47079a5026da)
provided a lifecycle hypothesis; its base-M4 register sequence was not copied
into this T6040 provider. Register facts and hardware requirements must be
separated from incidental proprietary software structure. Removing comments,
renaming code or asking another agent to rewrite it does not create clean-room
provenance.

## Licenses

| Target source | Existing SPDX |
|---|---|
| `drivers/usb/dwc3/dwc3-apple.c` | `GPL-2.0` |
| `drivers/usb/typec/tipd/core.c`, `tipd/spmi.c` | `GPL-2.0` |
| `drivers/spmi/spmi-apple-controller.c` | `GPL-2.0` |
| `drivers/phy/apple/t6040-usb2.c` | `GPL-2.0 OR BSD-2-Clause` |
| [experimental-hardware.dtsi](../patches/experimental-hardware.dtsi) | `GPL-2.0+ OR MIT` |

These file licenses take precedence over Wallace's general MIT license. Preserve
imported authors/notices; do not label the entire series MIT. Local patch
headers currently use `From: arch-m4 project`, without individual certification.
See [THIRD_PARTY.md](../THIRD_PARTY.md) for repository-wide exceptions.

## Publication versus contribution

[Asahi's reverse-engineering policy](https://asahilinux.org/copyright/) rejects
direct proprietary-code translation and normally separates binary analysis
from implementation, with specific trusted exceptions. Our record does not
establish compliance. Its [AI policy](https://asahilinux.org/llm-policy/) broadly
forbids material generative-AI contributions. This substantially agent-assisted
stack must not be represented as an acceptable Asahi contribution.

A personal experimental release is a different decision, still requiring a
provenance review. Mainline Linux's [coding-assistant guidance](https://cdn.kernel.org/doc/html/latest/process/coding-assistants.html)
requires compatible licensing, assistance disclosure and accountable human
review. An agent must not invent a human `Signed-off-by` certification.

The connector lookup, partner-identity lifetime, DWC3 deferred-probe cleanup and
cable-lifecycle fixes are narrower review candidates: they address Linux object
lifetimes/callbacks rather than introducing proprietary PHY sequences. Their
individual provenance and prerequisites still need review; they do not alone
provide working USB2.

## Standalone scope

[lib/hardware_profile.py](../lib/hardware_profile.py) is the canonical ordered,
hash-checked chain: three Wallace USB prerequisites, four imported SPMI fixes,
three TIPD corrections and five cable/PHY/retry changes: **15 patches**. Preserve
Alba Mendez/Sasha Finkelstein attribution and the
[Finkelstein/Milburn register-access reference](https://lists.openwall.net/linux-kernel/2026/08/26/982).

A standalone series also needs the right-port PHY, DARTs, SPMI power domain,
HPM2 connector and role graph. Extract USB-only nodes from the mixed hardware
fragment and [board.dtso](../sdboot/board.dtso) fragments 5/6. NVMe and telemetry
are unrelated. `arch-m4,usb-wait-for-cable` is a local enrolled-loader workaround,
not an established upstream binding.

Before release, resolve the PHY provenance through qualified human review and,
if necessary, a genuinely independent implementation from a hardware
specification. Preserve applicable license texts and disclose AI assistance.
Validate the isolated series. Report only the demonstrated right-port YubiKey
12 Mbit/s enumeration, reconnect and authentication; other ports, USB3, suspend
and fault-injected retry remain unproven. Exclude Apple binaries/disassembly,
firmware and private diagnostics. No release was prepared by this audit.
