# Aligned native PM and render-target composition

The PM exporter optionally consumes --render-profile and aligns only exported case0 to the checked render fixture. Full initialized/retained chain checks still execute for all256 cases. Case0 now has accelerator4e4=2, flags6d0=0, accelerator11188=16GiB and16 scene records. Native scene allocation becomes69824bytes rather than4224. The memory-provider budget remains a supplied256KiB policy fixture, not a hardware claim.

prepare-native-target-pm-fields.py hash-checks both prepared profiles, their artifacts and the private binary. It requires matching topology/memory/flags/record count, runs the complete native GTP allocation/packing success path, then the complete TA render-target loader and complete3D render-target loader. Whole-byte expected results, unchanged source objects, all15 TA parameter fields and the7 parameter fields within the3D descriptor are checked. Resource services remain supplied; firmware aliases are proposed and not installed.

Passed:256 initialized retention chains,256 caller bindings and256 initialized parameter loads; composed GTP/TA/3D loader checks each once. Local artifacts out/native-target-pm-aligned/{pm,combined}, with per-file hashes. No kernel changes, GPU publication or reboot.

This is partial descriptor composition, not complete command serialization. PM snapshots retain randomized untouched fields and external-service identities. Rebuild actual page/ring contents against Linux-owned resources; resolve inherited defaults, copied address domains, event/cache/queue lifetimes and remaining shader/state/work fields before publication. No rendered pixels or GPU execution proved. Private implementation-derived research, not a clean-room specification.
