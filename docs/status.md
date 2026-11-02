# Current J614s status

The running kernel is the forked `7.3.0-1-14-ARCH` (boot ID `e6a81654-428a-48c5-bb2d-e3a84209ac03`). The forked kernel, Aura, U-Boot, Mesa, audio and UCM packages are installed. The standard updater's full kernel DTB set and Aurora's default initramfs booted successfully without J614s-specific package settings. The metadata-only transition package has been uninstalled. GRUB now has one persistent entry with the host-local `user4k=on` and `appledrm.show_notch=1` preferences; that final regenerated configuration has not yet been booted. See [recovery](recovery.md) and the [update workflow](aurora-update-workflow.md).

Pacman is configured for Aurora's official binary feed and the other existing repositories, not a binary feed built from the fork. The fork-built package families are held in `IgnorePkg`; in particular, Aurora's current Mesa version sorts newer and would otherwise replace the local build.

The installed Mesa passed a post-boot Zink surface-reuse test and includes the fix proposed in Aurora Mesa #138. The installed microphone packages carry the J614 UCM and DSP proposals. Internal speakers are disabled until a J614s protection profile is qualified. The custom sudo bridge has been removed; the user's zsh alias invokes `run0`, and ordinary sudo uses the standard fingerprint and password PAM stack.

The J614s device tree names `apple/tpmtfw-j614s.bin`, which is not installed.
The current boot's keyboard and trackpad worked through the retained MTP
session without requesting it; the new driver's interface-start path requests
the firmware if it must start the interface. Trackpad recovery from a failed
handoff is therefore unqualified. An external mouse remains a useful fallback if that handoff fails.

See [hardware status](../FEATURES.md) for observations and gaps and the [update workflow](aurora-update-workflow.md) before refreshing Aurora components. Package versions and runtime behavior can change; check the live system before acting on this snapshot.
