# J614s headset jack module trial

The running kernel probes the CS42L84, but the headphone card waits for AOP
DAI 4. Its AOP audio node lists `dma`, `cout` and `cin`, while the current
driver registers the combined jack/speaker component only if `spkr` is also
listed. Adding `spkr` to the board tree would be inappropriate: internal
speaker protection on J614s remains unqualified.

This candidate uses Erik Bourget's upstream registration change,
[Aurora Linux commit acdfd796](https://github.com/aurora-silicon/linux/commit/acdfd796a37d9ebcc3b7c50c42d6a4131f6a4a1c),
from open [PR 437](https://github.com/aurora-silicon/linux/pull/437). The
patch here contains the two files changed by that commit, retained from the
repository's earlier `bce491f` PR-437 snapshot. It applies to the booted
kernel source with a line offset only. It registers the jack when both `cout`
and `cin` exist, and the speaker component only when `spkr` exists. The PR
reports playback, plug detection and capture on J713; the PR discussion notes
that broader shared-code regression boots and a separate loader dependency
remain outstanding. J713 results do not establish J614s behavior.

The installed J616 Jack ALSA UCM profile is already present. This is a
J614s-specific trial of the upstream common driver; no speaker DMA, amp,
speaker card or volume interlock is enabled.

## Build and recovery

The baseline is the saved source and config for installed `linux-m4rch`
`7.3.0-27`, kernel `7.3.0-m4rch-touchid`. A copy was patched under
`cache/jack-trial/linux-src`; the installed source tree and module were not
modified. The Rust bindings generated for this build differ from the saved
baseline only in the corrected local-version string. The upstream patch was
compiled with the installed toolchain. Single-module modpost initially failed
because it did not include module exports; rerunning modpost against the
baseline `Module.symvers` passed. Its generated module metadata matched the
baseline exactly, and the final module was linked with the kernel build's
recorded linker command. The resulting module has identical undefined-symbol
names, dependencies and vermagic to the installed original.

The historical candidate package placed the module under `updates/` and
pinned the exact kernel package version. A live unload/reload was avoided:
the existing microphone attach path treats an already-attached firmware
service as an error, so a reload can lose the working microphone until reboot.

On 31 October, `linux-m4rch-jack-trial 7.3.0-1` was installed on the SD
trial boot. `pacman -Qk` reported no missing files, `modprobe --show-depends`
selected the `updates/` module with `mic_check_123=1`, and both the candidate
and original module matched their recorded SHA-256 hashes. The running AOP
module was not replaced at installation; the hardware trial followed a reboot.
The tested module was subsequently incorporated into `linux-m4rch 7.3.0-28`
at its normal package-managed module path, and the temporary override package
was removed. `modprobe --show-depends` selects the packaged module. The
refreshed package booted on boot ID `c7c08627-2c0d-4806-bf4b-3933df129d1b`;
the jack ALSA card registered, and PipeWire reported the disconnected ports
unavailable. Playback and capture were previously tested with the identical
module; they were not repeated after promotion. The preceding packages and boot
files are retained in `cache/jack-promotion/recovery/`; see
`docs/recovery.md` for restoration.

Before playing audio, check card registration and connector state. Start at a
low headset volume, then test left/right playback and headset microphone if
present. Check logs for AOP, DMA, DART and codec errors; verify the internal
microphone and confirm speaker modules and sound card remain disabled.
Existing SD trial and boot recovery instructions remain in
`docs/j614s-sd-reader.md` and `docs/recovery.md`.

## Hardware trial — 31 October 2026

On boot `676536be-46a6-470e-8bfe-add186c9b14a`, the AOP microphone card and
the `MacBook Pro J616 Jack` card both registered. The headset ports reported
available. PipeWire initially retained the jack card's `off` profile; selecting
its existing `HiFi` profile exposed headphone playback and headset capture,
and made the headphone output the default. At 25% PipeWire sink volume the
owner confirmed a quiet left-only tone followed by a right-only tone in the
correct ears. The owner also reported clear playback of a five-second
headset-microphone recording. Its mono 16-bit capture peak was 118/32768
(approximately -49 dBFS), so capture gain and realistic speech levels still
need qualification despite the audible result. The recording was removed.

The inspected kernel log contained no AOP, ADMAC or DART errors from these
tests. No TAS amplifier module was loaded, the speaker bypass parameter stayed
zero, and no speaker card appeared. On unplug, PipeWire marked both headset
ports unavailable and switched the card off; on reconnect, both ports became
available, the HiFi profile returned and the headphone sink became the default.
Repeated boots, suspend/resume, internal-microphone capture after the change,
and prolonged use remain untested. The module in the installed kernel package
is byte-identical to the one used in this trial.
