# Native recovery bookkeeping after submitted work

Offline audit of Apple 25G83 / AGX353.14, source checkpoint
`d98fee493ff296fd94cdb3f30eb0df6e3e9a2df0`. The new decoder reads saved files and
executes three short instruction fragments in RAM. It does not change the
retained GPU session, candidate, graph, firmware or recovery gates. Numeric
range hashes and input identities are in the adjacent JSON evidence.

The concrete gap for recovery after work is a retained host work registry and
its fence/resource/client services. The shared table layouts are now bounded
and independently checked; implementing those layouts alone would not provide
the missing host services. This finding supplies no additional mandatory idle
reset action and does not explain the present phase2 scheduling stall.

| Boundary | Native contract | Present host / required future evidence |
|---|---|---|
| During stopped phase1 | `89663e4..8966444` iterates exactly128 retained host slots at accelerator+f938; each slot supplies +98 bit0 and +a0 u64. ASC slot200 resolves to `89ca3a0..89ca3ec`, writing flag at entry+0 and timestamp at entry+8 through firmware-host+2e8. A DMB follows all128 calls. | Owned shared_4 is already main+274, 0x800 bytes, stride16. Current idle values are zero. After work, establish a retained host slot registry, exact slot identities and last-submitted timeline updates before acknowledging2. |
| Before host phase2 | `8966534..896653c` increments the separate host recovery generation. On the branch selected by stack+40 bit0 clear, `896657c..89665e0` locks the fence list, conditionally calls `AGXWorkQueue::handleIOFenceComplete` when fence+20 and +98 are nonzero, then `AGXIOFenceData::reset` for each visited fence. Profiling-client restart follows; `896664c` invokes pre-resume. | No retained native fence list, completion callbacks or profiling clients exist in the idle experiment. Do not replace them with shared stamp writes or infer retirement from the generation increment. |
| After firmware phase3, before host phase0 | `89666cc..89666f8` barriers then calls `processFirmwareTACommandsRecovery(status_b+40b8)`. `89c9d9c..89c9f88` scans256 records, stride8. It retains a work queue by stamp index, resolves a command/resource, performs bounded-range resource operations, then releases the retained queue before advancing the record index. | Decode and reject active records today. Future active recovery needs registered queue/command identity and the external resource services described below. A zero shared record does not prove the corresponding host object absent or retired. |
| Client work reconciliation | The selected recovery-mode branch calls `processFirmwareInitiatedRecovery` at `8966730`; the alternate client traversal invokes the named `processAllChannelCommands` block `8966ce0..8966f3c`. Additional scheduler/event-stamp work precedes the common post-resume at `8966bfc`. | Preserve the branch distinction. Client channel traversal, restart reasons and retained command/resource ownership require an explicit host model before work reuse. The decoder deliberately does not fabricate these services. |
| Host phase0 and later reuse | Native post-resume requires3 and writes0. FW `6594..6678` publishes3, waits for0, clears request+4, restores its endpoint/worker path. | Existing fresh control consumption is separate liveness evidence. It is insufficient for fence completion, resource retirement, DMA quiescence, or safe unmapping. Recovery after submission and joined release remain prohibited. |

All addresses in this document are hexadecimal, including table sizes and
offsets. Decimal entry counts are explicitly written as128 and256.

The timestamp leaf has no index bound check. Its enclosing loop establishes
indices0..127. Bytes4..7 of each16-byte entry are untouched and remain
uninterpreted. The u64 timestamp is last-submitted bookkeeping, not a completed
stamp. Matched firmware `172c8..1737c` uses main+274 for the same128-entry loop.
When its mode permits that branch and either private18fd0c or the submitted
flag is nonzero, it obtains a hardware pending value. On the software branch
with a retained pending value, it stores
`((submitted_timestamp - retained_timestamp) & 0xffffffffff) + 1`.
The result can be2^40; masking after the increment would be wrong. Saved values
alone do not establish that branch's mode, hardware pending value or execution.

For a TA record, native `89c9e1c..89c9e30` uses
`active = (flags & 9) == 9`, `stamp_index = (flags >> 4) & 127`, and raw u32 at
record+4. This operand is passed with the retained queue and stamp index to
external target `a7e24a4`. Record indices0..255 are not stamp indices0..127;
multiple records can share a stamp index. Neither is automatically the
timestamp-table index or the recovery generation.

Matched FW `16694..167f4` constructs records under explicit command/mode guards.
Its qualified LUTs at58890 and58900 give the command field offsets below.
It copies the low7 index bits into flags4..10 and the other u32 into record+4.
Bit0 is set; bit3 reflects private queue field+20 being zero. The producer uses
status_b+48b8 as the record allocation counter. This is a source identity link,
not proof that Linux registered ownership for any command.

| Command type | Stamp index field | Stamp operand field |
|---|---|---|
|0|8ba|8b6|
|1|2154|2150|
|2|8e0|8dc|
|3|f54|f50|
|7,9|44|40|
|13|34|30|

The retained-resource path still needs these services: work queue retention and
registration (`retainWorkQueueForStampIndex`); command lookup (`a7e24a4`);
the accelerator+140 service checking descriptor+dc8 (`a7cfe60`); resource
descriptor/type access (`beaf410`, `a805a30`); creation of a temporary object
for offset/length (`bf9b0e8`), its virtual138 accessor, the range operation at
`b744da0`, and virtual28 release. The latter external symbol names are not
resolved in this driver image. Their argument/return flow is established;
their full service semantics, failure policy and ownership guarantees remain
unproven. The native loop uses descriptor+e18 resource, +e20 offset, +1170
length, retries failed temporary-object creation with a halved length down to
one, and asserts rather than silently resuming if required services fail.
An offline decoder must not substitute successful stub returns for this contract.

On boot1730 the before/after captures bind root+18 to main, root+b0 to status_b,
and main+274 to owned shared_4. Both complete0x800-byte tables are all zero in
both snapshots; token/phase changes0/0 to1/2. Each zero-table SHA256 is
`e5a00aa9991ac8a5ee3109844d84a55583bd20572ad3ffcd42792f3c36b183ad`.
FW `61f0..6234` explicitly clears0x828 bytes starting40b8 on the forced-host
path before skipping the spontaneous event publication. These observations
do not exercise recovery with retained submitted commands.

Run the read-only analyzer with a new output path:

```sh
python experiments/t6040-gpu/analyze-recovery-bookkeeping.py CAPTURE GRAPH_RECEIPT OUTPUT --self-test
```

The saved replay passed47 checks:12 actual native timestamp writes including
indices0/127 and padding preservation,12 actual TA predicate/extractions at
records0/255,5 actual firmware40-bit arithmetic cases,14 rejected malformed
inputs and4 decoder boundary cases. PAC calls, scheduling, cache coherence,
MMIO, fences and external resource services are outside those checks.
`resetFirmwareForRecovery` remains a pinned BTI/RET stub; the existing idle
proof and no-free lifetime guards are reused. No active recovery or work reuse
is authorized by this audit.
