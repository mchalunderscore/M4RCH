# Native PWRGATE admission-drain live startup review — 2026-10-09

Fresh boot `16868560-efd7-4c98-b58d-45cb88280d46` loaded the finalized
`de75ef4b…` owner and published the same 69-page graph. Native ON wrote full
REQ `0→0x2000` and verified all three PMC votes. STATUS0 selected the reviewed
native ACK bypass; this is not an ACK or an inactivity observation. The saved
post-active owner record retains its module, resources and sole PM reference.

Initial recovery failed again: completed 0 of requested 2, counter 1/phase 2,
host-stop 1, request-state 0/request-flag 1 and control 32/32/32. The distinct
`gfx-native-powergate-drain-session` marker and exact retained-session marker
consistently admit only `sample`, `gfx-snapshot` and one `gfx-powergate`.
No old-family or unknown-startup marker qualifies this startup. The baseline
snapshot completed without capture errors: physical word `0x1f0003ff` has BUSY 0,
ASC START is set (`CTRL44=0x10`, `STATUS48=0x4e`) and PM is held 1/usage 1/active/error 0.

Cold and baseline raw snapshots contain all 174 pages, unchanged 56-page render
backing and unchanged 35-page job pool. All 12 work cursor triplets remain zero;
control cursors are 32/32/32 and mapping head/tail 0/35. Target bytes remain
all 0xa5, completion backing is zero and all four hardware completion pages
are unchanged. The validated receive journal stays at 50,410 records, status 0
and doorbells 0. No work was submitted or rendered.

Root separately saved the loaded GNU note and refcount 1 at uptime 138.89,
after completed cold startup and before the terminal intent. The saved note
matches the ELF note read from this compiled owner, whose whole-file hash
matches the finalized receipt. This is a separate saved observation, not an
atomic startup observation. This reviewer made no hardware or sysfs reads.
The saved numeric refcount is used for the pure startup-parser replay.
`resident_session_active=true` in the baseline report is a retained lifetime
flag; `resident_session_usable=false` and diagnostic=true describe failed
recovery. Historical `cold-load-intent` is not live process status.

This review covers completed cold startup and the first typed snapshot only.
Separate reads are non-atomic; trace/statistics activity is not GPU completion.
Later admission draining, PWRGATE, CPU stop and OFF require their own evidence.
Retirement and repeatable restart remain unproved.
[Bound raw inputs and observations](2026-10-09-gfx-native-powergate-drain-live-startup-review.json).
