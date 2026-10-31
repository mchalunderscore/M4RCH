# J614s SEP and DCP reservations

On the Touch ID trial, Linux reported two overlapping reserved-memory pairs and
refused to mark two DCP OS-log nodes `no-map`. The pre-Touch ID boot had no
such errors. This is a real handoff conflict, not just a cosmetic warning:
Linux's `early_init_dt_reserve_memory()` refuses to mark any overlapping
previously reserved region `no-map`.

The live Apple device tree reports `SEPFW` as a 0x5ac000-byte span. On the
observed boot, two DCP `__OS_LOG` ranges and an ASC firmware range intersected
that span. Those are the addresses Apple supplied; the observed overlap is not
caused by calculating DCP addresses from the SEP descriptor. The same pattern
appeared on three candidate boots with different absolute addresses. Whether
SEP firmware itself accesses all bytes of its descriptor after warm attach is
not established. The running SEP uses Aurora's warm-registration path; the
kernel maps the full `sepfw` region only in its cold-boot path.

Aurora m1n1's [`dt_set_sep`](https://github.com/aurora-silicon/m1n1/blob/6918c029cc0919015844839fee3505b3a4e65e46/src/kboot.c)
publishes the whole descriptor as one mapped `sep-firmware` reservation. Its
[J616s DCP handoff](https://github.com/aurora-silicon/m1n1/pull/51) publishes
the DCP log nodes independently; its discussion contained no resolution of the
combined SEP case when checked on 31 October. Current `aurora-wip` still uses
the same SEP reservation approach. No corresponding upstream combined fix was
found. The local J614s U-Boot handoff therefore splits the SEP *reservation*,
not the firmware or the DCP buffers: existing intersecting `no-map` ASC/DCP
nodes retain their addresses and phandles, and the remaining pieces of the
full SEPFW range get their own reserved-memory nodes. The unneeded `sepfw`
reference is removed only for the J614s warm SEP when a split is needed. The
code refuses unexpected overlaps and falls back to the original live tree if
admission or editing fails. This preserves the entire descriptor while avoiding
intersecting reserved-memory nodes; it does not establish whether the firmware
considers the descriptor's contents exclusively owned.

The actual U-Boot transformation was run against this machine's real boot
FDT in memory: the original SEP interval was covered exactly once, and DCP/ASC
addresses, `no-map` flags and phandles were unchanged. A one-time boot on
31 October used the resulting U-Boot with the Touch ID kernel. Its log showed
all three DCP OS-log nodes as `no-map` and no reservation-failure or overlap
warnings; SEP restored one enrolled identity, the sensor came online, and the
xART guard reported no refusals. A further qualification boot used the same U-Boot with the final kernel; the
user confirmed the display, keyboard and trackpad worked, and the enrolled
right index finger matched. This evidence does not
prove suspend reliability, external display behavior, or the meaning of every
byte of the Apple firmware descriptor.
