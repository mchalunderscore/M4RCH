# Ordinary parameter-manager resource retention and staged page updates

Offline private-derived AGX353.14/Apple25G83, complete native
prepareAndRetain89fa7a8..89fb0d4 success path.512 successful cases return0 and
restore stack. Full PM, manager, TA descriptor, configuration, staged-update and
pending-vector bytes compare with independent struct models. Capacity8 and all
read/write/completed cursor combinations covered;768 pending drains,2688 block
preparations,896 dirty-block calls,256 staged-update requests.

Offsets are hexadecimal. The actual method binds TA descriptor retained-resource
fields d88,d90,da8,da0,dc0,db0,db8, using PM's current HWPB manager and ordinary
resources. First mappings prepare when PM1d0 or manager80 iszero. Resource/support
mapping generations publish to manager70/78 and PM1b0/1b8/1c0/1c8. Dirty1a8 processes
completed->read ring entries with block virtual138(argument2), then clears1a8.
Pending vector120 entries clear after virtual150; count128 clears.

A changed external page-list generation processes completed->read blocks through
PM virtual1c0. Independently, read->write blocks are processed and the final write
cursor publishes to staged update0 after an actual DMB ISH. PM28 marks update
state and PM140 captures completed cursor. For an unused manager30, PM virtual1c8
may set PM28=3 and PM144=staged cursor. Success marks PM6c=1.

The mapping preparations, support services/generation returns, retain, page-list
preparation, page generation, block preparation and staged-update methods remain
explicit no-op/return fixtures; their arguments are checked. This is not actual
mapping, registration or DMA/cache visibility. Error unwinds and invalid cursor
assertions are excluded. Emulated DMB does not prove concurrent CPU/GPU ordering.

No direct loadPBDesc call occurs in this native method. Its staged outputs and
retained descriptor resources still need joining to the later hardware-binding
path. In the full initializer audit PM readiness is external, and some ordinary
page-list/support resources used here are supplied explicitly; deriving their
actual preparation is a remaining gap. Do not claim a live parameter manager or
submission-ready driver from these success fixtures.

```
python experiments/t6040-gpu/audit-private-pm-retain.py \
 /boot/GPUC003/private-apple/com.apple.AGXG16X \
 docs/evidence/2026-10-08-private-pm-retain.json
```

Next trace the actual ordinary PM virtual methods/resource setup, page-list builder
and caller ordering into loadPBDesc, then bind the existing descriptor/register
recipes to Linux-owned work/queue/event/stamp identities and coherent completion.
The retained failed warm INIT still requires a normal reboot before live GPU
trials; offline work can continue. No commands submitted in this batch.
