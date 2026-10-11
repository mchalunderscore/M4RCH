The isolated package builder copies the distinct integrated kernel and its
matching module tree into a workspace directory. It substitutes the reviewed
external asahi_m4 module, rebuilds the original GFXN001 early storage/USB module
set, and preserves the early cpio and unrelated userspace bytes. It does not
install, select a GRUB default, load modules, or access GPU hardware.

Rebuild the package after the OF API kernel rebuild, using the matching final
external driver. The present out/gpu-native-integrated-boot-package-v15 is the
pre-OF-API artifact and must be regenerated before installation.

The new init writes `/run/modprobe.d/m4rch-native-trial.conf` before loading
early modules. This tmpfs is moved into the real root before udev starts. Its
blacklist and install-asahi_m4-/bin/false rule prevent a stale alias/module
autoload; the launcher must use explicit insmod on its hash-pinned integrated
driver. The GRUB fragment also supplies modprobe.blacklist=asahi_m4. No global
host modprobe file is installed, so fallback boots retain their configuration.

The original loader FDT must remain the boot input. The fresh binding sequence,
owned by the complete launcher on the next boot, is:

1. Verify distinct kernel release and exact hashes of launcher, driver and two
   metadata modules. Do not load asahi_m4 yet.
2. Explicitly load `m4rch_native_of_bridge_v15.ko` without an apply argument.
   This assigns a permanent phandle to the existing gfx genpd provider without
   replacing it. Explicitly load `m4rch_gpu_adt.ko` and capture its loader ADT.
3. Capture expanded live OF with `dtc -I fs` from the current devicetree base;
   `/sys/firmware/fdt` alone retains the original flat tree and lacks the new
   provider property. Capture the current boot UUID alongside these files.
4. Run `prepare_live_overlay_v15.py` with those explicit current captures and
   boot UUID. Its five physical spans must match fresh ADT, be disjoint from
   each other and current Linux memory banks, and match the ASC __DATA segment.
   Raw SGX bytes, ASC/SGX resources, mailbox IRQs and AIC owner come from these
   inputs. The overlay only describes existing loader-owned excluded memory;
   it allocates no reservation, page table, firmware or GPU memory.
5. Publish the result as `/lib/firmware/m4rch/native-current.dtbo`, then write
   `m4rch/native-current.dtbo` to the bridge module's `parameters/apply`.
   The bridge independently rejects live System RAM intersections before OF
   attachment. It retains attempted overlay/module ownership until reboot.
6. Explicitly insmod the exact integrated driver with `probe_only=0
   native_t6040_experiment=1`, then use the complete triangle UAPI/readback path.

The OF bridge needs the narrow exported `of_m4rch_ensure_phandle` API. Its
reproducible kernel patch changes only drivers/of/dynamic.c and include/linux/of.h.
`build_native_of_bridge_v15.py` builds the bridge and ADT capture against the
completed kernel together. Neither script loads them. All install/default
selection and hardware execution remain with the parent/complete launcher.

`prepare_combined_launcher_v15.py` bundles the final driver, bridge/ADT modules,
triangle UAPI executable and inputs, and portable fresh-overlay generator. Its
manifest lists every relative file path, byte count and SHA-256. The package
receipt pins that manifest and the final kernel Image; packaging performs no
activation. The generator bundles its own ADT parser and address translator,
so it does not import the offline saved-DT preparation script.

The complete launcher requires the pinned manifest hash and an explicit fresh
boot UUID. It rejects the consumed boot 29800a86-c89b-4072-b121-c40e264982dc,
wrong release/board, existing GPU/module owners, and any second `/run` claim in
the same boot. Kernel snapshot and continuous transcript capture must be ready
before loading modules. It performs the binding sequence above, then launches
the UAPI wrapper/C client in its own session for one submission. A successful
fence and validated pixels are both required for success.

The parent collection budget is 300 seconds; the triangle window is 90 seconds,
including the client's 60-second fence wait. On timeout the client process
group remains alive, preserving DRM/VM/GEM owners and any completion.json that
was written before failure. The same policy applies to a stalled insmod or
overlay-application caller. The result records PIDs/PGIDs and log paths. The
launcher never signals those groups, removes modules, unbinds the GPU, tears
down an overlay, releases their owners, or retries. Only the read-only dmesg
follower is stopped after final capture. The output directory contains
`trial.json`, stage logs, kernel transcript, fresh metadata/overlay receipts,
and `triangle/triangle.rgba` if fence/readback completed.

The saved offline FDT currently has no five GPU reserved-memory nodes, and the
gfx provider lacks a phandle. The bootloader metadata patch returns early when
the GPU node is absent; an ordinary phandle-property overlay also leaves the
live device_node lookup field unchanged. These are implementation gaps this
bridge addresses; copying a saved DTB with old reservation addresses is invalid.
