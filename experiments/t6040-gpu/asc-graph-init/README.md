# Allocations-enabled structural initialization batch

This experimental helper batches the relocated G16S object graph, cold RTKit
boot, root publication and bounded response capture. Explicit zero opaque
objects are fixtures, not valid production GPU configuration. It submits no
rendering work. The register batch installs eleven candidate SGX descriptors
using 24 read-only device pages, alongside the 21 object pages. Only qualified
profile-A core/SRAM voltage columns are populated. Firmware may fault.

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
The subsequent read-only batch passed that access, set statusA+0x14 to one,
and faulted on missing slot33 FenderRegsBumper at offsets0xa0/0xa4. See
docs/evidence/2026-10-07-gravity-gpu-readonly-register-result.json.
Mapped candidates are not individually validated merely because execution advanced.

Current diagnostic variant adds one owned read-only RAM page for slot33. It
contains the captured16-core mask0xf6fdb and is not a hardware Bumper mapping.
The helper patches the descriptor physical field to that owned page before
publication; hardware mask-programming input fields remain zero.22 object/RAM
pages plus24 read-only device pages are mapped. The RAM-surrogate native run
passed the mask consumer, then faulted writing missing slot35+0x1704.
Do not convert the surrogate into a production register map.
