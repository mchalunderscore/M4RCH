# Native T6040 components in the Gravity backend

The selected Gravity `asahi_m4` backend now has a T6040 register/voltage producer selected directly by `Platform::new()` and `hwdata()`, with a corresponding `FirmwareSpace` mapping path. The existing normal execution gate remains closed. Full bundle, power, and region-C builders reject this partial profile before using donor objects.

The actual Rust component matched independent saved numerical sources over all 9,600 canary-backed output bytes, 22 cluster steps, 17 descriptors and 97 mapped pages (37 writable). SGX-relative VA relationships and compact four-range AFR mapping are checked. The first qualification fixture used incorrect byte indices for a 256-byte ADT table; its failure is preserved and the corrected fixture passes without changing production code.

The external module build reached RUSTC, MODPOST, CC and LD and produced `asahi_m4.ko`, retaining 16 Rust warnings. Its wrapper then failed an assertion that mistakenly treated generated `asahi_m4.mod.c` as immutable source. The original wrapper/log are preserved; the exact make return was not persisted before that assertion, so it is not invented here. Independent closure confirms all 67 production source files still match the pinned stage, and the produced module has an AArch64 ELF header and valid target vermagic. No identical-source rebuild was required.

This is a partial native hardware-data component, with 0x2570 bytes of established field extent rather than a claimed complete object size. Slots 3/22/27/39/41 are absent; the existing publication caller rejects T6040 before copying the component. No normal boot, reset, queue execution or rendered pixels are claimed.

A direct matched-constructor follow-up already resolves native construction geometry for MCC (slot 3), CAXI (slot 22) and MTR (slot 39). It is saved as numeric operands and source-range hashes for the next integrated source batch; the compiled component remains untouched. MMIO permissions and ownership still require explicit treatment.
