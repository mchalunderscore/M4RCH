# TA postproducer aperture records and joined preparation

Private implementation-derived AGX353.14/25G83 work. Offline numeric emulation;
no GPU commands, live mapping, driver load, reset or power change. Offsets hex.

The actual caller8a1f7b4..8a1f860 invokes actual mcache aperture helper
895f738..895f878 through G16X vtable7eae388+10 slotfe8. That helper invokes
actual G16 record encoder89e8a9c..89e8ae0 at slotfb8. All targets/ranges are
pinned in the adjacent JSON. Authentication bypassed; tracing disabled.
1,024 cases pass entire9c0 command and1800 descriptor comparisons, unchanged
caller context and restored SP:8,166 records,61 empty paths,31 context-only
flag paths. Counts0..16, random fields and high pointer wrap are covered.

Caller clears bits0/2/3 of command98e. If descriptor1388 is nonzero OR any
of the four caller-context qwords390..3af is nonzero, it sets bit0 and bits2/3
from acceleratorf570 low2 bits, then copies descriptor1390..13af to96e..98d.

The helper starts by clearing descriptor13b0 and setting13b8/13bc to
ffffffff/0. For count=descriptor1388 >0, each16-byte input at1288 has an
address u64, length u32, DSID byte atc and size u16 ate. The actual HAL emits
16-byte records at command660+j*10. With qid=descriptor1274:

- start = (DSID<<47) OR (qid<<41) OR (address>>7) OR (1<<55), truncated to u64.
- end = ((address>>7)+length) OR ((1<<min(size,4))<<42) OR (1<<41).

Successful output descriptor13b0 is command760 pointer+600 with u64 wrap;
13b8=0,13bc=count. Count0 leaves the initial absent pointer/index/count values.
These are numeric hardware-format findings, not validated cache policy or safe
application allocation parameters. Native count bounds are not enforced by the
helper; the candidate tool requires<=16 to fit the observed reserved storage.
The caller's4th argument selector is0 in the checked TA path.

`prepare-native-sksm-registers.py` now consumes explicit u8 aperture_flags,
adds these records after native register production and exports
`ta-construction-descriptor.bin`. Only actual register backing and list metadata
must stay unchanged, not the entire reserved region. Descriptor output retains
CPU emulator relocations and excludes real notification output and counter
objects. Twelve malformed inputs fail before export. Sixteen paired fixtures
cover counts0..15, independent record words and pointer/count outputs, plus80
list/scheduler links and64 independent firmware-address values. Every receipt
keeps submission_ready=false.

## Joined descriptor preparation

`check-native-ta-preparation.py --paired-output DIRECTORY` optionally exports
64 prepared descriptor fixtures through the existing paired tool. Actual
TA/3D constructors, geometry, TA resource loaders, PM loaders and payload copy
are checked against independent full-byte models first. Each paired TA producer
output must equal the entire9c0 output of the original native TA producer run.
The pairing uses checked descriptor bytes instead of the standalone zero/minimal
register descriptor. Fixture render-target source, PM source and payload are
saved for diagnosis. Zero caller context/stack and explicit address-service
results remain fixtures; it is not a Linux-owned allocation graph or valid draw.

Post-reboot verification ran on8d5519d3-c1db-41a7-bb94-7c68e7ac0d10,
kernel7.1.13-m4rch-gpu-contract, source343bf9c before this evidence update.
asc_graph_init was absent; prior pinned failed warm INIT is cleared. No live
initialization attempted. Remaining: complete3D fields and channel scheduling/
publication, actual Linux address/cache/resource identity, completion/retirement
and coherent target readback. No rendered pixels established.
