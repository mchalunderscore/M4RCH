# GFX reset resident owner: independent offline review

Reviewed on 2026-10-09. The reviewed future candidate has no outstanding owner or wrapper blocker. This is a build and host-control review, with no kernel installation, module load, MMIO/sysfs operation, reset pulse or repeated wake trial performed by this review.

## Owner and lifetime

`gfx-reset-scope.h` requires the retained resident module pin, runtime-PM-held active consumer, ASC/mailbox mappings, installed attached root/context and all 174 owned page pointers. It refuses submitted work, any nonzero word in the 12 work cursor triples, any active TA record among 256 records, and unequal or out-of-range consumed/control cursors. Eligibility is phase 0 with a healthy session or phase 2 with a failed session; phase 1, phase 3 and other states are refused.

The explicit reset command permanently seals the owner even when its host preconditions reject the API. That refusal leaves `attempted=false`. Entry to the driver API sets `attempted=true` before the call, including API refusal before register writes and errors whose write outcome is uncertain. Neither flag proves that a physical pulse occurred. No second command can retry it. Every result retains backing, mappings, context, runtime-PM reference and resident module pin.

The sysfs callback and receive worker share `graph_io_lock`. The driver obtains its provider device lock, reset-controller mutex and genpd spinlock after that host mutex; the owner does not enter with those driver locks held. Worker cancellation is deliberately non-synchronous under the graph mutex. A queued worker can subsequently acquire that mutex, see the failed seal and return without receive handling or requeueing. This avoids waiting for a worker that is itself waiting for the caller's mutex.

`gfx-snapshot` calls the read-only driver snapshot and reads ASC/protocol state without receive draining. A snapshot error fails the host session. After reset intent or host stop, sample skips receive handling and the other GPU diagnostic helpers. Ordinary graph/owned/notification reads serialize on the same mutex and publish no firmware messages. The remaining diagnostic path can read a retained snapshot; firmware can still advance independently of the host mutex.

Feature-selected stop seals the session, clears ASC START once using a fresh control read and retains resident diagnostic access. It sends no AP_QUIESCED, IOP_SLEEP, receive ACK, INIT, control/work notification or root publication. It performs no PM put, unmap or release. `host_stopped` records the host stop request/readback, not independently established hardware idle or DMA retirement. The default feature-off stop keeps its prior behavior.

## Wrapper and future kernel binding

The resident wrapper accepts reset commands only with the exact future feature contract. It persists reset intent and the failed quarantine before opening/writing sysfs, issues one write, never retries, and keeps the seal after success, open/write failure, short write or interruption. The review found and resolved one admission gap: reset is now refused after `host_stop_requested`, matching the owner gate. Sample, GFX snapshot and packet-free stop remain available after an attempt; publication commands remain blocked.

A later metadata correction replaced the inherited top-level `module_sha256` with the rebuilt `asc-root-envelope/asc-root-envelope.ko` hash. That field, the artifact map and the actual file now agree at `35b5e933ee470bdfbd0db32e0fadfb1574c74932132e7bbdebf6e9fe46df39e1`. The runners already validate the artifact map, so this was receipt consistency rather than a runtime identity gap. The preparation record now binds the corrected receipt and preparer hashes; the eight compiled modules and owner sources remain unchanged and no rebuild was needed.

The dedicated preparer pins the saved baseline module and graph, checks its declared artifact/source fingerprints, copies to a new directory and recompiles all eight helpers. It changes the owner C/header integration and adds `GFX_RESET_SCOPE_TRIAL`; the joined-context and receive-service headers, graph, backing and graph receipt remain identical to the saved candidate. The original `build-root-envelope.py` is unchanged by this feature preparation.

The shared kernel validator binds the reviewed driver/header hashes, all 39 original maintained fingerprints with only the intended PMGR replacement, suffix-only configuration change, exact compiled vmlinux/Image/export hashes and the raw ELF `.notes` bytes. The separate kernel release is `7.1.13-m4rch-gpu-reset`; GNU build ID is `56bf77789b445b0e35cda49f621ff79122eb8d77` and raw notes SHA-256 is `73827a9260e9c49f49036380e62c14d8f2a535edabb808914af7ecbcec05f013`. The future receipt binds those notes so runtime checking uses the future compiled identity. The owner imports both GPL reset APIs; the kernel has no automatic API caller.

## Independent verification and limits

- Actual owner/header, idle checks, sample, worker and typed handler replay: **513 cases passed** under ASan/UBSan. It covered every page, cursor word and active TA index, phase selection, backing guards, API refusal/error/cleanup uncertainty, attempt-before-entry, valid-field logging, no post-seal publication, diagnostic access and idempotent packet-free stop.
- Default feature-off actual trace/cycle/typed-handler replay: **88 cases passed** under ASan/UBSan.
- Actual Python wrapper admission/intent replay: **26 checks passed**, including the resolved host-stop gate, durable-intent ordering, failure/short-write paths, interruption and feature/default stop behavior.
- All **10** future declared artifact hashes and **14** owner-source fingerprints matched. All **8** future helpers have the intended vermagic; both checked API imports are present. The saved baseline declared artifacts still match their original receipt.
- Separate-kernel review independently checked all **11** compiled/source artifact hashes, **10** unchanged baseline artifacts, linked GPL exports, independent raw ELF note extraction, and sample GPU/USB/PHY vermagic. A prior full 94,004-entry copy audit found only the intended PMGR source replacement and no source hardlinks.

These RAM replays use recording stubs for API/MMIO/PM/transport and cache maintenance. LSan is disabled under the managed ptrace sandbox. They establish host guard/control behavior, not real kernel scheduling, provider concurrency, private-cache coherence, physical reset coverage, fresh firmware/DATA restoration, successful restart, GPU execution or safe DMA retirement. A successful pulse return must not be promoted to any of those claims. No automatic restart follows the pulse and all caller DMA pages remain retained.

Full source and artifact identities, module vermagic and replay receipts are bound in the companion JSON.
