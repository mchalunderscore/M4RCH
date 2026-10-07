# Allocations-enabled structural initialization batch

This experimental helper batches the relocated G16S object graph, cold RTKit
boot, root publication and bounded response capture. Explicit zero opaque
objects are fixtures, not valid production GPU configuration. It submits no
rendering work and installs no SGX MMIO descriptors. Firmware may fault.

`build-root-envelope.py` generates its bytes from the tested parser fixture;
it validates the maintained kernel source/configuration and records hashes.
`run-root-envelope.py --graph --run` validates fresh captured ADT/kernel/firmware
identity, performs the owned shadow allocation/walk, unloads that shadow-only
instance, then publishes once in the cold firmware run. It stores firmware DATA
and all object pages after stopping ASC. No automatic reboot.

Published mappings, backing and power reference remain pinned until reboot.
Never force unload. Pre-publication handshake-only cleanup uses the established
acknowledgment/core-stop/empty-FIFO checks. A returned module, consumed pointer
or modified status word is not evidence of initialization or rendering success.

First native batch reached a null GFender descriptor access after root parsing;
see docs/evidence/2026-10-07-gravity-gpu-native-graph-result.json.
