# Matching Apple kernelcache retrieved read-only

The user identified the M4RCH APFS subvolume and explicitly required a read-only
mount. Root retrieved only `kernelcache.release.mac16j` from its unencrypted
Preboot volume on 2026-10-09. The input is an exact SHA-256 match for the 25G83
kernelcache previously used to extract the AGX and DCP drivers:
`7a9305932f2c7028ec294b55a5ab23844173328eb38639c722a4b54401dcb1eb`.
Its size is31,852,893 bytes. After offline decoding, root independently parsed
the Mach-O header and verified the containing kernel UUID
`41811D69-3027-674E-E0DB-2F6F64C70EEB` and366 fileset entries. The decoded
119,308,288-byte container has SHA256
`6158e1c0d591240808e26ff1da050b2fa0ed3eb17c1779d2ddde3171b959536f`.

Read-only volume metadata identified M4RCH as System volume1 and
`Arch M4 Boot Preboot` as volume2 in `/dev/nvme0n1p5`. Root mounted volume2 with
the cached APFS FUSE driver and explicit `ro,nosuid,nodev` options.
`findmnt` confirmed `ro,nosuid,nodev,relatime,user_id=0,group_id=0,allow_other`.
The inspected driver opens the backing device with `O_RDONLY` and rejects
writable file opens. Its local guard permits only an unencrypted Preboot
volume. Source hashes and the executable hash are bound in the adjacent receipt.
The volume was unmounted immediately after the copy and hash check.

The private copy and operational receipt remain ignored under
`out/private-apple/kernelcache.release.mac16j` and
`out/private-apple/kernelcache-retrieval.json`. No APFS writes, GPU publication,
reset, module operation or backing release occurred during retrieval.

This removes the artifact-access gap recorded in the earlier local inventory.
That inventory covered local mounted files and did not inspect APFS. The full
container can now supply the RTBuddy implementation to which the extracted AGX
driver delegates boot and power handling. Matching the container does not itself
qualify a reset sequence, its hardware coverage, recovery or DMA retirement.
The independent header check identifies both AGX firmware-provider filesets and
`com.apple.driver.RTBuddy`. Instruction and chained-pointer resolution remain
separate provider-analysis qualifications.
