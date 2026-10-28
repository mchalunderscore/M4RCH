# Internal-panel VRR

The promoted J614s stack requests VRR from display firmware at the internal
panel's 120 Hz mode and reapplies it after wake. The firmware reported VRR
enabled after wake and the owner reported normal desktop and lid-wake behavior.
Actual physical refresh-rate variation has not been independently measured.

The first trial exposed KMS VRR to KDE, but KWin's normal toggle did not
complete the modeset required by this driver. The promoted local patch hides
the KMS VRR option and requests VRR through the firmware path instead; the
missing KDE toggle is intentional. Wake uses a fixed 60 Hz intermediate mode
before returning to 120 Hz with VRR requested. This is a J614s workaround,
not proof of a general KWin defect or a calibrated refresh measurement.

The promoted source records are in
[linux-m4rch/promoted-source](../packages/linux-m4rch/promoted-source/).
Aurora [#451](https://github.com/aurora-silicon/linux/pull/451),
[#515](https://github.com/aurora-silicon/linux/pull/515), and Asahi
[#477](https://github.com/AsahiLinux/linux/pull/477) informed the work; their
board and hardware scope differs. Full trial details and optical-test caveats
are at `git show e7baa0e:docs/vrr-investigation.md`.
