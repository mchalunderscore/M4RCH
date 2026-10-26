# Retained native PWRGATE candidate

This distinct no-work profile adds one native EP0 PWRGATE202 request before
checked CPU stop and paired PMP/PMC OFF. It continues from boot `94cb4163`, where
native ON/OFF coordination and the normal PM put succeeded but physical BUSY11
remained set and retained firmware-owned DRAM continued changing. The current
STATUS0 owner remains pinned and admits only its existing read-only diagnostics.
This kit must never be loaded over that owner.

The native request is exactly `0x0060000000000202`. A fresh RX-empty admission
and sole request bound the following type 7 ACK with low8 equal 1 or 2, as selected
by the matched RTBuddy handler. Either ACK value denotes native host IOP
status 2; no SLEEP201 or INIT220 request is emitted. Before CPU writes, require
native `(STATUS48&3)!=0`, then fresh CTRL44 clear 0x10 and fresh CTRL44 clear 0x20
with verified readbacks. Only that checked stop can invoke the existing paired
OFF/sole PM put. ACK is a protocol observation, not writer-cessation proof.

The compiled dispatcher permits only `sample`, `gfx-snapshot` and
`gfx-powergate`. The first powergate intent seals other operations before any
hardware access and is consumed on refusal. Unknown/late ACK, pending/invalid
RX, receive failure, nonidle status or failed CPU control leaves PM/backing
retained. Following an OFF attempt, diagnostics retain the existing prohibition
on ASC/SGX/mailbox/PMP/PMC access. No independent STOP/OFF, reset, START,
INIT, application control, work publication, unmapping, freeing or unload is
admitted. Unknown post-ON startup failure admits no commands at all.

Cold startup retains the existing two initial recovery requests for comparison.
Terminal admission accepts known diagnostic phase 2 after 0/1 completed cycles,
or healthy phase 0 after 2, with their consumed controls, request/counter fields,
clean journal, one active PM reference and START set. All 69 graph pages and 174
owned pages, their context/mappings and the consumer/module lifetime remain
retained. The saved optional CTRL40 idle gate is absent; native mapper-inactive
and firmware-unmap effects remain outside this candidate's qualified scope.

`prepare-powergate-owner.py` reads the frozen native STATUS0 prepared owner,
checks every source pin and writes a new destination. It changes only Makefile,
startup/fallback logging and retention in `asc-graph-init.c`, the exclusive
dispatcher in `recovery-cycle.h`, OFF command-result naming and harmless unused
annotation in `gfx-reset-scope.h`; it adds `gfx-native-powergate.h`. It neither
builds nor loads a module. Selected output is
`out/gfx-native-powergate/prepared-owner-v5`; earlier source/qualification/build
drafts are preserved as historical artifacts.

`test-powergate-owner.py` compiles the actual new header and the actual
transformed startup fallback branches with AddressSanitizer and
UndefinedBehaviorSanitizer. The selected 55-case receipt is
`out/gfx-native-powergate/owner-qualification-final-v5.json`. It binds the header,
preparer, qualification script, prepared source receipt and the exact matched
native ranges in `out/gfx-native-powergate/native-ranges.json`. Provider/receive
helpers are mocked here; existing frozen helper qualifications remain required.

Root's selected candidate is `out/gfx-native-powergate/candidate`, built W=1
against the installed `7.1.13-m4rch-gpu-native-reset` kernel without warnings or
errors. Its owner SHA is
`7bced3badf35f4e99ade95428622e26e3259fbc37c16de13eb0d845e9b6745bc`.
At this checkpoint it has never been loaded, and wrapper qualification/final
receipt are pending. Finalization and a fresh checked boot must precede any
hardware invocation. Kernel/USB providers, the other seven helper modules,
prepared graph/backing and boot default remain unchanged.

Portable reduced evidence is in
`docs/evidence/2026-10-09-gfx-native-powergate-c-qualification.{md,json}`.
No private native binaries or full disassembly are included. No live PWRGATE
ACK, physical OFF, firmware/DMA cessation, reset/restart, resource retirement,
triangle completion or rendered pixels have been verified by this kit.
