# J614s upstream preparation

> Historical cache paths below refer to retired trial artifacts; the cache now retains only inputs needed by two current test helpers. For the current boot recovery path, see [recovery](../../docs/recovery.md).

Reviewed against upstream on 1 November 2026. These are proposed submissions,
not changes to the installed system. Hardware evidence comes from the combined
J614s stack; it does not establish that every prerequisite is available in an
unmodified upstream installation.

## SEP profile

The change from [Aurora Linux PR #813](https://github.com/aurora-silicon/linux/pull/813) was included in the merged [board PR #795](https://github.com/aurora-silicon/linux/pull/795); #813 was closed as a duplicate. The redundant local candidate has been removed from the active tree; the old package's exact patch series remains in its provenance archive.

- Target: Aurora Linux `aurora-wip` at `52f0a6bee13baf7311123b88f5d5913ca039539c`.
- Scope: add J614s to the existing T6040 profile's explicit board allowlist;
  retain the existing J616s profile, board guard and all other behavior. No
  new parameter, transport, profile or xART policy is introduced.
- The patch applies to that upstream file without fuzz. After application,
  `drivers/soc/apple/profile.rs` matches the source used for the installed
  Aurora 9.3 kernel; the submitted file differs only in its explanatory comment.
  The user reported
  successful fingerprint authentication with this kernel, including after the
  Aura stage-two boot. This is combined-stack evidence, not an isolated test
  of every code path or proof that a stock upstream boot enables the sensor.
- Prerequisites include a J614s-compatible device tree with the SEP and sensor
  described, a safe firmware/reserved-memory handoff, and the machine's own
  sensor inputs. Do not
  publish calibration, signed firmware, identity material or raw ADT data.
- The earlier kernel carried a separate xART-defaults policy patch; the
  current installed stack uses Aurora's defaults.

Suggested title: `soc: apple: sep: allow the T6040 profile on J614s`.

Suggested description: J614s uses the existing T6040 SEP profile, including
the existing warm-registration and sensor settings. Extend the board gate to
the J614s rather than admitting all T6040 machines. On a J614s using the
patched Aurora 9.3 kernel and the required board-specific boot and firmware
setup, fingerprint enrollment and authentication worked, including after a
subsequent boot. This does not qualify other T6040 boards or an otherwise
unmodified Aurora installation. The J614s DT is proposed separately in #795.

## Microphone UCM profile

Submitted as [ALSA UCM PR #9](https://github.com/aurora-silicon/alsa-ucm-conf-asahi/pull/9)
and [audio DSP PR #16](https://github.com/aurora-silicon/asahi-audio/pull/16).
The UCM candidate is [`ucm-j614-hpai.patch`](ucm-j614-hpai.patch), adding the exact
profile included in the forked UCM source.

- Target: Aurora `alsa-ucm-conf-asahi` `main` at
  `b9b2d0c82cbb46025e586b2dc9f2cae644d29999`. The J614 entry was absent at
  review; the existing J616 profile uses the same shared `3chan/HiFi.conf`.
  The candidate adds one card-name mapping and no new route or speaker setup.
- The installed candidate resolved the real J614 HPAI card, the three-channel
  HiFi profile and `Internal Mic Jack`; a one-second 48 kHz capture completed
  to `/dev/null`. This establishes device/profile resolution and capture
  operation, not microphone signal quality, channel ordering or lid behavior.
  The user has since selected the processed J614 microphone and confirmed a
  clear voice recording using this package and the J614 DSP graph. This does
  not characterize channel ordering, lid behavior, clipping or resume.
- The patch applies to the archived Aurora source from which the package was
  built. The target file is also absent on the current upstream main branch.
  The separate DSP rule is needed to expose a processed desktop source.

Suggested title: `aop_audio: add J614 high-power microphone profile`.

## Remaining dependencies and review

### Headphone jack on the #795-derived tree

On 2 November the running kernel exposed only the J614 HPAI microphone card;
the CS42L84 codec was detected, but the headphone card logged that
`mca-pcm-0` was not registered. The running kernel's `macaudio` module lacks
the `apple,j614-macaudio-jack` match, so the J614s board-tree node falls back
to the generic MCA configuration. Linux #795 adds the J614s jack match to the
existing J616 AOP jack configuration, which selects the AOP front end instead.
That is a source-level explanation for this mismatch; the exact replacement
has not been booted or tested with wired headphones.

Both the running tree and #795's T6040 audio node include the `spkr`, `cout`
and `cin` DMA names. With `spkr` present, the existing Aurora AOP driver already
registers the speaker and jack components, so the local patch that permits
jack registration without `spkr` does not change that path. Do not remove it
from the installed kernel until its replacement stack is built and verified;
it remains useful for a tree that deliberately omits the speaker stream.

- A stage-two trial using #795 head `2b2ec81a6744`, the J614s identifiers in
  [#816](https://github.com/aurora-silicon/linux/pull/816), and the local
  [loader compatibility include](j614s-loader-trial.dtsi) was staged on
  1 November 2026. The candidate retains #795's inherited speaker nodes and
  streams. Its verified bundle is `cache/j614s-pr795-trial/boot.bin`. On boot
  `3213ff95-83bd-4bdb-b862-7711e07edd5b`, the owner reported it works; the
  live tree and kernel logs showed J614 identifiers, the inherited speaker
  streams, keyboard, trackpad, display, GPU, Wi-Fi and NVMe root. The
  candidate has other local handoff changes and does not qualify #795 alone.
  The tested bundle and DTB were promoted as `aura-j614s-boot 20261101-4`
  and `aurora-j614s-config 20261101-5`, and GRUB was regenerated with one
  default entry. The final regenerated GRUB configuration has not been booted.
  The original verified bundle is preserved as
  `/boot/efi/m1n1/boot.bin.m4rch-pre-pr795` and
  `/var/lib/m4rch/j614s-pr795-trial-20261101/boot-known-good.bin`.
  Use macOS or recovery media to mount
  the EFI partition and copy that EFI backup over `m1n1/boot.bin`. GRUB's
  existing default kernel is unchanged.
- The [GPU and bootloader review](GPU-BOOTLOADER-REVIEW.md) records reduced
  source proposals, upstream comparisons, builds and hardware-test gaps.
- GPU 16-core admission currently uses a local opt-in and a narrowly matched
  fuse layout. The machine renders with it, but buffer offsets for this SKU
  remain a hypothesis. The [configuration-based proposal](gpu-t6040-layout-proposal.patch)
  keeps the narrow check and removes the explicit opt-in; its automatic
  admission and compute/preemption behavior still need hardware validation.
- The installed tree is based on [#795](https://github.com/aurora-silicon/linux/pull/795)
  with [#816](https://github.com/aurora-silicon/linux/pull/816) and a local
  loader compatibility include. Further compare display power links, SD and
  firmware handoffs before claiming that unmodified #795 has been booted.
- The generic jack registration fix is already in [#437](https://github.com/aurora-silicon/linux/pull/437),
  which retains unresolved dependencies on #434. The GPU deferred-close fixes
  in [#772](https://github.com/aurora-silicon/linux/pull/772) were folded into
  Aurora's broader integration branch; do not resubmit them as new work.
- The [DAPF handoff review](../../docs/j614s-dapf-handoff.md) found that
  the local readiness marker can report success when a bank is absent, and
  a validation error bypasses power cleanup. Do not submit it unchanged.
- The extra 32 KiB J614s PMP FDT-space allowance was removed for a trial.
  Boot `7cf3622e-d592-46e5-8a5a-432db520faa7` reached Linux; PMP exposed
  88 tunables totaling 16,517 bytes and its firmware and endpoint initialized.
  GPU, display and AOP initialized too. The next Aura staging recipe drops
  the allowance; the installed package is unchanged and the verified default
  stage-two bundle has been restored for the next boot.
- Cooling references to CPUs removed during boot are handled in
  [Aura #46](https://github.com/aurora-silicon/aura/pull/46). On the
  J614s DTB, 28 entries refer to two absent CPUs. The proposed helper
  reproduces all 80 cooling maps in the successfully booted tree; it also
  builds against current Aura. An empty resulting map is rejected explicitly.
- The flat-root address resolver is open for review as
  [Aura #45](https://github.com/aurora-silicon/aura/pull/45). On the
  J614s board DTB, the unpatched helper returns zero for a root-level DART;
  the submitted code resolves the address and passes focused host checks.
  The standalone branch builds; the matching local change booted as part of
  the integrated stage two, but this exact branch has not been booted alone.
- The source-built SD board description from
  [Linux #818](https://github.com/aurora-silicon/linux/pull/818) was merged
  into the still-open #795 board branch. A combined-stack J614s boot detected an SDXC card and its partitions
  without the earlier U-Boot SD tree rewrite or Aura SD power action. The
  The owner later confirmed mounting and editing files on the card during the
  trial. The standalone upstream branch and suspend remain unqualified.
- The kernel side of retained input is open for review as
  [#817](https://github.com/aurora-silicon/linux/pull/817), with the matching
  [U-Boot producer #29](https://github.com/aurora-silicon/u-boot/pull/29).
  The exact producer branch builds and its handoff tests pass, but has not
  been booted independently of the local integration stack. The remaining
  dynamic memory and firmware handoffs need separate ownership and hardware
  validation; see the [DAPF](../../docs/j614s-dapf-handoff.md),
  [ANS](../../docs/j614s-ans-memory-handoff.md), and
  [SEP/DCP](../../docs/j614s-sep-dcp-reservations.md) reviews. The later
  source-built SD trial removed the earlier SD tree rewrite, as described
  above; the owner also confirmed editing files on the card. Suspend remains
  unqualified.
  An older test also recorded an unexplained I/O error.

The GPU and MCC proposals are open as [GPU draft PR #804](https://github.com/aurora-silicon/linux/pull/804)
and [MCC PR #43](https://github.com/aurora-silicon/aura/pull/43). The proposed
[speaker-node removal #814](https://github.com/aurora-silicon/linux/pull/814)
was withdrawn: J614s hardware evidence supports retaining those nodes.
