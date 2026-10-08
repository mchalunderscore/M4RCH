# Export checked native PM preparation for resource integration — 2026-10-09

This adds an export path to the existing initialized-retention audit, not a substitute simplified PM implementation. Actual native initialization, metrics registration, scene/block creation, HWPB factory/reset, TA parameter loading, retention/page-list creation and two TA caller windows are executed by the existing harness. Every existing whole-object comparison still runs for all256 chains. The first passing branch now emits a hash-checked fixture package and explicit identity requirements before its emulated RAM is restored.

Tool: experiments/t6040-gpu/prepare-native-pm-fixture.py MACHO REPORT --prepared-output NEW_DIRECTORY. The parent audit's input binary SHA and method qualifications remain authoritative. Report additionally hashes the exported profile. No hardware, reboot or Apple instruction export.

## What is now concrete

The first checked graph has block capacity2 (one reserved slot), one scene and one state slot. Factor4 requires a32-byte HWPB page-list resource; one128KiB parameter block expands into four32KiB page entries. HW-state resource requests192bytes, counter4bytes, scene resource4224bytes and discard32768bytes. Block alignment32768bytes. The profile captures configuration inputs and memory-provider fixtures so these sizes cannot be mistaken for live T6040 policy. It records32 checked packed-ring indices and16-byte entries, explicitly **not actual firmware ring capacity**.

Seventeen snapshots/configuration inputs are emitted with file lengths and SHA256: PM/manager/block/TA host objects; HW state/counter; config; scene/aux records; frame indices/page list; packed-ring fixture; staged output; host vectors; device/queue configuration inputs. They preserve the parent's intentionally randomized untouched bytes and opaque-service outputs. They are research fixtures, not initialized uploadable GPU buffers.

Nine checked TA associations d78,d88,d90,d98,da8,da0,dc0,db0,db8 are labeled **host object identities**. Fifteen TA/3D parameter fields are recorded separately as native copied values. In particular, initialized vector values are CPU-service pointers in this audit. Firmware-visible equivalence is not established by copying them into a host descriptor; translating every retained object pointer to a GPU VA would also be wrong.

The exported block mapping is the parent's randomized mapping-service return. The page indices and packed ring were checked relative to that return; all must be rebuilt for the actual Linux-owned mapping. Extra values such as PM1d4 survive randomized fixture input into descriptor948/1258. The matched Virtual PM allocator calls an external inherited constructor and explicitly clears only selected fields afterward. Neither these exports nor the existing initializer tests prove the inherited constructor's complete defaults. Do not publish preserved fixture bytes or assume zero is correct without tracing their origin/use.

## How this moves integration forward

The missing step is now an explicit resource/domain conversion list tied to passing native preparation, instead of inventing replacement PM structures from offsets. Next supply coherent Linux-owned parameter-block/page/state/scene/metrics resources, rebuild numeric page/ring data against them, resolve copied pointer aliases and inherited defaults, and join this checked PM graph with the independently checked native render-target graph. Genuine configuration and context/queue/event/cache/retirement lifetimes still need verification. Complete work serialization and actual GPU submission/completion/readback remain unproved.

Prepared package is in native-pm-preparation in the private return bundle. No public or clean-room provenance claim. No triangle or accelerated desktop yet.
