# Aurora package candidates

The local signed Aurora testing database listed these 41 packages on 1 November
2026. Every entry has a downloaded signed stock artifact or the promoted
patched U-Boot artifact; the manifests are in the cache directories below. The
list includes 24 installed packages, available replacements and optional
packages; it is not a statement that each artifact is safe or that every
optional component should be installed. Versions reflect
the locally synced database, which can lag current upstream. Review exact
source pins, package signatures, dependencies, install hooks and J614s
compatibility before accepting an artifact.

- **U-Boot:** `2026.07.aurora6-1.1` built from an Aurora recipe, booted and
  installed; it is held for reviewed updates. See [integration](aurora-package-integration.md).
- **Aura:** [built J614s overlay](../packages/aura-j614s/README.md) is installed; its stage two booted successfully and its bundle was promoted as `aura-j614s-boot 20261101-3`. Stage one has not been installed or booted.
- **Kernel:** [staged recipe and built kernel and headers](../packages/linux-aurora-j614s/README.md);
  9.3 booted from its persistent default paths. The owner confirmed an
  external display worked on the promoted Aura boot, with HDMI connection and
  disconnection in the kernel log; USB-C display output remains untested.
- **Mesa family:** the local Zink fix needs evaluation against Aurora's host,
  FEX guest, Flatpak, OpenCL and software Vulkan outputs as a coordinated set.
  Aurora's FEX guest and Flatpak packages depend on the exact host pkgrel, so
  a patched host release requires compatible package metadata and artifacts.
  [`stage-aurora-mesa.py`](../packages/tools/stage-aurora-mesa.py) stages the
  three Aurora recipes at commit `2d2555e` with a common pkgrel `1.1` and the
  Zink patch, including the Flatpak manifest. All three staged source checks
  passed; the real native and FEX source preparation applied the patch without
  fuzz. The native build produced Mesa, Vulkan, Rusticl and Lavapipe packages
  at `cache/mesa-aurora-c208-staged/mesa-aurora/`; Aurora's `check()` reported
  122 passes and no failures before a packaging-only ownership adjustment and
  repackage. With the uninstalled stage libraries selected explicitly,
  `vulkaninfo` enumerated the M4 Pro as Borealis and `eglinfo` initialized
  Wayland Zink. `glxgears` rendered 575 frames in 5 seconds via Zink under the
  current Xwayland session, with no corresponding GPU errors in the kernel log.
  A second run selected the actual extracted Mesa and Vulkan package libraries
  and rendered 593 frames in 5 seconds.
  These checks do not establish the reported Wayland OSD lifetime fix under
  repeated surface reuse, FEX compatibility or extended workload stability.
  A [temporary stock FEX bridge](../packages/mesa-aurora-fex-bridge/README.md)
  preserves Aurora’s same-revision payload with adjusted dependencies; it does
  not carry our patch or establish FEX runtime compatibility. The patched
  guest build is not needed for the owner's working Proton FEX setup as
  currently observed: the owner reports it works, and the Aurora overlay
  service was inactive because its stock guest directory was absent.
  This does not establish every library Proton loads.
  The patched
  FEX recipe has not produced a package. An isolated x86_64 Arch root
  under QEMU verified its signed dependencies and began the real build, but
  GCC 16.2 repeatedly crashed compiling `nir_constant_expressions.c` at `-O3`,
  including when retried alone. The same source compiled at `-O1`; this does
  not establish a safe or equivalent release build. The emulated Clang could
  not map `libedit.so.0`. QEMU upstream has separately documented [guest
  page-size](https://gitlab.com/qemu-project/qemu/-/issues/2157) and
  [`mremap`](https://gitlab.com/qemu-project/qemu/-/work_items/3410) failures
  when host pages are larger; those reports do not prove the cause here. A
  native x86_64 builder or a properly qualified
  workaround is still needed. The partial tree and logs are retained under
  `cache/fex-x86-bootstrap/` and `cache/mesa-aurora-c208-staged/`; the
  invocation logs are `/tmp/m4rch-fex-build.log` and
  `/tmp/m4rch-fex-failed-target-retry.log`. The Flatpak extension was built in an isolated SDK environment for both 25.08
  and 26.08, and Aurora's repository validation passed for each branch. The
  earlier `aurora-flatpak-gl` 1.1 candidate has SHA-256
  `3de2e4d6ec51e935633742c498086c0d22cba1fb71b1d606793e24b0dbc72964`.
  On 1 November, Flathub's GlxInfo and VulkanInfo applications ran against
  both 25.08 and 26.08. Default GL reported accelerated M4 Pro rendering;
  forcing Zink reported Zink on Borealis and rendered glxgears on both
  runtimes. VulkanInfo enumerated the M4 Pro Borealis GPU on both; there were
  no corresponding GPU faults in the kernel log. This is a short test, not a
  general application or long-term workload qualification. VulkanInfo also
  reported a shader-cache timestamp warning for the llvmpipe software
  fallback; isolating Borealis emitted no warning and isolating llvmpipe
  reproduced it on both runtimes. In the extension `libLLVM.so.22.1` lacks a
  GNU build ID and has epoch-zero OSTree mtime; Mesa's llvmpipe cache code
  asks for an LLVM build identifier and falls back to mtime, consistent with
  the warning. A Flatpak-only LLVM identity workaround was subsequently
  tested and installed, then removed at the owner's request on 2 November.
  The restored `1.1` package keeps the Zink fix. VulkanInfo enumerated the
  M4 Pro and llvmpipe on both restored runtime branches; GlxInfo with Zink
  selected also reported the M4 Pro on each. See [Flatpak cache notes](../packages/aurora-flatpak-gl/README.md).
- **SEP:** The signed repository packages `aurora-sep 1-15`,
  `libfprint-aurora 1.94.100-3` and `fprintd-aurora 1.94.5-1` are installed;
  the last replaced distribution `fprintd`. The new SEP service changes
  calibration setup, while its loader still explicitly requests
  `xart_writes=1 provision_keybag=1`. The loader was initially inactive and its
  timer masked; after setup, enrollment survived a reboot and
  a fingerprint matched. The SEP timer is now enabled.
  The signed artifacts remain in `cache/aurora-sep-stock-candidates/`.
- **Speaker guard:** Signed stock `speakerguardd 0.1.12-4` is installed;
  its service remains disabled and inactive on this J614s. The old signed
  package is in `cache/speakerguardd-update-20261101/`. This does not enable
  or qualify the internal speakers.
- **ALSA UCM:** Aurora's installed package has no J614 HPAI profile. The
  [staged Aurora recipe](../packages/tools/stage-aurora-ucm.py) adds only a
  J614 name pointing to Aurora's existing three-channel microphone profile;
  it does not configure speakers. It produced the installed candidate
  `cache/aurora-ucm-j614s/staged/alsa-ucm-conf-aurora-10.aurora2-2.1-any.pkg.tar.xz`
  (SHA-256 `2e4adf5672e8cb543fffcb4a824648c36f5e9586fbd675915dd5ad882abee33e`).
  On the real J614s card ALSA reported three-channel FLOAT_LE capture at
  48 kHz and the `Internal Mic Jack` control; one second was captured to
  `/dev/null`. An isolated configuration assembled from the candidate package
  resolved `HiFi`, three channels, the actual card and the same jack control.
  Audio quality, lid behavior and session integration have not been tested.
- **Other installed packages:** The initially identified stock updates are retained
  in `cache/aurora-stock-update-candidates/`. The twelve installed packages
  without a version bump are retained in `cache/aurora-stock-current-repository/`.
  Each archive matches the signed local Aurora database and its detached
  package signature. These are acquisition checks, not installation approval
  or hardware tests. Signed stock artifacts for the 17 optional, uninstalled
  repository packages are in `cache/aurora-stock-optional-candidates/`; their
  dependencies and J614s suitability have not been qualified. In particular,
  the stock `linux-aurora` artifact is not a replacement for our J614s kernel.

The twelve unchanged-version repository archives differ in SHA-256 from their
older `/var/cache/pacman/pkg` copies. Both the older ALSA UCM archive and the
current database signature verified against Aurora's key. For all twelve,
the old and new archives had matching payload paths, modes, regular-file
contents and symlink targets; `.INSTALL` and `.PKGINFO` also matched after
excluding package build date, packager and size. Archive metadata and
compression were not compared, and this does not establish installed-file
integrity. Pacman's version comparison alone will not reveal these rebuilds.

```text
aurora alsa-ucm-conf-aurora 10.aurora2-2 [installed]
aurora alsa-utils-aurora 1.2.16-1 [installed]
aurora aura 1.0.0b1.r20261101-1 [installed: 1.0.0b1-1]
aurora aurora-audio 4.1.aurora2-7 [installed: 4.1.aurora2-3]
aurora aurora-bless 0.4.4.aurora2-1 [installed]
aurora aurora-boot 20261018-5 [installed]
aurora aurora-camera-denoise 0.1.0-2
aurora aurora-firmware 20261018-4 [installed]
aurora aurora-firstboot 0.1.12-1 [installed]
aurora aurora-flatpak-gl 1:26.3.0_devel.202610310638.c208afc352e-1 [installed: 1:26.3.0_devel.202610291706.14b6b0c4531-1]
aurora aurora-keyring 20261018-3 [installed]
aurora aurora-logos 1-1
aurora aurora-neo-platform-config 0.1.0-2 [installed]
aurora aurora-sep 1-15 [installed: 1-9]
aurora aurora-system-fixes 1-5 [installed: 1-1]
aurora avd-fw 0.1.aurora1-1 [installed]
aurora bankstown 1.1.0-1 [installed]
aurora docker 1:29.9.2-1.1
aurora fprintd-aurora 1.94.5-1
aurora kinfocenter 6.8.2-1
aurora libfprint-aurora 1.94.100-3 [installed: 1.94.100-1]
aurora linux-aurora 7.3.0.aurora1-8
aurora linux-aurora-headers 7.3.0.aurora1-8
aurora mesa-aurora 1:26.3.0_devel.202610310638.c208afc352e-1 [installed: 1:26.3.0_devel.202610291706.14b6b0c4531-1]
aurora mesa-aurora-fex-guest 1:26.3.0_devel.202610310638.c208afc352e-1 [installed: 1:26.3.0_devel.202610291706.14b6b0c4531-1]
aurora mil-hwx-compiler 0.3.1-1
aurora mutter-aurora 51.1.aurora1-1
aurora omarchy-ane-tools 0.5.7-2
aurora opencl-rusticl-aurora 1:26.3.0_devel.202610310638.c208afc352e-1
aurora plasma-setup 6.8.1-1
aurora speakerguardd 0.1.12-4 [installed: 0.1.12-1]
aurora speakersafetyd-aurora-profiles 1-1 [installed]
aurora triforce-lv2 0.3.2-1 [installed]
aurora uboot-aurora 2026.07.aurora5-1 [installed: 2026.07.aurora6-1.1]
aurora udisks2 2.11.2-1
aurora udisks2-btrfs 2.11.2-1
aurora udisks2-docs 2.11.2-1
aurora udisks2-lvm2 2.11.2-1
aurora upower-aurora 1.91.5.aurora1-1 [installed: 1.91.4.aurora1-1]
aurora vulkan-aurora 1:26.3.0_devel.202610310638.c208afc352e-1 [installed: 1:26.3.0_devel.202610291706.14b6b0c4531-1]
aurora vulkan-lavapipe-aurora 1:26.3.0_devel.202610310638.c208afc352e-1
```
