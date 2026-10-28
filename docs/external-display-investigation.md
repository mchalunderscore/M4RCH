# External displays

HDMI and a USB-C-connected TV each showed a picture in the external-display
trial. The USB-C display and internal screen returned after one suspend/wake.
The owner observed HDMI shadow flicker and unusual scaling; their cause was not
diagnosed. The stack was promoted and the normal entry booted, but external
displays have not yet been retested with automatic driver loading.

The installed stack adapts Aurora's J616s infrastructure to J614s, including
sequential display power control, m1n1 firmware-memory handoff and the local
U-Boot bridge. Relevant upstream work includes Aurora Linux
[#446](https://github.com/aurora-silicon/linux/pull/446),
[#451](https://github.com/aurora-silicon/linux/pull/451),
[#515](https://github.com/aurora-silicon/linux/pull/515),
[#516](https://github.com/aurora-silicon/linux/pull/516), and m1n1
[#56](https://github.com/aurora-silicon/m1n1/pull/56). J616s results alone do
not establish the J614s power, memory or routing contract.

Promoted patches are under the `promoted-source` directories of the
[Linux](../packages/linux-m4rch/promoted-source/),
[m1n1](../packages/m1n1-m4rch/promoted-source/) and
[U-Boot](../packages/u-boot-m4rch/promoted-source/) packages. The raw ADT is
private and remains at `out/external-investigation/private/current.adt`; do not
publish it. Full historical observations are available with
`git show e7baa0e:docs/external-display-investigation.md`.
