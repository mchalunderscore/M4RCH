# Native 3D completion pending-count release

Private-derived matched AGX353.14 / Apple25G83, offline only. This audit executes
AGX3DCommandDescriptor::complete at895e1ac..895e1f8, stopping at either the normal
continuation or old-zero diagnostic entry895e324. It does not execute the entire
complete method or prove that firmware notifications invoke it.

## Counter and scheduler selection

All addresses and offsets below are hexadecimal.

1. Write descriptor144 = ffffffff.
2. Select scheduler from accelerator descriptor10, tablef938 indexed by
   descriptor964 *8. Fixtures use32 valid table indices. The native pointer-
   authentication candidate is discarded by CSEL for these indices; this audit
   does not exercise malformed indices or authenticated-pointer failures.
3. Read descriptor2dc as an unsigned32-bit release count.
4. Zero count skips the atomic operation and diagnostic.
5. Otherwise LDADDAL adds the negated count to scheduler44, returning its old
   unsigned32-bit value. The resulting count is `(old-release)&ffffffff`.
6. Only an old count of zero selects diagnostic entry895e324. Reaching zero
   after a valid release takes the normal continuation895e1f8.

Thus scheduler44 is the same field previously incremented by the native
scheduler publisher. The decrement uses the descriptor's accumulated count,
which also supplies the low16-bit count in post-kick opcode14; it is not
necessarily a single decrement per descriptor.

The reviewed slice does not reject release>old. Characterization fixtures show
unsigned wraparound even when old is nonzero. These deliberately inconsistent
fixtures are not proof of a reachable native-driver bug. A Linux implementation
must preserve pending>=released under its synchronization/ownership contract;
it should not copy the arithmetic without that invariant. Old-zero fixtures
also show that subtraction happens before entering the diagnostic path.

## Diagnostic boundary

Static instructions at895e324..895e33c load scheduler48 and schedulerc/10,
prepare diagnostic arguments and call an external routine. The checker stops
at entry and does not execute that provider or subsequent control flow. This
is not evidence of a wakeup, fence signal or successful recovery.

## Reproducible verification

```
python experiments/t6040-gpu/audit-private-pending-release.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  docs/evidence/2026-10-08-private-pending-release.json
```

2048 native slice cases pass:256 zero release,1280 valid release (including
exact exhaustion),256 old-zero diagnostic entries and256 underflow
characterizations. Full descriptor, accelerator table and32 scheduler backing
objects match independent struct-based models, including preserved bytes.

128 additional roundtrips execute the isolated native publication atomic at
89db5c0..89db5c8 (2112 increments total), followed by this native release slice.
The initial pending count is restored in every case. These roundtrips are not
full scheduler submissions/completions and establish no firmware ordering.
The binary and both native-slice hashes are pinned in JSON; Unicorn MAX executes
the actual LDADDAL instructions. Emulated RAM does not establish concurrency,
DMA/cache coherency, notification routing or fence completion.

## Next implementation gap

We now have matching increment/decrement bookkeeping and independently checked
control-slot release. The missing link is the real firmware event/completion
consumer selecting a live descriptor and invoking completion exactly once.
Trace the deferred event worker and completion-buffer consumers before treating
an event or cursor movement as proof of retired render work. Shader/target
construction and executable GPU rendering remain unproved. The retained failed
warm INIT still requires a normal reboot before more hardware trials.
