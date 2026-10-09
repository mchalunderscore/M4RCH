# Independent native PWRGATE drain terminal review — boot16868560

The one combined `gfx-powergate` operation returned zero after an observed
management handshake, checked CPU stop, paired native OFF notification, one
normal PM-reference put and the strict physical-OFF predicate. This is the first
saved trial in this chain to clear BUSY. It does not establish restart, backing
retirement or rendering. All174 allocations, maps, context, consumer and owner
remain retained; the only admitted commands are `sample` and `gfx-snapshot`.

The exact selected owner is `de75ef4b…` and candidate receipt `39304966…`.
The [bound JSON](2026-10-09-gfx-native-powergate-drain-live-terminal-review.json)
independently verifies all10 artifact pins,18 owner-source pins, graph metadata
and fixtures, native bounded byte ranges and the cold, baseline, terminal and
later saved captures. It contains84 input pins. This reviewer performed no
hardware action or live register read.

After durable intent at kernel time182.835927, admission removed eight frames.
Every frame had the exact notification `0x0042000000000000` and endpoint32.
The first service call copied766 new records into the retained journal; the
other seven queued notifications added no records. The raw journal and all its
decoded80-byte entries agree: used50410→51176, doorbells0→8, statusflags0.
The addition comprises511 trace records and255 statistics records, with no
controller-event/completion records. Admission made ten four-operand samples
and one empty-RX wait poll, with no refusal or deadline/limit outcome.

The fresh before-request sample at182.837150 had CTRL44=`0x10`,
STATUS48=`0x6e`, RX114=`0x2ee01` (EMPTY set) and TX110=`0x2aa01`
(full bit16 clear), with the sole PM reference held and usage1/error0.
Exactly one202 was published at182.837152. At182.843801 the one removed
ACK frame was `0x0070000000000201`, metadata=`0x10ef0000000000`
(endpoint0). Seven ACK polls observed native type7/low8=1 and fresh empty RX.
The low16 value201 is not an echoed SLEEP request: the pinned native ACK handler
normalizes low8 values1 or2 to host IOP status2. No201 request was sent.

The CPU path recorded qualified native idle and fresh empty RX immediately
before writes, then two fresh CTRL44 RMWs clearing masks0x10 and0x20, with
readbacks0 and0. The second entry mask was already clear; the observation proves
the native write/readback sequence, not that bit0x20 had been set. The final
STATUS48 was `0x6d`, with its native idle low-bit predicate satisfied.
`cpu_stopped=1` and `host_stopped=1` precede delegated paired OFF.

Paired OFF wrote the full PMP request0x2000→0 and verified all three PMC votes.
STATUS.payload0 selected the native ACK-wait bypass; this is separate from the
observed management ACK and does not prove a PMP ACK or inactivity. The sole
`pm_runtime_put_sync_suspend` returned0. Accounting became held0, usage0,
runtime suspended/status2/error0. The first post-OFF provider sample at182.844248
reported domainOFF with no operation/cleanup errors; its physical word at
182.844249 was `0x0f000300`: ACTUAL/TARGET0, AUTO0 and BUSY0.
`word & 0x90001cff == 0` passed; the entire word need not be zero.
The result recorded provider_off_observed1, accounting_ok1 and snapshot_count1,
with no delayed physical polling. Once OFF was consumed, ASC/SGX/mailbox
sampling was disabled.

The admitted diagnostic at288.311982,105.467723 seconds after the terminal DRAM
sample, retained the same strict word, domainOFF and held0/suspended accounting,
with ASCsampled0. The entire69-page objects buffer, all174 owned pages and the
full raw receive journal are byte identical between terminal and later capture.
The separately saved power field at objects+0x3652c and owned+0x3e52c remains
10724; the logged field, journal51176 and doorbells8 also remain unchanged.
These are non-atomic sampled observations of retained buffers over this interval.
They do not identify every possible GPU writer or prove joined whole-GPU DMA
retirement, safe unmap/free, reset-vector restoration or repeatable reentry.

All56 dormant render pages match their prepared fixture, all35 job-pool pages
match cold capture, all12 work-channel cursor triplets remain zero, deferred
work rings remain exact, and control stays32/32/32. No work or triangle was
published. Host report `complete=true` records command/capture success;
`operation_failed=true` and `resident_session_usable=false` preserve terminal
quarantine. The host's separate historical `host_stop_requested=false` flag
does not negate the kernel's observed new CPU stop. Pure actual wrapper admission
permits only the two retained diagnostics and rejects a second `gfx-powergate`.

The earlier paired-OFF-only boot94cb ended with BUSY set at0x0f000b00 and changing
retained power bytes. The earlier no-drain bootd841 refused before202 and did not
identify the offending transport operand. This fresh trial directly observes
pending qualified EP32 notifications and succeeds after draining them and
performing the native PWRGATE/CPU-stop sequence. The combined difference supports
that execution hypothesis; it does not isolate each addition's causal effect or
justify replaying any consumed owner. A separate candidate must qualify retained
transport reentry before another hardware cycle.
