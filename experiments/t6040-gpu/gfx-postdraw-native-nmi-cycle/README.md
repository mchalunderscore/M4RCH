# Gravity startup prefix, traced draw and retained timeout fallback

This distinct v17 experimental candidate combines three source-derived Gravity
pre-ASC writes with the preserved traced TA/3D draw and a retained native NMI
fallback after a clean power-state ACK timeout. Normal T6040/G16S driver boot
is still closed in the selected Gravity tree; this tests its narrow startup prefix.

After paired coordinate ON, before the first ASC START, the owner reserves the
16K pages at 0x289000000 and 0x288d04000. It samples the actual GPU ID at
SGX+0xd04000 and all three inherited operands. It sets bit 0 by fresh RMW at
SGX+0x1000104/+0x1000108, then writes the source Gravity Fender policy 6 at
SGX+0xd06030. It records each before/requested/after value and verifies readback.
A failure retains the owner and PM; no compensating write or retry follows.

The unchanged native PID/subpriority recipe, trace 3 through control33, one
TA/3D publication and 15-second observation preserve execution diagnosis.
The host saves and seals full owned/object/image/completion/journal/DATA/PT
captures before one token-bound `postdraw-native-cycle` command.

A normally acknowledged native202 request uses the previous strict CPU-stop
path. Only a clean timeout after this candidate's own request may attempt the
matched native firmware-side NMI once: EP0 0x00f0000000000000, ASC+0x1004=0x10,
then ASC+0x1014=1. The new owner reserves/maps ASC's 0x2000 register extent.
It preserves raw EP1 frames without responding or inventing a crash-buffer ABI,
services qualified EP32 doorbells, and requires bounded drain plus fresh native
STATUS48 low-bit idle and empty RX before CPU-stop writes.

Apple's native host wrapper takes a fatal crash policy here. The experiment
executes only its firmware-side signal, with all backing retained. NMI does
not count as a management ACK. Other errors, unknown frames, absent ownership,
invalid reads or missing idle seal the attempt before CPU stop/OFF.

Checked CPU stop, paired OFF/one PMput, independent physical OFF and reference
accounting are all mandatory. Only qualified OFF admits one separate paired
ON/PMget and cold HELLO/map/BOOT7 management rejoin. All 174 pages, maps,
context and module remain pinned. No app/root/work replay, DMA retirement,
backing release, owner unload, arbitrary ACK/state-bit clear or second cycle
is admitted. This is a fresh-boot candidate; boot 5e12 is consumed.

The C checks exercise the actual helper and timeout branches. Host checks join
independently emitted C fixtures and test immutable capture-before-command
ordering. They do not establish hardware register behavior, rendering or restart.
Root alone executes hardware after finalization and a fresh user boot.
