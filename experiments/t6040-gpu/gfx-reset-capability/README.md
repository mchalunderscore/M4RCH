# GFX reset reference capability

This helper only verifies the registered J614s GFX provider and briefly acquires
and releases an exclusive reset reference. It has no reset, assert, deassert,
status, power, MMIO, ASC, root, page-table or GPU allocation operation. It does
not access or unload the resident GPU context. Only private CPU-side lookup
storage is allocated and freed.

Default `run_gate=0` refuses loading with EPERM. Gate1 requires the exact
`7.1.13-m4rch-gpu-contract` release, Apple T6040/J614s compatible machine, exact
GFX provider path/reg/label/compatible list, both zero cell counts, existing
platform-driver binding and a nonzero actual provider phandle. A missing phandle
returns ENODATA before constructing a private consumer. It never invents or
assigns a phandle and never attaches a node or changes live DT properties.

The expected current root metadata has no `phandle` or `linux,phandle` property.
Provider registration alone therefore may not supply the reference required by
the kernel reset lookup API. This probe can establish that boundary; it cannot
make an absent reference usable.

For a usable phandle, the helper verifies global resolution to the same provider,
constructs a private detached OF consumer and calls the exported fwnode lookup
with EXCLUSIVE only. No DEASSERTED flag or devres reset variant is used.
The private kobject release callback frees its owned property/name/value/node
storage because standard `of_node_init` uses unexported `of_node_ktype`.
Normal init releases the reset before the private node and provider references.
An unexpected private-node retention pins this helper to preserve its callback;
that diagnostic is not success and does not affect the GPU owner.

Build a disposable copy under ignored output against the matched Gravity tree:

```sh
make -C out/gpu-gravity-contract/linux M=/absolute/path/to/disposable/copy \
    ARCH=arm64 LLVM=1 W=1 modules
```

Before any native capability probe, root verifies the exact kernel notes/build
identity, helper hash and source review. Root owns all loading/unloading and the
resident GPU remains retained. This subagent only builds offline. A successful
lookup proves an exclusive reference was available; it does not prove reset
wiring, quiescence, firmware recovery, backing reuse or safe retirement. See
`docs/evidence/2026-10-09-pmgr-reset-scope.md` for that experimental boundary.

## Driver-owned experimental API

The capability check returned ENODATA on boot278a because the real provider has
no usable internal phandle. `gfx-reset-observation.patch` therefore prepares a
separate API in the existing built-in PMGR driver. Its snapshot only reads the
GFX state word. Its deliberately selected checked pulse excludes reset users,
holds the existing domain lock, checks clock/power and every command readback,
and reports uncertain cleanup separately. It never authorizes backing release.
The patch is inactive until deliberately integrated into a new kernel and called
by a serialized resident owner; it is not present in the running kernel.

The final modified driver object compiled with `W=1`, and the actual checked C
core passed98 fault cases under ASan/UBSan, independently reproduced by reviewer
and root. `test-gfx-reset-api.py STAGED_DRIVER OUTPUT_DIRECTORY` reproduces those
cases from a disposable patched source with its sibling `include/` tree. The
DT/device wrapper, real concurrency and hardware reset scope remain excluded.
The compiled object is not a loadable replacement PMGR module. Read the scope
evidence and `docs/evidence/2026-10-09-gfx-reset-api-review.md` before integration.
Matched RTBuddy analysis may refine which reset candidate should be tried first.

The root-owned gate1 capability probe on boot278a returned ENODATA: the actual
provider has no usable phandle (0 or U32_MAX; the log does not distinguish them). No private consumer or lookup was created, and the
resident GPU module/refcount remained unchanged. A private OF bridge is therefore
not a usable route on this boot.

`gfx-reset-observation.patch` instead adds a narrow driver-owned experimental
interface to the matched Gravity PMGR driver and a public header at
`include/linux/soc/apple/pmgr-gfx-reset.h`. The original driver source SHA is
c0484db37d902b17a5a8132dddb19fdd15a153eaec6caab14b69ad941b8b72ab.
The existing matching kernel tree has not been modified. The APIs are inactive
unless called by a future owner:

* `apple_pmgr_t6040_gfx_snapshot` reads the exact provider state word.
* `apple_pmgr_t6040_gfx_checked_pulse` rejects other machines/providers, existing
  reset references, inactive clocks/power, a transitioning power controller and
  either existing reset bit. It blocks new reset references, uses the existing
  domain lock, temporarily inhibits auto-PM, verifies disable/assert/deassert/
  release, and restores the original automatic policy after confirmed release.

Each poll permits at most101 reads and100 one-microsecond delays; the pulse
holds10 microseconds. Cleanup attempts to inhibit auto-PM and clear both device
control bits on every failure after a write was attempted, including errors
returned after a committed write. Bus errors can prevent or obscure cleanup.
The receipt retains the first operation error, first cleanup error and only
successful register observations. Success proves checked command readback,
not reset wiring, DMA drain, firmware restart or permission to release backing.

Both APIs are sleepable. The caller must hold GFX runtime-PM ownership, serialize
the resident worker, stop publication and retain all backing, and must not hold
the provider device/reset-controller/domain locks on entry. The implementation
holds the provider device lock across identity/drvdata lifetime and the reset
controller mutex across the pulse, refusing any existing reset reference.
It does not call the generic reset callbacks recursively or change their behavior.

The staged built-in driver object under `out/gfx-reset-capability/driver-api-v1`
compiles W=1. It is not a loadable replacement: the unchanged base driver relies
on an unexported built-in OF helper and has no external-module license declaration.
Do not load this compile-verification artifact. No full kernel build, installation
or pulse has occurred.

The actual C core is extracted from the staged patched driver and tested with
ASan/UBSan against an independent fault/order/state model:

```sh
python experiments/t6040-gpu/gfx-reset-capability/test-gfx-reset-api.py \
    out/gfx-reset-capability/driver-api-v1/pmgr-pwrstate.c \
    out/gfx-reset-capability/a-new-fault-check-directory
```

98 cases pass, including every primary read/write failure, writes committed
before returning EIO, both initial auto-PM policies, stuck bits, clock/target
loss, compound cleanup failures, busy/other-reset rejection, existing reset
references and failed reads that poison their output. The harness does not
qualify kernel provider lookup, real concurrency or hardware. LSan is disabled
because the managed sandbox uses ptrace; these core tests allocate no heap.
