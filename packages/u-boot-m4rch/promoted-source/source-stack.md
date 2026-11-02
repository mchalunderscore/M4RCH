# U-Boot source record — u-boot-m4rch 2026.07-21

> Historical cache paths below refer to retired trial artifacts; the cache now retains only inputs needed by two current test helpers. For the current boot recovery path, see [recovery](../../../docs/recovery.md).

Aurora `aurora-wip` commit `01f255b636737bc783b581b04584d1224ab06cf4`, archive SHA-256 `b1656feb1edcb418d4bf2f83aeb750be94fcd824a20f40259b90f75c67f5300a`, plus the ordered J614s behaviour and reservation patch series. The behaviour series provides MTP keyboard and Linux handoff; the reservation series handles overlapping SEP and DCP/ASC reserved-memory descriptors as described in `docs/j614s-sep-dcp-reservations.md`.

Binary SHA-256 `b21eba751a8541249da85ae81ca0fa5b884bbea2224fb5f173a803f3678caa04`. Booted with the Touch ID qualification kernel on 31 October 2026; the user confirmed display, keyboard and trackpad work. The source transformation preserves the reservations but does not establish physical firmware ownership of every overlapping byte. Previous source records are retained in `cache/touchid-candidate/pre-touchid-package-sources.tar.gz`.

Release 21 adds the J614s SD handoff series after the existing behaviour and
reservation patches. On the EFI handoff copy it validates the board, PCIe
port, DART maps and pin configuration; enables the reader's port, DART and
bus 2; and describes the GL9755 polarity. It selects the SD CLKREQ pin at
the PCIe controller and removes the root-port pinctrl properties, avoiding the
duplicate PIN1 claim seen on the prior SD trial boot. The input board DTB is
unchanged, so U-Boot's own PCI scan still sees the port disabled. The retained
m1n1 power step remains a dependency.

The earlier SD handoff booted on this machine and the owner confirmed
hotplug, reads and writes. The PIN1 ownership correction is built and checked
against the installed and previously captured live DTBs but has **not** yet
been booted. Binary SHA-256
`b25192d5f2f4c07f49ee0cc6f15d2c9ec5199cf201cc608c1a651c249ba0b018`,
configuration unchanged. Build input and log are retained under
`cache/jack-promotion/`; the prior tested SD image and its exact source are
preserved in `cache/jack-promotion/recovery/`. See `docs/j614s-sd-reader.md`.
