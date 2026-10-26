# Native result: FAILED; reverted

The 2026-10-07 trial hid the GRUB menu and caused the Linux MTP coprocessor
wake to time out, losing built-in keyboard and trackpad. The original stage 2
has been restored. Do not deploy this variant again until handoff is fixed.
See docs/evidence/2026-10-07-boot-keyboard-failure.json.

# J614s boot keyboard trial

The qualified Gravity NVMe loader deliberately disabled keyboard and USB input.
This variant enables `DM_KEYBOARD`, `APPLE_KEYB`, and `APPLE_MTP_KEYB`, using the
existing Gravity MTP driver. USB, PCI, the fixed NVMe bridge, enrolled stage 1,
and the exact installed stage-2 m1n1 binary remain unchanged.

Two U-Boot-only nodes describe the MTP helper and keyboard. The control DT adds
only these nodes; every original property is checked unchanged. `archnvme`
removes them from its separate handoff copy before applying the Linux overlay.
The working Linux HID/DockChannel binding remains intact. Five individually
checked MTP windows are added to U-Boot's existing narrow MMU mapping.

The current captured ADT lists local data at `0x514b34000`, remote endpoint data
at `0x514b2c000`, FIFO size `0x800`, ASC at `0x514600000`, mailbox at
`0x514608000`, and SRAM at `0x514c00000` (size `0xac000`). The primary m1n1
DockChannel implementation describes the paired FIFO/data banks. This qualifies
addresses and the proposed layout, not keyboard behavior on this board.

Sources: [pinned Gravity keyboard driver](https://github.com/GravityLinux/u-boot/blob/a2f6913694ff26908c16948af3f8372429782263/drivers/input/apple_mtp_kbd.c),
[m1n1 DockChannel implementation](https://github.com/AsahiLinux/m1n1/blob/main/proxyclient/m1n1/hw/dockchannel.py).

## Rebuild

Download the U-Boot revision in `profiles/gravity-loader.json`, then apply
`patches/gravity-uboot-j614s.patch` followed by
`patches/gravity-uboot-j614s-keyboard.patch` in the source tree. Build natively:

```sh
make apple_sdboot_defconfig
make -j8 UBOOTRELEASE=u-boot-m4rch-2026.07-mtpkbd LOCALVERSION=
```

From this repository, package against the original qualified boot bundle:

```sh
python3 sdboot/keyboard-stage2.py --uboot-tree /path/to/uboot --output out/keyboard-stage2
```

If the keyboard bundle is already installed, add
`--base-bundle /boot/keyboard-trial/boot-before.bin`. The base manifest remains
`/boot/loader-alignment/loader-manifest.json`; the trial's receipt is separate.
The packer requires the exact original bundle/component hashes, reviewed source
hashes and loader config. It checks ARM64 Image framing and both DT preservation
and boot-node removal. It never deploys or reboots.

## Native qualification and rollback

After installing the trial, reboot normally. At the GRUB menu, press an arrow
key to interrupt the countdown and move the selection, then boot the same GPU
contract entry. Check built-in keyboard/trackpad and USB again in Linux.
A successful build is not evidence that keyboard input works yet.

The backup `/boot/keyboard-trial/boot-before.bin` restores the previous stage 2:

```sh
sudo cp /boot/keyboard-trial/boot-before.bin /boot/boot.bin
sync
```

If Linux fails to boot, mount M4RCHESP from macOS and copy
`keyboard-trial/boot-before.bin` over `boot.bin` there. No re-enrollment is needed.
