# Read-only STOP confirmation

`confirm-stop.py` handles the observed, returned STOP EAGAIN on boot339b9e8e.
The one C STOP cleared START, then its immediate idle read was0x4c. A later
read-only snapshot saw START0 and native idle0x4e while the owner retained its
sole PM reference. The helper recorded that completion in host metadata;
it made no second STOP/sysfs write and changed no owner or candidate source.

The helper admits only the exact returned errno11, a fresh matching C result,
and the next successful read-only diagnostic with START clear/native idle,
usage1, active/enabled PM, no runtime error, and no OFF gate or PM attempt.
It validates the candidate, kernel and loaded module identity under the
existing operation lock. Before updating metadata it durably preserves the
original failed state and capture hashes. Recovery remains failed. Unknown
open/write/interruption/short-write outcomes are never reconciled.

The subsequent, sole normal PM put succeeded in accounting terms, but strict
OFF observation timed out: ACTUAL/TARGET0 and AUTO0 with BUSY11 continuously
set. The firmware-owned field continued changing for more than221seconds.
Current state has an OFF intent and consumed kernel gate, so this helper now
refuses. Only PMGR/retained DRAM diagnostics remain allowed; no resume, restart,
new STOP, reset, work publication, mapping release or module unload follows.

`test-confirm-stop.py` exercises the actual saved capture pair and targeted
negative mutations without calling the helper main or any live interface.
The independent live review records the confirmation and its limits in
`docs/evidence/2026-10-09-gfx-poweroff-live-review.md` and its JSON companion.
