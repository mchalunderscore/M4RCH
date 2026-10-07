# GPUC002: targeted Bumper / DFender trial

Read this kit from `/boot/GPUC002` on the internal ESP. Work in your existing
Linux project directory; write captures under `out/gpu-gravity-contract/`.
Do not rebuild from the macOS checkout's older generic kernel recipes.

## New mapping evidence

The 25G83 AGXG16X353.14 raw numeric table has13 entries. Its constructor
adds each primary offset to the physical GPU base. Your returned boot ADT
has SGX bus base0x88000000 and arm-io translation+0x200000000:

| Firmware slot | Name | Physical base | Resource extent |
|---|---|---|---|
|26|GFenderCfg|0x288d04000|0x8000|
|33|Bumper|0x288d44000|0x4000|
|35|DFenderMGPUCfg|0x288e00000|0x4000|

See `agx-pio-map.json` for all13 rows, source hashes, constructor/getter
addresses and limitations. The raw decoder independently reproduces the
already exercised GFender base. Host26A434 retains all13 offset/length pairs
but shifts IDs; do not use host IDs with25G83 firmware. These are static
candidates, not native power/permission qualification. The source was Apple's
cached matching kernel collection, not a guessed neighboring bank.

## Next native work

1. Verify SHA256SUMS and current boot/kernel,25G83 firmware/TEXT contract,
   native SGX translation, and your slot26/33/35 cached-pointer identities.
   Check each physical extent against native SGX resources. The mapping table
   provides extents, not firmware PTE permission flags or power sequencing.
2. Extend the existing graph helper with exact slot33/35 descriptors. Retain
   the existing firmware resource lifetime/pinning safeguards. Remove the
   slot33 RAM surrogate for the real-bank trial. Do not rerun the bank scanner.
   First perform a bounded exact-address read of Bumper+a0/a4/a8 and
   DFender+1704/1780 using the already qualified GPU power path. Capture before
   and after. Do not read a whole bank or experiment with unrelated offsets.
3. Review consumers and mapping permissions before firmware execution:
   slot33 producer writes+a0/a4/a8 when hardware+2560/+2568 masks are nonzero;
   slot35 writes+1704 and reads/writes+1780. Read-only leaves will not support
   those writes. Restrict any writable device mappings to the required bank
   pages and preserve the previously validated page-table ownership rules.
4. Run one explicit opt-in graph-init attempt after the offline serializer,
   consumer-offset and page-table checks pass. Keep the installed working
   kernel/default and original boot.bin. Capture complete crashlog, descriptor
   bytes, virtual/physical mappings, masks, power state, elapsed time, and
   kernel log. Do not claim acceleration merely because initialization
   progresses. If another missing mapping appears, use the static inventory
   or request source analysis rather than another broad hardware scan.
5. Keep arrays/resources pinned until normal reboot if firmware consumed them.
   A changed test module may require a clean reboot before the next attempt;
   never force-unload active firmware mappings. Stop after a fault and return
   the precise PC/FAR/ESR/cache-pointer state.

## Corrections / return requirements

Firmware hardware array: base0x640, stride0x28=40 bytes, copied prefix0x24=36
bytes. The CPU HAL table here has32-byte records; it is a different structure.
Old unprefixed28/24 wording must not become decimal28/24 in a serializer.
Do not automatically populate all firmware records from these13 CPU entries:
resource/slot correspondence is established for this25G83 table, and alternate
sentinels0xffffffff/0xdadadada have constructor-specific behavior.

Your promoted kernel-alignment/build source is missing from this macOS checkout.
Please include the current kernel-alignment recipes, sources.json/lock, patches,
GPU helper sources and relevant tracked diffs in the return, preserving upstream
pins and provenance. SSH fetch was unavailable here; a source tarball is fine.
Do not include private credentials, Apple binaries, or full system images.

Return a fresh `/boot/HANDOVER.md` plus a named archive under `/boot/GPUC002`.
Include every raw capture cited in it and checksums, and distinguish tested
results from candidates. This kit contains metadata and a static parser only;
it does not change the installed bootloader or kernel.
