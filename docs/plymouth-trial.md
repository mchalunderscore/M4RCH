# Plymouth

The installed Plymouth setup uses the Breeze theme, the standard mkinitcpio
`plymouth` hook after `udev`, and `quiet splash` in the normal GRUB entry. The
normal entry booted on 28 October. The attended trial had reached Plasma but
showed flicker between Plymouth and console messages; the exact cause was not
established. Shared DCP firmware TEXT reservations produced overlap messages
before Plymouth was added as well.

The old trial services, separate trial image and ESP rollback files were retired.
See [maintenance and recovery](installation-maintenance.md) for the current
boot chain. The historical trial record is preserved locally in
`out/documentation-before-condensing-20261028.tar.gz`.
