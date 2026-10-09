# Retained management-cycle Python qualification — 2026-10-09

The distinct four-command family has101 targeted offline checks passing,
including6 actual cold-main flows and10 actual resident-main flows. The selected
qualification is `out/gfx-retained-power-cycle/wrapper-qualification-final-v2.json`;
its source pins and the selectedv5 source profile were rechecked. The earlier83
checks remain preserved. Unchanged drain94/9 and original196/45 qualification
are composed through immutable pins.

One `gfx-retained-cycle` is admitted only after the original `gfx-powergate`
report and clean raw captures independently establish own202 ACK, checked CPU
stop, paired OFF, strict physical OFF and usage0/suspended/held0 accounting.
The proof is read and hashed again before admission. It binds the original
terminal operation; later cached first-epoch fields never substitute for fresh
second-epoch observations. The current kernel independently checks retained
identities and physical/transport state before any second reference or START.

The new intent is durable before command open/write. Its failure, interruption
or loss of host state cannot erase either epoch's intent or the first proof.
After the second intent only retained diagnostics remain admitted. Tests cover
these actual command/main paths, changed first-OFF captures and native operands,
exact dmesg rotation joining, family/marker/boot refusal and finalizer/profile
metadata. System access and writes were intercepted in RAM; no reviewer
hardware operation occurred.

The contract permits a bounded management-only roundtrip after autonomous
HELLO12 and the exact endpoint-map acknowledgments, using a separate PM
reference and coordination epoch. It preserves all174 allocations and emits
no INIT220, application root/context/work publication, firmware DATA restore
or application queue reset. Selected source/header checks and actual module
build/finalization remain separately bound. Mocked second syscall success
establishes no hardware reentry, second OFF, application rejoin, execution,
rendering or retirement.

[Bound qualification and source inputs](2026-10-09-gfx-retained-power-cycle-wrapper-qualification.json).
