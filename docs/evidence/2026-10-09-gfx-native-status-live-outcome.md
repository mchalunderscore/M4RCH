# Native STATUS0 coordinated trial — boot 94cb4163

The request-first native STATUS0 branch admits firmware startup, but the paired
native coordination sequence does **not** yield usable teardown. The sole cold
trial returned0, published the joined root and retained all174 pages. Its first
idle recovery requested two cycles and completed zero. No work was submitted.

ON wrote full PMP REQ0→0x2000 and verified all three PMC votes0→4 before firmware
START. Both ON and OFF selected native STATUS0 success: `ack_bypassed=1`,
`request_acked=0`, zero ACK-wait samples. This follows the selected native branch;
it establishes neither an acknowledgement nor inactivity.

The sole packet-free STOP succeeded with START clear and native ASC idle. The
sole paired OFF cleared full REQ0x2000→0 and all three votes4→0 with readbacks
before the owner's single normal PM put. That put returned0, leaving usage0,
suspended software state, runtime_error0, held0 and software domain OFF.

Physical OFF remained unqualified. All101 valid immediate provider observations
read `0x0f000b00`: ACTUAL0, TARGET0 and AUTO0, but BUSY11 set. The strict mask
`word & 0x90001cff` returned0x800. OFF returned `-ETIMEDOUT`. The measured initial
observation horizon is about0.114s; the printed delay metadata is not treated as
a per-read100ms delay. At a later permitted snapshot,262.22528s after the terminal
DRAM record, the physical word was unchanged and qualified firmware-owned
power+0x652c had advanced25589→57056. The receive journal stayed at50,410 records.
These separate, non-atomic captures show continued change in that qualified
field; they establish neither the identity of every writer nor global GPU
cessation. The field counts firmware initialization completions, not completed
application recovery cycles.

After OFF, the typed snapshot skipped ASC, SGX, mailbox, PMP and PMC access. It
read only the admitted driver-owned provider/software state and retained DRAM.
All174 pages, installed mappings, consumer and module remain pinned. The PM
reference has already been consumed; another put/get, control operation, STOP,
OFF, reset, START/INIT, submission, new owner/root, unmap/free/detach or unload is
not admitted. Only typed `sample` and `gfx-snapshot` remain admitted. A resident
lifetime flag does not make this diagnostic session usable for execution.

The result rules out omitted paired PMP/PMC coordination **alone** as a sufficient
explanation for the earlier failed physical OFF. The next concrete comparison is
the matched RTBuddy native PWRGATE202 handshake and checked CPU-stop sequence
before paired provider OFF. Our packet-free STOP omits that management transition
and native mapper bookkeeping. A distinct source kit is being prepared offline;
no next trial or reboot readiness follows from this observation. Mapper
deactivation, firmware state preservation, whole-GPU drain, repeatable restart
and joined-context retirement remain unresolved. Failed warm START/INIT trials
must not be repeated.

The [bound outcome JSON](2026-10-09-gfx-native-status-live-outcome.json) records
the exact fresh preflight, cold session and four operation paths. Independent
reviews cover [startup](2026-10-09-gfx-native-status-independent-startup-review.md)
and the terminal STOP/OFF/later snapshot. This is an actual hardware result;
the offline qualifications remain separate. No triangle, valid pixels, successful
reset, backing release or accelerated desktop is established. The goal remains
active; GRUB default5 and the installed native-reset kernel remain unchanged.
