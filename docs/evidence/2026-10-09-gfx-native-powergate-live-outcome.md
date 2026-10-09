# Native PWRGATE trial: refusal before management publication

Fresh boot `d841b8bf-bf1f-4499-9508-caf275909695` ran the prepared native PWRGATE
owner once. A boot-time USB PD `0-0a` initialization failure preceded GPU activity;
one normal targeted reprobe restored that unbound controller. The saved preflight
then verified the unchanged native-reset kernel, loaded USB identity, all three
PD bindings and USB role providers, and all ten artifact/eighteen source pins.

The cold trial returned zero, published the joined root and retained all 174
pages. Native ON verified the full PMP request and three PMC votes, using the
STATUS0 bypass branch. Initial application recovery again completed zero of two
cycles and remained in phase2/counter1 with control cursors32/32/32. The explicit
diagnostic-ready marker qualified one terminal PWRGATE operation, with no work.

The sole `gfx-powergate` intent returned `-EBUSY` **before sending the management
request**. The logged control value was0x10. All request, ACK, removed-frame,
CPU-clear, CPU-stop and delegated-OFF counters stayed zero. The earlier backing,
receive-journal, PM-accounting, idle-work, recovery-phase and control-cursor gates
passed; the remaining refusal reads were ASC STATUS48 all-ones, RX114 all-ones,
RX EMPTY clear, or TX110 bit16 set. The exact offending operand was not logged.
This result does not test whether the native PWRGATE handshake permits teardown.

No CPU write, paired OFF or PM put occurred. A later admitted typed diagnostic
still showed START0x10, STATUS0x4e, PM held1/usage1/active/error0, and physical word
0x1f0003ff/BUSY0. These later valid reads cannot identify the earlier refusal
branch. Qualified retained power+0x652c advanced4119→14722 across88.356453s;
the journal remained50,410 records. Separate captures are not globally atomic
and do not identify every writer or prove cessation.

The host and kernel intent are consumed. All174 pages, root/mappings, consumer,
exclusive claims and module remain pinned; the sole PM reference remains held.
Only typed `sample` and `gfx-snapshot` are admitted. Another request, CPU stop,
OFF, restart, publication, unload or backing release is not permitted. No triangle
was submitted. A saved read-only loaded GNU note matches the owner, with refcount1.

The next distinct candidate adds exact transport-admission diagnostics and a
bounded drain of only qualified pending application notifications before requiring
fresh RX-empty/TX-available admission. Any stale management frame, invalid record,
crash, overflow or failed bound must refuse before the single202 publication.
That hypothesis addresses a possible transport backlog; it does not assert the
cause of this observed refusal. The frozen trial sources and captures remain
unchanged. No additional current-boot control is authorized by the new preparation.

The [bound outcome JSON](2026-10-09-gfx-native-powergate-live-outcome.json) pins the
cold session, baseline, terminal operation, later diagnostic, USB recovery and
loaded identity. Physical OFF, repeatable recovery/restart, joined DMA retirement,
pixels and the accelerated desktop remain unverified. The full goal remains active.
