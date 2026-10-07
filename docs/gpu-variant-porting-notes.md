# Deferred G16S variant-porting writeup

User request: after the 16-core J614s driver is working, write a guide explaining
16-core versus 20-core differences for an independent implementation.

Keep measured facts and implementation-derived assumptions distinct. Preserve
source/capture provenance rather than assigning a blanket clean-room label.
Current known J614s topology: 16 enabled cores, cluster masks 0x3db/0x3db;
standalone Discord document describes a 20-core J616s with 0x3ff/0x3ff.
Both masks occupy ten slot positions per cluster; enabled-count differences
must not be confused with physical mask width or serialization array capacity.

Topics to qualify before the final guide:

- Core-mask/cluster geometry, cache/MCC apertures and chip-specific registers.
- ADT performance rows, voltage groups, core/SRAM columns and storage capacity.
- Firmware build/ABI identity and which offsets actually differ by variant.
- Init objects, MMIO descriptor roles, queue topology and work-command fields.
- Tested rendering/power/recovery behavior, reproducible inputs and limits.

A common firmware ABI does not establish identical initialization constants.
Separate document claims, captured ADT facts, firmware-instruction observations,
codec candidates and successful native behavior in every comparison.

2026-10-07 native read-only batch: firmware slot33 FenderRegsBumper consumer
at TEXT2a774..2a7c0 reads words+a0/a4 and partitions ten-bit fields. Physical
bank and enabled-mask interpretation not yet verified. Captured ADT packed
candidate3db|(3db<<10)=f6fdb. Keep this as an instruction observation, not a
native core-mask register result.
