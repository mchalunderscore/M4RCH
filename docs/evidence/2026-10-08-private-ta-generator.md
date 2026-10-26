# Complete native TA register producer

AGX353.14 / Apple25G83, offline private-derived evidence. Complete native
89dd2c4..89df4c0 plus actual encoder/append/empty override helpers return in
128 cases. This is six flag/subtype combinations repeated to check determinism,
not128 distinct valid render workloads. No live GPU activity.

10496 actual encoder outputs match the independent12-byte codec.256 metadata
link/count checks pass. The synthetic zero descriptor uses explicit1230/190
object fixtures and1428 map provider; the latter returns840000000. PAC bypassed.
The generator's manually written records and overall semantic recipe are
observed, not independently modeled by those codec comparisons.

With descriptor1558 clear, native backing is83 entries and exported count81;
with it set, backing84/exported82. Descriptor960 affects the initial mode value.
The donor work advertises65 TA entries with71 backing records. Therefore the
base-M4 donor TA work cannot be copied directly as the matched M4 Pro TA job.
Those differences also depend on incomplete native fixture initialization,
not solely on the16-core versus20-core hardware bin.

Exact ordered baseline records, function hash, input cases and identity
comparison are in the JSON. This closes the missing *native producer execution*
step, while complete descriptor initialization, parameter manager, work ABI,
live root/queue state and completion handling still require integration.

```sh
python experiments/t6040-gpu/audit-private-ta-generator.py \
 /boot/GPUC003/private-apple/com.apple.AGXG16X DONOR_JOB_RECEIPT.json \
 NEW_TA_RECEIPT.json
```
