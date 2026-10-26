# T6040 GFX PMGR reset scope

Offline source and saved-ADT review on 2026-10-09. No live sysfs, helper,
module, MMIO or reset operation occurred. This is a distinct hardware-reset
hypothesis, not a verified alternative to reboot or permission to free backing.
Exact source hashes and decoded records are in the adjacent JSON receipt.

The saved boot1730 ADT puts both GFX-SGX and GFX-ASC under the real GFX power
device. This makes GFX a concrete common-ancestor reset candidate. It does not
prove which engines, caches, translation units or DMA transactions its RESET
wire covers.

| ADT device | ID | Flags | Parent | Direct state register |
| --- | ---: | ---: | ---: | --- |
| GPX | 384 | 0x09 | none | group2 +0x000 |
| AFR | 385 | 0x09 | none | group2 +0x100 |
| GFX | 386 | 0x02 | AFR385 | group2 +0x110 |
| GFX-SGX | 400 | 0x10 | GFX386 | none: virtual/no_ps |
| GFX-ASC | 401 | 0x10 | GFX386 | none: virtual/no_ps |
| GFX-BUSY | 402 | 0x10 | none | none: virtual/no_ps |

SGX clock-gates and power-gates are `[400,402]`; gfx-asc clock-gates and
power-gates are `[401]`. Group2 selects PMGR reg54, bus address0x88e80000;
the arm-io range translates this to physical0x288e80000. The real GFX state
word is therefore at0x288e80110. The Linux provider path is
`/soc/power-management@288e80000/power-controller@110`, `reg=<0x110 4>`.
Do not concatenate these two cells into offset0x1104.

The existing GFX runtime-PM test verified off0 -> on -> off0 through this
provider before GPU startup. That test explicitly did not exercise reset.
Power-domain reachability and reset coverage are different evidence.

Root's separately collected boot278a metadata now verifies the same GFX node,
`#reset-cells=0`, and its registered platform provider bound to
`apple-pmgr-pwrstate`. The receipt SHA256 is
78f155a6291fe50e046f651c184d140e20a28175b36c40cf49f6e974d1110e9e.
This metadata adds no PMGR register read, reset pulse or coverage evidence.

The Gravity-based Linux `pmgr-pwrstate.c` implements device RESET at bit31:
assert writes DEV_DISABLE bit10, then RESET bit31; deassert clears RESET,
then DEV_DISABLE. Its combined reset holds for1..2 microseconds. It registers
one reset per provider and uses zero reset cells. The implementation states
that reset is synchronous and requires the device powered and clocked.

Three qualifications matter for a resident recovery experiment:

* Assert/deassert ignore each `regmap_update_bits` return value, return0 and
  do not poll for quiescence or completed reset. A successful reset API call
  therefore does not prove the writes happened, DMA stopped, or firmware restarted.
* The powered check uses software genpd status and only prints an error when
  off. The normal power-on path enables auto-PM; genpd on/target15 does not
  alone prove ACTUAL15 at the pulse. The implementation already distinguishes
  actual state from an auto-PM target when deciding whether a domain is active.
* `apple,force-reset` uses PS_RESET bit12 in the power-off transition. Its
  binding calls this power-control error recovery. It is not the bit31 device
  reset pulse. Changing that property is not a substitute for this experiment.

The pinned Gravity m1n1 tree at950e6b7 has the same bit10/bit31 sequence with
a10-microsecond pulse and a hard prerequisite ACTUAL==15. It supplies a useful
reference sequence, not proof of T6040 GFX scope. Its `pmgr_adt_reset` must
not be copied as a gfx-asc reset: it selects the node's clock gate401 and calls
the reset helper without power recursion or a virtual/no_ps guard. Gate401's
zero group/offset would select group0, not real GFX386. Power-enable recursion
does skip virtual gates and follows parents; reset does not. Target the verified
real GFX provider explicitly.

The extracted matched AGX G16X `getPMGRServiceDictionary` at0x89e92e0 merely
creates a service match for `ApplePMGR`; its short body does not qualify a GFX
reset pulse. Native idle `resetFirmwareForRecovery` at0x89d1650 is the already
reviewed empty override. Neither supplies the missing physical reset/DMA boundary.
RTBuddy restart/power-provider implementation remains outside the extracted AGX.

The candidate's recorded compiler command uses the inspected
`out/gpu-gravity-contract/linux` tree. Its reset header, reset core and
`Module.symvers` have no `reset_controller_add_lookup` or
`reset_control_lookup` API. A name-based global lookup must not be assumed.
The supported reset lookup is a consumer firmware-node reference.

There is a narrower source-supported route that need not attach a new node to
the live tree: a private detached OF consumer with one `resets` property holding
the actual existing GFX provider phandle. OF property parsing reads that private
consumer's property list, then finds the provider globally by phandle; reset core
matches the registered provider fwnode and calls its zero-cell OF translator.
Require a nonzero actual phandle and identity-check the resolved node. Consumer
tree attachment is not tested by this lookup path.

That route still needs lifecycle qualification before a helper is implemented.
Inline `of_node_init` references unexported `of_node_ktype`, so an external module
cannot use it unchanged. A custom private kobject release callback or a supported
OF allocation path must own all node/property/name/value storage. The OF fwnode
operations and reset lookup are exported. Use dynamic+detached node flags, keep
the consumer alive through lookup, release the exclusive reset before releasing
its consumer/provider references, and qualify every failure path. Do not borrow
module-static property storage that a dynamic node destructor would free.
The capability-only helper below now builds this lookup route; its private-node
lifecycle has not been exercised by this agent.

A software-node consumer is not a drop-in substitute in this exact reset core.
Although its property format can reference an OF fwnode, reset core invokes an
OF provider translator only if the consumer is OF. This provider has `of_xlate`
and no `fwnode_xlate`, so the software-consumer path leaves the reset ID invalid.

`experiments/t6040-gpu/gfx-reset-capability` now contains a separate capability
helper. Default gate0 refuses; gate1 validates the exact machine, kernel release,
provider metadata and platform binding, rejects actual phandle0/U32_MAX with
ENODATA, then briefly acquires/releases an exclusive reference if one is usable.
It has no reset-line, reset-status, power, MMIO, ASC, GPU-memory or DT-mutation
operation. Its private CPU node has a custom kobject destructor and is freed
before init returns. Unexpected private-node retention pins only that helper's
callback text and reports failure; it does not release the resident GPU owner.

The unpublished output is `out/gfx-reset-capability/build-v1`. W=1 build and
modpost passed; all27 imports are exported, with no reset/assert/deassert/status
operation import. Kernel GNU build ID is1c0b2b5b48a59316f75940aa4049a5f671eca95c,
notes SHAab3d4a13f2cfe6403d9a75e9d03f55202f12c200894e24dd773a8c7ec6d8663a.
Module SHA62d38420f61e370b4c8f84d2287abdc9db528ec9e43dbe1d5268fcaa576f5472;
build receipt SHA4be5d1d053f114b3c30c345cbabec9aef2797266965df13464faf3adc47a1388.
Root owns any runtime metadata-only probe after source review. Successful
acquisition would prove reference availability, not device reset scope.

Root subsequently ran the metadata-only capability helper once on boot278a.
It returned ENODATA at1028.877969: the provider has no usable phandle
(the helper rejects0 or U32_MAX; the log does not distinguish them). No
private CPU consumer, reset lookup, reset pulse or GPU publication occurred.
The helper is absent afterward and the retained GPU module/refcount is unchanged.
See `out/gfx-reset-capability/capability-live-278a044e-qualified.json`.
A private OF consumer is therefore not the next implementation route on this DT.

A distinct driver-owned implementation is now prepared as
`experiments/t6040-gpu/gfx-reset-capability/gfx-reset-observation.patch`.
It adds `apple_pmgr_t6040_gfx_snapshot` (register read only) and
`apple_pmgr_t6040_gfx_checked_pulse` (explicit experimental pulse) with a minimal
public header. The existing matching kernel tree and running driver are unchanged.
No full kernel build, installation or reset pulse occurred.

The API validates exact T6040/J614s machine and GFX provider path/reg/label/
compatible/binding under a retained device reference and provider device lock.
The pulse holds the reset-controller mutex, refuses all existing reset references
and prevents new acquisition until it returns. It then uses the existing domain
spinlock. Initial genpd must be on, ACTUAL/TARGET15, with no DEV_DISABLE,
RESET bit31, PS_RESET bit12 or BUSY bit11. It temporarily inhibits auto-PM,
rechecks state, acknowledges disable/assert, holds10 microseconds, acknowledges
release, then restores the original auto-PM policy. All historical flag writes
follow the existing driver's zero-write policy. Generic reset callbacks and
power/probe behavior are unchanged; successful probe only stores private drvdata.

Every failure after an attempted write runs best-effort cleanup, including a
write that committed before returning an error. Cleanup first attempts to inhibit
auto-PM, clears device RESET and DEV_DISABLE, and restores policy only after
inhibition/release readback. Bus failures can leave inhibition or release
unconfirmed. The observation retains the first operation error and first cleanup
error, plus successful register reads only. A failed read cannot corrupt an
already-valid saved observation. Snapshot performs no register update.

Each poll permits at most101 reads and100 one-microsecond delays, under the
existing spinlock. Both exported APIs are sleepable at entry. Caller must hold
GFX runtime-PM ownership, serialize its resident worker, stop publication, retain
all GPU/DMA backing and enter without the provider/reset-controller/domain locks.
Clean readback proves the PMGR command sequence, not reset coverage or DMA drain.

The modified built-in driver object compiles W=1. An external-module modpost is
not a deployment route: the unchanged base calls an unexported OF helper and has
no external-module license declaration. The compile artifact must not be loaded.
An actual-C fault harness passes98 ASan/UBSan cases: both initial auto policies,
every primary read/write failure, committed-write errors, stuck control bits,
clock/target loss, existing reset-user rejection and compound cleanup failures.
Provider DT lookup, real locking/concurrency and hardware behavior remain excluded.
LSan is disabled under the sandbox's ptrace; this C core allocates no heap.

Future qualification requires a deliberate kernel/API integration, a read-only
snapshot first, and then one deliberately selected idle/no-work pulse while the
resident owner retains everything. Do not combine the first pulse with AFR/GPX
power cycling, translation destruction or release. Observe ASC/engine/transport
state and require a fresh cold negotiation and fresh controls before reuse.
Neither a toggled reset bit nor successful reference acquisition establishes
DMA retirement. Exact newly extracted RTBuddy evidence may refine this sequence
before a hardware candidate is built. The already failed START/INIT and held-power
wake sequences must not be repeated unchanged.
