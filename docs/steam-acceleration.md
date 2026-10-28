# Steam acceleration on T6040

> Historical trial commands and diagnostic paths in this record may have been retired.
> See the [documentation index](README.md) for preserved source archives and
> the current setup; do not treat trial boot paths as current recovery instructions.

The 26 October 2026 package update fixes the initial Asahi native-context
OpenGL hang in muvm. The normal `/usr/bin/steam` launcher still selects
Zink/Honeykrisp GPU acceleration through FEX and muvm.

## Cause and change

Aurora Mesa queries `DRM_ASAHI_PARAM_GROUP_QUEUE_LIMITS` while creating a
Honeykrisp physical device. It sent `DRM_IOCTL_ASAHI_GET_PARAMS` through
`IOCTL_SIMPLE`. Stock virglrenderer 1.3.0 rejects that ioctl (`0x40186440`)
with EINVAL; the guest waits for a response that never arrives. A private
instrumented build identified this exact command behind the earlier generic
`CmdSubmit3d -> ComponentError(-22)` trace.

GET_PARAMS contains a userspace pointer, so adding it to the flat ioctl
allow-list would not be correct. The paired patches use its dedicated virtual
command instead. Queue limits return a bounded output payload. VM status
includes a bounded input payload with the VM id, and returns the sticky
kernel error. The host replaces the guest pointer with response storage.
Unsupported groups and malformed lengths are rejected before the kernel call.
Wire version 3 advertises this extension; the guest refuses extended queries
on older backends. VM status mirror registration is skipped under virtio,
where its GEM handle would need translation; the transported status query
remains active after fence waits.

The kernel, firmware and boot configuration were not changed.

## Package updates

- `mesa-m4rch 1:26.3.0.r20261026.f2c9dc3-2`: transport dispatch and VM status
  fixes, applied by `packages/mesa-m4rch/virtio-params.patch`.
- `virglrenderer-m4rch 1.3.0-3`: pinned virglrenderer 1.3.0 source, the pinned
  Aurora UAPI header, and the paired bounded parameter handlers. Replaces
  stock `virglrenderer` and provides its library ABI.
- `fex-rootfs-debian-m4rch 20261026-4`: patched amd64 and i386 Vulkan drivers.
  Its build-info marker identifies the transport revision. EROFS uses
  explicit 4096-byte blocks, including when built on a 16 KiB-page host.
- `muvm-m4rch` recipe revision 3 adds the paired backend dependency; its
  program code is unchanged.

The full Debian Mesa build helper applies the same patch to both architectures
before building. The rootfs builder requires its transport marker, and the
package rejects a missing marker or a non-4-KiB EROFS image.

The locally installed rootfs candidate updates only the two Vulkan libraries
in the existing image. These were cross-built with native shader-generation
tools and X11 Vulkan support. Original Aurora GLX/EGL libraries, Debian
packages and device-selection layers are retained. The full build helper
continues to build the complete X11/Wayland stack for subsequent rebuilds.

Local package archives and checksums: `out/steam-updates/`. Sources, build and
installation logs, clean image staging and probes: `out/steam-investigation/`.
Pre-update graphics files, versions and rootfs are retained in its
`installed-before/` directory. These local output directories are git-ignored.

## Validation and limits

- Both actual ELF64 x86-64 and ELF32 i386 glxinfo binaries report
  `Accelerated: yes`, Apple M4 Pro (G16S B1), Zink/Honeykrisp and OpenGL 4.6.
- The clean 4 KiB EROFS candidate mounts in muvm and passes both probes using
  the installed native graphics packages.
- An x86-64 glxgears run completed 532 frames in five seconds; the user also
  confirmed the window drew normally. This is a rendering smoke test, not a
  performance benchmark or proof of game compatibility.
- The CPU-only diagnostic path reached a user-confirmed Steam login. It used
  private Debian GLX/GBM/EGL libraries and is not the normal launcher path.
- `packages/tools/test-virtio-params.py MESA_SOURCE VIRGL_SOURCE` compiles the
  real patched handlers with a mock kernel. It verifies queue limits, sticky
  VM-error round trips, older-host rejection, payload bounds and guest-pointer
  isolation without GPU access. `make check` validates helper syntax.

A power-button forced shutdown occurred during the investigation. The user
reported a desktop freeze coinciding with a Firefox keyboard shortcut. The
previous kernel journal records a host Asahi submission rejected with EINVAL
at 14:51:32 UTC, but does not establish whether the desktop or a diagnostic
triggered it. Later x86 drawing and initialization probes completed without
new kernel entries. System stability and games remain separate acceptance
checks; Garry's Mod is the selected first game.

Use explicit x86 probe binaries: this rootfs does not ship glxinfo. Running
`FEXBash -c 'glxinfo -B'` can fall back to the native ARM executable and must
not be treated as an x86 test. Pre-reboot scratch logs were lost from `/tmp`;
subsequent sources and evidence are kept in the persistent workspace.

## Subsequent accelerated Steam black screen

The installed packages launched normal `/usr/bin/steam` successfully and showed
Garry's Mod's install dialog. App 4000 began downloading. At 15:17:59 UTC,
the desktop went black and VT switching did not restore a console. The
kernel recorded:

```
asahi 28a600000.gpu: [File 3 Queue 1]: IOCTL: submit failed! (submission ID: 867937 err: EINVAL)
```

The live DRM client table and `/proc/728/fdinfo` identify Asahi DRM client 3
as `kwin_wayland`, PID 728. This is the compositor's submission, not a direct
identification of a Steam guest command. The event correlates with Steam
window activity; the exact triggering command and the validation reason are
not captured by the current kernel log. EINVAL is a rejected submission, not
a CPU illegal-instruction exception or proof of a shader instruction fault.

Steam's VM was stopped. The display remained black and KWin did not answer
D-Bus. Thread stacks, KWin maps, DRM client fdinfo mappings, DRM state, kernel
logs, installed versions and boot id were saved before recovery in
`out/steam-investigation/black-screen-capture/` (78 files). KWin's main thread
was in a futex wait. A normal reboot was authorized by the user after capture.
No GPU reset register, kernel module or boot setting was changed.

Acceleration initialization and the drawing smoke tests pass; full desktop
stability and Garry's Mod execution do not yet pass. After reboot, investigate
the kernel's native submit validation for the compositor client and add bounded
failure diagnostics before repeating the failing window workload. The pinned
kernel integration source is `aurora-silicon/linux` commit
`9cbdd0734d9e186c5f5f5949a21b909d10c2571b`, plus the installed
`/usr/share/doc/linux-m4rch/kernel.patch`. Capture the command type/offset,
length, feature flags and the specific EINVAL branch, rather than inferring a
shader fault from the generic submit error. Preserve normal compositor and
multi-client ownership invariants when fixing it.

## Upstream review after the black screen (26 October 2026)

Aurora's default `integration/aurora` kernel remains at `9cbdd0734d9e` and
Mesa `aurora-wip` remains at `f2c9dc3fb59c`; both equal our source pins.
Development branches are ahead: `wip/j616s-gpu-parity-20261026` has 88 commits
and `wip/m4pro-mesa-tip-20261026` has 276. They are not interchangeable with
our 16-core J614s setup: the kernel series explicitly qualifies the 20-core
J616s calibration handoff, and Mesa PR 80 is draft with GPU gates pending.

Relevant findings:

- [Mesa PR 76](https://github.com/aurora-silicon/mesa/pull/76), explicit virtio
  BO unbinding before VA reuse, is merged and already present in our pin.
  It fixed EINVAL/mmap failures in CS2 on M4 Pro under FEX/muvm.
- [Mesa PR 60](https://github.com/aurora-silicon/mesa/pull/60), diagnostic logs
  for unbounded CPU fence fallbacks, is also already present. The new failure
  has no captured message identifying one of those fallbacks.
- [Kernel PR 460](https://github.com/aurora-silicon/linux/pull/460) pre-sizes
  the tiler buffer to avoid 25G83 firmware growth hangs and reports unblocking
  CS2 map loads under FEX/muvm. It is draft and not in our pin. This is a
  relevant future game-load issue, not an established fix for the immediate
  KWin EINVAL submission.
- [Mesa PR 80](https://github.com/aurora-silicon/mesa/pull/80) consolidates
  M4 Pro support, priority fallback and bounded compression. Its extensive
  CPU tests do not claim completed M4 Pro GPU qualification. Do not treat its
  276-commit branch as a tested black-screen fix.
- [Kernel PR 423](https://github.com/aurora-silicon/linux/pull/423), shared G17
  admission/completion/recovery improvements, is already an ancestor of our
  kernel pin. Its existence does not establish another missing update.
- muvm's latest checked release is 0.7.0; libkrun's latest is
  [1.19.7](https://github.com/libkrun/libkrun/releases/tag/v1.19.7), both
  installed. Libkrun main targets a different API; it is not a drop-in update.
- Official virglrenderer tags end at 1.3.0. Its Asahi backend history still
  reports the original native-context implementation; the dedicated Aurora
  queue-limit/VM-status extension is not supplied by a newer checked release.

The branch comparisons and commit lists are retained under
`out/steam-investigation/upstream-review/`. No upstream pin was changed during
this review. No verified ready-made upstream fix for the KWin rejection was
identified; capture the failing validation branch before selecting a fix.


## Garry’s Mod gameplay and installed follow-up packages

The owner confirmed a visible gm_construct map and working movement via Steam,
FEX and muvm with GPU rendering. The successful one-shot launch used
`-windowed -width 1280 -height 720 -nosound -nochromium -condebug -noaddons
-noworkshop +map gm_construct`. No permanent game launch options were changed.
The normal launch had remained on the blue Loading screen. Actual
Scout-on-Soldier loader checks resolve the client, Chromium, audio and shader
libraries; the earlier fallback shader-library probes do not establish a
missing runtime dependency. Chromium/menu startup remains unresolved.

muvm silently skips its PulseAudio socket proxy when socat is absent. socat was
missing on this installation; adding it and starting the proxy let ALSA default
and pulse device-open probes succeed in the actual Steam runtime. Audible game
sound remains untested. muvm release 4 now depends on socat, and rootfs release 6
adds a PulseAudio ALSA default. Existing VMs keep their mounted rootfs until the
next VM restart.

Installed on 26 October: Mesa release 3, virglrenderer 1.3.0-3, muvm 0.7.0-4,
rootfs 20261026-6 and Steam launcher 1.0.0.81-4. Archives and checksums are in
`out/steam-updates/`. The launcher quotes the complete Steam command into one
muvm argument so reserved muvm flags such as -h cannot consume game options.
Its round-trip test covers empty arguments, quotes, newlines and shell syntax.

Mesa release 3 captures the first rejected native EINVAL command stream per
process, bounded to 1 MiB, without changing the ioctl return or errno. Files
are private (0600) under `$XDG_STATE_HOME` or `$HOME/.local/state`, named
`asahi-submit-PID-fdN-qN.bin`. Decode using
`python3 packages/tools/read-submit-capture.py PATH`. A fresh desktop session
is needed for KWin to use the installed diagnostic library. No desktop or game
restart was performed during the final package installation because the owner
was using the machine for other work. The Alt+Tab/Win+T freeze is unresolved.

Validation passed: launcher argument round-trip, paired parameter handlers,
submission capture bounds/errno/permissions, `make check`, and package file
presence checks. These checks do not establish normal menu or audio playback.

## Chromium startup investigation

The installed Linux x86-64 libcef reports CEF 80.0.4 (commit 2143), Chromium
80.0.3987.122. This was confirmed both from cef_version_info's constant table
and by loading the real library in Scout-on-Soldier under FEX. dlopen succeeds.
This differs from the CEF 86 version in the current Facepunch wiki.

A direct menu test with Chromium enabled reproduced the Loading screen.
The game log records repeated FEXServer socket connection failures (abstract
socket refused; /run/user/1000/1000.FEXServer.Socket absent). Its Chromium
child was a zombie and PID 1 in its own PID namespace (NSpid 2645 1), whereas
the named FEX socket exists in the outer guest. chromium.log remained empty.
The immediate failure is therefore an emulated subprocess failing to reach its
FEX service during isolated startup; this does not prove the exact namespace
or sandbox operation responsible yet.

Facepunch's [HTML wrapper source](https://github.com/Facepunch/gmod-html/blob/master/html_chromium/ChromiumSystem.cpp)
sets no_sandbox=false and command_line_args_disabled=true and supplies its own
argv. Adding --no-sandbox as a game option cannot reliably reach CEF. Diagnostic
scripts and a temporary initialization interposer are under
out/steam-investigation; no installed game binary has been replaced.
The [upstream patch tool](https://github.com/solsticegamestudios/GModPatchTool)
provides a newer CEF and integration wrapper; it has not been installed or
validated on this setup. A standalone utility subprocess diagnostic lacked
Chromium's IPC descriptors/resource arguments, so its broker/resource errors
are not evidence of missing installed game assets.

A scoped cef_initialize interposer confirmed settings.size=432 and
no_sandbox=0. Repeating with only no_sandbox=1 removed the immediate FEX socket
failure/namespace-child pattern, but cef_initialize did not return and no menu
loaded. This is not a sufficient workaround and was not installed. The hook
was injected for the single test through FEX_ENV, preserving normal executable
identity. The earlier explicit-loader attempt required an absolute -game path
and is not used as evidence of normal game behavior. Native backtraces only
show FEX host/JIT frames and do not identify the stalled guest CEF function.
The test instance was terminated after capturing logs. No persistent sandbox
setting, launch option, game file or graphics package was changed in this
investigation. A controlled test of the newer CEF plus its matching HTML
wrapper is the next step; old CEF's exact internal wait remains unidentified.

## General correctness causes isolated (26 October)

Native syscall tracing replaced the earlier sandbox speculation. Chromium calls
clone(CLONE_NEWUSER|CLONE_NEWPID|CLONE_NEWNET|SIGCHLD), then execveat on its
zygote binary. The new FEX instance tries its abstract socket (ECONNREFUSED) and
/run/user/1000/1000.FEXServer.Socket (ENOENT). pressure-vessel has a private
runtime directory, so that named socket is already absent before Chromium's
clone; no additional Chromium chroot is needed to cause this failure.

A small x86 program reproduces it without Chromium or graphics: unshare user
and network namespaces, map the original UID/GID, then exec itself. It succeeds
in the outer muvm guest but fails inside Scout-on-Soldier. Exposing the existing
FEX socket through PRESSURE_VESSEL_FILESYSTEMS_RW makes the same test succeed
inside the runtime with network isolation retained. Sources:
`packages/tools/fex-namespace-exec-probe.c`; passing capture:
`out/steam-investigation/namespace-exec-with-socket.log`.

Steam package 1.0.0.81-5 now adds a guest bootstrap which includes the live FEX
socket in pressure-vessel's filesystem bindings, preserving existing entries
and explicit FEX_SERVERSOCKETPATH. It adds no CEF switches and changes no game
binaries. The launcher/bootstrap tests pass, including duplicate/absent sockets.
This fixes service visibility for other isolated x86 subprocesses as well.
Already-running Steam needs a fresh client environment before normal launches
inherit it; the direct diagnostic runtime tests set it explicitly.

With this corrected, unmodified Chromium starts its subprocesses and logs a
second fatal error: madv_free_discardable_memory_posix.cc line 31, ENOMEM.
The exact Chromium 80 source shows this line checks a plain anonymous writable
mmap, not a failed MADV_FREE call. Native trace of renderer PID 4396 records
RLIMIT_DATA lowered from infinity to 16 GiB, followed by a failed 4096-byte
anonymous mmap. FEX source registers prlimit_64 and x86-64 setrlimit as direct
host syscall passthroughs in LinuxSyscalls/Syscalls/Passthrough.cpp; guest data
limits consequently apply to emulator memory as well.

`packages/tools/fex-data-limit-probe.c` isolates the semantic mismatch: set a
64 MiB soft RLIMIT_DATA, mmap 4096 writable anonymous bytes, restore the limit.
The native ARM64 build passes; x86-64 under FEX fails with ENOMEM in the same
muvm guest. Results: `out/steam-investigation/data-limit-comparison.log`.
The trace files `cef-memory-syscalls.*` preserve the actual CEF sequence.
A correct emulator fix must account for guest memory separately from emulator
memory while preserving resource-limit enforcement and query semantics. No
ignore-RLIMIT patch or permanent sandbox bypass has been added. The game menu
remains blocked on this second issue. The previous no-sandbox test did not
isolate it sufficiently to justify a fix and is superseded by these traces.

## FEX accounting candidate and confirmed Chromium menu

The owner confirmed "menu now shows just fine" with the original CEF binaries
and sandboxing enabled after installing the accounting candidate and fixing its
internal descriptor relocation. No GModPatchTool, CEF replacement or persistent
no-sandbox option was used. Audio was disabled for this menu diagnostic.

The repo now carries `packages/fex-emu-m4rch/guest-data-limit.patch`, applied by
its PKGBUILD and checksummed by prepare.py. Guest private writable mappings are
charged independently of FEX's runtime allocations, with Linux's shared/stack
exclusions and zero-soft-limit compatibility rule retained. The recipe builds
from the same upstream pin; no broad FEX version upgrade was needed.

The native ARM64 baseline and x86-64/i386 regressions cover allocation refusal,
mapping/protection/remap/unmap changes, brk, error cases, concurrent allocations,
remote prlimit, descriptor reshuffling and fork/exec inheritance. Fork snapshots
and partial-mprotect accounting were subsequently tightened. Clean package
builds and logs are retained in out/steam-investigation/package-build/fex-clean
and fex-clean-package.log. Menu confirmation was on revision 3; revision 5 adds
those standalone-tested hardening changes.

This specifically virtualizes RLIMIT_DATA. Modified limits cannot yet be handed
to a native ARM64 helper transparently: such execs are rejected, retaining
rather than dropping enforcement. Privileged hard-limit raises are also not
implemented. Read the [package notes](../packages/fex-emu-m4rch/README.md) for
validation scope and compatibility boundaries before treating the candidate as
an upstream-ready general resource-limit implementation.

Final installed artifact: `fex-emu-m4rch 2610-5`, rebuilt from clean pinned
sources, installed and tested through `/usr/bin/FEX` in muvm. All nine regression
groups passed on native ARM64, x86-64 and i386; both emulated architectures also
passed the explicit native-handoff rejection test with limits retained. Package
file checks reported zero missing files. Archive and checksum:
`out/steam-updates/fex-emu-m4rch-2610-5-aarch64.pkg.tar.zst` and `SHA256SUMS`.
The already-working game was left running during final installation.

## Idle Steam VM memory (27 October)

With Steam open and no game tracked, the host Steam service charged about
6.36 GiB, including about 4.44 GiB anonymous and 1.87 GiB file-backed memory;
these cgroup numbers include both unreclaimable and reclaimable allocations.
The host VM process had about 4.49 GiB PSS. Guest process PSS totals were about
2.51 GiB, including nine Steam web helpers totalling 2.04 GiB and two Steam
processes totalling 0.39 GiB. The largest web helper alone had 0.89 GiB PSS,
mostly anonymous. These are FEX processes and do not separate Steam's own
allocations from emulator overhead. Guest free reported 2.5 GiB used and
1.2 GiB buffer/cache, with 15 GiB available and no guest swap. The configured
VM maximum is demand allocated, not a reservation of the full 80% of host RAM.

A one-time guest-only `drop_caches` test reduced guest cache from 1.15 GiB to
0.40 GiB; afterward the host service charge decreased approximately 0.45 GiB
and the VM process PSS by about 0.40 GiB. This is a rough before/after, not a
controlled attribution of every page. Guest cache will refill; no cache policy
was changed. Host memory PSI was zero and the Steam VM had essentially no swap.
There is no evidence yet that a web-helper leak or any specific browser view is
responsible; Steam UI, FEX and VM overhead have not been separated further.

Guest diagnostics require `muvm -i` with a terminal-backed stdin: with a
regular/non-pollable stdin the client fails `epoll_ctl` with EPERM, even though
the guest server accepted the request. The earlier EPERM was not evidence that
the guest refused diagnostic commands.

### FEX lookup-cache comparison

FEX 2610 defaults to `DisableL2Cache=true` and `DynamicL1Cache=true`; the running
Steam processes had no environment override. One fresh test VM ran Steam with
`FEX_DISABLEL2CACHE=0` and `FEX_DYNAMICL1CACHE=0`, verified in the web-helper
environment. After about a minute, guest process PSS totalled 3,442 MiB,
including nine web helpers at 2,816 MiB and two Steam processes at 492 MiB.
The host VM PSS was 4,899 MiB. Steam was shut down cleanly and started again
through the normal launcher with no cache overrides; at a similar elapsed time,
guest PSS totalled 2,751 MiB, nine web helpers 2,281 MiB, and two Steam
processes 372 MiB. Host VM PSS was 4,139 MiB. Thus the default settings saved
about 691 MiB guest PSS and 760 MiB host VM PSS in this single startup trial.
These measures overlap; do not add them. The runs are not identical controlled
workloads, so values are approximate and not a game performance measurement.
The temporary test VM was stopped and the default Steam session restored. No
persistent configuration was changed.

### Shinri loading and exit, 27 October

The Windows GMod/Proton 11 launch connected to the server at 16:19:30; at
16:24 the host had approximately 0.5 GiB available, 8.5 GiB in zram swap and
recent measurable memory pressure. Guest PSS at that point included GMod
2,091 MiB, Steam web helpers 1,952 MiB, Chromium renderer processes 608 MiB,
Steam 401 MiB and xalia 286 MiB. The guest reported no PSI memory stalls or
swap. Its unusually high dynamically adjusted watermark made MemAvailable
unreliable as an indication that it had run out of allocatable memory; do not
assume a guest OOM from that number. Host pressure is real, but does not prove
the cause of the slow load or the subsequent crash.

Steam removed the game at 16:25:59. `console-linux.txt` records XIO and Wine
client errors during shutdown, but they do not establish the initiating fault.
The only guest minidumps found were older, empty assertion files; no useful
crash dump was recovered. The Steam launcher reporting exit code zero is not
the GMod process's verified exit status. No kernel OOM or Asahi GPU fault was
found in the host log during the event. After exit, the VM still had 5.86 GiB
host PSS and 4.26 GiB SwapPSS, while host zram held approximately 8.6 GiB of
logical pages compressed into about 3.0 GiB of RAM. These measurements overlap;
swapped data is not entirely resident in addition to the compressed storage.
A useful next reproduction needs Proton/Wine diagnostics plus time-correlated
CPU, host PSI and swap activity, to distinguish FEX execution cost from host
reclaim and game/server issues. Do not infer a crash cause from the preload
warnings or the X connection error alone.

### Prepared capture for the next Shinri attempt

On 27 October Steam was stopped cleanly and the existing GMod record had no
launch options. A copy of its local configuration was saved in the private
capture directory, and the game-specific launch option was set to enable
`PROTON_LOG=1` with `PROTON_LOG_DIR` and `PROTON_CRASH_REPORT_DIR` pointing to
`out/shinri-diagnostics/20261027-setup/`. Steam was restarted and the option
remained present. Proton logging and crash reports can contain account names,
paths, and other diagnostic details; review before sharing. The log and crash
output cannot be confirmed until the next Proton launch.

`m4rch-shinri-monitor.service` runs `packages/tools/shinri-monitor.py` every
10 seconds for up to two hours, collecting timestamped host memory, PSI,
swap activity and VM counters plus guest process PSS, CPU ticks, memory and
PSI. It stops 60 seconds after a detected `gmod.exe` exits, and copies Steam
logs and the host kernel journal for the capture period. The VM command uses
a pollable stdin and has been verified against the running guest. Stop early
with `systemctl --user stop m4rch-shinri-monitor.service`; read `finished.txt`
and `samples.jsonl` from the private capture directory. The launch option is
persistent until removed in GMod Properties; remove only the added logging
text after diagnosis rather than restoring an old whole Steam config.

### Live font-handle investigation

The 16:32 Proton 11 run emits `err:font:alloc_font_handle out of realized font
handles` in Wine process 012c, identified by its load log as `gmod.exe`.
Valve's `proton_11.0` Wine source has `MAX_FONT_HANDLES` 5000. The prior Wine
upstream change to support up to 5000 realized handles is therefore not an
obvious missing fix. The exact source revision corresponding to the installed
binary has not independently been verified. A third-party Proton fork raises
that bound further, but doing so would be a diagnostic workaround, not proof
that the handle growth is legitimate or bounded.

The first observed Wine `0xe24c4a02` exception in the GMod main thread occurs
at log timestamp 98.127; the first font-handle exhaustion appears at 302.327.
The exception repeats thousands of times, unwinding through the loaded
`lua_shared.dll`; the log shows handling, not an unhandled crash. This is
consistent with repeated Lua error handling but does not reveal the Lua error
text, source or cause, and predates the font failure. `PROTON_LOG=1` enables
verbose exception/unwind tracing in the installed Proton and the log exceeded
145 MiB while the game was still running; that diagnostic can itself add
substantial overhead.

The downloaded Shinri content is a GMA stored as `.bsp`; its script
`lua/includes/cl_precache.lua` is heavily obfuscated. The separate cached
content-loader Lua is LZMA-compressed and creates four fonts in its download
failure UI, but its existence does not establish that path executed or caused
the 5000 handles. The obfuscated script was extracted as data for inspection,
not executed. No game or Proton binary was replaced. A focused follow-up needs
the actual Lua error/stack or a verified counter of font create/release events;
the current evidence is not enough to justify a permanent limit increase.

At 16:44:56 the host journal recorded the libkrun VM receiving SIGABRT with
`SI_USER`; systemd then reported SIGKILL at 16:45:01. A host core dump exists.
No kernel OOM kill was identified; the sender and cause were not established.
The capture monitor was stopped and completed its final snapshots. The exact
temporary Proton launch option was removed while Steam was no longer running;
the other game settings were preserved. This disables verbose logging on the
next launch. The monitor now avoids requesting a guest command when no VM is
observed, since `muvm` can otherwise start a new VM.

After the VM exit the host had about 9 GiB available, but Plasma Shell had
again accumulated approximately 1.47 GiB of unevictable cgroup memory. A
shell-only restart reduced its charge to 0.23 GiB and raised host available
memory to about 10 GiB; Konway was restored. This reclaims memory temporarily,
not a proven fix for repeated accumulation or menu lag. A fresh game run
without `PROTON_LOG` is necessary to assess the logging and memory effects.

## ARM64 Steam and Proton (27 October)

Valve's ARM64 Steam client runs in muvm's 4 KiB guest, without translating the client through Linux-user FEX. Steam Linux Runtime 4 ARM64 (4185400) and Proton 11.0 ARM64 (4628740) are installed in the existing Steam library. Proton still uses its own FEX-based translation for x86 Windows game code. A missing `lsof` caused Steam WebUI transport error 0x3008; the launcher supplies a locally unpacked, checksum-verified ARM64 `lsof`, GTK 2 and IBus support libraries. The package `steam-m4rch` 1.0.0.81-9 launches the ARM64 client and retains the former client as `steam-x86`.

With no game running, two one-at-a-time 8 GiB muvm samples on the same desktop and account showed total guest process PSS of 1,294,760 KiB for ARM64 Steam and 2,747,486 KiB for x86 Steam/FEX, a roughly 1.39 GiB difference. The views, cache history, and exact time after startup were not identical; host VM PSS and guest PSS overlap and must not be added. Details and sample files are in `out/steam-arm64-experiment/`.

GMod's original Windows CEF failed to load its menu under both 32- and 64-bit builds with ARM64 Proton 11 and Experimental. Disabling FEX multiblock did not help. The prior Linux-user FEX socket and RLIMIT_DATA fixes are not automatically present in Proton's separate Windows/ARM64EC FEX path, and surviving Windows processes showed an unlimited Linux data limit; the short-lived subprocesses were not captured. A checksum-verified upstream GModPatchTool CEF 137 update applied to an isolated game copy produced a working menu, confirmed by the owner. Its 152 changed files were verified with upstream BLAKE3 hashes and migrated to the existing game; the original files and previous x86 Proton prefix are in the private `out/steam-arm64-experiment/recovery-before-arm64/`. The restore script `out/steam-arm64-experiment/restore-original.py` checks hashes before restoring the original files, GMod tool selection and x86 prefix. Quit Steam before running it and then use `steam-x86`; Steam game updates or verification can overwrite the CEF patch.

The user-confirmed menu also worked after migration. During a subsequent Shinri load the host experienced heavy swapping, less than 1 GiB available, and approximately 7.6 GiB GPU/driver resident memory. A Steam client reduction alone has not solved the game's memory pressure. Proton's full diagnostic logging remains disabled.

References: https://github.com/ValveSoftware/Proton/blob/proton_11.0/toolmanifest_arm64.vdf ; https://github.com/UbuntuAsahi/steam-arm64 ; https://github.com/aurora-silicon/aurora-steam-native/pull/8 ; https://github.com/solsticegamestudios/GModPatchTool ; https://github.com/Facepunch/garrysmod-issues/issues/6921
