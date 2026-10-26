# AURG016 integrated 16-core GPU experiment

This uses the same Aurora kernel image and board handoff as the successful
revision 5, with a rebuilt Asahi module. The option `t6040_16core=1` admits only
T6040 with one die, two ten-slot clusters and masks `0x3db,0x3db`. Default module
behavior retains upstream's layout guard. The 20-slot compute and two-cluster
render buffers are an experimental hypothesis on this fused SKU, not a measured
16-core layout. Normal rendering, compute, recovery and firmware checks remain
enabled. No firmware, render-node or synthetic-test milestone is presented as
proof of working acceleration.

The pinned private Aurora Vulkan driver supplies Zink OpenGL. The session uses
`KWIN_RENDER_NODES` to select Asahi while the existing simpledrm device presents
the panel. Native DCP remains disabled. Mesa and tools include a private fallback
library directory for absent SONAMEs such as LLVM19; Arch's normal ABI libraries
take precedence over those fallback dependencies. Built-in speaker amplifiers
remain disabled and their modules are omitted.

The default GRUB entry is `Experimental Aurora 16-core GPU (Plasma/Zink)`.
SDDM, when installed, is enabled temporarily and ordinary Plasma Wayland session
entries use the GPU wrapper for this boot. Select Plasma Wayland at the login
screen. The existing AURD001 entry and the explicit last-successful revision 5
entry remain available. The GPU console entry provides a recovery shell with
the same experimental stack when a desktop session cannot start.

If the root has no display manager, log into a local TTY and run:

```sh
/run/aurora-direct/with-mesa dbus-run-session /usr/bin/startplasma-wayland
```

Use the desktop normally. For a visible Vulkan workload in that session:

```sh
/run/aurora-direct/with-mesa /opt/m4rch-aurora-direct1/bin/vkcube --wsi wayland
```

Revision 1 registered Asahi on this native 16-core GPU, but Plasma failed before
rendering: its user service retained old QPainter overrides and its GBM plugin
could not resolve libgallium without LD_LIBRARY_PATH. Revision 2 wraps KWin's
own service launch and supplies relative RUNPATHs for every bundled ELF,
including GBM/DRI plugins. The EGL vendor JSON names the private library explicitly.
Those revisions did not produce a working native desktop.

Revision 2 reached Zink but could not select a Vulkan physical device. Native
journal metadata shows KWin running with CAP_SYS_NICE (effective mask 0x800000).
The Vulkan loader ignores environment ICD overrides in secure execution mode.
Revision 3 exposes the private ICD and EGL vendor through RAM-backed trusted
system discovery directories, preserving installed files and KWin's capability.
The fix was reproduced offline with an actual file-capability executable:
AT_SECURE=1 hid the environment override and the trusted manifest successfully
created an instance of the private Vulkan driver. This does not prove rendering.

The owner subsequently reported a working accelerated Plasma Wayland desktop
on revision 3 after launching the session command manually from tty2, with
glxgears around 2400 FPS with vblank disabled. SDDM repeatedly crashed. This is
an owner-reported native success. The subsequently preserved logs identify
Apple M4 Pro (G16S B1) through the Borealis Vulkan driver and the Zink OpenGL
renderer. FPS alone is not used as renderer identification. The report
is saved in `out/aurora-direct/gpu16/native-attempt-3/owner-report.json`.

The SDDM failure is its Xorg server segfaulting during GLX/AIGLX initialization.
Revision 4 changes only display-manager startup and collection: it uses a
temporary Wayland SDDM configuration and runs its KWin compositor with the
same private graphics wrapper. Existing autologin settings are retained. The
kernel, GPU module and Mesa binaries stay identical to working revision 3.
The native journal also contains DRM modifier errors, a lost GPU client, and
Flatpak access errors for the private runtime; acceleration is established,
but broader graphics/application stability is not qualified by this result.

A recorder saves the journal and dmesg immediately into a unique
`/boot/AURG016/return-*` directory and follows startup for 90 seconds, flushing
every five seconds. It does not submit GPU work or gate desktop startup.
A separate service records standard Vulkan driver discovery alongside desktop
startup, so its device-enumeration result is retained even during a short boot.
A timer adds one full return bundle approximately two minutes after boot,
including kernel/module state, Vulkan/EGL diagnostics and available KWin support
information, at `/boot/AURG016/return-*`. Collect again after exercising the
desktop or after a failure:

```sh
sudo sh /run/aurora-direct/collect.sh
```

Full snapshots use a new `full-*` child directory beneath the startup return
directory, avoiding the recorder-directory collision found in revision 3.

Automatic collection is diagnostic and does not gate desktop startup or prove
rendering. Kernel timeouts can prevent a diagnostic process from completing;
the collector writes the base logs before querying graphics. If the screen
hangs, photograph it and return to macOS. No automatic reboot is performed.

After mounting the ESP in macOS, restore the ordinary AURD001 default with:

```sh
python3 experiments/aurora-direct/select_boot.py test
```

Or restore the original AURA001 loader/configuration pair with `stable`.
Select the GPU candidate again with `gpu16`. The selector verifies the GPU kit
before selecting it and preserves the loader/configuration pairing.

Failed early AURD001 revisions 1–3 were relocated to hash-verified workspace
copies under `out/aurora-direct/esp-archives`; successful revisions stay on the
ESP. Source provenance and installed-file checks are in the GPU kit manifest
and staging receipt. The failed GPU revision 1 kit and its native journals are
also preserved under `out/aurora-direct/gpu16/native-attempt-1`; revision 2 logs
are in `native-attempt-2`, and replaced GPU kits are hash-archived in `backups`.
AURG016 revision 3 has an owner-reported working manual desktop; SDDM startup
and wider stability remain unresolved. The exact revision 3 initramfs is also
preserved on the ESP as `AURG016.saved-r3`, using the unchanged AURD001 kernel.
GRUB offers `Aurora GPU - working revision 3 (manual Plasma)` as a recovery
entry which boots directly to a TTY. Revision 4's Wayland SDDM fix still requires
a native boot test.
