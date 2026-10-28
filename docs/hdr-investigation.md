# Internal-panel HDR

The owner visually tuned the promoted J614s HDR path and reported that the
desktop and HDR video look good. This is not a measured calibration: panel
luminance, color accuracy and the exact PQ response have not been verified.
The synthetic metadata and the firmware's approximately 600-nit limit are
not measurements of the panel.

The local implementation tags the primary surface for PQ, includes the GPU
conversion changes, and uses a 2:1 surface ratio on the J614s desktop-firmware
panel. In the attended comparison the 2:1 setting made KDE's test logo visible
and improved the owner's content; this is visual evidence, not proof that the
ratio reproduces an accurate transfer curve. Do not infer measured nits from
KDE's nominal values. The owner is satisfied with visual tuning; further
calibration would require suitable measurement equipment and a validated path.

The promoted kernel source records are under
[linux-m4rch/promoted-source](../packages/linux-m4rch/promoted-source/).
Asahi's unmerged [HDR PR 431](https://github.com/AsahiLinux/linux/pull/431)
informed the early investigation; it did not establish a J614s implementation.
The [HDR admission and surface-layout tests](../experiments/hdr-j614s/) require an explicit path to the patched
kernel source; they passed against the promoted source before its extracted
build tree was retired. Full observations and provenance are at
`git show e7baa0e:docs/hdr-investigation.md`.
