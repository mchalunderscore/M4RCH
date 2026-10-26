# Retained AP notification policy, matched native driver

The matched native driver separates AP host notifications from IOP management requests. Its retained target2 route does not send an AP OFF notification. It preserves the management endpoint's cached remote AP state, and a later ON notification skips B20 when that cache already equals20. This gives the duplicate-AP33 crash a concrete native ordering and publication explanation.

| Parent enum | AP notification, type B | IOP request, type6 |
|---|---|---|
| 0 / OFF | B201 | 201 |
| 1 / ON | B20 | 220 |
| 2 / retained Sleep / PWRGATE | unsupported; no wire message | 202 |
| 3 / quiesce | B0 | 0 |

These are separate domains. `signalApPower` accepts parent0/1/3 and constructs typeB messages; parent2 returns invalid argument before publishing a message. `requestPowerState` accepts0..3 and indexes a different table at `0xfffffe0007bfe338`: fullwords `[0x0060000000000201, 0x0060000000000220, 0x0060000000000202, 0x0060000000000000]`, SHA `4ffd451f7888c049df63fc0a165d9368092bf42d2b6a46fbc04d0895d8877d9d`. This table finding authorizes no INIT220 trial.

The complete parent change function first notifies endpoint routes with `(new, current)`, then performs and records the transition, then notifies `(recorded current, recorded current)`. On the managed branch, the original requested state is passed through the selector to performAllRoutes. The selector can performON first when needed; it does not silently replace requestedOFF0 with retainedPWRGATE2. Actual action-selection flags remain unbound.

For a parentON1 toOFF0 change, the management pre-callback reaches `signalApPower(0)` and conditionally sends B201, waiting/checking the cached remote201 before watchdog quiescence. The subsequent managed perform0 indexes management201. Therefore this path shows B201 before management201; it does not establish a universal B201 prerequisite before202.

For parentON1 toretainedSleep2, the pre-callback reaches `signalApPower(2)`. That helper returns invalid argument without sending; the callback ignores its return and quiesces the watchdog. Perform2 sets local parentIOPstatus7 and sends management202. The post `(2,2)` callback sends no AP notification. The experimental first direct202 omission of B201 is consistent with this retained native route. Its later strict physical PMGR OFF does not prove parentOFF0 orAPOFF0.

For retainedON1 fromold2, the pre `(1,2)` callback sends no AP notification. After boot/perform, post `(1,1)` processes runtime flags and invokes signalAPON. That helper maps1 towire20, reads the management object's cached remote field108, and equality returns before constructing, sending or waiting for a newB20. It does not require or create a fresh HOST reply when it skips.

The cache's publication is explicit: management initialization zeros108; receivedtypeB dispatch stores its low32 power value into108 and wakes waiters. The complete handleRemotePowerState does likewise. This is separate from the parenthostflag byte108 and from firmware internalAPstate33. Reusing the management endpoint on retainedON bypasses initialization. The ON postcallback can reset watchdog fields10c/110/118 under a parentflag, but it does not clear108. Complete type7ACK handling changes parentIOPstatus and does not publish APremote108. Thus a successfully received coldB20 can remain nativecached20 across retained202 and suppress the laterduplicate. Runtimecallback selection, skip123 and nativeobjectbinding remain unknown in our manual owner.

The actual current crash record preserves coldB20, first202/ACK201, secondHELLO/maps/Running and the secondB20, with noB201 in that saved history. The bounded firmware diagnosis showsB20 maps tointernal33 and requesting equalstored33 asserts. The manualowner has no qualifiednative remote-state mirror. FirmwareAP33 should not be mistaken for nativehostremote108.

The next bounded offline hypothesis is an explicit carried wireAP20 proof from this sameowner's ownedcoldB20 and fresh exactreply, retained withnointerveningAPchange. After fresh Running7/20, a distinctowner could skip B20 onlywhilethatproof is intact, expose the skip separately from anyfreshreply, and evaluate the existingexact202/low1or2 managementshutdown boundary underfreshPM/identity/CPU/FIFO guards. This remains unimplemented and unqualified. AddingB201 would introduce a differentparentOFF0 transition without evidence that it is required forretained2.

The companion JSON pins15 complete boundednativefunctions, the requesttable and14savedinputfiles. Privatekernelcache previouslyboundSHA is `6158e1c0d591240808e26ff1da050b2fa0ed3eb17c1779d2ddde3171b959536f`; nofullcontainer rehash, broadsource audit, newowner, build, test orhardwareaction was performed. Currentowner remainssealed withsecondreference and174allocations retained; noecho orcurrentretry.
