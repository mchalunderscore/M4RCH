# Third-party code and license exceptions

The root [MIT license](LICENSE) covers original project tools, configuration,
tests and documentation. It does **not** relicense imported material,
derivatives, firmware, dependencies or generated binaries. Existing file SPDX
headers and upstream notices take precedence. This inventory was checked on
2026-10-05; it is not a clearance of every binary image component.

| Material | License and retained provenance |
|---|---|
| Asahi installer-derived enrollment/stub logic in `lib/card.py`, `lib/internal_boot.py`, `lib/stub_payload.py`, `sdboot/recovery-enroll.sh`; installer/extractor fetched by `lib/firmware.py` | MIT; [asahi-installer c53d66dc](https://github.com/AsahiLinux/asahi-installer/tree/c53d66dc71937efa2530d4323c81addaebb5a09b), with [ASAHI-LICENSE](third_party/ASAHI-LICENSE) retained. Generated launchers must retain that notice too. |
| `tests/fixtures/m1n1-{nvme,rtkit}-base.{c,h}`; imported `patches/m1n1-*.patch` source changes | MIT; [m1n1 16b1f61f](https://github.com/damsleth/m1n1/tree/16b1f61fd2a995f855da8909411d06005d1e2b35). Fixture [README](tests/fixtures/m1n1-nvme-base.README) and [license](tests/fixtures/m1n1-nvme-base.LICENSE) retain origin and Asahi notice. Upstream PCIe/SMP commit pins are in [sources.lock.json](sources.lock.json); NVMe commits/hashes are in [lib/nvme_handoff.py](lib/nvme_handoff.py). |
| Wallace harness/source inputs and imported patches | Repository MIT notice: [WALLACE-LICENSE](third_party/WALLACE-LICENSE), CJ Damsleth, [Wallace 55f116dd](https://github.com/damsleth/wallace/tree/55f116dd0e0f28d1412c6be728a101f7d861c473). The T6040 PHY is separately `GPL-2.0 OR BSD-2-Clause`; its TIPD transport and DWC3 target sources are GPL-2.0. Repository MIT does not override them. |
| `patches/linux-*.patch`, SPMI/TIPD/DWC3/NVMe implementation patches and imported Linux source fragments | Target-file terms: predominantly GPL-2.0/GPL-2.0-only; NVMe YAML binding is `GPL-2.0 OR BSD-2-Clause`. [Linux base e9d2237c](https://github.com/damsleth/linux/tree/e9d2237cd064e6d086d938cd9c85e0c963cf7291). Preserve imported author/sign-off headers. [lib/hardware_profile.py](lib/hardware_profile.py) records exact USB/NVMe source commits, hashes and origins, including Alba Mendez, Sasha Finkelstein, Alyssa Milburn, Sven Peter and Yureka Lilian. |
| `patches/experimental-hardware.dtsi`, `patches/t6040-j614s-trackpad-power.dtsi` | Existing `GPL-2.0+ OR MIT` SPDX; retain that choice and upstream DT provenance. |
| `sdboot/archsd.c`, `sdboot/sd_pcie.h`, `sdboot/gl9755.h`, `sdboot/gl9755_card.h`, `sdboot/gl9755_pci.h`; U-Boot replacement-source snippets in `sdboot/prepare_uboot.py`, `sdboot/uboot-noio.patch` | GPL-compatible source; listed C/header helpers retain `GPL-2.0+`. [U-Boot 8aa706b2](https://github.com/AsahiLinux/u-boot/tree/8aa706b2daa49b64102e44067d8514de8a26dc42) has individual exceptions, including GPL-2.0-only PCIe code. Its combined binary must retain GPLv2-compatible terms; do not claim every component permits later GPL versions. Embedded derivative snippets retain target-source terms even inside an otherwise original Python tool. |
| `packages/grub-m4rch/` copied/derived distribution recipe and support files; upstream memory-fix patch; compiled GRUB | GRUB is GPL-3.0-or-later. [ALARM recipe c1c4c53a](https://github.com/archlinuxarm/PKGBUILDs/tree/c1c4c53a48ac05adcda9539a10e2466b891e3ee7/core/grub) and [Neal Gompa's fix 711110da](https://gitlab.freedesktop.org/gnu-grub/grub/-/commit/711110daccaf15df695b270d13f76b5bc84a64dd) are recorded in [source.json](packages/grub-m4rch/source.json). Preserve recipe maintainer attribution. No explicit recipe-level grant was found in the pinned ALARM root/contribution notes; its package license field is not a grant for copied recipe files. Clarify that unresolved scope before claiming publication clearance. |
| Built paru and its fetched dependencies | Paru is GPL-3.0-or-later, [9ac35788](https://github.com/Morganamilo/paru/tree/9ac3578807a87858651e81a02586ceb947686e7c), pinned by [source.json](packages/paru-m4rch/source.json). Cargo dependencies retain their own licenses; paru's package installs its upstream LICENSE. |

Complete texts are retained at [GPL-2.0](third_party/LICENSES/GPL-2.0.txt),
[GPL-3.0](third_party/LICENSES/GPL-3.0.txt) and
[BSD-2-Clause](third_party/LICENSES/BSD-2-Clause.txt). GPL-2.0/BSD text came from
the pinned Linux `LICENSES/preferred/` files, extracting their `License-Text`
sections. GPL-3.0 came from `grub-2.16/COPYING` in the cached source archive after
verification against `packages/grub-m4rch/source.json`. These texts do not
replace author-specific notices or grant new rights.

Apple/Broadcom firmware, Apple recovery files, IPSWs, extracted proprietary
binaries/disassembly and generated firmware-bearing packages/images are local
inputs/outputs, outside the MIT grant. Do not include them in a public source
release. Distribution packages and other fetched build dependencies retain
their individual licenses.

## Reverse-engineering scope

USB2 is not the only area involving proprietary binary analysis:

| Area | Recorded basis and review boundary |
| --- | --- |
| USB2 PHY | Wallace's decoded Apple PHY initialization and local binary-derived reset/shutdown ordering; see [USB provenance](docs/usb-patchset-provenance.md). Analysis and implementation were not independently separated. |
| Trackpad reset | [The retained patch](patches/linux-j614s-trackpad-power.patch) explicitly records AppleHIDTransport kernelcache analysis for the power contract and delays, combined with ADT data and Asahi GPIO precedent. It needs its own provenance review. |
| Bootability investigation | The retired external-SD investigation inspected Apple's Bootability framework to explain a failed `bless` call. That history is retained privately; the current stub derives from the MIT Asahi installer. Inspection alone does not establish copied implementation or clear every subsequent change. |
| NVMe, CPU frequency, SMP and SMC telemetry | Recorded inputs are licensed upstream/community source and platform data. This audit found no equivalent local proprietary-code translation evidence; it is not a complete provenance clearance of those inputs. |

Failure to follow a textbook clean-room process is not itself a finding of
copyright infringement. [Asahi's policy](https://asahilinux.org/copyright/)
distinguishes hardware facts/traces from direct software translation and
restricts concurrent binary analysis and implementation. Licensing metadata
alone does not establish compliance. Its separate
[AI policy](https://asahilinux.org/llm-policy/) broadly excludes material
generative-AI contributions; that affects this agent-assisted project beyond
the USB work. No human certification or upstream acceptance is implied here.
