# Native power assertion plus policy/Fender candidate v23

This distinct, initially unselected candidate combines the frozen v22 policy path and nineteen
native descriptor byte corrections with one native-shaped opcode 0x0a/bool 1
policy command after the full draw capture is sealed and before the existing
single 202/NMI teardown. Root owns builds, finalization, selection and hardware.
The current consumed boot 09 is refused before candidate or live-device reads.

The command is an idle-power policy request. Native bool 1 permits that policy;
it is not a direct OFF or cancellation command. This experiment transfers that
request to the postdraw shutdown caller. Its enclosing native caller and order
are not reproduced, and no work retirement is inferred from command processing.

The new helper validates root+0x20 points to owned Region C, requires its
assertion equal the fresh consumed statusB+0xe438 counter and refuses invalid or
near-wrap baselines before any store. Initial opcode 0x16 is class 0 and keeps
its existing no-bump behavior. The helper validates control baseline 33/33/33 and the
unpublished slot 33 record. It replaces exactly that 64-byte record with opcode
10 and a 32-bit bool 1, verifies cache-cleaned bytes, increments the packed Region C+0xe51 32-bit
host power assertion once with the matched DMBISH/cache-clean ordering, verifies
a fresh readback, then publishes producer 34 once,
then sends one endpoint 33/class 0x84 notification. Processing requires exact
cursors 34/34/34 plus one increment of statusB+0xe438. The independent native
GPU-off observation is statusA+0x10 equal to zero, with +0x14/+0x18/+0x1c captured
as context. Each wait is bounded to two seconds and 2001 polls.

A clean processing timeout or clean GPU-off-word timeout is diagnostic and
continues the inherited single teardown attempt. Invalid access, malformed
operands, crash/transport ambiguity or publication uncertainty refuses while
retaining ownership. A fresh admission drain follows the helper to restore the
existing 202 deadline. Strict physical OFF and paired PM accounting are unchanged.

Host evidence reports host assertion publication, policy processing, firmware GPU-off, 202 acknowledgement,
native NMI, fresh ASC idle, CPU stop, Fender disable, strict physical OFF and PM
accounting separately. It preserves the immutable precycle capture and saves
only dmesg after the cycle. There are no postcycle RAM samplers, retries,
application/work replay, owner unload, backing free or second cycle.

The new source preparer and actual-C qualification are owned by the runtime
agent. The host qualifier composes frozen v22 C77/host28/three main flows and earlier scopes, exercises changed log
acceptance/refusals and the actual intercepted capture-before-cycle main, and
checks consumed-boot refusal. It does not rerun old whole qualifications.

The finalizer rederives the complete source projection and checks the actual
AArch64 owner's `graph_bytes` ELF symbol against the nineteen-byte corrected
arena. It creates new build/preparation receipts with selection false. A separate
root review and report must select the candidate before a fresh hardware trial.

No offline result proves GPU execution, pixels, DMA retirement or rebootless
render restart. Native normal boot and full desktop integration remain separate.
