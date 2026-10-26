# Retained owner integration for paired PMP/PMC coordination

This is a separate future source kit. It does not alter the attempted owner,
build or load a module, install a kernel, change boot configuration or access
hardware. The protocol core is maintained separately in
`../gfx-native-coordinate/gfx-coordinate-core.h`. Read the frozen
`docs/evidence/2026-10-09-gfx-native-shutdown-coordination` and
`2026-10-09-gfx-pmp-pmc-linux-integration` pairs before qualifying a candidate.

`prepare-owner.py` accepts only the exact attempted power-off owner's three
source hashes and prepares a new source directory without overwriting one.
It copies source inputs only, transforms the ON/OFF and lifetime boundaries,
adds `GFX_NATIVE_COORDINATED_SCOPE_TRIAL`, and records input/output hashes.
It performs no compilation or hardware operation. Existing cold graph,
backing and other helpers remain outside this kit.

ON runs after the normal physical GFX runtime get and the existing cold ASC
and FIFO checks, before START, firmware boot and joined graph allocation or
publication. It invokes the root core with enabled=true. OFF runs after the
existing retained no-work/STOP/ACTIVE checks and terminal gate consumption,
before clearing held and making the sole PM put. It invokes enabled=false.
These placements preserve the qualified native order.

The adapter reserves the full native PMP5003c0000/30000 and
PMC504000000/1000000 resource spans. It rejects available OF MMIO aliases
before mapping and again before OFF. `request_mem_region()` also rejects
reserved ownership. Neither test proves the absence of unregistered raw
writers; this controlled experiment excludes competing helpers and dynamic
DT/bindings. No PMP firmware startup, bootarg patch, PMC initialization or
synthetic compatible DT node is added. Future boot qualification must check
the exact kernel, source/ADT pins and ownership before module load.
OF resource enumeration stops at the first nontranslatable index in a node,
as the existing OF API loop requires. It does not claim to discover a later
resource hidden behind a malformed earlier entry. The future preflight must
reject unexplained/malformed resource descriptions rather than infer complete
ownership absence from this bounded adapter scan.

PTD reads use two separate 64-bit reads at entry*16, preserving payload and
raw status. They are not an atomic native LDP snapshot. Request writes are
full64-bit at10000+entry*8, restricted to entry1e0. PMC reads and writes are
full32-bit words at8ac000/4/8. The root core owns masks, ACK semantics, guards
and its15second/15001sample bound. The adapter supplies monotonic time,
sleepable1ms delays and raw event logs. No runtime hardware equivalent of
native object mode2 is claimed. STATUS0 is refused by the stricter trial
contract, not interpreted as safe inactivity. Unchanged request/voter bits
are logged without attributing an effective transition.

Before preparing or invoking ON, the adapter marks startup retained and pins
the module. Thus every ON refusal, mapping/resource failure, attempted write
failure and later startup failure retains the consumer, any held PM reference,
acquired resources and mappings. No automatic PM put or cleanup follows an
ON invocation. A failure before START returns module-init success with the
module pinned; no graph or joined pages have yet been allocated/published.
The future runner must record this from module/dmesg state and must not load
another owner or try to remove it because graph sysfs is absent.

All owner pin sites use one idempotent helper, so a successful ON followed by
resident entry keeps one lifetime pin. Cleanup and ordinary retirement are
refused after any ON invocation. The OFF gate remains terminal; failed
coordination returns before PM put and keeps held=true. Partial coordination
is recorded without rollback or retry. If all coordination succeeds, the
existing single PM put and strict OFF predicate still apply. The174 joined
pages stay pinned once created. No ASC/SGX/mailbox access follows OFF intent,
and no work, reset, warm wake, detach/free, unload or reboot is introduced.

This kit needs actual-core, adapter/lifetime and build qualification before
creating a future runnable candidate. It does not establish GPU cessation,
DMA/UAT/cache retirement, repeatable restart, rendering or pixels.
