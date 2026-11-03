# m4rch

J614s (MacBook Pro 14-inch M4 Pro) hardware enablement and Aurora-based package integration. The work builds on [Aurora Silicon](https://github.com/aurora-silicon).

The machine runs the forked Aurora kernel, Aura, U-Boot, Mesa and audio packages. Aurora's shared boot configuration and standard stage-two updater booted successfully without a J614s configuration package. Internal speakers remain disabled pending board-specific protection and qualification.

The [Aurora ALARM fork](https://github.com/mchalunderscore/alarm-aurora/tree/j614s/full) maintains the modified component recipes. M4RCH retains recovery notes and current hardware limitations. Installer development is in the [Aurora installer fork](https://github.com/mchalunderscore/aurora-installer/tree/j614s/full).

The [Aurora NixOS fork](https://github.com/mchalunderscore/nixos-aurora/tree/j614s/full) pins the same experimental component stack. Its NixOS configuration and installer have not been hardware qualified; the branch is based on an older Aurora revision and its image builder is disabled pending boot and update review.

- [Current status](docs/status.md) and [hardware evidence](FEATURES.md)
- [Setup reproduction inventory](docs/setup-reproduction.md) and [update workflow](docs/aurora-update-workflow.md)
- [Boot and authentication recovery](docs/recovery.md)
- [Installer firmware investigation](https://github.com/mchalunderscore/aurora-installer/blob/j614s/full/docs/j614s-firmware-investigation.md)

Boot components, board device tree and firmware handoffs must be reviewed as a coordinated set. Machine-specific firmware and retained build inputs are not distributed in this repository. Check the recovery instructions before changing the boot chain.
