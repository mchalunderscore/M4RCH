# Additive boot installation for the checked GFX reset trial

The saved installer is a source template. Copy it into the reviewed artifact
directory before binding it in `artifact-receipt.json`; it resolves inputs
relative to its own location. The prepared directory is
`out/gfx-reset-install`. Default invocation audits only. Execution requires
root, `--execute`, the exact reviewed receipt SHA256, and a separately prepared
writable boot mount. The installer never changes mount state or reboots.

Generate the initramfs in the workspace with `mkinitcpio --nopost`, the separate
release's module root (`-r`), workspace hook directory (`-D`), explicit config
(`-c`) and workspace output (`-g`). The actual build command, installed baseline
hook/init hashes, root geometry and extraction checks are in the saved build
receipt and boot evidence. Clone the installed GPU-contract init/hook to preserve
the early `dwc3_apple` preload. The embedded SART/NVMe/USB modules must match the
new kernel's staged modules.

Do not use the generic package or boot-update hooks for this experiment. They
can rebuild all baseline presets and regenerate the current menu from a stale
template. The isolated installer publishes only the new release's module tree,
`/boot/GFXR001` artifacts and an appended GRUB entry. It preserves the exact old
menu prefix and default index1, holds the normal updater lock, validates fixed
reviewed hashes at publication, and publishes the menu last. A partial failure
leaves new paths and a progress receipt for inspection, without an automatic
retry or removal. The original menu is retained as `grub-before.cfg`.

This install changes no live GPU state. The initial installation preserves default1. The user later requested default4
for `7.1.13-m4rch-gpu-reset (GFXR001 checked reset trial)` because GRUB input
is unavailable; that separate change is recorded in the installation evidence.
GPU execution, reset coverage and DMA retirement are separate test outcomes;
none follows from a successful boot installation.
