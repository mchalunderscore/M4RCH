# AUDP001 revision 8: shared register layout and live-session adoption

R7's native logs confirm the PMP supplier/report correction worked:
`J614s boot display power retained; no J713 PMP command sent`. Binding then
stopped at `Unexpected disp_reg value in 'apple,bw-scratch': 4`.

The sixth physical ADT resource (coprocessor plus five display apertures) is
the same `0x504800000/0xbc000` range used by the bandwidth provider. Our DT
correctly describes it, but the generic firmware-list builder counted all
five display apertures and then attempted to append bandwidth at index 5.
The existing native bandwidth specifier names index 4 and offset `0x20000`.
R8 keeps all six physical resources in the DT, requires an exact provider/
shared-aperture range match, and uses that range once as firmware register 4.
The firmware list therefore has five complete entries, with no duplicate or
uninitialized sixth entry. Malformed scratch resources smaller than a word
are rejected before subtracting their size.

The subsequent bind/start audit found native desktop sessions were not marked
as adopting the live DCP and were excluded by the existing session pin helper.
R8 qualifies native J614s desktop firmware plus the inherited-mappings marker,
sets its hardware adoption flag, and admits that same qualified session to
the existing device/domain/module retention mechanism. It checks that the
coprocessor is running and skips the CPU RUN write. Pinning occurs before
RTKit registration; failure cleanup retains DMA backing. This does not route
the desktop firmware through H17 protocol or broaden the global H17 helpers.

`prepare_shared.py ROOT OUTPUT` applies the changes after r7. Build and export
only the stripped appledrm module. `tests/shared.py ROOT OUTPUT LIVE_DTB`
extracts the actual full register-list builder, scratch parser, firmware
register reply/bounds helpers and retention functions. Under ASan/UBSan, the
r7 native data yields five exact physical firmware replies; malformed aliases,
sizes, offsets, indices and lists are refused. J616s' original append path and
legacy retention remain covered. The original builder fails the native case.

PR445 was closed in favor of PR446, which carries the display commits unchanged
with external dependency/PHY fixes and updated host fixtures. External DCP/PHY
changes remain excluded here. The corrected common/rate fixtures from commit
`7efa9c4fa0c1611ef3a2d5b7e78b6b07691f5173` now run all four upstream rate tests
against this candidate successfully, including the publication/HPD fixture
that could not compile in r5. Fixture provenance and checksums are in the audit.

`package_shared.py` keeps the exact tested r7 kernel, loader and every module
except appledrm; three initramfs entries change. `stage_revision.py --apply`
installs r8 as the default and retains r7/r6/r5 plus the five pre-DCP entries.
Only the obsolete r4 entry and its exclusive kernel/initramfs are archived and
removed for space. Kernel name remains `7.3.0-m4rch-dcp006`, loader DCP005;
the runtime banner/profile identify r8. Speakers stay disabled. No reboot is
performed. Evidence is in `out/aurora-dcp/native-r7` and `shared-r8`.

The audit also found missing AVD firmware `apple/avd-fw-v5-t1.bin`, independently
preventing video-decoder probing. That is not changed by this DCP candidate.
Native RTKit/IOMFB startup, retained-buffer DMA, panel takeover, brightness and
refresh switching remain unverified until the user's next boot.

## Revision 7: native PMP supplier/report readiness

The r6 native logs confirm that framebuffer lookup now succeeds. Component
binding reaches `j614s_display_power_prepare()`, then refuses `-ENODEV` before
DCP startup. PMP's Rust driver reports firmware/endpoint readiness, but its
live node lacks `apple,pmp-report`, and `apple_pmp_report_wait_supplier_ready()`
only accepts J713/T8132 or J613 report types. Both conditions prevent native
T6041 readiness from being observed. The display consequently stays simpledrm.

R7 completes the existing PMP-to-report phandle relation in the same early
OF changeset that admits the display devices. It requires the native PMP and
report compatibles, available nodes and the report's existing phandle; an
existing conflicting relation is refused. Nothing creates another PMP owner.
U-Boot's existing native `pmp_handoff()` already enables the PMP before Linux
enters this gate, even though the source template leaves it disabled.

The readiness API now recognizes the native J614s/T6041 supplier and report.
It reads the existing bound report through its matched offsets and uses
T6041's existing nonzero-status running rule. Device locking/removal guards
remain. A zero-time check reads once and returns `-EAGAIN` if not ready;
it no longer risks the polling macro's unlimited zero-timeout semantics.
J713 bit-0 and J613 exact-status rules remain unchanged. No J713 display-power
command is sent; native DISPINT remains logical ID 17, outside that command's
four-bit field. Initial display power is retained, and display sleep stays
inhibited for this trial.

`prepare_supplier.py ROOT OUTPUT` applies the correction after r6. Build
kernel and modules with LOCALVERSION `-m4rch-dcp006`, install matching stripped
modules, remove TAS2764/TAS2770, and regenerate depmod. The actual topology
and readiness C functions pass `tests/supplier.py ROOT M1N1 OUTPUT LIVE_DTB`
with the r6 tree under ASan/UBSan, including staged topology, identity/link
mismatches, allocation failure, bound/removal guards, timeout handling and
legacy status semantics. The original readiness function fails against the
same correctly linked native report.

`package_supplier.py` preserves all but four r6 initramfs entries: matching
modules, kernel-release config, banner and profile. The loader remains the
exact tested DCP005 binary. `refresh_supplier.py --apply` makes r7 the default,
retains r6/r5/r4 and the five pre-DCP fallback entries, and archives/removes only
the obsolete r2 entry and its two payloads to make space. Original rollback
remains available. The installed kernel reports `7.3.0-m4rch-dcp006`.

R7 has not been booted: DCP firmware startup, internal-panel takeover, physical
backlight and refresh switching still require the user's native test. Evidence
is in `out/aurora-dcp/native-r6` and `out/aurora-dcp/supplier-r7`.

## Revision 6: native boot framebuffer selection

Revision 5's native return bundle proves the loader and bridge completed,
the kernel admitted the inherited display handoff, and SID0/SID16/SID23
translation tables were preserved. It then stopped before DCP startup:
`apple-drm display-subsystem: reserved-memory node 'framebuffer' not found`
and `adev bind failed: -19`. The desktop remained on simpledrm at 3024x1890.

This is our native-DT integration gap. The boot framebuffer is described as
`/chosen/framebuffer`, without a legacy `framebuffer` memory-region on the
display subsystem. PR445's existing boot-framebuffer reader already handles
that representation, but its board selector only admitted T8132. Revision 6
adds T6041 to that selector; explicit framebuffer memory regions retain their
existing lookup path. No addresses, memory reservations or firmware data are
invented. The native aperture is taken directly from the saved/live DT.

`prepare_bootfb.py ROOT OUTPUT` applies the one-predicate correction after
the r5 preparation. Build modules with the existing r5 configuration, export
the stripped `appledrm.ko` and its `apple_drv.c` into `out/aurora-dcp/bootfb-r6`,
and run `tests/bootfb.py ROOT M1N1 OUTPUT LIVE_DTB`. The test extracts the actual
production selector and aperture reader, uses m1n1's libfdt with the failed
boot's saved tree, and runs under ASan/UBSan. It covers the real aperture,
disabled/duplicate framebuffer refusal, reserved-memory preference, J713 and
legacy selection. The original selector fails against the same native tree.

`package_bootfb.py` preserves every other module and all but three initramfs
entries; `refresh_bootfb.py --apply` installs r6 as the default. Kernel release
remains `7.3.0-m4rch-dcp005`, loader remains DCP005, and their binaries are
byte-identical to r5. Only appledrm, the runtime banner and runtime profile
change. The corrected module imports the same kernel symbols. All eight
previous entries and the original pre-DCP rollback remain available. Only
the unreferenced r3 initramfs was archived, hashed and removed to make room;
the r3 kernel remains because the r4 fallback references it. Built-in speaker
amplifier modules remain excluded. Nothing reboots the machine.

This removes a demonstrated bind blocker; r6 firmware startup, panel takeover,
backlight and refresh changes still require a manual native boot. Evidence is
under `out/aurora-dcp/native-r5` and `out/aurora-dcp/bootfb-r6`.

## Revision 5: PR445 desktop DCP backend for J614s

Revision 5 uses PR [#445](https://github.com/aurora-silicon/linux/pull/445)'s
dedicated T6041 desktop-26.6 backend, replacing our J614s use of `iomfb_m4`.
The display source directory is pinned to `579cfbd0762a152be943746de22a2702b8dc0116`
(Aurora `653c489a8347` plus PR commits 4-7). The PHY and external-display
commits are excluded. The rest of the existing kernel, including working
GPU16, radio, input, camera and USB3 support, stays on its prepared source.
Kernel and modules are `7.3.0-m4rch-dcp005`; loader version is `DCP005`.

`prepare_desktop.py` imports that directory and records its source hashes and
the additional patch. J614s keeps its actual six register windows, including
the fifth DISP0/shared aperture at `0x504800000/0xbc000`; J616s still requires
its original five. The existing PMP owner remains pinned. The first takeover
tries a firmware-listed native 3024x1964 mode near 60 Hz, instead of using the
J616s pixel-clock constant. The new backend supplies its own mode-info,
bootstrap, power, compact EPIC, callback and timestamp handling. Its firmware
catalog controls available refresh rates; 120 Hz is not fabricated or claimed
tested on this machine. VRR and HDR stay off. `show_notch=1` uses the full panel
height. Our saved ADT confirms `user-accessible-max-nits = 600` (16.16), matching
the new backend's maximum. Display suspend remains temporarily inhibited.

Review follow-up adds desktop callback envelope bounds and minimum typed
input/output sizes before callbacks read or write their payload. ABI padding
is allowed. The raw D114 dictionary and deferred backlight reply are checked
as well. External processors are explicitly disabled, so the series' external
PHY ownership/dependency review findings do not change the working USB3 driver.

The remounted ESP contained a fresh revision-4 return bundle. It proves that
the UUID, board, firmware and all three table roots passed, then m1n1 refused
at `sid23-translator`. Its `dt_get_address()` returned zero for direct root
children without an ancestor `ranges`, although the native flat-root DT has
valid absolute addresses. `prepare_flat_root.py` adds bounded decoding for a
direct root child with 2/2 address/size cells and complete 16-byte reg tuples.
Nested buses without a translation remain rejected. No stream validation,
protection, ownership or live translation check is bypassed. The production
decoder passes against the actual control, template and revision-4 live DT;
the original decoder fails the same test. Thus the r4 TTBR-mask correction did
not resolve the native refusal; this is a separate demonstrated blocker.

Build with `prepare_desktop.py ROOT PINNED_SOURCE OUTPUT`, LOCALVERSION
`-m4rch-dcp005` and the existing LLVM build recipe. VMAP_PFN is the only config
addition apart from LOCALVERSION. Install matching stripped modules, remove
TAS2764/TAS2770, regenerate depmod and prepare a fresh r4 runtime with
`prepare_desktop_runtime.py`. Apply `prepare_flat_root.py` to the r4 m1n1 source
and build with `M1N1_VERSION_TAG=DCP005`; control DT and U-Boot are unchanged.
`package_desktop.py` checks the first-stage window, kernel/module identities,
unchanged runtime entries and speaker exclusion. `refresh_desktop.py --apply`
installs it as GRUB default with a separate r4 fallback, the six prior
fallbacks and original pre-DCP rollback. It archives and retires only the
unreferenced revision-1 kernel/initramfs to make room. Nothing reboots.

Artifacts, source patches, validation and staging receipts are in
`out/aurora-dcp/desktop-r5/`. The full kernel/modules and loader compile.
Production register/D006 and loader tests run under ASan/UBSan, including
pre-fix negative controls. Upstream boot-log tests pass 2/2; mode parsing,
metadata decoding and retry tests pass. The upstream publication/hotplug host
fixture cannot compile with PR445's new lookup/VRR helpers and is recorded as
not executed, not passed. Native takeover, physical brightness and refresh
changes still require the user's manual boot.

The sections below document earlier revisions and their source history.

This is an **untested native candidate**, built for the 14-inch M4 Pro J614s,
16-core GPU and the existing Arch stub's macOS 26.6.2 / 25G83 firmware. It aims
at internal-panel DRM takeover, initial scanout and desktop page flips using
the working Aurora Asahi/Zink userspace. It does not qualify another board,
firmware revision, external display, HDR, VRR or a display sleep/resume cycle.

The default GRUB entry is `m4rch-aurora-dcp001` after `refresh_trace.py --apply`, as
requested. The five existing GPU16 and framebuffer fallback entries remain.
Nothing reboots the machine. Built-in speaker devices remain disabled and both
TAS2764/TAS2770 amplifier modules are removed from the trial module archive.
External audio is allowed. Sleep and lid-triggered suspend are inhibited for
this trial through temporary `/run` overrides; the installed sleep policy is
not changed.

## Revision 4: handoff correction and persistent native evidence

Revision 3's native return proves the screen remained simpledrm at 3024x1890.
The expected mode-switch option was present, but kernel admission rejected a
missing handoff marker before any DCP probe. The saved tree has no DCP firmware
reservations. KDE also reported no kernel backlight interface; the reported
brightness change does not establish DCP backlight success.

Revision 4 corrects the loader's T8110 TTBR root calculation to use the same
bits 29:2 address mask as the production DART driver. Previously bits 31:30
could contaminate the computed physical address. A production-header host
regression passes with this change and fails with the original calculation.
The actual native TTBR values were not saved, so this is a verified code
correction, not a claim to have established the cause of the native refusal.
All board, firmware UUID, segment, DRAM, table-region, translation and ownership
checks remain in place. No display firmware, stream root or TCR is replaced.

m1n1 now exports its exact stage/refusal line, live identity/UUID, bounded raw
segment metadata, and ADT/register values from the checks it already performs.
These `/chosen/m4rch,dcp-*` properties are published after transactional DT
rollback, so rejection cannot discard the evidence. U-Boot preserves that
metadata and records its own bridge result, source line and consumer. The
runtime prints these properties before loading appledrm and captures them in
the normal return bundle. A successful handoff continues into the full existing
DCP/brightness/multi-mode path. This is not a guard-bypass build.

`DCP004` is the loader revision. The kernel/modules remain the exact
`7.3.0-m4rch-dcp003` binaries; the default entry reuses `/AUDP001/r3/vmlinuz`
and loads the updated `/AUDP001/r4/initramfs.img`. Mesa, module archive, UCM,
startup policy and speaker exclusions are byte-identical to revision 3.
Only the runtime script, collector and runtime profile change inside the
initramfs. GRUB reduces `drm.debug` to `0x04` and increases the log ring to 8 MiB,
avoiding the atomic-commit flood that erased early lines from the r3 dmesg.

Rebuild with `prepare_handoff_trace.py` on the prepared r3 m1n1 source and
`prepare_bridge_trace.py` on the prepared r3 U-Boot source, then rebuild both
loaders. Repack a fresh r3 initramfs using `prepare_trace_runtime.py`.
`package_trace.py` validates the assembled artifacts and unchanged payloads;
`refresh_trace.py --apply` installs revision 4 as the default. Artifacts and
logs are under `out/aurora-dcp/handoff-r4/`. Existing r2/r3 payloads and every
fallback entry remain intact, and original pre-DCP rollback is still supported.

`tests/loader_trace.py` compiles the actual admission header with deterministic
ADT/MMIO shims and real libfdt under ASan/UBSan. It exercises successful
admission, sixteen refusal paths, post-rollback evidence and an original-code
negative control. Bridge tests check that both success and rejection preserve
m1n1 evidence across disjoint device trees. These do not establish native
DCP takeover or mode switching. No native success is claimed for revision 4.

## Revision 3 multi-mode experiment

Revision 3 is `7.3.0-m4rch-dcp003`, installed under `AUDP001/r3/` by
`refresh_modes.py --apply`. It retains the same loader, GPU/Mesa payload and
three upstream integrations as revision 2. The default entry enables
`appledrm.j614s_modeset=1`; the runtime also passes that option explicitly to
modprobe. Without this option, the backend retains its previous fixed-mode
behaviour. The revision-2 retained-mode entry is preserved separately, alongside
all five known-working pre-DCP fallbacks. Original pre-DCP restoration remains
`python3 /Volumes/M4RCHESP/AUDP001/restore.py`.

The new path parses `TimingElements` if present, otherwise
`PreferredTimingElements`, publishes every accepted physical 3024x1964 SDR
mode, and prefers the highest advertised refresh rate up to approximately
120 Hz. It does not fabricate 120 Hz when firmware does not advertise it,
virtual resolutions, HDR, or adaptive refresh. Catalog validation preserves
porch/rate/unit/color checks and rejects duplicate timing IDs, overflow and
truncated input. The complete catalog and every requested color/timing ID are
logged for the return bundle.

Atomic validation checks against this immutable catalog. Commit sends A413
with the actual firmware color/timing IDs, serialized with display swaps and
brightness, with an 8.5-second bound. A nonzero firmware result, transport
failure or failed health check marks the session failed; the driver does not
record a rejected mode as successfully programmed. Repeated commits of the
already programmed mode avoid another firmware call. Mode-change errors now
reach the existing DRM failure path instead of being ignored.

`audit_modes.py` checks the exact private T604x UUID and relevant dispatch,
packet-size and vtable instructions. The A413 thunk at `0x1c4de4` accepts an
8-byte color/timing request and writes a 4-byte result; its vtable target is
`0x2363c8`. This establishes the packet layout, not native mode-switch success.
Aurora's H17P path documents retained-panel A413 rejection (`0x8000000b`).
This candidate deliberately attempts the T604x path rather than assuming that
restriction is universal. Existing swap encoding is retained; ProMotion
presentation-timestamp requirements are not yet qualified. A black screen,
rejected command or stalled presentation is a possible outcome. Display
suspend remains disabled and no donor power-state command is introduced.

`tests/modes.py` compiles production parsing and the actual modeset function
with host transport/DRM shims under ASan/UBSan. It checks firmware-ID/packet
order, 48/60/120 catalogs, capacity/duplicate/truncation rejection, 120-to-60
transitions, no-op commits, rejected responses, timeouts and failed health
checks. These are host regressions, not native panel or KUnit tests.

For a fresh source build apply `prepare_modes.py` after the revision-2 source
preparation, set LOCALVERSION to `-m4rch-dcp003`, then rebuild kernel/modules
and the initramfs. `kernel-multimode.patch` records the exact extra source diff.

## Revision 2 upstream integration

The candidate includes these pinned open Aurora PR diffs, applied cleanly over
our existing native-working J614s/GPU16/DCP port:

* [#429](https://github.com/aurora-silicon/linux/pull/429),
  `90c0d00eb53799ed927526d90a4425ec07a9baa6`: preserve explicit non-coherent DMA
  on LoC-zero CPUs. Both loader templates additionally mark J614s DCP, PIODMA
  and scanout non-coherent. Revision 1 missed this dependency and is expected
  to fail the retained backend's coherency checks. The GPU node is unchanged.
* [#427](https://github.com/aurora-silicon/linux/pull/427),
  `bec833e0bc581f74744265f0613832e8291db0cc`: check the struct page for GPU
  page-table pages outside the reserved mappings instead of borrowing unchecked.
* [#433](https://github.com/aurora-silicon/linux/pull/433),
  `986ec63833586a1451575a4fb05b3d2b95679a53`: bounded recovery waits and revised
  cancellation propagation to help innocent GPU clients survive a recovery.
  This includes the upstream documented error-semantics change; it is not a
  claim that native GPU recovery has been tested on this J614s.

`upstream/` preserves the exact imported diffs and head/author metadata.
`prepare_upstream.py` checks all patches before applying them; `--verify`
checks their reverse applicability after a build. These are local integrations,
not changes to the upstream PR state. #428, #435/#436/#444 and draft #423 are not
included. Existing common thermal-governor dependencies are already enabled.

Revision 2 used kernel `7.3.0-m4rch-dcp002`. Its's ESP payloads live in
`AUDP001/r2/`; revision 1's payloads remain untouched. The default entry retains
its stable ID and points to revision 2. The top-level restore script still
restores the original pre-DCP working loader/GRUB pair, including if a refresh
stops between replacing its active files.

## What changed

* An explicit J614s/T6041 profile uses the physical 3024x1964 panel and 12096-byte
  boot stride. The visible boot framebuffer can exclude the notch. The bounded
  parser reads firmware-advertised timing/color IDs rather than substituting
  J713 IDs. Horizontal rates are 16.16 kHz; vertical rates are 16.16 Hz.
* Second-stage m1n1 preserves the boot display, validates the live firmware UUID,
  all eight firmware segment types and native SID23/SID0/SID16 table regions,
  verifies table protection before opening a retained translator, and publishes
  actual per-boot reservations. Saved physical addresses are never replayed.
* U-Boot transfers reservations into the Linux tree with fresh consumer and
  memory phandles. Display/DART/mailbox nodes stay disabled in its output.
  Only this kernel's early `m4rch.dcp=1` admission enables the complete graph.
* Retained DART support admits the T6041 apertures and preserves the actual TCR
  value, including firmware DAPF bypass. It does not reset inherited roots or
  hand firmware-owned tables to the generic mirror path.
* Display power stays in its boot state. The driver pins the existing PMP owner
  and checks its report readiness and native DISPINT entry. It sends no donor
  J713 power-state command. This is why display suspend is not enabled.
* The initramfs loads appledrm before Asahi and the desktop. The previous GPU
  experiment probes are replaced with passive display/driver/log collection.
  Runtime libraries, services and modules are temporary mounts/overrides.

The actual T604x firmware image UUID is
`6CC9349E-D30B-33FB-B12B-8D6D38F9F1B3`. Offline inspection corroborates RPC READY
identity `0x45bc9ef4`, A407 size `0x1bd8`, surface offset `0x588`, DVA offset
`0xe38` and nullable offset `0x1bcb`. This supports attempting the shared M4
backend; it does **not** establish complete wire compatibility or native
success. Strict UUID, protocol, packet-size and table checks remain active.
Revisions 1 and 2 retain the inherited display mode. Revision 3 attempts the
explicit mode-switch path described above. Native timing/scanout behavior
still needs testing.

## Inputs and rebuilding

The working source pins are Aurora Linux
`420a1c8f5492daeaa59ffba565aac610f5218d27`, integrated tree
`d6b171e95516b1683968d220800acee244c01869`, Aurora m1n1
`9f7cdfbd0623d96f21965434c3a7dda799ffcff4` and Aurora U-Boot
`7680260272f3612a13f0c9a6c7bfbc5e9ba7ce8c`. The enrolled Aurora first-stage image
is unchanged. The local native J614s/ANS/DAPF bridge and 16-core GPU adaptation
are retained. Prepared control-tree radio identity `apple,mriya` is retained and
copied with the live radio calibration into Linux. No Wallace source is added.

Build on the case-sensitive Linux filesystem in `m4rch-dcp-build`, not the macOS
bind mount. `/project` is this repo. Current work trees are `/work/linux` and
`/work/loader/{m1n1,uboot}`. Start from the native working sources/patches above;
preparation scripts intentionally reject unexpected or already patched anchors.

1. Apply `experiments/aurora-direct/prepare_gpu16.py` and `prepare_kernel.py` to
   the native Linux tree, then run `prepare_upstream.py` and `prepare_modes.py`. Merge `test.config`, set LOCALVERSION to
   `-m4rch-dcp003`, disable LOCALVERSION_AUTO and run olddefconfig. Build with
   `make LLVM=1 -j8 Image modules` (Clang/LLVM19, Rust1.85.1, bindgen0.71.1).
   Install stripped modules, remove the two speaker amplifier modules and run
   depmod for `7.3.0-m4rch-dcp003` before archiving.
2. Apply the saved native m1n1 J614s patch, then `prepare_loader.py`. Build with
   `make -j4 BUILDSTD=1 RELEASE=1 M1N1_VERSION_TAG=DCP001` and the artwork pin
   `80d14f8b6f485b310e305a84b4b806361518ddd1`.
3. Run `prepare_templates.py`; apply the native AUBS001 U-Boot patch/config,
   then `prepare_uboot.py` and build. Do not add a `pmp` alias: Linux has a direct
   PMP phandle and the native m1n1 control path must not assume a donor ADT path.
4. Unpack the retained working AURG016 initramfs into a fresh directory, then
   run `prepare_initramfs.py ROOT out/aurora-dcp`. Pack sorted `newc` CPIO with
   uid/gid 0 and deterministic gzip. Keep its original executable permissions.
5. Export the components/configs into `out/aurora-dcp`, run `package.py`, then
   `refresh.py` to inspect the revision-1-to-2 plan and `refresh.py --apply`
   to install it. `stage.py` is the original fresh-native-ESP staging path; do
   not rerun it over an existing candidate.

`out/aurora-dcp/manifest.json` records payload and source hashes; the exported
kernel/m1n1/U-Boot DCP patches accompany the separate preparation scripts.
`audit.py` and its firmware audit are read-only. Decoded Apple firmware remains
private under ignored `out/aurora-dcp/private/`, outside public source/bundles.
Existing `/boot/DCP001` research inputs are separate and are not overwritten.

## Validation and first boot

The kernel/modules, m1n1 and U-Boot compile. The actual ARM64 DMA setup
function passes a host regression with ASan/UBSan; the pre-PR429 source fails
the same test as expected. Seventeen host recovery/watchdog/deadline tests
pass using imported production logic. Serialized-template checks establish
explicit NC on all three display devices, retained SID assignments, disabled
boot admission and identical GPU-node properties. These are host tests, not
a native GPU recovery or kernel KUnit run. The real timing parser is tested
under ASan/UBSan with physical-panel catalogs, variable IDs, 60/120-Hz selection,
color selection, wrong units/porches/panel, virtual modes and every truncated
prefix. Cross-tree DCP tests verify remapped references and reject foreign
owners. Both supported and unsupported existing full board-handoff fixtures
pass under ASan/UBSan, including CPU release addresses, memory, calibration,
USB, speaker exclusion and malformed-input refusal. Build/package validation
checks the embedded DT, firmware admission, kernel/module identity, speaker
module exclusion and first-stage chainload window.

Boot the default **Aurora DCP internal panel + GPU (AUDP001 r4 handoff + multi-mode; speakers disabled)**
entry manually. Give the driver/desktop startup time to finish. A black screen
alone does not prove Linux froze: try Ctrl+Alt+F2 if needed. Select the existing
Experimental Aurora 16-core GPU entry in GRUB to return to the prior desktop.

Bounded live dmesg/journal capture starts before display-driver loading and is
flushed every few seconds into `/boot/AUDP001/return-*`; snapshots include the
live DT, startup log, DRM connectors/state and service status. A fuller passive
snapshot is scheduled after startup. It does not run modetest or extra GPU
workloads. For a later manual snapshot, run:

```sh
sudo sh /run/aurora-direct/collect.sh
```

To restore the exact pre-candidate loader and GRUB pair from macOS, mount the
ESP and run:

```sh
python3 /Volumes/M4RCHESP/AUDP001/restore.py
```

The restore script validates ESP identity and both current/backup hashes and
refuses to overwrite unrelated later changes. It never reboots. The older
bootstrap refresh/selector guards intentionally do not recognize this new GRUB
layout; restore first rather than bypassing their historical receipts. APFS
stub files, first-stage enrollment and previous Recovery rollback files are
not changed by candidate staging.

## R9: retained native display buffers

R8's native boot bound the DCP component and reached RTKit protocol 12. Its
first 16-KiB buffer request failed with `-ENOMEM`, followed by a power-ACK
timeout. The log did not print the request IOVA, so it cannot by itself identify
whether that particular buffer was host-allocated or firmware-provided.

The source review found a concrete integration mismatch: the retained SID23
provider reserves its entire aperture from ordinary DMA allocation, while the
imported desktop driver still called `dma_alloc_coherent()` on that device.
R9 connects RTKit buffers, AFK rings, IOMFB command memory and the legacy EPIC
fallback to the existing retained allocation API. Firmware descriptor requests
use the paired SID23/SID16 allocator and mapper, without a cached CPU alias.
Logical unmap/release does not free retained pages or remove their mappings.
Firmware-placed RTKit buffers receive the provider's writable-data validation;
native RTKit requests now log both IOVA and size.

`prepare_buffers.py`, `tests/buffers.py` and `package_buffers.py` reproduce the
change. Production callback tests run under ASan/UBSan; the original r8 host
allocation branch reproduces `-ENOMEM` with the reserved SID23 fixture. The
normal in-tree build preserves all 504 imported symbols and all module metadata
apart from its filename, including dependency metadata. The four upstream rate
tests pass using the previously pinned PR446 fixture corrections.

Only `appledrm.ko` changes inside the module archive. The kernel remains r7's
`7.3.0-m4rch-dcp006`, and the DCP005 loader remains unchanged. R9 uses
`/AUDP001/r9/initramfs.img`; staging makes it the default and archives the r5
test initramfs, retaining its shared kernel for the r6 fallback. Built-in speaker
amplifiers remain excluded. Native takeover still requires a manual boot test.

The disposable build container was absent after the reboot. Its environment
was reconstructed from the saved integrated source tree, exact PR445 pin and
local patches. The restored r8 DCP source and kernel config match the saved
copies exactly. The generated `Module.symvers` and a complete prepared-tree
archive are saved under ignored `out/aurora-dcp/` for future recovery. The newly
rebuilt kernel image is not staged; only the corrected display module is used.

## R10: merged J616s architecture

R10 supersedes the R5–R9 display integration. It builds the complete Aurora
Linux tree at `6dc07e43e394d73db0de16079d3eb9463207543c` (merged PR446) and
m1n1 at `1efafe1fe0ec134b89d55c2cc64106a66a4df2b7` (merged PR51). U-Boot
retains the native-tested Aurora pin `7680260272f3612a13f0c9a6c7bfbc5e9ba7ce8c`.

The DART driver is byte-identical to merged Aurora. J614s uses its ordinary
locked-DART mirror and DMA API, without the local J713 diversion, retained-DMA
wrappers or display-specific PMP guard. The common m1n1 publisher admits J614s
and publishes its live firmware UUID, named regions and standard
`apple,t6041-handoff` marker. The native U-Boot bridge transfers names, region
types and remapped consumer phandles, including the framebuffer and unmapped
OS log. Both templates explicitly use J614s's `apple,mriya` radio identity.

The local display changes are the early node admission, component match,
six physical register windows sharing five firmware registers, and initial
3024×1964 non-VRR 60 Hz selection. The native-qualified GPU16 adaptation and
PR427/429/433 patches remain. The working Mesa, UCM and runtime commands are
preserved. Speaker nodes are disabled and TAS2764/TAS2770 modules are excluded;
upstream Macaudio Kconfig still selects those codecs for compilation.

The new preparation entry point is `prepare_j616.py`, with `kernel`, `m1n1`,
`templates`, `uboot` and `fixtures` components. Start from clean pinned trees;
apply the native `aurora-loader/prepare.py` adaptations before its loader
components. Do not apply the older DCP `prepare_kernel.py`, `prepare_desktop.py`,
`prepare_shared.py` or `prepare_buffers.py` to this source tree. m1n1 uses
Clang 19 with BUILDSTD and the AUDP010 version tag; Linux uses `LLVM=-19`.
`audit_j616.py` exports and checks the actual built source. `package_j616.py`
assembles the matching kernel, modules, runtime and loader.

Artifacts and receipts are in `out/aurora-dcp/j616-r10/`. `stage_j616.py --apply`
installs `/AUDP001/r10/{vmlinuz,initramfs.img}`, replaces `boot.bin`, and selects
`m4rch-aurora-dcp001` as the GRUB default. R9 remains a GPU/framebuffer fallback
under the new shared loader: its older display gate does not admit the new
marker. Its previous loader is backed up at
`/AUDP001/r10/previous.candidate.boot.bin`. The obsolete r6 initramfs and its
otherwise unreferenced r5 kernel are archived locally before retirement.
Original rollback backups and working boot entries remain intact.

Validation: complete kernel/modules and loaders built; 248 matching modules;
63/63 upstream display fixtures, plane-layout control and 8/8 M4 error-path
fixtures passed. The extended resource fixture covers the native shared
aperture. The production cross-tree bridge passes ASan/UBSan with both final
templates; the installed GRUB menu passes its syntax checker. The enrolled
stage1 is unchanged and the packed stage2 fits its existing window.

Native boot/takeover is still untested. Display suspend remains inhibited,
external display processors remain disabled, and upstream VRR stays disabled.
The initial target is native internal-panel takeover at 60 Hz; firmware-listed
fixed higher-refresh modes remain unqualified. The agent never reboots.
