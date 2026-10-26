# Pure coordination core qualification — 2026-10-09

The actual `gfx-coordinate-core.h` passes 182 RAM-only C cases under AddressSanitizer and UndefinedBehaviorSanitizer. This qualifies the pure protocol core against the [frozen native PMP/PMC evidence](2026-10-09-gfx-native-shutdown-coordination.md), with the limits below. No device, privileged operation or hardware callback was used.

The [JSON receipt](2026-10-09-gfx-coordinate-core-qualification.json) binds the exact core, C harness, Python runner and native evidence source hashes. The tested core SHA-256 is `417179e014653c2b97e55888346cbda70c79a4166fe2a1ca191d741f7201ad01`. Sources remained unchanged during compilation and execution. The build used clang 23.1.1, `-Wall -Wextra -Werror`, and `-fsanitize=address,undefined`; both compilation and execution returned 0 with empty diagnostic output. Leak detection was disabled because the host's ptrace restrictions prevent LeakSanitizer; ASan memory checks and UBSan remained enabled.

The harness is [test-coordinate-core.c](../../experiments/t6040-gpu/gfx-native-coordinate/test-coordinate-core.c), driven by [qualify-coordinate-core.py](../../experiments/t6040-gpu/gfx-native-coordinate/qualify-coordinate-core.py). It made 247,748 assertions over 243,950 mocked I/O callbacks. The cases cover:

- Paired ON/OFF ordered PTD/voter traces, full 64-bit request preservation, and unrelated 32-bit voter preservation.
- Raw second-word ACK bit1 acceptance and rejection of native decoded bit54 alone; zero, invalid and wrong request-bit acknowledgements.
- STATUS0 refusal before or after the request write, all-ones payload/status/voter guards, elapsed-time and frozen-clock sample-count timeouts.
- A valid ACK immediately before the 15-second deadline, exactly at it, and after it; deadline expiry before the first ACK sample.
- Negative and positive errors at every read/write point in the successful sequence, including errors after writes that were delivered to RAM. Each failure stops further I/O; no compensation or retry occurs.
- Changed request readback, changed voter readback at each rail, and preserving a newly observed unrelated voter bit before its write.
- Repeated ON/OFF and OFF without a completed ON returning without any external callback; failed admissions remain consumed.
- Refreshing the request after preflight preserves a mutation during that preflight. A deliberately injected external update after the final snapshot is still overwritten, demonstrating the remaining ownership limitation.

Review identified a late-valid-ACK deadline bypass in the first core version. The parent fixed it by checking the clock before loop reads and after the ACK read before accepting success. The exact tested source includes that fix and the final request refresh. This review did not edit the core.

The callback contract requires `read_ptd` to return the **raw** second PTD word. The same serialized owner must manage each session and the shared request/voter resources. Whole-word RMW preserves the observed source word; it is not atomic against another writer, and post-ACK readback cannot detect an external update that was overwritten.

The experimental core deliberately differs from native: STATUS0 is refused instead of bypassing ACK, all-ones inputs are refused, polling has a sample cap and delay callback, and exact request/voter readbacks are required. The native selected loop busy-polls; this harness does not qualify a future experimental `usleep` implementation, MMIO mappings, memory barriers or scheduling context.

The core contains no physical target15/0 operation. Surrounding owner placement—native ON notification after physical ON and OFF notification before physical OFF—is outside this RAM test. A successful protocol observation does not prove GPU firmware cessation, cache/UAT/DMA retirement, backing release, reset, restart or rendering readiness. The frozen live OFF failure remains unchanged.
