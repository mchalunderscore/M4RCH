# Reset-kernel USB recovery and persistence

On boot `ce6572c9-2491-4c87-8e27-6e82cc0ac657`, root normally unloaded the stale `dwc3_apple` glue and loaded the corrected reset-kernel module. Both commands returned zero; no force unload or reboot occurred. Dmesg records the USB disconnects, all three host controllers restarting, and device enumeration including the right-port YubiKey. All three DWC3 role providers appeared and all three SPMI PD devices (`0-0a`, `0-0c`, `2-0c`) bound. PCIe Wi-Fi remained up. The recorded USB reload preceded GPU publication.

This confirms recovery of the missing USB role-provider dependency in the current boot. It does not establish GPU teardown, reset coverage, execution, or repeatable GPU recovery. Physical ports and both connector orientations were not exhaustively retested during this correction; PD IRQ support remains separate from the observed binding/polling success.

Root then installed the exact reviewed glue module and corrected initramfs with hash checks and backups. This changed two files:

| Installed file | Corrected SHA-256 | Original backup |
| --- | --- | --- |
| `/usr/lib/modules/7.1.13-m4rch-gpu-reset/kernel/drivers/usb/dwc3/dwc3-apple.ko` | `6491446266d7ab6ba4ec3b3c0229d609b2b465b73ab065a0834d66265babdd98` | `/boot/GFXR001/usb-before-ce6572c9/dwc3-apple.ko` |
| `/boot/GFXR001/initramfs.img` | `86dec6ff3b9a4aef1678632d1fcf2371f01e9755c3f39ec15a42fc0b9485d01d` | `/boot/GFXR001/usb-before-ce6572c9/initramfs.img` |

A subsequent independent read-only observation verified both installed hashes and both original backup hashes, all three PD bindings, all three DWC3 bindings and role providers. The reset kernel Image and GRUB configuration remained unchanged; GRUB still defaults to entry 4, `7.1.13-m4rch-gpu-reset`. The corrected initramfs retains the prior early glue preload and differs only in its glue-module member, as established by the offline CPIO comparison.

The next boot using this corrected initramfs, including a cold boot, has not yet been verified. Future source rebuilds must include the already promoted fixed-host role-switch patch: the retained maintained baseline source still omits it. Historical offline qualification documents remain unchanged. The JSON companion binds root's native reload/promotion receipts, before/after logs, independent post-promotion observation and prior artifact review. This documentation agent made no hardware, sysfs, boot or installed-file changes.
