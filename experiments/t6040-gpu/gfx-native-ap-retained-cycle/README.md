# Retained AP ON cycle, v11

The captured v10 panic was `Invalid AP power: 33`: the first management-only
202 shutdown preserved the firmware's AP ON state, and the second B20 request
attempted that same transition again. Native RTBuddy keeps the cached remote
AP state across management target 2 and skips an ON notification when it is
already 0x20. This kit models that retained state explicitly.

The cold `power_ack()` hook records one owned B20 request and an exact, fresh
EP0 B20 reply. It requires RX empty and TX available before and after the
request log, rejects late or pending replies, and establishes a known AP
remote state of 0x20. The actual root-publication condition also checks that
proof after the reply log. Two complete cold rows use the separate prefix
`m4rch gfx-native-ap-retained-cold:` and phases `request` and `reply`, with:

```
request_attempted request_write_attempted request_message request_metadata
reply_observed reply_message reply_metadata ap_remote_state ap_remote_known
```

The second cycle refuses a missing cold proof before acquiring its second PM
reference. After separate paired ON, checked START, HELLO12, the two exact map
acknowledgments and exact autonomous EP0 Running7/20, it logs and consumes one
AP ON skip intent. It refreshes ownership, first-shutdown history, PM, CPU and
FIFO guards after that log and after the second202 intent log. There is no
second B20 request, fallback, AP B201/B0 transition or fabricated fresh HOST
reply. A second202 still needs its own low1/2 acknowledgment, checked CPU stop,
separate paired OFF, one PM put and strict physical OFF/accounting result.

Six complete rows describe each second-cycle phase: the primary prefix
`m4rch gfx-native-ap-retained-cycle:` and its `-state`, `-transport`,
`-management`, `-off` and `-on` variants. Each row must fit in 511 bytes,
including its terminating newline; cold rows are counted separately.

The selected source is prepared from frozen v10 `prepared-owner-v2` into
`out/gfx-native-ap-retained-cycle/prepared-owner-v2`. The earlier v11 v1 source
and qualification remain historical. The preparer verifies the frozen v10
receipt and every source pin, changes only the Makefile, owner and recovery
dispatcher, and adds the new header. It never builds or loads a module.

`test-native-ap-retained-cycle-owner.py` compiles the actual prepared cold
helper, root-publication condition, new header, second coordinator and copied
receive worker against RAM callbacks with ASan/UBSan. Its 122 targeted cases
cover cold ownership, the AP33 duplicate-transition firmware model, missing
mirror refusal before PM get, fresh skip/request-intent guards, exact Running,
journal capacity and low1/2 shutdown acknowledgments. It composes the saved
unchanged 135-case qualification without rerunning it. The selected output is
`out/gfx-native-ap-retained-cycle/owner-qualification-v2.json`.

This is a management protocol experiment. The mocks do not prove hardware
reentry, a second shutdown, application rejoin, rendering, DMA cessation or
allocation retirement. Runtime native framework flags remain unobserved.
The original allocations and first-shutdown evidence remain retained; only
the root agent may perform a separately admitted trial on a fresh boot.
