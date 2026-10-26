# Reset-kernel USB role-provider source gap

Boot `ce6572c9-2491-4c87-8e27-6e82cc0ac657` initialized all three DWC3 hosts but exposed no USB role providers. All three SPMI PD devices remained unbound with `SN201202x initialization failed` as a deferred-probe reason, including after one normal probe per device. No GPU publication preceded this finding.

The reset kernel rebuilt DWC3 glue from maintained source `904b3c03eaa422440a40a3fb276915f9230340ec0ec9f49a732ee5a36c10ba70`. Its fixed-host branch initializes the host and returns before `dwc3_apple_setup_role_switch()`. All three live DWC3 nodes request `usb-role-switch` while specifying `dr_mode = "host"`. TPS common probe requires the linked role provider; class lookup returns `-EPROBE_DEFER` when the provider is absent. This establishes a source-level dependency failure. The exact current failing return site was not traced live.

The same gap was resolved and promoted on 2026-10-07 using `patches/experimental-t6040-fixed-host-role-switch.patch`. The promoted package replaced only the glue module and early loading recipe, preserving the maintained source. Its README explicitly required future source rebuilds to apply the patch. Regular boot `6a0a6204-876f-4fd5-9330-60efe15d5186` subsequently verified all three PD bindings and role providers. Source-preservation checks for the reset kernel preserved the maintained source but did not account for this separately promoted module correction.

## Prepared correction

The existing patch applied cleanly to an isolated copy of reset-kernel DWC3 glue and headers in `out/gfx-reset-usb-fix/module`. Patched source `7ca78866b27aa670134ded04820c26b7cabfb17640c410ee5cf3b307e0aa5b0c` is byte-identical to the previously promoted source. The external module built with `LLVM=1 W=1` without diagnostics:

- Module: `/home/alice/Desktop/m4rch/out/gfx-reset-usb-fix/module/dwc3-apple.ko`
- SHA-256: `6491446266d7ab6ba4ec3b3c0229d609b2b465b73ab065a0834d66265babdd98`
- Build ID: `39d100615339cf32659ae189c63dafad540753ab`
- Vermagic: `7.1.13-m4rch-gpu-reset SMP preempt mod_unload aarch64`

Its `.text`, `.rodata`, `.rela.text`, `.init.text` and `.exit.text` are byte-identical to the old promoted glue module. The new module binds the reset-kernel ABI; the old contract-vermagic module must not be loaded into the reset kernel. Reviewed kernel source/config/artifact fingerprints and both installed glue modules remained unchanged during this preparation.

A workspace-only clone of the reset initramfs inputs replaced only the glue module. `mkinitcpio --nopost` completed without sudo, and extraction executed no init code. Direct CPIO member comparison verified all five early members and all 295 main member names, modes and bodies unchanged except the corrected glue. `/init`, root geometry/release configuration, other modules and binary dependencies are byte-identical. The corrected initramfs is `/home/alice/Desktop/m4rch/out/gfx-reset-usb-fix/initramfs.img`, SHA-256 `86dec6ff3b9a4aef1678632d1fcf2371f01e9755c3f39ec15a42fc0b9485d01d`.

## Native recovery boundary

A normal live replacement is technically possible: module unloading is configured and the observed `dwc3_apple` reference count was zero. Unloading and loading glue disconnects and re-enumerates every USB device; no uninterrupted USB guarantee follows. Wi-Fi was up through PCIe and USB Ethernet was down at the read-only observation. Root alone decides and performs any bounded native trial. This agent did not unload/load drivers, write sysfs, mount, reboot, modify installed files, or touch the GPU. No native recovery success is claimed here.

The JSON companion binds receipts, patch, prior promotion and regular-boot evidence, plus the current failed probe capture. Private/raw captures remain under ignored `out/`.
