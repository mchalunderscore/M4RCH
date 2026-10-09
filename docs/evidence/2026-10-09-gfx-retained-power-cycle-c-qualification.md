# Retained native power-cycle C qualification

The distinct retained power-cycle source passes 102 actual C cases under
ASan/UBSan. It preserves the successful first PWRGATE/OFF epoch and admits at
most one separately owned power reference, autonomous transport boot and second
management PWRGATE/OFF. This is offline qualification for the next experiment,
not a successful hardware reentry, repeated teardown, application recovery,
rendering or DMA retirement result.

The selected source is `out/gfx-retained-power-cycle/prepared-owner-v6`; its
source receipt has SHA-256
`4f8288982b3d2e926cce11ebe800744ea92f668008e77600929d691319e3ec9a`.
The final actual-header qualification
`out/gfx-retained-power-cycle/owner-qualification-final-v6.json` has SHA-256
`0bcc3860d865fe22ba4adec88aff4f405196548246ebc22fe84e6917deccc305`.
Earlier prepared sources and qualification receipts remain historical.

The first typed `gfx-powergate` captures all 174 owned page pointers and physical
addresses, the same consumer/MMIO mappings and installed host root descriptor.
Its drain, 202, ACK, CPU stop, paired OFF and sole PM put use the unchanged
successful drain header. The new typed `gfx-retained-cycle` consumes a distinct
intent before callbacks. It requires every first handshake/CPU/coordination/OFF
success field, unchanged retained identities, fresh strict physical OFF and
usage0/suspended/error0 accounting. It does not repair or rewrite the first
epoch's flags. Its own intent seals the copied receive worker directly.

One `pm_runtime_resume_and_get` obtains the second reference. A negative return
does not transfer a reference; a positive return retains that reference on every
uncertain later result. Fresh physical ACTIVE and usage1/error0 precede ASC
access. Both before and after the separate second coordinator ON, the source
requires fresh valid CTRL44/STATUS48/RX114/TX110, START clear, exact status0x6a,
empty RX and available TX. Status6e/6c/48 refuses before START. The sole START
uses another immediate fresh CTRL44 RMW.

The autonomous protocol uses a separate static 16-record host journal, preserving
each removed message and metadata before interpretation. It accepts only EP0
HELLO12/12, then the two exact maps observed during the successful cold trial:
base0/bitmap3/nonfinal and base1/bitmap3/final. It parses all six native map-base
bits, refuses aliases or different shape before map ACK, and sends no INIT220,
system/application endpoint start, application root or shared address. The
four-second jiffies deadline and 4001 polls are finite bounds, not a hard
wall-clock guarantee.

The matched native transport route sets host status5 after HELLO and status6
only after the final map ACK succeeds. Its normal PWRGATE transition selects
status7 and sends request202 without an application-root prerequisite in those
inspected bodies. This supports an explicit, limited management hypothesis:
after our fresh HELLO/final-map exchange, one fresh four-operand CPU/FIFO and PM
check admits the second request202. A reserved journal slot and fresh RX EMPTY
prevent an old frame or missing ACK capacity from qualifying it. Only the native
EP0 type7/low8=1 or2 ACK after that request permits idle checking and separate
fresh CTRL44 clear10/clear20 operations.

The second OFF has its own coordinator session, observation, intent, PM put and
strict physical witness. It validates CPU stop again before coordination, never
resets the first coordinator session, and consumes the second reference once.
After that put, only safe provider/software and retained DRAM observations
follow. Successful completion additionally requires all first evidence fields
and retained host identities to remain unchanged. Diagnostics label the old OFF
fields as first-epoch history and separately report current usage/runtime status
and second-epoch state.

The replay compiles the actual new two headers, the actual unchanged coordinate
core and the actual transformed receive worker. It injects missing first success
fields, changed page/PA/root/context identities, fresh OFF/ACTIVE errors, PM
get/put accounting failures, all cold-boundary operands, coordinator failures,
fresh START races, autonomous protocol/version/map/endpoint errors, missing or
late ACKs, journal capacity, CPU idle/RMW failures and strict BUSY remaining set.
Every consumed retry refuses without further get, START, request or put. Queued
worker calls cannot receive or reschedule after the distinct intent, including
when the first recovery-failed field was deliberately false.

The first successful epoch is simulated in this new-header harness; the original
85-case drain qualification and actual first strict-OFF capture compose
separately. Runtime PM, provider, CPU/mailbox and retained DRAM adapters use RAM
callbacks. The actual second coordinator core is exercised, while its MMIO
binding uses RAM callbacks. No new kernel module was built or loaded by this
qualification. The separate compiled candidate and wrapper qualification must
be bound before a fresh-boot hardware trial.

Machine-readable pins and cases are in [the evidence JSON](2026-10-09-gfx-retained-power-cycle-c-qualification.json).
