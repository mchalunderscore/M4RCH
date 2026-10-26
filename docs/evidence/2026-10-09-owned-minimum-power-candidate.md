# Minimum-active-state integrated draw candidate — 2026-10-09

Prepared and built, not run. The previous first-NOP diagnostic left target and completion memory unchanged; the user confirms desktop/input/USB/networking remain normal. Main asc_graph_init retains its backing and GFX power. A fresh normal Linux reboot is required for this candidate. Do not force unload or warm INIT. Kernel and boot default are unchanged.

## Evidence and hypothesis

Matched private host binary SHA256 3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e, Apple25G83 AGX353.14. Native initPowerAndPerformanceData atfffffe00089a862c fills hardware+fc4 with its state cap, and hardware+fc8 onward with frequencies converted from Hz to MHz using multiply0x431bde83, shift50. Relevant stores:89a8a84/89a8aa4/89a8ac4. Matched firmware2f518 copies this array; c660/c678 consult the cap, and zero bypasses the state-selection path. Our preceding fixture had both cap and frequency array zero. This is a plausible execution blocker, not a proven cause.

Native initFirmwareData atfffffe00089cd104 also sets hardware constants: ed0=24000 (cd150), ee0=1 (cd5a4), ee4/ee8=1/1 (cd164), f04=31 (cd16c), and enabled core count2570 (cd7c8). The candidate fills those same fields and count16 for this 16-core topology. No direct MMIO overrides.

The candidate selects only the first active ADT frequency group, 338 MHz in both clusters, with existing matching core/SRAM voltage rows. Cap1 and frequency entries0/338 restrict the experiment to the lowest active group. This is experimental policy rather than reconstruction of Apple's entire power constructor. Secondary profile stays disabled; remaining zero fields, higher-state mapping and complete power tuning remain unqualified. The accelerator virtual method atslotf68 is getSamplePeriodAICClocks; power-object timing fields must not be called performance limits.

## Candidate and capture

Eight32-bit hardware words change, affecting exactly10 graph bytes. Native-entry-signal backing is identical: native first-NOP dependency1 restored, shared context, timestamp1 TA/3D commands, authored shaders, target, fragment hold254 and its release retained. This is an integrated draw attempt.

New read-only live observations collect unbanked21048/50/58/60 and startup211c0, plus target page20/completion page47 byte-change counts at1s,5s,15s and before-stop. No bank selector writes while firmware runs. Post-quiesce bank snapshots cannot establish execution history; live counts address that gap. A changed byte alone is not GPU completion or valid triangle proof. Preserve fault reports, queue cursors, firmware DATA, output and event/stamp evidence together.

Matching7.1.13-m4rch-gpu-contract LLVM/W=1 build passed. Trial module SHA2560142d8e64535a75fcc7637416cadc5f51edba5fb0bbb6d05df120beeadd35fb4. Graph SHA2563ac49db564e2dbef1d711294d98f6b43613228e49cbc12d68af7a36e61426b88. Artifact/source hashes, all graph object hashes, exact graph change, unchanged backing, MHz conversion and analyzer live-log decoding passed offline checks.

After reboot, run from the repository:

```sh
sudo -n python experiments/t6040-gpu/run-root-envelope.py out/owned-minimum-power/live-candidate --graph --run
```

Then use analyze-owned-work.py with the prepared/graph candidate and the new boot capture path. Inspect live-output/progress, faults, post-return memory and firmware records before deriving another correction. Target remains zero/unverified until hardware execution and image layout are established.

Sources: experiments/t6040-gpu/prepare-owned-minimum-power.py; asc-graph-init/asc-graph-init.c; analyze-owned-work.py. Artifacts: out/owned-minimum-power/prepared/graph and live-candidate. Private implementation-derived research, not clean-room; exclude private binary/full firmware TEXT/disassembly from return exports. Full build and change receipts are in the companion JSON.
