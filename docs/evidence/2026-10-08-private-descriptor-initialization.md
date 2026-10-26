# Native descriptor constructors and PM scene arrays

Private-derived AGX353.14 / Apple25G83, offline only. No GPU command, reboot,
kernel/default change or public push.

## Complete constructors

The actual 3D initializer 895da40..895dc90 and TA initializer
8a213c0..8a21594 execute together. 512 complete 3D cases and 512 complete
TA cases including their actual 3D parent match an independent full 0x1800-byte
model. Original bytes, queue scalar, length and allocation result vary;
debug retain is present/absent. External services and their argument order are
checked rather than described as having executed their real implementation.

Descriptor virtual slot1e0 resolves from the pinned vtables to895d5e4 (3D)
and8a20cb0 (TA). Both actual getter bodies return descriptor+210. This pointer
is stored at408, with410=2. It is embedded storage, not an inferred buffer size.
The 3D initializer establishes sentinel900/144/2d4=ffffffff,400/c40=1,
1c1..1c2=0101, a resource-root+90 pointer at138, queue550 at160 and zero at168.
It clears the common client range4b0..800, several state/queue ranges and applies
maskfffff000003fffff to c38. The TA parent composition preserves this foundation
while adding its previously checked own defaults and14d0 mask.

The inherited IOGPU service is supplied explicitly: its required task binding
and vtable are pre-established fixtures. Cast, retain, lifecycle/state init and
allocation remain external. Zero helpers implement checked byte clearing.
The inherited return value is varied0/1 and ignored by visible 3D/TA code, which
returns1. This observation does not authorize continuing with an actual failed
IOGPU initialization. PAC is bypassed for unsigned fixture objects.

The joined preparation now starts with these actual constructors at the same
descriptor address used by the later TA generator. Its64 cases pass320 complete
intermediate comparisons,256 expected firmware addresses and5248 encoder checks.
It replaces the prior zero-descriptor starting point, while inherited services,
PM subtype and resource/lifecycle providers remain explicit fixtures.

## Parameter-management scene array producer

The native initializer slice89fcf2c..89fd040 computes a stride from alignment
using `(alignment+3)&(-alignment)`, clears count*stride scratch bytes and populates
the existing PM vectors. Both record vectors advance by80 hexadecimal bytes.
The scene record stores mappedBaseA+i*stride at0 and mappedBaseB+i*stride at8;
remaining bytes are preserved. The other record backing is unchanged here.

Final publications:

| PM object offset | Value |
| --- | --- |
| b8 | first record base + count*80 |
| c8 | separately supplied mapped base |
| 98 | configuration object pointer |
| a0 | mapped base +40 |
| 80 | configuration object +40 |

All offsets hexadecimal. Actual preceding allocation and address-domain
selection remain outside this slice; map sources are distinct explicit fixtures.
1,024 cases with counts0..32 and power-of-two alignments1..128 match complete
object, vectors, scenes and scratch expectations:16,368 scene records and32,736
vector elements. Unused tails and non-scene record backing remain unchanged.
Valid vector capacity equals count; failure paths are not covered by this audit.
This identifies where descriptor loader88/a8 indexed pointers are produced;
it does not establish a full usable PM allocation or valid live context.

Next trace the preceding allocator/register-resource calls and HW parameter
buffer manager state reset, then connect context/root, matched work records,
KSM queues and event/stamp lifetime. The retained failed warm INIT still requires
a normal reboot before the next live hardware session. Offline work can continue.

Scripts consume the local pinned Apple binary and export only numeric findings.
This is private implementation-derived research, not a clean-room specification.
