# m4rch

Arch Linux ARM packages for the Apple MacBook Pro (14-inch, M4 Pro),
Mac16,8 / J614s / T6040. Kernel, m1n1, U-Boot and Mesa builds derive from
[Aurora Silicon](https://github.com/aurora-silicon).

The working setup includes GPU acceleration, the internal 120 Hz display,
brightness and approximate, uncalibrated HDR, Wi-Fi, input, USB3, camera and
microphone. The owner reports Steam/Shinri and cooling are about as good as
on macOS after extended use; this is practical experience rather than a
claim that every workload has been qualified.

- **Sleep:** attended suspend and lid wake passed on AC and battery. A USB-C
  TV also returned after one suspend. See [sleep investigation](docs/suspend-boot-investigation.md).
- **VRR:** the promoted display stack enables VRR and reapplies it after wake.
  The desktop looked normal; physical refresh variation has not been
  independently measured. See [VRR investigation](docs/vrr-investigation.md).
- **External displays:** HDMI and a USB-C TV each produced a picture. HDMI
  flicker and scaling were observed but not diagnosed. The normal GRUB entry
  contains the promoted stack and has booted normally; external output under
  automatic driver loading remains to be tested. See
  [external display investigation](docs/external-display-investigation.md).
- **Power profiles:** the installed daemon provides Power Saver, Balanced and
  Performance. Power Saver caps P-cores at 3.300 GHz and E-cores at 1.788 GHz;
  Balanced and Performance retain the existing maxima. An attended sleep/wake
  passed with Power Saver active. See [power-profile investigation](docs/power-profiles-investigation.md).
- **Audio:** the internal microphone is configured, with its local processing
  package installed. The headphone jack awaits a direct test. Internal speakers
  remain disabled pending machine-specific protection evidence; see the
  [speaker safety assessment](docs/j614s-speaker-safety-investigation.md).

[Package recipes and installation notes](packages/README.md) describe the
installed system and build limitations. The existing cached installation kit is
older than the current promoted stack and must not be reapplied blindly. The
working boot chain uses the local `archnvme` bridge; Aurora's standard boot
work is being tracked in the [boot comparison](docs/boot-upstream-comparison.md).

`make check` validates the retained source tests. `make packages` is a historical
macOS-hosted container workflow that still needs local inputs and validation
updates; it is not a one-command rebuild of the installed system. See the
[package guide](packages/README.md) before building or installing packages.

For maintenance, build limitations and recovery status, see the [maintenance inventory](docs/installation-maintenance.md).

The old SD-card implementation and dependent Aurora trial workflows have been
retired. Historical tracked sources are available in Git history at `bce491f`;
the current installation and build workflow is documented in the package guide.
