# KWin device loss investigation

> Historical trial commands and diagnostic paths in this record may have been retired.
> See the [documentation index](README.md) for preserved source archives and
> the current setup; do not treat trial boot paths as current recovery instructions.

On 26 October 2026 at 22:01:12 GMT, the previous boot's journal recorded
`kwin_wayland` PID 736 submitting work to Asahi file 3, queue 1. The kernel
returned `EINVAL` for submission 1329664. Mesa then reported
`vkQueueSubmit failed (VK_ERROR_DEVICE_LOST)` and KWin reported a lost graphics
context and a failed swapchain allocation. This establishes a compositor device
loss following a rejected submission; it does not establish a hardware fault,
the window action that triggered this particular submission, or why the kernel
rejected it. The user reports that snapping windows and Alt+Tab trigger the
failure. An earlier black-screen incident also identified KWin's Asahi client.

The installed Mesa diagnostic captured the failed command stream in the private
file `~/.local/state/asahi-submit-736-fd29-q1.bin` (mode 0600). Its payload
SHA-256 is `746283b464373a77a4422933d41cf2699d8afb501c07cc1c7ac6add759366853`.
Decode it with `python3 packages/tools/read-submit-capture.py PATH`. It has
12 render commands and two compute commands, with intervening attachment
records, one input sync and four output syncs. Ten render passes have a
4096×2048 framebuffer; the final render pass is 3232×1900. The batch is below
the kernel's 64 hardware-command limit, its relative barrier indices do not
exceed the preceding command counts, and the inspected render dimensions,
sample counts, tile sizes and tile buffer sizes satisfy the static checks in
the saved G17 command source. Those observations do not validate VM mappings,
sync objects, historical dependencies, or the rest of each command.

The saved stream contains command bytes but not the VM mapping state or sync
array. The kernel logs only the overall error, so offline packet inspection
cannot identify the failing validation branch. The next diagnostic step is to
instrument the installed kernel's submit path with bounded, rate-limited
failure-stage and command-offset reporting, including checks for validation,
ordering, destination resolution and enqueue, without exposing GPU addresses
or weakening validation. Compare the actual installed source and patch first.
A new kernel build and reboot would be needed to collect this information.
Reproducing either trigger can freeze the session; arrange a recovery path and
save work first. No settings, driver, kernel or desktop session were changed in
this investigation.

## Diagnostic boot prepared

The pinned source and installed kernel patch were rebuilt as
`7.3.0-m4rch-diag` with the stage-reporting patch in
`patches/diagnostics/asahi-submit-stage.patch`. The host's Rust 1.99.1 and
Clang 23.1.4 were used; the existing kernel was built with Rust 1.85.1 and
Clang 19.1.7. In particular, the newer compiler disables the kernel's BTI
option through Kconfig. This is a separate, temporary diagnostic build and
has not yet been boot-tested.

The separate diagnostic image, initramfs and module tree were installed, and
GRUB's default was changed to the diagnostic entry at the user's request.
The original kernel, initramfs and boot entry remain present. A copy of the
previous GRUB configuration is `/boot/grub/grub.cfg.before-m4rch-diag`.
Because GRUB input is unavailable and there is no verified automatic fallback,
a failure to boot the diagnostic kernel may require external recovery.

The initramfs file list matches the current initramfs after normalizing the
kernel release name. The generated GRUB configuration passed
`grub-script-check`; installed image and module hashes match the build outputs.
The running kernel was not changed and no reproduction has been attempted.

After reboot, check `uname -r` for `7.3.0-m4rch-diag`, then reproduce one
trigger. After a freeze and restart, collect the diagnostic and associated
kernel messages with:

```sh
journalctl -k -b -1 --no-pager | grep -E 'asahi submit diagnostic|submit failed|GPU.*(fault|timeout|reset)'
```

If the desktop remains responsive after the trigger, use `-b` instead of
`-b -1`. The diagnostic identifies the submission ID, stage, and byte offset;
`enqueue-index` instead reports a zero-based hardware-command index. At most
32 diagnostic records are emitted per module load. A failure reported as
`validate-fields-or-range` can still refer either to a command field or to its
address being outside the allowed range; the actual GPU addresses are not
logged.

## Reproduction on the diagnostic kernel

On the next diagnostic boot, the user reproduced a KDE freeze. At 22:20:53
GMT the kernel reported submission 25948, `stage=validate-mapping`, render
command byte offset 56, `EINVAL`. The matching KWin capture is
`~/.local/state/asahi-submit-732-fd29-q1.bin`, payload SHA-256
`cda4bec902e521df2bdf6089d570b3efbf646d01d883d323419855fd31b91710`.
The optimistic pass over the command succeeded, while the subsequent checked
pass failed; this narrows the issue to the checked address-coverage path, but
does not distinguish missing mappings, permissions, VM lock/walker failures or
concurrent changes. The render has two fragment attachments and depth and
stencil surfaces; the saved command stream alone does not identify the failed
resource.

A more detailed diagnostic Asahi module was compiled and installed for the
next boot, with the prior stage-only module saved as
`out/kwin-diagnostic/asahi-stage-diagnostic.ko`. The running module is unchanged.
Its failure-only log gives the range-check ordinal, requested size, access
(1 read, 2 write, 3 read/write) and caller line in `g17/command.rs`. It does
not print GPU addresses. This module has the same kernel release and external
symbol requirements as the installed stage-only module; compilation and
installation do not establish hardware behavior. After another reboot and one
controlled reproduction, look for `asahi mapping diagnostic` alongside
`asahi submit diagnostic` and `submit failed`. The first failure is still
captured by Mesa under `~/.local/state/`.

## Second reproduction: fragment attachment

On 26 October at 22:29:38 GMT, the previous boot logged submission 14824,
`stage=validate-mapping`, command offset 8328. The detailed log reported
check 13, 3,801,088 bytes, write access, caller line 81. In the diagnostic
source, line 81 validates an attachment. The immediately preceding command
sets two fragment attachments; its first entry has exactly the logged size,
while the second is 4,849,664 bytes. The failed range is therefore the first
fragment attachment. Its start and size are 16 KiB aligned. The corresponding
capture is `~/.local/state/asahi-submit-735-fd29-q1.bin`, payload SHA-256
`20013350e60973627205bd0c7b931922c9342bfaa179e43455237249c35459b0`.

The kernel could not establish writable coverage for the entire range. Its
coverage function returns false for an unmapped page, a page lacking write
permission, an out-of-range page, a page-table walk error, or a VM lock error.
The log does not distinguish these cases or show whether Mesa described the
range correctly. Mesa constructs fragment attachment entries using the image
plane address and its full layout size; this is a lead for comparing the image
layout and binding against the kernel's mapping and permissions, not proof of a
fault in either component. The submission's rejection led to Zink reporting
`VK_ERROR_DEVICE_LOST` and KWin losing its graphics context. No corrective
change was made based solely on this evidence.

## Page-level follow-up prepared

Review of the current Mesa source found that ordinary image BOs are bound
read/write unless flagged read-only, and freshly imported BOs are explicitly
bound read/write. Image-plane binding also checks that the full plane fits in
its memory object. These source paths describe intended behavior; they do not
prove the failed image's actual runtime binding or rule out mapping lifetime,
permission, page-table walking, or synchronization problems.

The next-boot diagnostic module reports `asahi page diagnostic` on a failed
checked range: expected and visited page counts, invalid leaf count, pages
denied the requested access, and the first bad relative page index. Missing
intermediate tables appear as fewer visited than expected. An inspection error
is reported separately. The inspection reacquires the VM lock after the
original failure, so a changing mapping can yield different results; a fully
valid follow-up inspection does not invalidate the original failure. It does
not expose GPU addresses or change acceptance decisions. Its pre-update module
is saved at `out/kwin-diagnostic/asahi-range-diagnostic.ko`.

The module compiled against the same diagnostic kernel and retained the same
external symbol requirements. `tests/test-asahi-coverage-diagnostic.py`
exercised the actual inspection routine with a simulated page-table walker,
covering full, missing, invalid, non-writable and masked-address cases. No
hardware verification or corrective fix has yet been established. Reboot and
reproduce once more to obtain the page classification; search the previous
kernel journal for `asahi page diagnostic` after recovering the session.

## Third reproduction: missing leaves

At 22:46:20 GMT submission 18769 failed while checking a 3,801,088-byte
fragment attachment. All 232 pages were visited and all had invalid leaf
entries; no page was rejected for write permission. The page-table inspection
reacquired the VM lock after the failed check, so it is a follow-up snapshot.
This supports a missing mapping but does not identify who removed it. In two
older complete captures of the same-sized failure, the color range follows the
valid depth attachment's allocation by one 16 KiB guard page. This is a lead,
not proof that the guard or depth mapping caused the loss.

The Mesa command-stream capture could not create its file on this reproduction:
the PID and filename were reused from an older boot, and `O_EXCL` preserved the
old file. No new stream was saved; the existing file must not be mistaken for
this event. Mesa package release 4 fixes the collision by trying bounded unique
suffixes while preserving `O_EXCL`, permissions and original error behavior.
The actual capture functions passed a collision regression test; the package
was built and installed without restarting the desktop. A new session is needed
to load the updated library.

A new diagnostic module is staged for the next boot. Alongside page counts it
reports `logical`: 0 means no overlapping logical GPUVA, 1 means partial overlap,
2 means one GPUVA covers the whole range, and values 3 and 4 mean partial or
full coverage respectively with that GPUVA marked invalidated. This is a
second snapshot under the VM lock, not a history or a change to validation.
The module compiled and the existing coverage-classification tests passed; the
previous module is saved at `out/kwin-diagnostic/asahi-page-diagnostic.ko`.
The distinction can show whether to investigate BO lifetime/unbinding or
restoration of a retained logical mapping. No underlying GPU fix is established.

## Fourth reproduction: no logical GPUVA

The previous boot on 26 October logged submission 21941 at 23:15:09 GMT.
The 232 pages of the 3,801,088-byte fragment attachment were invalid and the
follow-up VM snapshot found `logical=0`: no overlapping logical GPUVA. Thus
this observation does not fit a retained GPUVA merely marked invalidated for
restoration. The inspection reacquired the lock, so it is still possible that
mapping state changed between the failure and inspection. The new Mesa capture
worked: `~/.local/state/asahi-submit-740-fd29-q1-0.bin`, payload SHA-256
`be3a204d38744269e1744f8ee2c628506b3dbf6cc0b303e07683bc1297642919`.
The same two attachment sizes appear in this capture.

The Mesa image-binding source checks plane bounds and uses a read/write BO
mapping, but the snapshot does not establish whether the BO was subsequently
freed, explicitly unbound, replaced or was never bound. A read-only bounded
mapping-operation history has therefore been staged in the diagnostic module
for the next boot. It retains at most 128 recent VM operations in kernel
memory, and emits only the most recent overlapping operation's kind, age and
whether its range exactly matches; it never emits stored GPU addresses. Kind
1 is a successful map, 2 is an unmap using a device context, 3 an unmap
without one, 4/5 are remap holes with/without a device context, and 6 is a
whole GPUVA removal. These are callback-context classifications, not definitive
process or ownership attribution: delayed cleanup and VA reuse can complicate
interpretation, and an older event can fall out of the history. Recording and
inspection do not relax validation. The previous module is preserved at
`out/kwin-diagnostic/asahi-logical-diagnostic.ko`.

The module compiled with the diagnostic kernel's release and unchanged
external symbol set. Tests exercised the history's empty, overlap, boundary,
wrap and eviction behavior, and the existing page-inspection tests passed.
The running driver is unchanged. A new boot and one reproduction are needed
to collect history. No underlying fix has yet been established.

## Fifth reproduction: short history inconclusive

On 27 October at 06:44:45 GMT, submission 18892 again failed on the
3,801,088-byte fragment attachment: all 232 leaves were invalid, no logical
GPUVA overlapped, and no matching event was found in the preceding bounded
128-event history (`event=0`). The lack of an event does not mean no operation
occurred: it may have been overwritten, or its path may not be instrumented.
The preserved capture `~/.local/state/asahi-submit-750-fd29-q1-0.bin` has
payload SHA-256
`6bc95ff1be7b74d154ebcb073e6210009835efaad0c083f11bcfaa0e2b804836`.

A longer-history diagnostic module is staged for the next boot. It retains
4,096 events in a virtually allocated per-VM buffer and reports the total
number of events, so an empty match can be interpreted alongside whether the
history wrapped. The recorded addresses remain private in kernel memory, the
reported categories have the same limitations described above, and the
acceptance check remains unchanged. The short-history module is retained at
`out/kwin-diagnostic/asahi-short-history-diagnostic.ko`. The longer-history
module compiled with matching release and external symbols; tests exercised
the actual history helpers at the new capacity and the page-inspection tests
passed. Hardware behavior and the underlying fix remain unverified.

## Sixth reproduction and restart-free testing

On 27 October at 07:46:08 GMT, submission 26928 failed on an unmapped
4,980,736-byte fragment attachment. The diagnostic found an exact-range
unmap event 136 recorded operations earlier, classified as an unmap without
a device context (`event=3`). This callback context includes cleanup paths;
address reuse and deferred cleanup mean it does not prove which object owned
the old mapping. The 4,096-event history had wrapped (`total=17410`), but the
matching event was still retained. Capture:
`~/.local/state/asahi-submit-754-fd29-q1-0.bin`, payload SHA-256
`6bc95ff1be7b74d154ebcb073e6210009835efaad0c083f11bcfaa0e2b804836`.

An experimental Mesa patch, `packages/mesa-m4rch/attachment-lifetime.patch`,
holds a reference to a bound image BO for the image lifetime and retains BOs
represented by native render attachment snapshots until command-buffer reset.
The goal is to avoid losing backing for a recorded stream. This is a candidate,
not a confirmed root-cause fix: the trace does not prove the removed mapping
belonged to the same image when the stream was recorded. Longer retention may
also increase memory pressure. The candidate was built as package release 5
but has not been installed. The running desktop still uses release 4.

Testing without restarting the desktop:

- CPU-only tests exercise the actual image bind and attachment snapshot logic
  with simulated BO ownership, plus the actual command-buffer retention set's
  deduplication, growth, release and allocation-failure paths.
- A separate offscreen process loaded the candidate ICD, performed three small
  GPU render-and-readback iterations and verified their pixels. It produced no
  kernel submission error. This is a basic rendering check, not a reproduction.
- A separate virtual KWin process on its own session bus loaded the candidate
  ICD through Zink. It opened two test windows and completed 20 sequences of
  left tile, right tile and the window-switch shortcut. Its scripting log
  confirmed two windows and geometry changes; it still answered D-Bus after
  the test. The installed release 4 also passed the same isolated sequence,
  both with default settings and with a copy of the user's KWin settings
  including Karousel and the geometry-change effect. There was no submission
  error in the kernel log. Therefore this test does not yet reproduce the
  original freeze and cannot demonstrate that the candidate fixes it. The
  D-Bus shortcut invocation is not a physical Alt-key hold and the virtual
  desktop is not identical to the user's running session.

The local repeatable probe is `out/kwin-diagnostic/nested-probe.sh`; it is run
under a private `dbus-run-session`. Its default ICD is the private candidate;
set `M4RCH_TEST_ICD=/usr/share/vulkan/icd.d/asahi_icd.aarch64.json` for the
installed baseline. Both tests still share the physical GPU, so isolation does
not guarantee protection from a device-wide GPU or firmware fault. The current
KDE session was neither restarted nor changed during these tests.

## Candidate test on the main desktop

After installing Mesa package release 5 and rebooting into the diagnostic kernel,
KWin froze during repeated Alt+Tab at 08:23:43 GMT on 27 October. The live
journal confirms KWin PID 759 received EINVAL on submission 14142, at render
command offset 56: the 4,980,736-byte writable attachment had 304 invalid
pages and no logical mapping. An exact-range unmap without a device context was
recorded 23 operations earlier; address reuse still prevents identifying the
same object conclusively. Zink reported VK_ERROR_DEVICE_LOST. The rejected
stream was captured at `~/.local/state/asahi-submit-759-fd29-q1-0.bin`, with
payload SHA-256 `ffa3a0149247952af3c2e986067b92dc5fc19e5b5ff1c71b2bee50d8c70b5d6d`.
The candidate therefore did not fix this reproduction; it does not rule out
other lifetime paths or a different underlying cause.

## Unmap source diagnostic

Review of the active G17 VM lifetime code found a candidate race worth checking:
GEM handle close can defer object-wide mapping cleanup while jobs are active,
while subsequent mapping admission does not explicitly exclude reimporting that
same object. If a newer mapping is attached to the same GEM object before the
queued object cleanup drains, object-wide cleanup may remove it. This is a code
path hypothesis, not a demonstrated explanation of the captured failure; the
prior `event=3` also covers ordinary batched unmaps and deferred range cleanup.

A diagnostic-only module, built and installed for the next boot, classifies
whole-node unmaps as event 7 for handle-close object cleanup, event 8 for
ordinary batched VM_BIND unmaps, and event 9 for deferred range cleanup. Other
paths retain their old codes. The source change is
`patches/diagnostics/asahi-unmap-source.patch` and layers on the existing
mapping diagnostics. The module has the same vermagic and undefined symbol set
as its predecessor. Existing mapping-history and page-coverage tests passed;
the new classifications have not yet been exercised on hardware. The prior
module is saved at `out/kwin-diagnostic/asahi-before-unmap-source-diagnostic.ko`.
No mappings or validation rules are changed by this diagnostic.

## Handle-close cleanup identified

After reboot, the 27 October 08:37:25 GMT reproduction failed in KWin submission
18275 on the same 4,980,736-byte writable attachment: 304 invalid pages and no
logical mapping. The most recent overlapping history event was an exact-range
handle-close cleanup (`event=7`), 135 operations earlier. This identifies the
unmap path, but not whether this was the same allocation that KWin later
submitted: VA reuse and deferred cleanup remain possible.

For the next boot, a further diagnostic-only module tags a successful batched
map when the same GEM object is waiting in the deferred object-cleanup list
(event 10). If an exact-range handle-close cleanup subsequently unmaps that
mapping before another overlapping trace event, it records event 11 instead of
7. Event 11 would establish that ordering for the tracked range, not by itself
prove how or why userspace imported the object. An ordinary event 7 or a
missing event is inconclusive: the capture is bounded, other paths may exist,
and cleanup may already have been moved from the pending list. Source change:
`patches/diagnostics/asahi-rebind-race.patch`, layered on the prior diagnostic.
The module compiled with matching vermagic and undefined symbols, and the
existing mapping history and page-inspection tests passed. The added detection
has not been exercised on hardware and does not alter mapping or validation.
The previous module is saved as
`out/kwin-diagnostic/asahi-unmap-source-diagnostic.ko`.

## Rebind-before-cleanup observed

At 08:43:38 GMT on 27 October the new trace reported event 11, exact=true,
for the 4,980,736-byte unmapped attachment in failed KWin submission 29922.
For this traced path, the same GEM object had been mapped while its handle-close
cleanup was queued, and the later cleanup removed that exact newer mapping;
there was no intervening overlapping trace event. The submission then failed
with EINVAL and KWin reported VK_ERROR_DEVICE_LOST. The trace is an ordering
observation and does not identify the originating application import call.
The failure capture is `~/.local/state/asahi-submit-756-fd29-q1-0.bin` with
payload SHA-256 `c33cb6a5f9cb3466fcfde657d29ffab0f99eff281e3082fa653c4351d2fc7e9a`.

## Candidate deferred-close fix

A candidate module is installed for the next boot. A successful rebind removes
the same GEM object from the pending close-cleanup list while holding the GPUVM
reservation; its retained reference is released only after that reservation is
released. If cleanup has begun draining, new mapping commits wait until it
finishes. A drain waits for commits admitted earlier before taking its cleanup
list. This preserves the new mapping in the observed ordering. Superseded old
mappings are retained until a later handle close or VM teardown, so the change
may increase memory retention. It does not establish correctness for every
possible close/reimport interleaving and requires hardware validation.

Patch: `patches/diagnostics/asahi-deferred-close-rebind-fix.patch` (applied on
top of the earlier diagnostic patches). The module compiled with matching
vermagic and identical undefined symbols. `tests/test-asahi-pending-close.py`
exercises the actual cancellation helper for object identity, reference
retention, missing objects and absent lifetime state. Existing mapping-history
and page-coverage tests pass. These checks do not exercise actual kernel
concurrency or the GPU. The prior diagnostic-only module is retained as
`out/kwin-diagnostic/asahi-confirmed-race-diagnostic.ko`.
