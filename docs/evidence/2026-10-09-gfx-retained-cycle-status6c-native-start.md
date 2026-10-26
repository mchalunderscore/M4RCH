# Native stopped-start predicate after the status6c refusal

The second power reference succeeded on boot
`5bf0a178-e6d8-4def-8088-74ad7ea87727`, but the retained-cycle experiment refused
at CTRL44=0, STATUS48=0x6c, RX114=0x20001 and TX110=0x20001. That refusal happened
before the separate second paired ON, START or management exchange. The exact
status6a requirement is our conservative cold-boot gate; it is not a predicate
in the matched native stopped-CPU start bodies.

This is a bounded offline review of the current captured refusal and native
AppleA7IOP/ASCWrapV6 route. It reverified the 15 already qualified native ranges,
six small additional ranges and six calibrated backend slots. No hardware action,
new policy, candidate preparation, rebuild or frozen-source edit was performed.
The companion JSON binds their exact bytes and current saved ADT applicability.

Matched `RTBuddy::_performPowerStateChangeGated` selects start options0 for prior
IOP status2 (PWRGATE) when the native `running` property is absent, as it is in
the saved GFX configuration. It sets the host IOP status4 and invokes
`AppleA7IOP::startCPUWithOptions`. The options0 route enables provider power,
activates the mapper when selected, maps retained preloaded firmware, marks the
host backend started, initializes mailbox/outbox handling, optionally synchronizes
the timebase, then calls V6 `_runCPU(true)`.

The common start body and V6 `_runCPU(true)` impose no STATUS48 idle, low-bit or
exact6a check. V6 run reads CTRL44 freshly and writes that value OR0x10. The
native `_isIdle` check belongs to CPU stop: it accepts either STATUS48 low bit.
Status6c fails that stop-idle predicate, but this does not make it a checked
native start refusal. Provider and mapper callbacks remain separate scopes;
absence of a check in these bodies does not prove the entire platform sequence
is reproduced by our experiment.

The mailbox and timebase differences do not identify a missing hardware value
behind the current refusal. The matched V6 `_disableAllInterrupts`,
`_enableInboxInterrupt` and `_enableOutboxInterrupt` bodies are no-ops. Generic
`_apInitializesMailboxes` returns true. V6 `_enableOutbox(true)` performs one
fresh RMW of RX114 bit0, and the captured RX114=0x20001 already has that bit set.
Native IOInterruptEventSource enabling is host bookkeeping; the retained owner
uses polling. The current saved GFX ADT lacks `ignore-mailboxes` and
`force-timebase-sync`; absent timebase synchronization therefore is not an
omitted selected native hardware action. No speculative timebase write or
interrupt reset is justified by this result.

The preloaded memory qualifications remain narrower than recovery. Native
preloaded fixup skips copying DATA to its target. Repeated iBoot mapping may
intentionally do nothing while its retained mapped flag remains set. V6 unmap
does not itself clear that flag. The saved SRAM-backup policy remains unselected.
Neither these bodies nor runCPU(true) program an ASC reset vector. Runtime
mapper `setActive` effects remain unresolved; this review supplies no Linux UAT
stream reset, context reattach, root replacement or firmware memory restore.

One distinct future hypothesis is supported for a bounded experiment: after its
own successful request202, qualified ACK, checked CPU stop, paired OFF, strict
physical OFF, fresh same-consumer PM get and physical ACTIVE, recognize only the
captured START-clear/status6c/empty-RX/available-TX state as an additional
stopped-start admission. Perform the separate second paired ON before the final
four-operand admission, then permit at most one fresh native CTRL44 ORSTART at
known6a or6c. Seek autonomous HELLO12/map and retain all original pages, mappings
and context. No INIT220, application endpoint/root publication, shared queue
reset or application recovery would follow without separate evidence.

That would test a new state: the old failed warm START trials lacked the now
captured own PWRGATE202 and strict physical OFF boundary. It is not evidence
that status6c is bootable, that paired ON restores status6a, or that the reduced
owner reproduces all native mapper/provider effects. The current compiled
owner's intents remain consumed; this report admits no retry or new policy.

Machine-readable proof is in [the evidence JSON](2026-10-09-gfx-retained-cycle-status6c-native-start.json).
