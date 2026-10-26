# Early STATUS0 refusal and bounded flash layout guard

The saved boot493814fd capture qualifies an early startup refusal, not a
retained joined session. Cold entry was CTRL44=0/STATUS48=0x6a; the GFX snapshot
was valid, domain_on1, ACTUAL15/TARGET15, BUSY0. PMP/PMC regions were reserved and
mapped. STATUS-before then read payload0/rawstatus0 and returned ENODATA(-61):
request_attempted0, request_acked0, ACK samples0, vote attempts/verified0.
The module returned success only to retain its consumer, sole PM reference,
module pin, ASC/mailbox and acquired PMP/PMC mappings/claims. START0, root0 and
commands[] are explicit in the saved receipt and log. The earlier shadow
allocation pass released its backing normally; no cold joined pages/context
were allocated or published. No further hardware operation is qualified here.

The matched native function writes the full64-bit masked REQ at
`0xfffffe000984974c` before testing the selected row flags at9838..9850. GFX
flags3 select the wait in both ON/OFF directions. The STATUS payload read at98d8
produces a nonzero flag at98dc..98e8; the zero test at998c branches directly to
the success return at9a94, before the ACK read at99a4. The loop repeats the same
zero-success test at9a7c. Thus the native STATUS0 branch skips ACK **after** the
request write and continues to the caller's PMC operation. It does not skip the
request, prove PMP inactivity, supply a cessation ACK, or qualify DATA/mapping
retirement. The existing native evidence and private disassembly pins match;
this review adds no new disassembly or readiness hypothesis.

The separate `experiments/t6040-gpu/gfx-coordinate-native-status/flash-layout-guard.py`
admits only the single phram reservation of size0x94000 moving within one
captured RAM interval. It requires a canonical unit address, 16KiB alignment,
nonoverflowing 64-bit interval, unchanged 2/2-cell identity reserved-memory
translation, no overlap with fixed GPU/MMIO/firmware/table envelopes, and no
overlap with another reserved-memory interval. Only that node's unit address
and reg base normalize. Its compatible, size and property set remain exact;
all311 other captured nodes/properties remain exact, including the separate
phram reservation of size0x4000. Duplicate/extra/missing nodes or malformed
metadata refuse. The caller must still pin the baseline/helper and verify
native ADT selection independently. The guard reads supplied metadata only.

Sixty offline cases pass using the actual original and boot493814fd layouts,
both RAM boundaries, full/partial fixed-region overlaps, reserved-region
collision, wrong sizes/addresses/translations and malformed or duplicated
metadata. Raw layout hashes71236d89.. and e2adc898.. share normalized hash
`cd8aa099cda21fcd8dab8278d65145546b26311f2c8d67139fb83bf921371f8c`.
The frozen exact guard and candidate were not modified. This helper supports
a separate native STATUS0 candidate and prevents another harmless flash
relocation from requiring an exact-layout rebase; it grants no action on the
currently retained owner. The companion JSON records all60 cases and input pins.
