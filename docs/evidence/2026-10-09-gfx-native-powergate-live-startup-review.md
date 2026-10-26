# Native PWRGATE live startup review — 2026-10-09

Fresh boot `d841b8bf-bf1f-4499-9508-caf275909695` loaded the finalized
`7bced3ba…` owner and published the same 69-page graph. Native ON wrote full
REQ `0→0x2000` and verified all three PMC votes. STATUS0 selected the reviewed
native ACK bypass; this is not an ACK or an inactivity observation. The saved
post-active owner record retains its module, resources and PM reference.

Initial recovery failed again: completed0 of requested2, counter1/phase2,
host-stop1, request-state0/request-flag1 and control32/32/32. The exact new
ready and retained-session markers consistently admit only `sample`,
`gfx-snapshot` and one `gfx-powergate`. The baseline typed snapshot completed
without capture errors: physical word `0x1f0003ff` has BUSY0, ASC START is set
(`CTRL44=0x10`, `STATUS48=0x4e`), and PM is held1/usage1/active/error0.

Both cold and baseline raw snapshots contain all174 pages, unchanged56-page
render backing and unchanged35-page job pool. All12 work cursor triplets remain
zero; control cursors are32/32/32 and mapping head/tail0/35. Target bytes remain
all0xa5, completion backing is zero and all four hardware-completion pages are
unchanged. The validated receive journal stays50410 records, status0 and
doorbells0. No work was submitted or rendered.

The cold wrapper enforces the loaded GNU note match and positive module
refcount before qualifying startup. These raw note bytes and the numeric count
are not saved by this capture; the independent review relies on the pinned
successful wrapper path for that gate and uses minimum-positive1 for its pure
startup-parser replay. No current hardware or sysfs read was made by this
reviewer. Root separately saved a later, post-terminal loaded GNU note match
and refcount1 for this boot; that corroborates retained identity at its later
capture time, not an atomic startup observation. `resident_session_active=true` in the baseline report is a retained
lifetime flag; `resident_session_usable=false` and diagnostic=true describe the
actual failed recovery state. Historical `cold-load-intent` is not live process
status.

This review covers completed cold startup and the first typed snapshot only.
Separate reads are non-atomic, and trace/statistics activity is not GPU
completion. Later PWRGATE, CPU stop, provider OFF, retirement and restart require
their own actual evidence. [Bound raw inputs and observations](2026-10-09-gfx-native-powergate-live-startup-review.json).
