# Native PWRGATE admission-drain candidate finalized

The distinct next candidate at `out/gfx-native-powergate-drain/candidate` is
built, finalized and independently reviewed. It has never been loaded. The
currentd841 owner remains pinned after a consumed pre-request admission refusal;
only its retained diagnostics remain admitted. No current-boot retry follows
from this preparation.

The actual d841 operation returned `-EBUSY` before sending202. The exact offending
transport/status read was missing, so a pending application notification is a
hypothesis. The new owner logs CTRL44, STATUS48, RX114 and TX110 together and names
the exact refusal condition. It services only endpoint32 with the exact existing
notification word0x0042000000000000, using the unchanged receive service to retain
records and advance qualified consumer cursors. Every removed frame is logged.
Preexisting EP0, unknown, crash or invalid frames refuse before publication.

Admission has a nominal11ms jiffy deadline,12 waiting polls and64 removed-frame
limit; the64th frame seals, allowing at most63 before successful admission.
Scheduling and finite receive service can exceed11ms wall time. A fresh sample
immediately before the sole202 request must still show valid reads, START set,
RX empty and TX available. The original native type7/low8{1,2} ACK, fresh RX-empty
checks, native CPU-idle check, two fresh CTRL44 clears/readbacks and paired OFF
remain in order. Every terminal outcome retains all174 allocations, root/maps,
context, consumer, claims and module. There is no retirement or restart path.

The selected source is `out/gfx-native-powergate-drain/prepared-owner-v2`.
The installed kernel and all nine non-owner artifacts remain unchanged; the
69-page graph and56-page dormant render backing are exact comparison inputs.
Of17 original common owner sources,13 remain unchanged and the same four change;
one distinct header is added. Frozen source versions, captures and receipts
remain preserved.

Root's actual W=1 build completed zero with no warnings or errors. The compiled
owner has the correct installed-kernel vermagic and inspected provider imports.
Actual C/header/transformed-startup replay passes85 ASan/UBSan cases, including
the retained handshake/CPU/OFF cases and30 admission cases. Independent replay
matches the author's qualification. Targeted actual Python replay passes94 cases,
including9 full mocked cold-main flows and actual resident paths; the prior196
cases/45 cold flows remain separately bound. These are offline checks, with
existing receive/provider helpers mocked at the C header boundary.

Owner SHA256: `de75ef4b8c772a56de3026ceb622b940206ed7d0a1ac660a25cae323216681f3`.
Receipt SHA256: `393049662c9966922fda7f66cbfa1c762efc2f0840492042b581e96271a7b6a5`.
Preparation SHA256: `f0fbf1090d73aad478f5b06a76a2f3900d672834c83a4201e0d01103e03fd923`.
Root and the independent reviewer checked10 artifacts,18 owner sources and16
preparation inputs. The prior PWRGATE wrapper refuses all three new-family
commands. The actual new preflight CLI refuses currentd841 before candidate
validation, native sysfs reads or GPU access, without creating an output file.
Both retained94cb andd841 boots are explicitly refused.

After a fresh normal boot, root verifies the machine before one cold trial:

```sh
sudo -n python experiments/t6040-gpu/gfx-native-powergate-drain/preflight-fresh.py out/gfx-native-powergate-drain/candidate out/gfx-native-powergate-drain/fresh-preflight.json
sudo -n python experiments/t6040-gpu/gfx-native-powergate-drain/run-root-powergate.py out/gfx-native-powergate-drain/candidate --graph --run
```

Only successful preflight and qualified startup permit a baseline typed snapshot
and one combined `gfx-powergate`. Then save the outcome and use only retained
diagnostics. Never retry management, replace the owner or use old wrappers.
GRUB default5 and the installed native-reset kernel already match.

The [bound final prepared JSON](2026-10-09-gfx-native-powergate-drain-prepared.json)
joins the compiled module and final receipts to [C/native qualification](2026-10-09-gfx-native-powergate-drain-c-qualification.md),
[wrapper qualification](2026-10-09-gfx-native-powergate-drain-wrapper-qualification.md)
and [independent review](2026-10-09-gfx-native-powergate-drain-independent-review.md).
Matched private Apple-driver findings remain available; no new full disassembly
or private binary is published. ACK, strict physical OFF, whole-GPU drain,
repeatable restart, joined retirement, rendered pixels and the accelerated desktop
remain unverified. The full goal remains active.
