# U-Boot source record — u-boot-m4rch 2026.07-19

Aurora `aurora-wip` commit `01f255b636737bc783b581b04584d1224ab06cf4`,
archive SHA-256 `b1656feb1edcb418d4bf2f83aeb750be94fcd824a20f40259b90f75c67f5300a`,
plus the ordered J614s `behaviour` series. Its last patch adds the retained
MTP keyboard and Linux handoff, using the existing J713 session inventory and
packet replay implementation. This is scoped to J614s. The combined patch hash
is recorded in `patches/behaviour/original.sha256`; the U-Boot binary SHA-256 is
`da769992da67d86c0e946e9af9930384046ef8d232194b0d202318e752370d1c`.
The owner confirmed keyboard input in GRUB and working keyboard and trackpad in
Linux after booting the combined m1n1/DTB/U-Boot bundle. This is not a
reproducible-build or complete peripheral-qualification claim.

The preceding 2026.07-18 source record, local changes and known-working boot
artifacts were saved in `cache/mtp-promotion/` before promotion.
