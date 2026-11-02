# J614s GPU and bootloader review

> Historical cache paths below describe past trials and are not current recovery instructions; most of those artifacts are no longer in the checkout. For the current boot recovery path, see [recovery](../../docs/recovery.md).

Reviewed 1 November 2026. The GPU candidate booted successfully for one
trial; the existing kernel remains the default. The MCC loader candidate was
selected for a separate boot, then the previous package-managed loader was
restored. The [GPU draft PR #804](https://github.com/aurora-silicon/linux/pull/804)
and [MCC PR #43](https://github.com/aurora-silicon/aura/pull/43) are open.
A successful build or short GPU run does not establish that every firmware
offset is correct.

Review branches and proposed PR descriptions:

- Linux `aurora-wip` base `52f0a6bee13b`: [GPU branch](https://github.com/mchalunderscore/linux/tree/codex/t6040-16core-layout),
  commit `c6665bed9ad1dce905ee35c4cebaf44054792ebb`; [PR description](https://github.com/aurora-silicon/linux/pull/804).
- Aura `main` base `212e3d10173f`: [MCC branch](https://github.com/mchalunderscore/aura/tree/codex/j614s-mcc-admission),
  commit `31d511f8d77a0f37df100287ccda54736a7452e9`; [PR description](https://github.com/aurora-silicon/aura/pull/43).

Each branch contains one commit. The GPU branch's three file blobs match the
hardware-tested source; the MCC branch's file matches the candidate patch
used in the loader build. The complete branch trees have not separately been
built or booted, and the PR descriptions identify the combined stack and
remaining test limitations.

## Context-save observability check — 2 November 2026

The running package kernel `7.3.0-1-14-ARCH` includes #804 and reports the experimental GPU layout. The actual GPU was not reset or stressed during this inspection. The current `asahi_g17` trace events expose host scheduling, command publication/completion, firmware messages and raw reports; none is an identified, decoded GPU context-save or restore event. The readable `/sys/kernel/debug/aurora-g17/firmware_reports` exposes raw firmware report tags and words, but their meaning is not established here. Neither changing a report count nor overlapping fences alone establishes preemption.

In the pinned Linux source `24bfd5ba2c182bf67d40c7d02f4947d124f04fa4`, `g17/queue/compute.rs` allocates the separate preemption and operand-state buffers as firmware-shared, write-combined CPU mappings. `g17/object.rs` has bounded word readers, while its mutable byte view explicitly requires that firmware not be accessing the object. These provide a possible observation route in a disposable instrumented kernel after the relevant queue is demonstrably idle; they do not establish that the buffers are written, which bytes are saved state, that a save and restore happened, or that the layout is correct.

A useful follow-up needs both a discriminating control and an independently observable event: capture per-queue buffer change summaries at a properly synchronized idle boundary, compare otherwise equivalent work with and without a demonstrable interruption, and confirm a resumed workload's results. Establish GPU-to-CPU visibility and queue lifetime before reading; do not print firmware memory or GPU addresses. A host-visible progress signal or decoded firmware event would need separate qualification as proof that the original dispatch had actually started and was interrupted. If the timer-disabled firmware and available priority policy cannot produce or identify such an event, the test must report inconclusive rather than infer preemption from overlap. A passing compute experiment would not independently validate render deflake or every offset; comparison with a trusted 16-core reference or maintainer analysis remains necessary.

The instrumented follow-up boot and bounded workload have now run on the target. Both operand banks and the preemption buffer changed during solo calibration before the competing queue was submitted, so writes to these buffers do not by themselves demonstrate a context switch. The trace did not identify a save/restore event; results and controls are described in [the context-observation experiment](../j614s-gpu-context/README.md). The 16-core offsets and preemption remain unverified.

## GPU trial result

### Follow-up validation prepared

On the restored default `7.3.0-1-9.3-ARCH` kernel, which carries the earlier
opt-in but uses the same T6040 command-buffer layouts, Aurora's M4 native GL
hardware program passed 32 rendering, compute and geometry-feedback rounds
and 30 seconds of bounded compute load with readback. Its log is
`cache/j614s-gpu-trial/baseline-native-gl46.log`; this is a baseline, not a
run of the PR candidate.

The [priority experiment](https://github.com/mchalunderscore/M4RCH/blob/f87ee7e694f9fdd893add08a2f427442cf1c45c9/experiments/j614s-upstream/gpu-priority-check.c) submits real Vulkan compute
work to distinct queues, waits for a GPU start timestamp, and compares a
low-versus-medium run with a same-priority control. On the baseline kernel,
the contender finished while the background fence was unfinished in 5/5
valid rounds for both conditions. This confirms the checked work completed
correctly under queue overlap, but does not distinguish hardware preemption
from concurrent execution or establish firmware buffer offsets. The log is
`cache/j614s-gpu-trial/baseline-priority.log`. The current Mesa path rejects
high-priority queues on this GPU; this test uses low and medium priorities.

The G17 firmware initialization sets `CONTEXT_SWITCH_TIMER_MASK` to zero;
according to the source this disables periodic timer interruption for the
listed engines. It does not prove that every other form of preemption is
disabled. Aurora's `compute-preempt-tests.py` tests host priority policy and
explicitly does not execute hardware. An observable firmware event, trusted
independent buffer-layout source, or another discriminating hardware test is
still needed before claiming preemption or offsets are validated.

On the PR candidate boot `6c6016fd-a269-49a6-bc89-ee1037fa01f4`, Aurora's
native GL test passed 32 rendering, compute and geometry rounds, plus 30
seconds of bounded compute with verified readback. The queue experiment again
reported fence overlap in 5/5 low-versus-medium rounds and 5/5 equal-priority
rounds. A separate tracefs instance captured Aurora's compute publish and
completion tracepoints while repeating the experiment. In all ten identified
rounds, the firmware completion timestamps placed the contender's compute
commands before the recorded GPU start of the long background compute command.
The query used as a start marker was a separate GPU command, so availability
of that marker did not show that the long dispatch had begun. The reported
fence overlap is therefore not evidence that a running dispatch was interrupted.
Raw local results and trace are under
`cache/j614s-gpu-trial/validation/6c6016fd-a269-49a6-bc89-ee1037fa01f4/`.
No GPU or DART errors were found in the checked kernel log. The tracepoints
report firmware timestamps, not a decoded preemption or context-save event.

A follow-up trace delayed the contender by 40 ms after the marker and again
completed the contender with the background fence unfinished in 5/5 rounds
for each priority condition. In all ten traced rounds, the firmware timestamps
still placed both contender commands before the reported background-dispatch
start. This did not establish a preemption event or make the prior marker a
reliable proxy for dispatch start. Those results are in the `delay40/`
subdirectory. The active test source now labels the result inconclusive; an
exact copy of the original source used in the first trace is retained beside
its hash manifest. Mesa rejects HIGH priority on this GPU, and its current
kernel/firmware tracepoints do not decode a context-save event. No scheduling
override or unsupported priority was enabled.

Review of Mesa's `hk_sync.c` explains why changing the query stage alone is
not a sufficient live-start signal: a TOP_OF_PIPE timestamp can be attached
to the next compute stream, but the G17 driver collects the firmware timestamp
as that command retires. Its completion code documents reading the public
words only after firmware retirement or a closed recovery acknowledgement.
An end-of-command result can help compare reported timestamps afterwards; it
does not provide a documented, synchronized notification that the dispatch
is running. A useful Linux follow-up would need a separately qualified live
firmware observation or another bounded experiment that demonstrates an
actual context save and restore. Neither that observation nor the hardware's
interpretation of the 16-core buffer offsets has been established here.

The known PR candidate was selected for the follow-up boot after checking
its kernel, initramfs, modules, GRUB and known-good Aura loader. The prior default remains selected on later
boots. The validation checked the booted kernel, ran the native GL hardware workload
and priority experiment, and saved logs. Those workloads
provide more evidence but cannot by themselves prove the contested offsets or
preemption.

The candidate kernel `7.3.0-1-9.3-gputrial-ARCH` and its modules were built
from the retained Aurora 9.3 source with the proposed GPU patch. Its separate
initramfs uses the existing Aurora configuration but filters the obsolete GPU
module parameter inside the trial image and loads the new driver there. The
kernel release, GPU module vermagic and contents were checked, including PMP,
NVMe, SART, Btrfs, dm-crypt, dm-integrity and the installed Wi-Fi firmware.
The initramfs build emitted missing-firmware warnings for Renesas USB,
DockChannel HID and MT7932; Aurora's vendor-firmware service is present in
the image. These checks do not prove peripheral or boot success.

The root staging script archived the current Aura bundle and GRUB files in
`/var/lib/m4rch/j614s-gpu-trial-20261101/`, kept the existing default entry,
and selected `m4rch-j614s-gputrial` through GRUB's one-boot `next_entry`.
The user reported a successful boot; boot ID
`5f4b8e50-b95b-41a1-b303-9b8d9a9605b4` ran the trial kernel and logged its
experimental-layout warning. The one-boot setting cleared. A 15-iteration
Wayland/Zink shared-surface rendering run succeeded, and an offscreen Zink
compute shader produced the expected 262,144 results after 64 arithmetic
rounds per result. No matching GPU/DART failure was found in the kernel log.
These short tests do not establish preemption correctness or complete graphics
qualification. The stage-two loader was unchanged during this trial. GRUB normally clears
the one-boot entry before starting the kernel and selects the old kernel on
the next boot. If necessary select the original entry from the GRUB menu;
external recovery can restore `grub.cfg` and `grubenv` from the archive.
The separate MCC trial bundle is at `cache/j614s-mcc-trial/boot.bin`, with its
receipt in the same directory. It was verified and selected at
`/boot/efi/m1n1/boot.bin` before the user rebooted. On boot ID
`2695a943-5568-47e8-ba6c-5dcb23378900`, the user reported a normal boot;
the default kernel started, and PMP, GPU, display, Wi-Fi and SEP drivers
initialized. The loader version string is the same as the earlier build, so
the boot log alone does not independently identify the exact loader binary.
After the trial, the package-managed bundle was verified and restored as the next default.

Aura stage two does not automatically revert on failure: the previous bundle is at
`/boot/efi/m1n1/boot.bin.m4rch-pre-mcc` and in
`/var/lib/m4rch/j614s-mcc-trial-20261101/`. The EFI backup has SHA-256
`7faa2fa33f05f4020e3bb1bd39af3100ca6bffa3812c1f23dcb77e2960af85bd`.
From macOS or recoveryOS, mount EFI partition `E8DC-7E45` (PARTUUID
`f4c270bd-b482-43e3-880c-b60541cf8e78`), then in its `m1n1` directory verify
the backup hash, copy `boot.bin.m4rch-pre-mcc` over `boot.bin`, sync and verify
the destination hash. These notes describe an older trial; use the current
[recovery guide](../../docs/recovery.md) for the installed default.

## GPU: describe the observed alternative in the SoC configuration

Aurora Linux `aurora-wip` at
[`52f0a6bee13b`](https://github.com/aurora-silicon/linux/commit/52f0a6bee13baf7311123b88f5d5913ca039539c)
accepts the T6040 layout measured on a 20-core M4 Pro and explicitly rejects
other active-core counts. Aurora's [T6040 follow-up #420](https://github.com/aurora-silicon/linux/pull/420)
moved operand-state and render deflake layouts into the SoC configuration. The
upstream `hw/t6040.rs` documents that the existing values were measured on a
20-core GPU; the [original work #408](https://github.com/aurora-silicon/linux/pull/408)
describes the firmware-version and calibration checks. None of that establishes
the correct 16-core layout.

The running patch adds a module parameter plus a match on chip, die count,
cluster count, reported core slots, active-core count and both fuse masks.
For the observed match it retains Aurora's `TWO_BY_TEN` operand buffer and
`TWO_CLUSTERS` deflake configuration. The operand buffer has two preemption
banks and per-cluster tails; size alone does not establish the required firmware
offsets. Successful 2D and Vulkan/Zink rendering gives useful evidence but does
not verify the compute preemption banks or all GPU workloads.

The source describes three `0x800`-byte records per core per bank: 20 slots
give `0x1e000` bytes, while 16 active cores give `0x18000`. The configured
second-bank offset includes an additional `0x400`, so the distinction is
`0x1e400` versus a hypothetical `0x18400` before accounting for any further
firmware rules. That arithmetic explains why simply allocating a buffer large
enough does not resolve the question. It does not establish whether firmware
uses physical slots, enabled cores, or another layout; the hypothetical
offset has not been tested and must not be treated as a specification.

The Aura overlay previously carried a host-only GPU calibration test. It has
been removed from the active source stack; the original promoted-source patch
is preserved in the compressed provenance archive. It did not change loader
behavior or establish Linux PR #804's firmware layout.

[`gpu-t6040-layout-proposal.patch`](https://github.com/mchalunderscore/M4RCH/blob/f87ee7e694f9fdd893add08a2f427442cf1c45c9/experiments/j614s-upstream/gpu-t6040-layout-proposal.patch) puts the
observed masks and slot count in T6040's `CoreLayout`, with generic matching in
G17 and no board-specific exception in the common driver. The existing
measured 20-core path remains unchanged; T8140 has no alternate. The proposed
alternative retains the exact mask, slot and cluster checks and reports a
warning on use. Earlier identity validation already checks the T6040 die
count. It admits any T6040 reporting that exact topology, not only a device
identified as J614s. It changes explicit opt-in to automatic admission, which
is a policy choice for upstream review. Neither broader mask admission nor
the 16-core buffer offsets are established by the evidence here.

All three affected files match the relevant current upstream source byte for
byte. The proposal applies cleanly to those upstream versions. In an isolated copy of the
installed source, the old admission patch was removed and this proposal applied;
an out-of-tree build with the installed kernel configuration and Rust 1.99
compiled the real `drivers/gpu/drm/asahi/asahi_core.o` successfully. The
build emitted Rust deprecation warnings. Kernel `checkpatch.pl` found no style
issues with the missing-commit-message check excluded; the proposal is not yet
a commit. It did not build a complete bootable
kernel or test the new automatic admission. Object SHA-256:
`f2756c435585ec311af75d9f6ebae760b992393e06474a76597342013db4e7b3`.
The earlier generic-code exception was superseded; its exact patch is kept at
`cache/j614s-upstream-provenance/gpu-16core-no-optin-proposal.patch`.

Before a ready-to-review submission, exercise the candidate on the target
through an attended boot, then run real render and compute workloads including
preemption and check kernel faults. A passing stress run helps but does not
prove the firmware offsets. Compare them with authoritative per-SKU evidence
if available, and disclose the remaining uncertainty. Do not publish device
calibration or proprietary firmware.

## Aura: smaller MCC board admission

Aurora Aura `main` at
[`212e3d10173f`](https://github.com/aurora-silicon/aura/commit/212e3d10173f86d6f36e3a749fce3b90eb077c51)
still accepts board ID 6 under the T6041 firmware-cache path, then checks the
ADT geometry, register ranges and cache status. The installed J614s patch also
requires the `J616sAP` ADT compatible on the existing board ID 6 path; that
additional restriction changes Aurora's J616s behavior and is unnecessary to
add J614s.

[The MCC proposal](https://github.com/aurora-silicon/aura/pull/43) leaves the
existing J616s admission unchanged and admits board ID 4 only when the ADT
also identifies `J614sAP`. All Aurora geometry, register-range and cache-status
checks remain in place. The J614s condition is identical to that in the
booted patch. Aura's unmodified `mcc.c` at the current tip matches the source
at the booted Aura package pin apart from trailing blank lines.

The reduced patch applied cleanly to the current source and compiled and
linked in an isolated Aura stage-two build using the remaining booted overlay
and the existing toolchain. The resulting candidate's SHA-256 is
`02401e66a219d7953eeb246c8291c86f4df937c503123471b5551b53690b7292`.
The assembled candidate was selected for the subsequent successful boot
described above. This is combined-stack boot evidence, not a captured MCC
initialization trace or an independently measured booted-binary hash.

## Other boot handoff

- **Display:** Aurora's [m1n1 display PR #51](https://github.com/aurora-silicon/m1n1/pull/51)
  established the T6041 handoff on J616s; Aura's [platform consolidation #16](https://github.com/aurora-silicon/aura/pull/16)
  includes that work. Our display patch adds J614s to that board list and
  separately preserves its inherited framebuffer in `display.c`. Both steps
  affect different stages; a successful internal/HDMI display on the combined
  boot does not prove either can be deleted. The extension may be separable
  as a small upstream proposal after checking the producer/consumer chain.
  Submitted as [Aura PR #44](https://github.com/aurora-silicon/aura/pull/44):
  the running device tree has the T6041 handoff marker, and the user confirmed
  the internal display and HDMI on the combined loader. The standalone branch
  built as an ESP stage-two image; it has not itself been booted. The existing
  host harness passed 44 guard scenarios with ASan and UBSan.
- **SD:** The package-managed loader still makes the J614s-specific Aura
  power call and applies the U-Boot tree rewrite. Two later combined-stack
  trials omitted the Aura power action; the second also omitted the U-Boot
  rewrite and used the source-built board description. It detected an SDXC
  card and read its partition table. Those tests support moving the power
  description into Linux, but do not qualify sustained writes, suspend or
  a clean-room power state. The exact upstream board branch has not been
  booted. See the [SD trial record](../../docs/j614s-sd-reader.md).
- **Retained input and memory:** Aura publishes readiness and reservations;
  U-Boot and Linux consume live MTP/RTKit and DART handoff information. The
  checks have dependencies across all three components. No deletion is
  justified until those contracts are mapped and a real boot comparison shows
  the remaining paths preserve input, firmware and reserved memory.

Do not publish unreviewed bootloader changes or schedule a reboot automatically.
