# DCP001 initial Linux preparation (2026-10-07)

Read-only baseline: /boot/DCP001/captures/dcp-20261007T211915Z-baseline-69ksjd24.
131 selected DT properties captured; no live DCP/DISP/crossbar/panel nodes found.
Only chosen framebuffer is present, serviced by simpledrm. DRM_APPLE disabled.
Native source contains Gravity's IOMFB26.6 path, but exact26.6.2 gate and hardware
matching only explicitly cover T8132. T6040 topology/providers/stream identities,
bw-scratch, shared DISP0 aperture and firmware reservations must be constructed
and verified before any takeover boot. Do not copy boot-specific segment addresses.

Prepared Kconfig-only candidate from unchanged maintained .config, with
DRM_APPLE=m and DRM_APPLE_AUDIO=n. Resolves DRM_GEM_DMA_HELPER=m,
DRM_KMS_HELPER=y, APPLE_PMP_REPORT=y, MULTIPLEXER=y; existing RTKit/backlight
remain enabled. Not compiled, installed, selected or loaded. Maintained config
SHA c6bc96eb25e6831820737d36695a81779ac43f2377c1ac37f6eefb0374de1fae
unchanged. Candidate/config diff in private return captures.

Reproduce from repository root:

    mkdir -p out/dcp001-config
    cp out/gpu-gravity-contract/linux/.config out/dcp001-config/candidate.config
    out/gpu-gravity-contract/linux/scripts/config --file out/dcp001-config/candidate.config --module DRM_APPLE --disable DRM_APPLE_AUDIO
    make -C out/gpu-gravity-contract/linux KCONFIG_CONFIG="$PWD/out/dcp001-config/candidate.config" ARCH=arm64 LLVM=1 olddefconfig

Future compilation needs an isolated output tree/config with dependencies, not
mutation of the currently maintained build. Do not load a newly built module
merely because it compiles. No Apple binary or derived disassembly tracked.
