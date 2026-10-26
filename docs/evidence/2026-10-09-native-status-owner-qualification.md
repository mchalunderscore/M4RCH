# Native STATUS0 owner adapter qualification

The separate native STATUS0 adapter passes56 actual RAM/stub cases under
ASan/UBSan, plus compilation refusal when its distinct profile is absent.
LeakSanitizer is disabled for the sandbox ptrace restriction. No hardware,
candidate load/build or frozen-source mutation was performed by this review.

Independent reversal of the adapter delta restores the exact frozen a9dc2ef9..
source. Only the native STATUS0 compile-profile assertion and passive
ack_bypassed/status_payload/status_raw logging differ. The root preparer's
transformation reproduces that exact new adapter and rejects a changed input.
The prepared startup, physical OFF and recovery dispatcher sources remain
byte-identical to the frozen execution bridge. The tested adapter is9798b263..
and the actual native STATUS0 core isb7a7376a..; the JSON records full hashes.

The harness retains the previous40 admission/lifetime cases, adapting the
old zero-status refusal fixture to an invalid all-ones status. Added cases
exercise zero-status ON and OFF through the actual MMIO adapter, distinguish
ACK bypass from ACK receipt in passive logs, preserve a nonzero raw status,
verify the64-bit request aperture and three32-bit voter writes in order, refuse
a repeated OFF, and retain ownership after request/voter readback failures.
Exported OF iteration still balances node references, including early aliases.

The actual prepared startup, cleanup, failure and retirement source gates are
compiled and executed with stubs. A zero-status START admission retains the
module/consumer; all subsequent cleanup/failure/retirement paths remain pinned.
The exact OFF source segment executes coordination before held=false and the
one PM put. Complete OFF permits one put; partial voter failure or invalid
dashboard status permits none and keeps the PM reference/resources retained.
Source ordering also confirms physical PM get before ON coordination, START
after coordination, and joined allocation/publication after START.

This qualifies adapter integration and lifetime/order behavior in RAM. It does
not qualify live STATUS0 semantics, atomicity against external writers, GPU
recovery, reset, DMA retirement, context reuse, execution or rendering. The
companion portable receipt includes16 independently verified input pins and
the saved RAM qualification hash; the frozen40-case harness remains unchanged.
