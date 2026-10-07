# T6040 fixed-host role provider investigation

The live a9112962 boot has three initialized DWC3/xHCI controllers but no
/sys/class/usb_role entries. All three PD providers remain deferred with
SN201202x initialization failed. User's boot-connected right-port YubiKey was
absent before the GPU trial; left-port passkey works. This is not proof of a
GPU-induced USB regression or of a common cause with another project.

Source mismatch: dwc3-apple.c fixed-host branch initializes xHCI then returns
before dwc3_apple_setup_role_switch(). Live DT requests usb-role-switch on all
three controllers. tipd/core.c common probe requests the connector's graph role
switch; roles/class.c returns -EPROBE_DEFER if the matching provider is absent.
Exact failing probe stage still needs native diagnostic confirmation; several
other probe operations can return a deferred dependency too.

Candidate patches/experimental-t6040-fixed-host-role-switch.patch registers the
provider only for T6040 after successful fixed-host initialization, outside the
initialization lock. Keeps device-role rejection; unwinds core on registration
failure. Other fixed-host platforms unchanged. W=1 external module build passed.
Not installed, selected or loaded. Protected maintained source/config unchanged.
Do not unbind/reset working host controllers while the current hub is in use.

Reproduce: copy DWC3 headers and dwc3-apple.c into an isolated external-module
directory, apply the candidate there (not to the protected maintained tree),
write Makefile containing obj-m += dwc3-apple.o, then:

    make -C out/gpu-gravity-contract/linux M="$PWD/out/usb-role-probe" ARCH=arm64 LLVM=1 W=1 modules

The current out/usb-role-probe contains the compiled candidate. Native test
requires an isolated next-boot module/kernel recipe with original module backup
and rollback. On that boot, BEFORE GPU work, inspect usb_role/typec class entries,
PD deferred-probe reasons, controller bindings and USB IRQs. Check known device
in right and both left ports, both connector orientations, cold and warm boot.
If PD remains deferred, add stage-specific common-probe error diagnostics and
resolve the actual next dependency. Do not bypass mux/IRQ/role ownership checks.
No port-supply or orientation conclusion comes from root hubs alone.

## Staged USBR001 boot

User authorized next-default staging. GRUB entry3 now boots the same kernel
with a separate initrd that loads candidate glue before root udev. Original
module tree/initrd/entry1 unchanged. Stage script validates CPIO member bodies
and module hashes. Restore /boot/USBR001/grub-before.cfg to /boot/grub/grub.cfg
for rollback. No native trial completed or package promotion yet.

## Promotion result

Trial fcfa7ebf: user confirms all three ports work. Three role providers, two PD
controllers bound, right YubiKey enumerated;0-0a ENODEV remains. Package revision
7.1.13-2 contains exact tested module plus package-owned init/hook early-load
recipe. Regular GRUB default1 restored, USBR001 backup entry3 kept. One regular
boot validation still due. Package-fix.py builds revision2 from pinned baseline
payload, no full kernel rebuild; future source rebuild must apply the patch.
