# m4rch

Arch Linux ARM packages for the Apple MacBook Pro (14-inch, M4 Pro),
Mac16,8 / J614s / T6040. Kernel, m1n1, U-Boot and Mesa builds derive from
[Aurora Silicon](https://github.com/aurora-silicon).

The working hardware configuration includes GPU acceleration, the internal
120 Hz display and brightness, Wi-Fi, input, USB3, camera and microphone.
Built-in speakers remain disabled. DCP suspend/resume, VRR and external display
processors remain disabled. Headphone audio still needs a direct test.

[Package recipes and installation](packages/README.md) describe the current
setup. Modified packages use the upstream name followed by `-m4rch`.
The system uses pacman, stock mkinitcpio hooks and presets, `grub-mkconfig`,
and Asahi's `update-m1n1`. Graphics libraries install to `/usr/lib` and Plasma
uses its standard session. Routine updates use standard Arch tools; a one-time
transition script is provided alongside the packages.

```sh
make packages
```

Build artifacts and validation logs are written to `out/packages/`.
The current local build prerequisites are listed in the package documentation.
The standardized package set has booted successfully on the Mac. The latest
fan-controller revision still needs hardware verification. Steam's updater
completes, but accelerated OpenGL inside muvm currently hangs; a graphical
Steam session has not yet been verified.

The [historical SD-card workflow](README.legacy.md), its `Makefile.legacy`,
and `experiments/` retain earlier work for reference. Their update scripts are
not part of the current packages.
