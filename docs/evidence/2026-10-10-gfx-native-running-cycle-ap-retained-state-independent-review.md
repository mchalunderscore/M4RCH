The native driver skips a repeated HOST ON notification when its cached AP wire state is already20. Its management initializer starts that cache at0; the cold HOST B20 reply publishes20. The type-7 Running notification updates a separate IOP state and does not clear the AP cache. The retained ON route reuses an existing management endpoint and compares its cache before constructing a new HOST message.

| Parent state | AP notification (type B) | IOP request (type6) |
|---|---|---|
| OFF0 | B201, conditional on remote cache | 201 |
| ON1 | B20, skipped when remote20 | 220 |
| Retained Sleep2 | no AP message; AP helper refuses2 | 202 |
| Quiesce3 | B0, conditional on remote cache | 0 |

The outer transition notifies before the perform route and again afterward. Retained Sleep2 from ON1 does not send B201; it requests management202. Reentry ON1 then takes the already20 skip when that state is retained. Thus the first direct202 was not shown to omit a required parent OFF notification. The experiment's physical PMGR OFF is not proof that native full parentOFF0 occurred.

The saved df540 cold capture has an own B20/fresh exact reply. E2 reached Running20 and attempted another B20; its reserved firmware crashlog says `Invalid AP power: 33`. Independent captured-TEXT decoding maps valid wire20 to internal33 and proves the equal-current-state panic branch at the captured PC. The unconditional v10 B20 requirement was a failed hypothesis. Its sources and reports remain unchanged.

The next bounded lead is to carry the verified same-owner cold AP20 state through the successful first202/OFF, skip duplicate B20 after fresh qualified HELLO/maps/Running, and test the existing management shutdown boundary. Actual native flags and cache are unobserved in the manual owner; its own explicit kernel state proof is required. Neither successful second shutdown, application rejoin nor DMA retirement is established. No current retry, echo, INIT220 or power command was issued.

The companion JSON binds15 complete native functions and the request table directly to saved private bytes and disassembly, plus the exact actual cold, E2, crash and source inputs. No whole-container rehash or hardware access was performed.
