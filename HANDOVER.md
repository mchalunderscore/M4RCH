# first native control consumption; 32-refresh batch prepared

boot3cfad7b5-4782-4083-9043-8d15a295ff67, trial sourceae7476b and exact
slot22-startup-candidate artifacts. regular7.1.13-m4rch-gpu-contract kernel,
promoted package7.1.13-2 and default GRUB entry unchanged. all3 PD controllers
and USB role providers bound before/after; user confirms everything normal.

gate1 passes; gate2 returns0. the previous slot22 write-permission fault is
gone in this bounded observation. no EHLC crashlog header and zero mailbox
messages during30seconds. this is absence of a recorded fatal event, not a
proof that firmware remained healthy indefinitely.

native control12 cursors advance0/0/1 ->1/1/1. the unchanged opcode16 record
is consumed. this is our first native control-handler consumption on the
qualified mapping fixture, beyond earlier startup writes/faults. DATA globals
18eec8/146908/146914 finish zero, consistent with the refresh model. main
32c=1 and344=abcdabcd; prior header/power/status mutations remain present.
29 non-atomic owned-RAM snapshots have one unique hash and no observer errors;
consumption occurs before the first snapshot. no job/queue execution, receive
channel validation, complete initialization or GPU acceleration claim.

next candidate:32 identical operand-free opcode16 records, initial producer32.
only32 bytes differ from the successful fixture:31 additional opcode bytes and
the producer byte. same47 owned pages/100 device leaves/147 total mappings,
same36 writable device pages. no new permission, address, doorbell, FList,
shader or render/compute command. work0..11 stay empty RAM surrogates and
receive13..16 remain zero/unqualified. batch stays below the ring's page extent
and does not wrap. maximum32 explicitly checked, nonempty staging rejected.

15 mapping/serialization/batch-bound tests pass. offline matched-TEXT drain
replays1/2/16/32 records, returns with equal cursors and exact handler counts;
32-record replay7508 instructions. explicit zero private state, disabled cache
configuration and omitted pointer authentication remain model assumptions.
the drain's X0 is the producer snapshot, so32-record replay uses32, not1.
W=1 eight-helper build passes without warnings; all receipt hashes verified.
prepared artifacts:out/gpu-gravity-contract/refresh-batch-candidate.

private Apple AGX353.14/25G83 audit adds12 pinned instruction-site checks.
notifyFirmwareStarted sets CPU-object1715; bootFirmware waits for that bit
then sets CPU2a8; isGFXBooted reads1715. these are host bookkeeping, distinct
from our native control consumption. receivedMessageFromAKF dispatches masked
message class2 via an accelerator callback; callback routing remains unresolved.
initFirmwareSharedData maps CPU resource880 into main+200, currently zero in
our fixture. role/backing/extent are not qualified: do not fill this pointer
based only on its offset. five shared-pointer positions254..274 independently
corroborated. next audit: trace transport callbacks/start notification and the
complete resource880 allocation, then receive descriptors and nested contents.

evidence:2026-10-08-control-consumption-result.json,
2026-10-08-refresh-batch-{candidate,model}.json and
2026-10-08-private-startup-notification-audit.json. raw native capture:
asc-graph-init/boot-3cfad7b5-4782-4083-9043-8d15a295ff67.
analyze-control-result.py verifies the actual trial fixture before reporting
consumption. private binary/full disassembly/TEXT excluded from Git/bundle.
implementation-derived research, not clean-room.

NORMAL LINUX REBOOT required for the next publication. resources are pinned,
ASC stopped; AP_QUIESCED/IOP_SLEEP acknowledgements absent. never force-unload
or republish on this boot. no macOS change needed and no automatic reboot.
after r verify fresh boot, USB baseline and matching artifacts; run:

    sudo -n python experiments/t6040-gpu/run-root-envelope.py out/gpu-gravity-contract --graph --run

expected next result:control cursors32/32/32 with no fatal notification; any
partial drain or crash must be recorded. analyze against refresh-batch-candidate,
not the previous one-record fixture. rebuild using --control-refresh
--control-refresh-count 32. keep bounded mailbox/live
RAM captures. rendering still requires real channel state, job/command ABI,
allocation/coherency and interrupt completion, beyond this control batch.

---

# Empty-channel trial had no reported fatal event; longer observation built

Boot0fed45ec-b07a-4e53-b7d5-c43f57baba0c. Gate1 passed, gate2 returned0;
no post-publication mailbox messages in5seconds. DATA crashlog reservation
containsEF fill, no validEHLC header. Fresh DATA sampler with explicitCPU
cache invalidation yields byte-identical capture. Owned main_header/power/
status changes establish firmware object writes. NOT proof of complete init,
AFR completion, stable firmware execution, production queues or rendering.
Raw capture and exact trial module match pinned build receipt. Sourceb8959fa.

USB PROMOTION VERIFIED: installedpackage7.1.13-2, DWC3moduleSHA53f89da...
and initrdSHAd612b96... match qualified promotion. Three role providers exist.
Right PD2-0c failedENODEV at4.888074 BEFORE GPU activity. Normal targeted
SPMI drivers_probe of only unbound2-0c succeeded at289.013380; user confirms
right USB works and everything normal. Working left controllers untouched.
Transient boot probe readiness remains unresolved, not a missing promotion or
GPU-caused detach. Common probe collapses several stages intoENODEV; need
VID/mode/power/status failure-specific diagnostics before persistent retries.
No persistent retry policy installed. Keep all3-provider fix in future rebuilds.

NEXT CANDIDATE BUILT: same47 objects/100 device leaves, no new mappings,
commands or cursor advances. Observation30seconds (parameter bounded5..60s),
1-second non-atomic owned-RAM snapshots; changed full frames archived. DATA
read-only sampler invalidates CPU lines; TEXT/table samplers unchanged.
Ten mapping tests,2 observer integrity tests andW=1 build pass. Current state
already pinned/stopped: NORMAL LINUX REBOOT needed before another cold trial.
Same default1/kernel/initrd; no macOS needed. Check USB baseline before GPU;
if2-0c fails again, capture first then targeted normal reprobe; do not unbind
working controllers. Run rebuilt run-root-envelope --graph --run after reboot.
Evidence docs/evidence/2026-10-08-empty-channel-result.json and
 docs/evidence/2026-10-08-long-channel-candidate.json. Candidate artifacts
out/gpu-gravity-contract/long-channel-candidate. Never force-unload graph.

---

# Empty-channel structural batch prepared; normal Linux reboot needed

Prior table-register trial recorded in commit8d6ccbb. New candidate provides
13 independent zero RAM cursor pages and13 zero16KiB ring pages for work0..11
and control12. Main+20+i*20 contains3 cursor pointers then ring pointer;
cursor words at own page+0/+8/+10. No ring entries submitted or cursors advanced.
Other channels13..16 unchanged/unqualified. This is a structural RAM surrogate,
NOT hardware-backed work-channel state or production ring-capacity validation.
Hardware cursor setup needs separate native SGX mapping and ownership work.

Owned arena now47 pages;100 device leaves unchanged;147 mapped total.
No MMIO/RAM overlap. Same narrowly qualified29 RW device pages unchanged.
Ten tests pass; W=1 external build passes. Matching captured TEXT66ec actual
code executed offline: empty check returns0, individually unequal cursor on
each12 work channels returns1;48 pointer/cursor reads in empty case. No native
publication of this candidate yet. Build/source receipts and graph/module kept
out/gpu-gravity-contract/empty-channel-candidate; evidence
 docs/evidence/2026-10-07-empty-channel-candidate.json.

NEXT: normal Linux-to-Linux reboot, same regular default1 and promoted USB
package7.1.13-2. Verify USB/input then rebuilt run-root-envelope --graph --run.
Current graph backing pinned: never force-unload or warm-start another trial.
No macOS needed for this structural qualification. Kernel/initramfs/bootloader
not changed; candidate is external module only. Firmware init, AFR completion,
all receive channels, rendering and production queues still unestablished.

---

# GPUC004 primary table-register routine returned; channel cursor NULL

Boot3c210c1d-4b3d-4f02-bdb3-f642f19baf8c, regularGPUC001 and USB all3
providers/PD bindings present before/after. Gate1 shadow walk passed;
gate2 returned normally. New2528-byte valid/new Crg8 task2 PC66f8,FAR0,
ESR96000004. LDRW through main+20 NULL cursor. Caller379a0 follows
returned call15e60: previously faulting primary table-register routine completed
on this invocation. This is a concrete milestone, not full initialization.
AFR all16 completion still unproven. Resources pinned; reboot needed for next
publication. No installed kernel/initramfs/default change.

NEXT: empty-channel structural fixture for12 work channels plus control.
Native firmware66ec compares first/third cursor pointers of each32-byte
record beginningmain+20; main+1a0/1b0 control comparison follows. Three
independent32-bit cursors plus ring pointer matches donor serialization, but
T6040 real work cursors are hardware-backed; RAM fixture only diagnoses
structural startup, not production queue implementation or submission.
Validate empty/nonempty cursor checks against matching TEXT offline; never
advance a ring or submit jobs. Other receive-channel setup remains unqualified.
Raw capture out/gpu-gravity-contract/asc-graph-init/boot-3c210c1d-4b3d-4f02-bdb3-f642f19baf8c.
Evidence docs/evidence/2026-10-07-gpuc004-table-result.json.

---

# Next GPU batch built; normal Linux reboot required

GPUC004 trial results below preserved in commitc050fe6 and raw boot capture.
Following candidate adds only existing primary leaves288010000/288020000 RW:
STRX160a8 primary+21108 and selectorSTRX160d0 primary+103a8, with related
register writes on the same pages. Total leaves unchanged100, objects21;
11 ordinary SGX +16 AFR +2 platform writable. All other grants preserved.
Nine tests pass; W=1 build passes; no second native trial on this pinned boot.
Firmware descriptor AFR range semantics still experimental; no success claim.
Candidate receipt docs/evidence/2026-10-07-gpuc004-next-candidate.json,
artifacts out/gpu-gravity-contract/gpuc004-next-candidate. Raw successful build
and attempted-trial module/graph/source/receipt archived separately.

NEXT USER ACTION: normal Linux-to-Linux reboot. GRUB default1/regularGPUC001
unchanged; promoted USB package7.1.13-2 retained. Do not force-unload pinned
ASC graph resources or attempt another firmware boot before reboot. After
reboot verify USB baseline then use rebuilt run-root-envelope --graph --run.
No macOS handoff needed for current Linux qualification path.

---

# GPUC004 segmented AFR trial returned — 2026-10-07

Regular promoted USB baseline verified before the trial. All3 role providers
and all3 SPMI PD controllers remain bound afterward; user reports everything
normal. GPU gate1 shadow walk passed; gate2 returned0; Linux did not hang.
100 device leaves +21 object pages;9 ordinary SGX,16 AFR,2 platform RW pages.
Matching25G83 AGX constructor proves four40000 physical ranges at28b000000,
28b200000,28b400000,28b600000 concatenated into virtual100000. Fourteen pinned
instruction words and constant pair checked;8 serialization tests pass,W=1 build.
Only AFR pages containing16 captured RMWs are RW; other48 AFR pages RO.
Primary leaf288004000 RW for all7 selector+4000/+4008 writes.

New2544-byte/footer-valid Crg8: task2 PCfffffc00000160a8,
FARfffffc2000221108,ESR9600004f (write permission). Physical288021108,
leaf288020000. Task6 old2a3f0 fault absent, but scheduler/task change means
all16 AFR RMW completion is NOT proven. Firmware cached slot20 has exact
new physical/virtual/total/per-range/flags record; descriptor accepted/copied,
not proof of successful hardware configuration. Changed main_header/power/
status objects captured; no queues/rendering or full initialization claim.

NEXT: normal reboot required, no force-unload/restart. Prepare primary leaves
288020000 (160a8 and table-register writes),288010000 (160d0 selector103a8)
RW together from captured routine15e60; preserve other restrictions. No new
installed kernel, initramfs or bootloader required; regular default1 remains.
Full evidence docs/evidence/2026-10-07-gpuc004-afr-result.json and ignored raw
out/gpu-gravity-contract/asc-graph-init/boot-6a0a6204-876f-4fd5-9330-60efe15d5186.
No host AFR MMIO scan; Apple binary/private disassembly excluded from return.

---

# Regular promoted USB boot verified — 2026-10-07

Boot6a0a6204-876f-4fd5-9330-60efe15d5186, regularGPUC001/default1,
package7.1.13-2. User confirms all3 ports work. All3 role providers AND all3
PD controllers0-0a/0-0c/2-0c bound; successful host role transitions observed
on382280000/38a280000/392280000 during user's port checks. Prior0-0a ENODEV
not reproduced. Empty devices_deferred capture. Current lsusb may be empty
because last logged change returnedcharging-only roleNONE; use transitionlogs
and user's device tests, not root-hub presence alone. No GPU trial at this pre-trial USB snapshot.

Evidence docs/evidence/2026-10-07-usb-regular-boot-verified.json; raw capture
out/usb-role-provider/boot-6a0a6204-876f-4fd5-9330-60efe15d5186. USB correction
qualified for this regular boot; cold/warm repeatability remains to characterize.
Continue GPU qualification from this working baseline.

---

# USB role-provider fix promoted after all-port trial success

User confirms all3 USB ports work onfcfa7ebf trial boot. Linux records three
role providers, right-port YubiKey bus5, PD0-0c and2-0c bound/polling with
successful cable callbacks. PD0-0a still failsENODEV; no full PD/IRQ claim.
No GPU firmware attempt on this boot.

Promoted package linux-m4rch-gpu-contract7.1.13-2. Only3 packaged files differ:
DWC3 glue module (exact tested hash), init-nvme early modprobe dwc3_apple, and
mkinitcpio hook including that module/dependency. Kernel image unchanged.
Regular GPUC001 initramfs regenerated; exact embedded module and kmod loader
verified. GRUB default1 restored, USBR001 validated trial retained as entry3.
boot.bin unchanged cb3ab77bdac7f276b5331d8580a5ee1b81f8bd215c0cba1449391a73d790ef09.
The generic package post-install boot-update hook overwrote GRUB with its old
hardcoded menu; corrected regular+trial menu installed and script-check passed.
Future package updates need to preserve this menu/default, not generic defaults.

NEXT: one normal promoted boot; record all3 physical-port functionality BEFORE
GPU activity. Then continue primary-SGX write/AFR static qualification. Maintain
separate0-0a ENODEV investigation, cold/warm/charging/orientation distinctions.
Original1 package + initrd storedUSBR001. Full rollback: install rollback-package
with pacman-U, restore normal-initramfs-before to GPUC001/initramfs.img and
initramfs-linux-m4rch-gpu-contract.img, then restoregrub-before.cfg last (package
hooks overwrite GRUB), reboot normally. Trial backup remains independently
bootable with its included candidate. No installed file was changed by hot-unbind.

Source patch/build/package recipe and evidence tracked; root package owns fix.
Protected existing build tree kept unchanged for GPU helper provenance; next full
kernel rebuild must apply experimental-t6040-fixed-host-role-switch.patch to its
source. Package-fix.py reproducibly updates the pinned baseline payload/module
and early-load recipe; pkgrev2 was not a full kernel rebuild. Evidence
 docs/evidence/2026-10-07-usb-role-provider-promoted.json. Rawlogs/sysfs/IRQs in
out/usb-role-provider/boot-fcfa7ebf-d24f-4dec-9c4c-e3d2e97912ef.

---

# USBR001 loader corrected after initramfs stop

First trial stopped BEFORE candidate load: both hashes passed, but BusyBox
insmod applet was absent. User restored original entry and booted successfully
(12b4833d-bf5e-4958-8b7d-c668776f65d1). This is a packaging failure, not evidence
of driver failure. Corrected initrd adds usr/bin/insmod -> kmod and invokes it.
Extracted actual image kmod/insmod --help PASS; CPIO/init/module hashes checked.
Fixed imageSHA8b308fe1760284fa10e8faa73d985ffef67ebc2f68d3faea854ccde6d54d4997.
GRUB default3 reselected for authorized next USBR001 trial. Failed image/receipt
preserved inUSBR001; original entry/module unchanged. No candidate live-loaded
or promotion. Reboot normally when ready; qualify USB/PD before GPU activity.

---

# USBR001 staged as next GRUB default — 2026-10-07

User authorized separate USB role-provider trial as default, promotion only
if native tests pass. GRUB default3: GPU-contract kernel, /USBR001/vmlinuz and
/USBR001/initramfs.img. Kernel identical to GPUC001; kernel package/module tree,
original GPUC001 initrd and entry1 untouched. Candidate DWC3 glue preloaded by
trial initrd after NVMe root validation, before root udev. Exact candidate/core
hashes verified in initrd before insmod; any load failure stops before root
userspace. Original installed module will not replace an already-loaded module.
This is a boot-isolated module trial, not a promoted package/new kernel version.
No automatic reboot or live USB driver replacement was performed.

Next boot BEFORE GPU activity: verify role providers in /sys/class/usb_role,
PD/typec bindings, devices_deferred reasons, kernel logs and known USB device
on each physical port in both orientations. Test right-port boot-connected
YubiKey and hotplug. Retain cold/warm boot distinction and charging setup.
If PD still deferred, identify next dependency rather than declaring success
from root hubs. Do not start GPU firmware until USB baseline is collected.

Rollback (keyboard cannot select GRUB reliably): from remote Linux or shared
boot filesystem restore /boot/USBR001/grub-before.cfg to /boot/grub/grub.cfg,
then reboot normally. This selects original entry1/initrd and installed module.
Original module copy also retained inUSBR001; root copy was never changed.
GRUB script-check passed; staged image/kernel hashes match source. See
 docs/evidence/2026-10-07-usb-role-trial-staged.json and
 experiments/usb-role-provider/stage-initrd.py for reproducible staging.

---

# Linux USB investigation: missing fixed-host role provider candidate

See experiments/usb-role-provider/README.md. All three live DT controllers
request usb-role-switch, but fixed-host DWC3 probe returns before registering
it. Live role class empty; PD common probe requires graph provider and may
returnEPROBE_DEFER there. Candidate patch now built W=1 against current kernel;
NOT installed/loaded. Native exact failing stage/right-port causality remain
unconfirmed. No live USB reset/unbind or extra GPU attempt. Next separate boot
should qualify role/provider completion and physical ports BEFORE GPU testing.
Protected maintained source/config/kernel/default unchanged. Full build/module
receipt in docs/evidence/2026-10-07-usb-role-provider-candidate.json. Archive
includes source patch/instructions; candidate module retained locally in out.

---

# USB port correction — right-port failure predates GPU trial

User clarified YubiKey was connected to RIGHT port since boot a9112962, then
moved it to a left port to use passkey. Left ports work; right port does not.
Pre-GPU lsusb snapshot already lacked that key. PD providers0-0a/0-0c/2-0c
failed SN201202x initialization at16.572seconds; GPU publication was64.928.
Live devices_deferred still lists all three, without driver bindings. Thus the
right-port failure predates this GPU attempt. All six root hubs existing does
not prove physical port functionality; unchanged attached hub enumeration only
qualifies those devices. Earlier generic user confirmation is superseded by
this specific port report. No controller/provider reset attempted.

Next: investigate/reproduce boot-time PD initialization, including a known key
on right BEFORE GPU work. Keep GPU resources pinned until normal reboot.
Evidence2026-10-07-gpuc003-repeat-usb-result.json includes correction; raw late
USB tree/log/deferred captures included in GPUC003 return. No Wallace comparison
verified; similar symptom alone does not establish shared cause.

---

# GPUC003 repeated with working USB — 2026-10-07

Boot a9112962-2426-4029-b412-6c4d74bf273e. User reports USB working after reboot.
Captured USB BEFORE any GPU activity: six root hubs plus external hubs,
TONOR microphone, ASIX Ethernet and digital AV adapter. USB/Type-C drivers
loaded. Repeated identical built module/graph, without new mapping permissions.
Independent receipt check PASS (36 device leaves,10 writable,57 mapped VAs).
Cold native gate1/shadow check and gate2 bounded observation returned.

USB enumeration unchanged after trial; no new disconnect, IRQ storm or unknown
IRQ logs. User confirms USB devices, desktop and built-in input remain normal.
Contrast prior recovery boot,
whose pre-GPU baseline lacked the USB driver stack. This supports an earlier
boot initialization gap; do not claim all possible delayed effects excluded.
Same new valid2544-byte crash: PCfffffc000002a3f0, FARfffffc20002040a0,
ESR9600004f. Both platform consumers passed again; slot17 primary SGX page
288004000 remains RO. No extra write permissions or AFR mapping enabled.
ASC stopped, graph/power pinned; NORMAL REBOOT before further firmware start.

Evidence docs/evidence/2026-10-07-gpuc003-repeat-usb-result.json; native capture
asc-graph-init/boot-a9112962-2426-4029-b412-6c4d74bf273e and USB baseline
usb-baseline/same under out/gpu-gravity-contract. Continue Linux static source
analysis before next batch; no macOS handoff needed just to repeat this fault.

---

# GPUC003 platform accesses pass; recheck USB before next trial — 2026-10-07

Boot710c3031-553b-4a76-b06f-bef667b4b2a1, same GPU-contract kernel/default/WFI.
Display was recovered by disabling persisted KWin Zoom effect. Normal display
scale remains2; no display/GPU/DCP/kernel changes were made for that fix here.
GPUC003 kit hashes and private AGX hash/eleven instruction checks passed.

Added exact platform class: slot0 PA502414000->VAfffffc2001a00000, slot11
PA5003d8000->VAfffffc2001b18000, each4000 and writable. Existing SGX aperture
checks and eight-page whitelist retained; no slots9/10 added.57 mapped VAs:
21 object pages plus36 device leaves, two owned tables. Seven serialization
tests, matching W=1 external build and independent kit receipt check passed.
Native gate1 allocation/shadow walk unloaded normally before one gate2 cold
firmware attempt. Build completion and module hashes verified before loading.

Firmware advanced beyond slot0 andslot11. NEW2544-byte crash, validfooter,
PCfffffc000002a3f0, FARfffffc20002040a0, ESR9600004f. STRX writes
28040000e60050 to primarySGX slot17+40a0 (physical2880040a0) whose page is RO.
Following STRX+40a8 uses1f4. Need narrow page write qualification next, not
whole-primary aperture writes. Execution beyond3aa0c supports prior platform
consumers passing; host did not read back AIC mask-clear or telemetry registers.

AIC arithmetic cross-check: native2720/4096 IRQs, AIC3 config starts10000;
SW_SET14000, SW_CLR14200, MASK_SET14400, MASK_CLR14600. Slot0+634/2000
unmasks IRQ429. Metadata+84/+284/80 refers toIRQ1063. Before/afterIRQ snapshot
Err=0; neither IRQ has a dedicated registered visible host counter, so do not
claim absence of interrupts. No new IRQ storm/error log. ASC stopped, graph,
power and all backing pinned; no force unload/warm start. No init/render proof.

HOST QUALIFICATION CHANGED: user first reported everything normal, then noticed
USB no longer working. Pre-GPU DCP baseline already had no USB controller/PHY
modules or USB IRQ entries; post-trial drivers/bindings also absent. Causality
unresolved. Stop hardware work. NEXT BOOT: verify USB, modules/bindings/logs
before any GPU helper/power/firmware activity; compare fresh boot with this
baseline. User intends to reboot and re-test. No automatic reboot issued.

AFR offline lead:2a404 loads cachedslot20 AFRRegisters (18f748), then read/OR/
write+0c and+i*10000 for i1..15. Matching private AGX constructor stores
physical28b000000 toHAL20 field5be8 at89ea5b8..5c0; field208 receives40000.
Adjacent stored addresses28b200000 and28b400000 suggest grouped resources.
Do not assume40000 covers firmware's sixteen offsets; trace construction and
firmware serialization/grouping before adding mappings. Binary is now locally
available, so further static analysis can continue on Linux; no immediate macOS
handoff required. Keep private binary/derived disassembly out of Git/archives.

DCP baseline saved in /boot/DCP001/captures/dcp-20261007T211915Z-baseline-69ksjd24.
Live selected DT contains no DCP/DISP/panel/crossbar nodes, only chosen framebuffer.
DRM_APPLE disabled. Separate Kconfig candidate DRM_APPLE=m, AUDIO=n resolved;
not compiled, installed or loaded. Maintained .config hash unchanged. See
 docs/dcp001-preparation.md and /boot/DCP001/LINUX-HANDOVER.md. No DCP hardware
attempt or framebuffer takeover. Keep first DCP startup separate from GPU tests.

Evidence docs/evidence/2026-10-07-gpuc003-platform-result.json; raw native
out/gpu-gravity-contract/asc-graph-init/boot-710c3031-553b-4a76-b06f-bef667b4b2a1.
Return /boot/GPUC003/linux-return.tar.gz includes source, raw graph/data/ADT/logs,
IRQ and USB diagnostics, receipts/check outputs; firmware TEXT code and private
Apple binaries/derived disassembly excluded. Private DCP diagnostics returned
separately underDCP001. Provenance is Apple binary analysis, not clean-room.

---

# Eight-page write batch passes MCW; platform mappings next — 2026-10-07

Boot d7988335-efa2-43bf-a984-0f0f1427ca86. Kernel/default/bootloader/WFI unchanged.
Six serialization tests and matching W=1 external-module build passed. Sparse
SGX-relative layout now has 21 object pages, 34 device leaves, two owned tables,
55 mapped VAs. Eight exact writable pages: GFender 288d04000, GCPMS 288d10000,
MCW 288d40000, Bumper 288d44000, PRC 288d4c000, DFenderMGPUCfg 288e00000,
shared clock/counter 288e1c000, DFenderCSCfg 288e40000. Other leaves remain RO.
No production configuration or GPU work queues supplied.

Sixteen exact pre-reads completed with GFX genpd, without firmware wake or host
register writes. Initial build was still running when an older six-read module
was loaded; that capture is explicitly archived as -old-reader. It is not
sixteen-read evidence despite its intent file. Waited for build completion,
reran expanded module and verified all sixteen new log addresses in order.
The harness now rejects an incomplete/mismatched sequence automatically.

Cold native root publication returned to Linux after bounded observation.
ASC stopped, published module/backing/GFX retained; never force-unload/free.
User confirms desktop, built-in input, USB and networking remained normal.
Same sixteen exact post-reads passed: MCW +0 changed 101051->100051 and +4 f->1;
Bumper ffff6fdb/ff/0 -> f6fdb/0/0; counter 0->70700777. Firmware therefore
passed the previous MCW permission fault. No full initialization/rendering.

NEW crash: valid newly written 2544-byte log; PC fffffc000003a9ec, FAR 634,
ESR 96000044. Cached slot0 GPCAICSWInt pointer at18f428 is zero; instruction
stores2000 at +634. Following instructions load18f5e0, slot11
PushTelemetryDashboardConfigSpace, read/OR/write+758 (b00) then write+254
(200000). Both platform slots are outside GPUC002's thirteen HAL GPU-bank rows.

NEXT: focused macOS static-analysis request on matching 25G83 / AppleAGX353.14:
resolve slot0 GPCAICSWInt and slot11 PushTelemetryDashboardConfigSpace physical
base/extent, constructor or platform-resource binding, flags and interrupt
bit/register semantics. Include checked source offsets/instructions, firmware
identifier, provenance and normalized table extracts; no Apple binaries needed.
For slot0 reconcile firmware +634/2000 with J614s ADT meta-sw-interrupt records
502414084 and502414284 (raw word80). Gravity g16_platform.rs aligns the latter
to502414000 but that is a candidate, not proof of this firmware's binding.
Kernel irq-apple-aic.c lays out software IRQ arrays dynamically using max_irqs;
do not guess an interrupt write based on aperture containment. Slot11 needs its
own resource resolution; do not substitute donor telemetry addresses blindly.
Send this whole packet so the macOS checkout has current tracked patches,
configs/pins/helpers and evidence, not only this prose.

Further native firmware startup requires a normal reboot because resources
remain pinned; another reboot alone does not resolve these two mapping gaps.
Continue offline Linux work where useful; no automatic reboot has been issued.
Evidence: docs/evidence/2026-10-07-gpu-write-batch-result.json and raw captures
asc-graph-init/boot-d7988335-efa2-43bf-a984-0f0f1427ca86, exact-register-read/same
under out/gpu-gravity-contract. Return packet /boot/GPUC002/linux-return.tar.gz
includes this document and source/raw captures, excluding firmware TEXT code
image, Apple driver binaries, credentials and system images. Input kit preserved.

---

# Sparse SGX layout and counter writes pass; MCW next — 2026-10-07

Boot60b99992-6e38-4dbf-9ed4-eae746b9463d; same kernel/default/boot.bin/WFI.
Fresh ADT/kernel checks passed. Exact target288e1f860 read0 normally before
firmware, using existing GFX genpd; prior five bank reads repeated successfully.

NEW layout: MMIO VAfffffc2000200000 + primarySGX-relative physical offset.
21 object pages,32 unique device leaves,53 total mappings,2 owned tables.
Six tests cover sparse VA uniqueness/containment, slot29-D10000 normalization,
shared40/41 page, second counter page remaining read-only, narrow write pages,
profileA and binned masks. W=1 module build passed. Sparse TLBI invalidates all
object/device VAs; sorted/deduplicated pages share one owned L2 and avoid RAM.
Slot17 extent corrected to21400 from matching static record. Existing firmware
root descriptors preserved. No whole-aperture mapping/write permission.

Three writable physical pages ONLY: Bumper288d44000, DFender288e00000 and
shared counter/clock288e1c000. HAL40 and slot41 refer to the same page/VA;
effective permissions recorded per descriptor. Counter second page288e20000
remains read-only. Firmware descriptor41 write flag set, no unrelated grants.

NATIVE cold trial completed bounded observation and stopped ASC. Counter exact
readback changed0->70700777, confirming real write and passing prior2b7f8
fault. Real Bumper programming repeatedf6fdb/0/0. User confirms desktop/input,
USB/networking all normal. No full initialization, queue/rendering success.

NEXT fault: NEW2544-byte validfooter crashlog, PCfffffc000002d15c,
FARfffffc2000f40000, ESR9600004f (write permission),x10=100051. Instructions
load cached31 virtual18f900, read MCW+0, ANDffffe0ff, then store+0; next store+4.
Physical288d40000 is matching static HAL31 MCW resource. Native read completed
before denied write. This is another deliberately read-only mapping, not null
address/ABI rejection. Need narrowly scoped MCW write permission next.

Offline batch plan: docs/evidence/2026-10-07-gpu-next-qualified-write-plan.json
lists captured write consumers in static-source banks to reduce one-bank-at-a-
time reboots. Plan itself enables nothing. Evaluate exact offsets/access and
size semantics before extending permissions; do not blanket-enable13 banks.
Can continue from Linux; no macOS visit needed. NORMAL REBOOT REQUIRED before
another firmware start: backing/mappings/power pinned; never force-unload.

Evidence: docs/evidence/2026-10-07-gpu-sparse-counter-result.json. Raw capture
under out/gpu-gravity-contract/asc-graph-init/boot-60b99992-6e38-4dbf-9ed4-eae746b9463d/
and exact-register-read/boot-60b99992-6e38-4dbf-9ed4-eae746b9463d/. Source-at-trial
preserves exact helper/fixture/module. All raw DATA/object/ADT/logs plus tracked
source/alignment pins/configs/patches in /boot/GPUC002/linux-return.tar.gz.
Firmware TEXT code image omitted per no Apple binaries request; exact hash,
normalized contract and instruction-word checks supplied. Prior GPUC002 input
kit preserved. No credentials, Apple driver binaries or system images.

---

# GPUC002 real Bumper/DFender trial advances — 2026-10-07

Boot e84612d6-9ed1-422a-ba2b-ede8da14bd43; unchanged GPU-contract kernel,
original boot.bin/default/WFI. Received GPUC002 input checksum verification
passed for all4 files; matching25G83 static map/provenance saved in
 docs/evidence/gpuc002-input/. Apple source binaries were not supplied/needed.

Fresh ADT translation/resources and kernel notes matched. Five exact reads
completed using GFX genpd; no scan or host register writes. Bumper288d440a0=
ffff6fdb,+a4=ff,+a8=0; low20bitsf6fdb matches16-core mask. DFender288e01704=0,
+1780=fe66. Helpers unloaded normally. Initial ADT sysfs-path typo stopped
before GPU access; sampler unloaded; corrected path/validation then passed.

NATIVE trial removed RAM surrogate. Slots33/35 now map real banks288d44000 /
288e00000,4000 each, writable device leaves ONLY on those2 pages. Descriptor
flags1; hardware+2560=f6fdb,+2568=0. Slot32 ScratchRam extent corrected from
8000 to20000 using matching static map.21 object pages,32 device pages,2 tables.
Cold RTKit/root publication, five-second capture, ASC stopped; backing pinned.
Five serializer checks and matching-kernel module build passed.

Readback after firmware: Bumper+a0=f6fdb,+a4=0,+a8=0. This confirms real mask
programming, replacing the previous RAM-only diagnostic. Firmware mask globals
18bb60=f6fdb,18bb70=3db,18bb80=f6c00. DFender reads unchanged0/fe66; execution
passed earlier null slot35 write1704. User confirms all peripherals normal.

NEXT fault: NEW2544-byte crashlog validfooter, PCfffffc000002b7f8,
FARfffffc20001c7860, ESR9600004f (write permission),x12=70700777. Instructions
load cached slot41 virtual18fa90, then STRW12[base,+60]. Physical target
288e1f860 lies in HAL40 GFXCLKGENMGPU page288e1c000+4000. This is our deliberate
read-only PTE stopping a write, not another null bank. Counter offset/role came
from donor map; qualify exact target/access before granting its page write.
Do not grant writes to the whole MMIO aperture. Keep scanner quarantined.

ALSO prepare coherent MMIO virtual layout: captured2b9e4..2b9ec computes from
slot29 virtual then subtractsD10000. Dense unrelated bank VAs used so far do
not preserve SGX-relative arithmetic. Map qualified banks at a shared MMIO
virtual base+their primarySGX offset, preserving sparse page ownership,
no RAM overlap, shared-page permission unions and complete TLBI coverage.
This can be prepared from Linux before next trial; no new macOS handoff needed
merely to address the current PTE/layout issues. No further firmware start
until NORMAL REBOOT; never force-unload/free published mappings.

Evidence: docs/evidence/2026-10-07-gpuc002-real-register-result.json.
Raw: out/gpu-gravity-contract/asc-graph-init/boot-e84612d6-9ed1-422a-ba2b-ede8da14bd43/
and exact-register-read/boot-e84612d6-9ed1-422a-ba2b-ede8da14bd43/.
Source-at-trial/ contains exact helper/fixture/module snapshots. No full GPU
initialization, rendering or acceleration established. Apple binary-analysis
provenance explicit; current result strengthens register roles, not clean-room.

Return packet /boot/GPUC002/linux-return.tar.gz includes this document, current
tracked repository (alignment recipes/pins/configs/patches/helpers), trial
config/build receipts, raw data/object/log captures and checksums. Firmware TEXT
code image remains local and is excluded to honor no Apple binaries; its hash,
normalized contract and checked instruction words are included. No credentials,
Apple driver/kernel binaries or full system images included.

---

# Bumper RAM diagnostic passes; real slot33/35 mappings needed — 2026-10-07

Boot54817cb4-dc3e-46a6-99c3-432ea842b99e recovered from prior speculative-bank
hang. Scanner remains quarantined and was NOT repeated. Current kernel/default,
original boot.bin and continuous WFI unchanged.

NEW FINDING: Bumper mask registers are programmed by firmware from hardware
fields+2560/+2568 (writes+a0/+a4/+a8). The subsequent readback at2a774 is not
established as a fuse/identification read. Initial zeros at the candidate bank
are therefore inconclusive, not grounds to reject its physical address.

Four OFFLINE producer/consumer cases passed using captured instructions:
16-coref6fdb,20-corefffff,single-cluster3ff,zero. Cluster outputs preserve
packed bit position. Tool model-bumper-mask.py and evidence bumper-mask-model.

NATIVE DIAGNOSTIC executed: slot33 now points to an owned READ-ONLY RAM page
preloadedf6fdb, not an MMIO Bumper mapping.22 object/surrogate pages,24 read-only
device leaves,2 owned tables,46 mappedVAs. Hardware mask-programming inputs
2560/2568 stayzero. Helper patches descriptor physical PA to owned RAM before
publication. Firmware read RAM mask and wrote fullf6fdb to18bb60, cluster0=3db
to18bb70, cluster1=f6c00 to18bb80. Surrogate page unchanged.

Next concrete blocker: slot35 FenderRegsDFenderMGPUCfg cached virtual18f9a0
is zero. NEW2544-byte crashlog validfooter: PCfffffc000003963c, FAR1704,
ESR96000044 (write), x8=0. Captured instructions39634 ADRP18f000,
39638 load#9a0,3963c STRWZR[x8,#1704]. No complete initialization or rendering;
surrogate does not prove native Bumper identity/programming.

Raw: out/gpu-gravity-contract/asc-graph-init/
boot-54817cb4-dc3e-46a6-99c3-432ea842b99e/. Native evidence:
docs/evidence/2026-10-07-gravity-gpu-bumper-surrogate-result.json.
Read-only bank scan failure remains separately preserved. User confirms desktop,
input,USB,networking all normal. Five batch checks passed; matching-kernel
external module build passed. Captured offline mask cases4 passed.

NEXT productive hardware step: macOS/register-map source investigation to
establish actual Bumper33/DFenderMGPUCfg35 addresses and access prerequisites.
Focused request: docs/gpu-macos-register-map-request.md.
Shared-boot bundle: /boot/GPUC001/register-map-handoff.tar.gz includes this
handover, request, offline tools, native capture and failure evidence. Return complete46-name
mapping table if feasible, not just one bank. Conservative offline inventory:
210 locally resolved accesses across12 slots, with3 exact instruction anchors
checked; audit-register-consumers.py and register-consumers.json. Not a full
CFG/access-coverage proof. No further speculative-bank scans.

Another GPU firmware start requires NORMAL REBOOT because published resources
remain pinned. No additional reboot merely for recovery is needed. Keep kernel,
boot/default/WFI; handoff can proceed to macOS for mapping evidence.

---

# Speculative Bumper-bank scan hung machine; quarantined — 2026-10-07

Failed boot583a2999-d384-4e7d-8760-efd842a6bc90; recovered automatically into
54817cb4-dc3e-46a6-99c3-432ea842b99e, same GPU-contract kernel. No retained
probe modules after reset. No kernel/default/stage2 change was made.

Initial bounded host reads at288d000a0/a4 and288d01500/1514 returned0;
known GFender control288d04010 returned11020a. Both helpers unloaded normally.
An expanded read-only batch across15 candidate banks (secondarySGX+bank*4000,
skip knownGFender, offsets+a0/+a4) then hung the entire laptop. User reports
trackpad haptics stopped and automatic power cycle after about20seconds.

Earlier bounded samples survive in the previous journal, but no failed-batch
bank message does. Pstore empty. Exact triggering read and reset cause UNKNOWN.
The first new bank in program order was288d08000, only a lead, not proven fault
address. Do not infer a register-map identity from zeros or a bus hang. Read-only
MMIO can still stall hardware; aperture containment is not an access guarantee.
No firmware start or register writes by reader were attempted in this batch;
GFX was resumed through the existing genpd provider.

Scanner QUARANTINED: source.c.disabled, Makefile rejects build, failed module
preserved as out/gpu-gravity-contract/bumper-candidate-read/
failed-bank-batch.ko.disabled. Failed source/module hashes and post-reset logs:
docs/evidence/2026-10-07-gravity-gpu-bumper-scan-hang.json. Do not rerun it.

NEXT: obtain attributable physical Bumper mapping/access prerequisites, using
source or macOS tracing rather than more speculative aperture scans. Slot33 and
firmware+a0/+a4 consumer remain verified; physical bank does not. Larger batches
remain appropriate where each register address/access prerequisite has evidence.
Current reboot already cleared the failure; no additional reboot needed merely
to recover. Keep original boot.bin, current default and continuous WFI.

---

# Read-only register batch advances; Bumper descriptor next — 2026-10-07

Boot c6a64586-e1fb-4d69-802b-a9d066be2c7a, same GPU-contract kernel.
BATCH EXECUTED: cold handshake, shadow validation,21 object pages plus2 owned
page tables,24 read-only device leaves covering11 candidate SGX descriptors,
profile-A core/SRAM voltage cluster columns, one allocations-enabled root
publication, five-second observation and stopped-ASC snapshots.

Former slot26 GFender access passed: cached virtual18f838 now contains
fffffc2000174000. StatusA+10 and+14 both equal1; prior run+14 stayed0.
Firmware DATA changed68364 bytes. This is further initialization progress,
not complete initialization, render submission or GPU acceleration. Read-only
leaves grant no SGX write permissions; advancement does not validate every bank.

New2544-byte structured crashlog has valid repeated footer, task6,
PCfffffc000002a77c, FARa0, ESR96000004, x8=0. Exact captured TEXT words checked:
2a774 ADRP18f000;2a778 loads cached virtual18f950;2a77c reads+0xa0;
2a780 would read+0xa4. Cachedbase18f420/stride28 identifies slot33,
FenderRegsBumper (record18f948, hardware+b68). Slot33 virtual is zero.
Following instructions combine the words and partition ten-bit masks. Candidate
packed ADT enabled mask is0xf6fdb (3db | 3db<<10), but Bumper register identity
and physical address are NOT established. Task6 role is also unqualified.

NEXT: identify Bumper physical bank from attributable register-map evidence,
then add that descriptor and other independently justified mandatory consumers
in a useful read-only batch. The captured firmware copy table establishes slot
name/number, not its physical bank address. Current Gravity platform map and
uploaded ABI document do not supply Bumper. Do not guess it from neighboring
addresses or silently treat all donor offsets as validated. Keep two-cluster
mask width separate from enabled-core count in the variant-porting writeup.

Raw capture: out/gpu-gravity-contract/asc-graph-init/
boot-c6a64586-e1fb-4d69-802b-a9d066be2c7a/ (TEXT/DATA, ADT, tables,
objects, dmesg, attempt and validated build receipt). Decoded registers and
instruction checks: docs/evidence/2026-10-07-gravity-gpu-readonly-register-result.json.
User confirms desktop/input/USB/networking all normal. Four register-batch
checks and five graph checks passed. The builder now labels device access in
its generated receipt; cleanup diagnostic now reports all45 invalidated VAs.
Those metadata/log fixes postdate this native artifact; raw hashes preserved.

NORMAL LINUX REBOOT REQUIRED before another firmware start: published object
backing/mappings/power stay pinned. Never force unload or retry a warm wake.
Kernel/default/original boot.bin/continuous WFI unchanged; GRUB input deferred.
No macOS handoff currently required for the next evidence investigation.

---

# Native allocations-enabled GPU graph consumed; GFender mapping blocker — 2026-10-07

Boot e1e8db50-10f6-46b5-8d73-a593b7e2c611, same GPU-contract kernel.
Original working stage2cb3ab77... is installed; built-in input and GRUB display
recovered after full power cycle. GRUB keyboard work deferred by user.

BATCH EXECUTED: shadow allocation/walk, cold RTKit handshake/crashlog/ON,
21 structural object pages plus2 owned tables, all16 relocated edges, writable
firmware mappings, endpoints32/33, allocations-enabled root publication and
five-second observation. Existing firmware root descriptors preserved. Native
root globals contain matching main/statusA/statusB/RegionC pointers and G16S
identifier; statusA+10 changed0->1. Complete object snapshots captured.

Firmware progressed beyond root parsing and produced a NEW2160-byte structured
crashlog (valid repeated footer), with PCfffffc0000029ea8, FAR10, ESR96000004,
x9=0. Pinned instruction reads cached descriptor26 virtual address at18f838,
then dereferences+10. Register-table audit names slot26 FenderRegsGFenderCfg.
The explicit zero-opaque fixture intentionally lacked MMIO descriptors; this
is a concrete missing mapping, not a hardware/firmware ABI rejection. No complete
initialization, work submission or rendering established. StatusA+14 remains0.

One additional READ-ONLY native sample at candidate288d04010 returned11020a;
helper unloaded. Candidate is primarySGX288000000+d04000 (secondarySGX+4000),
contained in both ADT apertures. Firmware extracts bits8..15=2 and bits16..19=1;
consistent with topology, not full register-role/permissions proof. No SGX
register writes by our host helper. GFX power held by retained graph.

Raw capture: out/gpu-gravity-contract/asc-graph-init/
boot-e1e8db50-10f6-46b5-8d73-a593b7e2c611/. Includes firmware DATA/TEXT, ADT,
tables, all objects before/after, endpoint logs, Crg8 registers, source/artifact
receipt and GFender candidate read. Evidence: docs/evidence/
2026-10-07-gravity-gpu-native-graph-result.json and next-register-batch.json.
Preflight Python hash-type mistake occurred BEFORE any graph insmod, separately
archived with zero tables/noASC modules, fixed then fresh checks reran. No
warm-wake retry was performed. Published graph refcount1 remains pinned, ASC
control0/status6e. NEVER force unload/free mappings or release GFX power.

User smoke check after batch: desktop, keyboard/trackpad, USB and networking
all normal.

NEXT: normal Linux reboot required before another GPU firmware start. Keep
original boot bundle/current kernel/default/WFI. Build next useful batch from
required MMIO mappings plus already-qualified shared graph fields. Device MMIO
PTEs need device attributes, not shared-RAM attributes. Trace later mandatory
slot consumers before mapping containment-only candidates. SGX relative offsets
must use the correct primary base; do not blindly add them to second resource.
Use docs/evidence/2026-10-07-gravity-gpu-next-register-batch.json. No macOS needed.
Deferred writeup request saved in docs/gpu-variant-porting-notes.md: after16-core
driver works, compare16/20-core variants with explicit evidence/provenance.

---

# Working input restored; allocations-enabled GPU batch prepared — 2026-10-07

Full shutdown/power-on recovered GRUB display and built-in keyboard/trackpad,
confirmed by user and by both Apple DockChannel input devices registering on
boot e1e8db50-10f6-46b5-8d73-a593b7e2c611. /boot/boot.bin matches original
cb3ab77bdac7f276b5331d8580a5ee1b81f8bd215c0cba1449391a73d790ef09.
Bootloader input work is deferred; do not reinstall the failed MTP variant.

GPU experiment now prepared: asc-graph-init publishes the entire structural
fixture in one cold run (17 objects,16 relocated edges,21 object pages plus2
owned tables). Shadow allocation/walk precedes live mapping. Read/write firmware
PTEs; allocations-enabled G16S root; opaque contents explicitly zero; candidate
page-table geometry/status fields. No donor T8132 MMIO descriptors, SGX register
writes, queues, shaders or rendering commands. This is not a production init
graph. User explicitly requests larger useful batches and accepts recoverable
hangs. Run captures endpoint responses, firmware DATA, and all21 object pages.
Every published resource pins until reboot, even if ASC stop succeeds; never
force unload. Artifacts/source hashes in asc-root-envelope/build-receipt.json.
Runner persists attempt intent before hardware changes. Current kernel/default
and continuous WFI unchanged; no macOS work needed.

---

# Keyboard trial FAILED and stage 2 restored — 2026-10-07

Boot 9a42112c-6d16-46a9-ae4c-77c0526fd868, same GPU-contract kernel.
User observed no visible GRUB menu and loss of built-in keyboard/trackpad in
Linux. Kernel: dockchannel-hid 514600000.hid timed out waiting for RTKit
endpoint map (-62), failed to wake coprocessor, and probe failed. Only USB
YubiKey keyboard registered. This is a real native regression, not a successful
keyboard trial. GPU firmware publication was NOT attempted on this boot.

Restored /boot/boot.bin from verified /boot/keyboard-trial/boot-before.bin.
Readback SHA256 cb3ab77bdac7f276b5331d8580a5ee1b81f8bd215c0cba1449391a73d790ef09
matches qualified working Gravity loader. No enrolled stage-1, kernel, GRUB
configuration or WFI changes. Running MTP state is not repaired by replacing
the file. Next action: full shutdown and power-on to reset firmware state,
then verify built-in input and usual peripherals. Recovery still pending.

Capture: out/keyboard-stage2/failed-boot-9a42112c-6d16-46a9-ae4c-77c0526fd868/
(dmesg, kernel journal, live DT, input devices, hashes and result).
Evidence: docs/evidence/2026-10-07-boot-keyboard-failure.json.
Do not reinstall the failed keyboard bundle. Investigate RTKit helper
startup/quiesce/stop and FIFO replay before another native keyboard trial.
U-Boot MTP use is a suspect, not a proven root cause; GRUB display regression
also remains unexplained. Preserve these captures. GPU work can resume after
restored input is confirmed; current boot has no GPU probe resources retained.

---

# MTP keyboard stage-2 trial installed; reboot for GRUB input test — 2026-10-07

Installed /boot/boot.bin SHA256:
e67d38fabffc9c2d1e6414c9335fc896525d4cbc8b2b5481d3cb3dcd7f082758.
Backup /boot/keyboard-trial/boot-before.bin SHA256:
cb3ab77bdac7f276b5331d8580a5ee1b81f8bd215c0cba1449391a73d790ef09.
Native ESP identity and backup/new-bundle readbacks passed. No reboot performed.
Stage 1 unchanged; exact working stage-2 m1n1 retained. Existing GPU-contract
kernel/default entry and continuous WFI unchanged. U-Boot remains based on
Gravity a2f6913694ff26908c16948af3f8372429782263 (2026.07).

Enabled DM_KEYBOARD/APPLE_KEYB/APPLE_MTP_KEYB and stdin=mtpkbd; USB/PCI remain
disabled. Added two boot-only MTP nodes and five individually checked MMU
windows for ASC, SRAM, mailbox and paired FIFO data. Every original baseline
DT property is preserved. archnvme removes the two nodes from its separate
handoff copy before applying the existing Linux overlay. The working Linux
HID binding remains intact. Native compilation, resolved config, reviewed
source hashes, component framing, DT preservation/removal checks passed.
Keyboard behavior is NOT YET hardware-tested. See docs/boot-keyboard.md and
docs/evidence/2026-10-07-boot-keyboard-trial.json. Exact installed receipt and
rollback bundle are in /boot/keyboard-trial/.

NEXT REBOOT: press an arrow key during the GRUB countdown; try moving between
entries, then boot the same GPU-contract entry. Confirm Linux keyboard/trackpad,
USB and networking. No re-enrollment or macOS work required unless boot fails.
Rollback from Linux: sudo cp /boot/keyboard-trial/boot-before.bin /boot/boot.bin;
sync. If necessary mount M4RCHESP from macOS and copy keyboard-trial/boot-before.bin
over boot.bin there. Prior loader-alignment manifest identifies the BASE bundle,
not this trial; use keyboard-trial/installed.json for its exact component hashes.

GPU work: captured-firmware parser emulator now reproduces the observed disabled-
allocation rejection (52 instructions, 26 root accesses) and returns from the
root parser with allocations enabled (2223 instructions, 979 object accesses).
All enabled-model accesses fit explicit templates. This is ONLY a bounded
Unicorn model: RTKit receive substituted, pointer authentication omitted, zero
opaque fixtures, no MMIO/real hardware initialization/rendering proof.
Three regression tests pass, including deliberately reducing status B to two
pages and observing the actual instruction's out-of-template access.
Evidence: docs/evidence/2026-10-07-gravity-gpu-parser-{disabled,enabled}-model.json.

IMPORTANT CORRECTION: status B requires at least e43c bytes, FOUR 16KiB pages,
from pinned reads at c728/c72c/e434/e438. Combined with power minimum6564,
there are20 known backing pages plus1 provisional unknown root+c0 marker:
21 candidate object pages, plus2 owned table pages. Older19-page candidate
claims below are superseded. Completed native18-page marker trial is still
valid for its tested capacity. Five updated offline graph tests pass.
Register-table audit independently qualifies the 0x28 descriptor stride and
0x24 copied prefix; names/containment are not proof of T6040 register roles.

GPU NEXT: prepare a batched allocations-enabled native structural-init probe
with corrected backing and full evidence capture. No additional arena-only
reboot. Keep every published page/mapping/power reference pinned until reboot,
even on failure. Zero opaque objects are an explicit experimental fixture,
not a complete production initialization graph. User accepts recoverable hangs
and asks for larger useful test batches. The next keyboard reboot also provides
a fresh GPU ASC; prepare/run the native graph probe in that boot once its
artifact/fresh-boot checks pass. Do not repeat warm ASC wake in the current boot.

---

# Expanded native arena PASSED; profile-A voltage geometry qualified — 2026-10-07

Boot 0ce64a9c-cdcd-4030-b5a8-684d085ba0b7, matching GPU-contract kernel.
Fresh ADT, artifact hashes and normalized firmware TEXT passed. The shared
runner now exercised natively: 18 object marker pages plus two tables (20
owned pages). Existing firmware root2 preserved; empty child borrowed. All
18 leaves mapped; endpoints32/33 started and observed for250ms with no traffic.
NO ROOT ADDRESS SENT. AP QUIESCED/IOP SLEEP acknowledgments and core stop
(control0/status6e) passed. Normal unload restored child and invalidated18 VAs.
Post-unload table snapshots show zero borrowed L2 and no owned-page references.
No retained probe/resources; no cleanup reboot needed. No firmware object
read/full initialization/rendering proof. Kernel/default/WFI untouched.
Evidence: docs/evidence/2026-10-07-gravity-gpu-expanded-arena-result.json.

Original attempt.json incorrectly retained mapping_or_publication_performed=false
from validation, despite mapped_expected_pages=true and logs proving mapping.
Summary explains this; raw capture preserved; runner fixed for future attempts.

New manually reviewed/hash-pinned parser-loop finding: profile A reads BOTH
cluster columns, core1008/100c and SRAM1408/140c, with40-hex row stride across
16 storage slots. It reads voltages even where frequency is zero. This confirms
the separate-cluster geometry in the shared document. Do not confuse16 storage
slots with the11 decoded voltage groups. Offline codec now emits full400-byte
arrays, explicitly zeroing the remaining5 rows and unused14 columns, instead
of leaving tail rows opaque. Four candidate hardware arrays use this geometry;
profile-B consumer semantics and A/B group/frequency assignment remain unknown.
Fresh ADT Python/Rust cross-check passed; standalone core+SRAM wire now800 bytes.
Eight Rust codec tests passed, including tail-zero and opaque-field preservation.
No running-driver change. Evidence: voltage-consumer-audit.json and
voltage-storage-wire.json. Earlier580-byte standalone wire is superseded.

Additional qualified power-object finding: main+471 target has a u32 write
at6560 and an independent u32 read6420. Minimum extent is6564, TWO16KiB pages;
earlier40-byte provisional minimum is superseded. Plan now requires18 known
pages plus an unknown root+c0 marker would make19 candidate object pages. The
completed18-page mapping trial remains valid for that capacity, but it does
not establish this revised graph's extent/content correctness. Another
arena-only reboot is unnecessary; carry this into the eventual full-graph
trial. Five updated graph tests passed. Evidence: power-extent-audit.json and
init-graph-power-revision.json.

NEXT: finish explicit object contents/transitive pointers, channel/status
contracts and T6040 hardware/register settings before positive initialization.
Root+c0 target extent remains unknown. Full graph acceptance and rendering are
still untested. ASC sleeping6e; a future firmware trial needs a normal reboot,
but another arena-only repeat is unnecessary. No new positive trial ready yet;
continue useful offline qualification before requesting another reboot.

# Expanded graph/status qualification and next mapping trial — 2026-10-07

Offline work only this round; no modules loaded or firmware started. WFI and
kernel/GRUB default remain unchanged. Current ASC remains sleeping6e after
the earlier clean arena shutdown.

Hash-pinned firmware audit now confirms root+a8/b0 status-pointer provenance.
Status B (root+b0) is read at48f0 asu64: minimum extent48f8, at least TWO16KiB
pages. Status A has u32 writes14/1c after parser return (minimum20). Region A
(root+08) has u32 read10 (minimum14). Root+b8 object has u32 read/write680
(minimum684, within standalone document6a8). Root+c0 pointer is copied but its
target extent remains unknown. No claim that notification fields48e0/48e8
are independently verified. Evidence: status-fields-audit.json.

Expanded sizing plan:17 objects,16 pointer edges,278528 bytes (17 pages) of
known minimum backing; root+c0 target explicitly unreserved. Earlier13-page
native preflight does NOT cover this expanded plan. Offline assembler requires
all17 explicit opaque templates, rejects missing/short inputs, preserves other
bytes and relocates16 edges. Five boundary/preservation tests passed. Every
output remains unpublishable: opaque contents/transitive pointers/full layouts
and T6040 hardware contracts still require work. Conservative tracer now439
hints; hints are not qualified semantic findings.

NEXT REBOOT TRIAL READY: expanded arena probe compiled for the current matching
GPU-contract kernel.18 marker object pages plus two tables (20 owned pages);
one marker page for unknown root+c0 target is capacity testing ONLY. NO ROOT
ADDRESS SENT. Same acknowledged retirement requirements. Updated runner records
expected page count and post-unload table/L2 snapshots, verifies zero borrowed
L2 and no references to any owned page. Expanded native trial NOT YET RUN.
Build/module hashes: docs/evidence/2026-10-07-gravity-gpu-expanded-arena-preparation.json.

Normal Linux reboot needed for fresh cold ASC; no new kernel/install/default
change and no macOS handoff needed. After reboot run:
sudo python experiments/t6040-gpu/run-root-envelope.py out/gpu-gravity-contract --arena --run
Do not replay while ASC sleeping6e; do not force-unload a retained probe.
This trial qualifies allocation/mapping cleanup, not initialized GPU firmware
or acceleration. Full positive graph remains a later step.

# Full provisional arena preflight passed; clean teardown — 2026-10-07

Boot541905c2-2712-49f1-a5a7-5269b8d26f6c. Retained root-reader probe cleared
by reboot. Firmware initially cold; fresh ADT/text validation passed. New
asc-arena-preflight allocated15 owned16KiB pages (two tables +13 object pages),
checked42-bit PA bounds/leaf entries, preserved firmware root2 and installed
only verified-empty borrowed child. START32/33 observed250ms, no messages.
NO ROOT ADDRESS SENT. AP QUIESCED and IOP SLEEP ACKs, core stop6e and emptyFIFO
passed; refcount0; normal unload removed child, invalidated13 VAs and freed
backing/power. Read-only post-unload snapshots: reservedL2 allzero; NO owned
page references in captured table/L2 reservations. No resources retained.
This qualifies arena construction/retirement, not firmware object reads or
initialized-graph teardown. Evidence2026-10-07-gravity-gpu-arena-preflight.json.

Important correction to earlier raw-row caution: both independently decoded
cluster tables collapse16 raw rows into11 contiguous voltage groups. Existing
Python contract.ladder and Rust profile.ladder agree on all22 groups; generated
wire core/SRAM columns independently checked and unused columns zero. Separate
cluster voltages preserved. Earlier16-vs11 warning is NOT a row-count blocker;
full profile A/B assignment/other power fields still need qualification. New
build-cluster-voltage-wire.py emits offline inputs, no frequency assignment or
power estimates. evidence2026-10-07-gravity-gpu-cluster-voltage-wire.json.
Candidate hardware_voltages codec patches only the four documented arrays,
preserving unknown fields;8 meaningful wire tests passed. Not driver-linked.

Static straight-line pointer tracer produced296 access hints, NOT semantic
proof. Manual/hash-pinned audit qualifies main+250 asu32 gate, main+3e0 asbyte
bit-selection, and main+10 object pointer: firstu32 gate; enabled path copies
128bytes starting+4, reaches84. Full88 extent remains document claim. Additional
main240 field still unresolved. evidence2026-10-07-gravity-gpu-init-fields-audit.json.

NEXT: continue full G16S graph construction/qualification before a positive
publication trial. Do not merely enable allocations on a zero-pointer root.
Main240, full pointer graph, channel/status objects, hardware register/MMIO
contracts, voltage profiles and post-publication lifetimes remain explicit.
ASC now sleeping6e; next firmware run needs normal reboot for cold state.
NO cleanup reboot required; no kernel/package/default change. Shared runner
--arena integration prepared but not separately exercised; native run used
captured direct harness. Source experiments/t6040-gpu/asc-arena-preflight.
Build all helpers via build-root-envelope.py. Same default1, WFI retained.

# Native root-reader negative control PASSED — 2026-10-07

Boot5e408089-cfa5-4406-b1be-44791905520a, same default1 GPU-contract kernel.
Fresh metadata/normalized firmware qualified. HELLO/maps/crashlog/IOP ON/AP ON
passed. Existing root2 preserved; verified-zero borrowed L1 child mapped to
owned leaf/envelope pages. START32/33 and root publication sent. EP1 crash
notification10110001de4000 received. Newly written structured crashlog at
DATA+a0000 contains EXACT expected rejection:
Host-mapped FW allocations are disabled, but FW only supports enabled
(init_data_addr=0xfffffc2000100000)!
Stack includes fffffc000002fa2c, the qualified parser's disabled-allocation
error callsite. Header declares5b0 bytes; sections bounded; terminal32-byte
record exactly repeats opening header. Old kernel decoder treats footer's
flags as section length and does not support that terminal form; offline
script explicitly checks identical repeated header instead.

This corroborates owned root mapping/cache visibility, message delivery, root
consumption and G16S interface comparison. NOT full initialization, queues,
rendering or GPU acceleration. Host stayed available for capture; user-visible
peripheral status not independently asked this boot.

ASC stopped control0/status6e. Deliberate rejection skipped power retirement;
probe and mapping/backing/power remain pinned as designed. NEVER force unload.
A normal reboot is now required to reclaim them and obtain another cold ASC.
No new kernel/install/default change required. Next prepare enabled-host root
with complete mapped pointer dependencies; do not merely set+2c=1 on this
zero-pointer envelope. Full main/hardware graph and performance ladder
conversion remain blockers before positive initialization trial.

Evidence docs/evidence/2026-10-07-gravity-gpu-root-reader.json and
2026-10-07-gravity-gpu-root-reader-crashlog.json. Offline decoder
experiments/t6040-gpu/decode-root-crashlog.py; raw samples/logs under
out/gpu-gravity-contract/asc-root-envelope/boot-5e408089-....

# Root-reader first boot: guarded refusal, correction ready — 2026-10-07

Boot66756857-e512-4d3d-91c4-9e582b816cb5. Cold firmware table reservation
initially ALL ZERO. First runner stopped before firmware start; sequencing
corrected to map only AFTER HELLO/maps/crashlog/IOP ON/AP ON. Those handshakes
then passed. Owned envelope pages allocated/shadow walk passed, but mapping
refused because firmware table descriptors carry AF bit10: root105fff7c403,
L1 105fff80403; TEXT leaf10000be44c3; DATA leaf20010001d444c3.
NO bootstrap slot changed, NO root transmitted. This is not an interface or
initialization failure; the old guard expected low bits3 instead of403.
ASC stopped control0/status6e. Old failure path skipped retirement ACKs and
pinned asc_root_envelope resources. NEVER force unload. Reboot required.

Additional finding: after ON, root slot2=200105fff744cb points to the separate
reserved page105fff74000; captured page is all zero. Old post-shutdown snapshots
missed this live descriptor. Preserve it; do not replace slot2. Corrected helper
borrows an empty child slot in that verified zero page instead. Fresh ADT checks
its exact base/size. Any unexpected descriptor or nonzero child page refuses.
Offline captured-table model walked proposed leaf/root, preserved root2 and
restored the child page to zero. No native mapping has been attempted yet.

Corrected helper rebuilt W=1 clean: allow only AF bit10 on table descriptors,
retain exact addresses/type checks, verify valid leaf TEXT/DATA translations,
require slot2 empty. root_prepare now runs after handshake. Prepublication
refusals now attempt acknowledged AP QUIESCED/IOP SLEEP instead of immediately
pinning. Publication still always pins until following reboot. Corrected helper
not loaded on this sleeping/pinned boot. Next owner r: fresh validation then
run-root-envelope.py --run, same kernel/default1. No macOS handoff/install.

Evidence docs/evidence/2026-10-07-gravity-gpu-root-envelope-first-boot.json;
raw samples/logs out/gpu-gravity-contract/asc-root-envelope/boot-66756857-....
Original loaded-module SHA was not copied into per-boot receipt and its build
receipt was overwritten during correction; do NOT assign new helper's hash to
that run. Runner now preserves the complete validated build receipt per boot.

# Minimal G16S root reader trial ready; reboot boundary — 2026-10-07

Current boot38792891-2fb1-4c7c-92eb-84e6b530125b, same GPU-contract kernel.
NEW source experiments/t6040-gpu/asc-root-envelope; matching module and helpers
built under out/gpu-gravity-contract. Native allocation-only gate1 passed three
runs with normal unload. Defaultgate0 refusal confirmed. Fresh ADT, bootstrap
TEXT/DATA translations, target slot2 empty, and parser firmware qualified using
read-only samplers; all helpers unloaded. No root mapping/publication performed.
Evidence docs/evidence/2026-10-07-gravity-gpu-root-envelope-preflight.json.

NEXT requires a normal reboot for cold ASC status6a (this boot already slept).
Do not replay START from6e. No new kernel/package/default-entry changes needed.
After owner "r", validate/run:
sudo python experiments/t6040-gpu/run-root-envelope.py out/gpu-gravity-contract --run
Save work. This sends a minimal root with correct G16S ID but disabled host
allocations (+2c zero), intentionally expecting firmware's specific early
rejection BEFORE main/RegionC dereferences. It tests owned backing/table/cache/
transport/interface, not initialization or acceleration. Parser's error string
and branch checked in captured TEXT. Transmission or silence is not success.
Raw before/after DATA retained for structured crashlog interpretation. Probe
retains pages/PTE mapping/power after publication and pins until FOLLOWING
reboot; never force-remove. Host hang possible. Read README for exact bounds.

New firmware finding: current TEXT SHA72beef809ef62a6a7ba9862cf60595135811bbedbb732346571f64818744e199
versus historical f09648... differs in only14 bytes inside two tagged8-byte
payloads at59841 (GKTS) and59924 (ECAP), lengths8. Meaning not established.
All other bytes match. Normalized SHA190cef1946a23dfbde180592629631c3b28d0509a17eb76108b7c9a52accd9ac.
firmware_text_contract.py checks exact image outside only those payloads plus
exact tag/length; changed parser instruction rejected in verification. Fresh
instruction audit evidence2026-10-07-gravity-gpu-firmware-interface-current.json.

Full-graph caution: ADT perf-state-count16, gpu-num-perf-states15,
perf-state-table-count2; perf-states/perf-states-sram256 bytes each and
perf-states1/perf-states-sram1 128 each. Donor builder/standalone voltage note
11-row assumptions need explicit conversion qualification, not truncation.
This minimal rejection root contains no hardware-data/voltage table.

# G16S nested pointers qualified; explicit graph plan — 2026-10-07

Offline captured-firmware audit now independently corroborates two more paths:
main+0 -> hardware-data; hardware+26b8 -> nested counter object. fcec/fcf0
loads main global18e4c0,fcf4 dereferences main,fcf8 loads nested pointer;
fd04 reads nested+e00 u64. Independent14d20/24/28 chain reaches the same
object and14d48 reads indexed+e20. Pointer and counter-like use confirmed;
full e40 extent and counter semantics remain document claims.

Root+20 -> Region C is stored at global195748 by2f300.3888/388c load that
pointer,3890 adds e51,3894 reads u32. Confirms parent/offset/width, not the
host-write protocol. main+240 remains unresolved:15aa0/15b80/382c4/38380
matches are unrelated global146240 accesses. Do not use those as ABI evidence.
All signatures verified against exact TEXT SHA in the executable audit.

experiments/t6040-gpu/plan-init-graph.py produces an OFFLINE relative-arena
plan:13 independently paged objects,12 pointer edges,212992 provisional bytes.
No GPU VAs, physical allocations, firmware serialization or publication.
Incomplete extents are labelled; topology stays J614s16 cores3db/3db.
Plan includes explicit unresolved dependencies, including channels/status,
hardware descriptors/voltages, main240, ownership and mapping lifetimes.
Evidence docs/evidence/2026-10-07-gravity-gpu-init-graph-plan.json.

Validation: graph bounds checks passed and rejected an out-of-parent pointer;
all7 G16S wire-codec tests passed. Boot-table audit now verifies lengths and
SHA256 for ALL snapshots before interpreting them; original translations
reproduced. No live GPU changes or reboot requirement introduced. Continue
qualifying object contents and constructing a T6040-specific allocation preflight;
normal startup remains gated and warm wake unresolved.

# Application observation passed; native firmware ABI corroboration — 2026-10-07

Current GPU-contract boot 38792891-2fb1-4c7c-92eb-84e6b530125b; WFI Y.
Cold HELLO/map/crashlog, IOP/AP ON and START32/33 passed.250ms observation
received zero application messages. Exact shutdown ACKs, stop and normal unload
passed. No probe resources retained; no reboot needed for cleanup. Silence does
not prove readiness or execution. No initialization graph/work submitted.

OFFLINE BREAKTHROUGH: captured loaded RTKit3255.160.4 TEXT independently
corroborates document G16S identifier0c8aa322039604c0. MOVZ/MOVK at offset2f254
construct it;2f250 loads root firstu64;2f264 compares;2f268 branches on mismatch.
Root copying reaches finalu64+c0, consistent with c8 bytes. Copied root+18 main
pointer is stored at firmware global18e4c0. Routine3734 loads main,3738 adds471,
373c dereferences power pointer.537c loads main,5380 adds254,5384 dereferences
block+18. These are static code findings, not initialization acceptance proof.
Earlier contiguous-byte search gave no match because constants are instruction
immediates. Snapshot hash and instruction signatures recorded for reproducibility.

NEXT: build explicit G16S initialization-object/allocation plan from this evidence;
qualify remaining hwdata/RegionC/control-object layouts and unknown extra main
field+240. Maintain our16-core3db/3db topology and independent cluster voltages.
Do not transplant donor single-cluster builder, blindly shift all unknown fields,
or publish root until mapped backing, cache/lifetime handling and object extents
are concretely reviewable. Normal T6040 startup remains gated. Do not request
another reboot merely to repeat app observation. Warm wake still unresolved;
next actual cold publication experiment will require reboot once prepared.

Evidence docs/evidence/2026-10-07-gravity-gpu-app-observation.json and
2026-10-07-gravity-gpu-firmware-interface-audit.json. Reproduce static audit using
experiments/t6040-gpu/audit-firmware-interface.py on the captured TEXT snapshot.
Full disassembly/logs retained in out/gpu-gravity-contract. Same default1 kernel;
owner "r" means rebooted and ready. Earlier checkpoints follow.

# Application START and shutdown passed; table audit captured — 2026-10-07

Current GPU-contract boot 9a7d7e28-5156-4a4b-aeb5-c24bbcd50c5a; WFI Y.
Fresh metadata validated. Crashlog1, IOP/AP ON, START32/33, AP QUIESCED,
IOP SLEEP, stop readback and normal unload passed. No retained probe resources.
START transmission is verified; app readiness/work completion not established.
No init graph, work submissions or new DMA addresses were supplied.

Read-only snapshots captured ttbs/pagetables/l2/handoff and helpers unloaded.
Offline 16 KiB, shifts36/25/14 traversal matches TEXT and DATA physical addresses.
Candidate root/bundle share an absent top-level entry: real mapped backing is
needed before publication. ttbs/l2/handoff snapshots zero. This is a limited
snapshot audit, not allocation permission or complete collision/coherency proof.
Neither interface identifier was found as contiguous bytes in older sampled
TEXT/DATA; split instruction constants remain possible, so no ABI conclusion.

NEXT: a normal reboot is needed for the next fresh-cold firmware experiment,
NOT to clear pinned resources this time. Warm restart is unresolved; avoid
replaying START from sleeping status6e. Prepared asc-app-observe starts32/33,
observes up to250ms/32 messages without replies or init graph, then attempts
acknowledged shutdown and conditional unload. Recapture/revalidate boot firmware
DATA and matching kernel/module hashes. No kernel build or macOS handoff.
Continue explicit G16S init-graph planning; do not enable donor T8132 bootstrap.
Normal GPU startup stays gated. Owner "r" means rebooted and ready.

Evidence docs/evidence/2026-10-07-gravity-gpu-app-start.json,
2026-10-07-gravity-gpu-graph-samples.json and 2026-10-07-gravity-gpu-boot-table-audit.json.
Offline walker experiments/t6040-gpu/audit-boot-tables.py. Next source
experiments/t6040-gpu/asc-app-observe, built helper out/gpu-gravity-contract counterpart.
Earlier checkpoints follow. Same default1 GPU-contract kernel retained.

# Managed wake unresolved; application endpoint trial prepared — 2026-10-07

Current GPU-contract boot df0ffd12-a6a3-4973-a4fe-f6923f80cf71; WFI Y.
Cold HELLO/map/crashlog, IOP ON/AP ON, AP QUIESCED/IOP SLEEP passed again.
INIT220 with ASC START unchanged and continuous GFX power reference still
produced no messages in four seconds. Final control0/status48 failed stop.
asc_managed_wake is pinned; REBOOT REQUIRED. Never force removal or retry here.
This rules out START toggling or power release as the sole explanation, but
does not establish why wake fails. No further blind wake variations queued.

NEXT: normal reboot, same default1 kernel. Revalidate fresh ADT/build/module
hashes. Prepared asc-app-start starts crashlog1, validates/echoes reserved DATA
offer, establishes IOP/AP ON, then sends START to advertised application32/33.
No root/init graph, command submissions or new DMA buffer. Then request AP
QUIESCED/IOP SLEEP and attempt stop/conditional retirement. Capture all messages;
pin on failure. This advances the GPU path without requiring warm wake first.
Application readiness is not demonstrated by sending START alone: distinguish
message transmission, firmware responses and future initialization acceptance.
Full T6040 driver startup remains gated. Warm restart still requires investigation.

Receipt docs/evidence/2026-10-07-gravity-gpu-managed-wake.json; raw logs
out/gpu-gravity-contract/managed-wake-boot. Next source experiments/t6040-gpu/asc-app-start;
matching helper out/gpu-gravity-contract/asc-app-start. No kernel rebuild/macOS
handoff needed. Owner "r" means rebooted and ready. Earlier notes follow.

# Cold retirement reproduced; managed wake next — 2026-10-07

Current boot 666c136e-bee9-45f0-80a7-e30e6b4fe34a, GPU-contract kernel; WFI Y.
Fresh ADT revalidated DATA bounds. Cold endpoint1/crashlog boot, IOP ON, AP ON,
AP QUIESCED, IOP SLEEP and normal unload succeeded again. Explicit INIT220 after
manually stopping ASC and dropping/reacquiring power produced no messages.
Final control0/status48 did NOT satisfy stop readback. asc_crashlog_wake retains
resources; REBOOT REQUIRED; never force removal or retry in this boot.

NEXT: normal Linux reboot, same default1. Prepared asc-managed-wake keeps ASC
START and the same GFX power reference across three bounded protocol cycles:
cold HELLO/map/crashlog/ON/shutdown, then INIT220 warm wake without manually
stopping the controller. Only finally attempts core stop and conditional unload.
This follows the donor distinction: RTKit shutdown changes AP/IOP protocol states,
not the ASC start bit. Candidate explanation only, not native qualification.
Revalidate fresh boot ADT, build ID and module hash before loading. No application
endpoints, graph construction or new DMA buffers. Keep normal GPU startup gated.

Receipt docs/evidence/2026-10-07-gravity-gpu-explicit-wake.json; logs
out/gpu-gravity-contract/wake-boot. Next source experiments/t6040-gpu/asc-managed-wake,
matching helper built in out/gpu-gravity-contract/asc-managed-wake. No kernel rebuild
or macOS handoff required. Owner "r" means rebooted and ready. Earlier notes follow.

# Crashlog boot and shutdown passed; explicit wake next — 2026-10-07

Owner shorthand: a message consisting of "r" means rebooted and ready to continue.
Current GPU-contract boot 518f3863-eb8c-4593-9378-b7686c41706d; fresh ADT
captured with matching-kernel read-only helper, then helper unloaded; WFI Y.

Cold bounded HELLO12/map exchange + system endpoint1 start succeeded. Firmware
requested crashlog buffer 0x10001de4000+0x8000. Checked wholly within this boot's
reserved DATA range 0x10001d44000+0x138000, page aligned and disjoint from Linux
System RAM; echoed firmware's own offer. No new DMA allocation or RAM write.
IOP ON20, AP ON20, AP QUIESCED10 and IOP SLEEP1 ACKs all observed. Core stop
control0/status6e and empty RX FIFO allowed normal module unload. One successful
crashlog-only retirement, no application endpoints/initialization graph/rendering.

Repeat with ASC START alone from status6e produced no HELLO in four seconds.
Resources retained by asc_crashlog; REBOOT REQUIRED. Never force removal.
The low status bits alone do not distinguish fresh status6a from stopped/sleeping
status6e. Do not label status6e a fresh cold boot. Driver C apple_rtkit_wake uses
IOP INIT220; next prepared probe adds that explicit wake sequence, gated separately.
It accepts cold status6a, or warm6e only with wake_gate=1. Not yet run natively.

NEXT: normal Linux reboot, same default1 kernel. Recapture/revalidate firmware
DATA bounds and bind helper to new boot/build/module hashes. First qualify cold
boot/shutdown with asc-crashlog-wake; after successful unload try explicit warm
wake_gate=1. Retain on failure. No kernel build or macOS handoff required. Keep
normal T6040 startup gated. Successful shutdown does not yet prove repeatable
restart, full driver teardown or acceleration.

Receipt: docs/evidence/2026-10-07-gravity-gpu-crashlog-shutdown.json.
Sources experiments/t6040-gpu/asc-crashlog and asc-crashlog-wake. Logs/artifacts
out/gpu-gravity-contract counterparts. Earlier checkpoints follow; rollback
remains /boot/GPUC001/grub-before.cfg -> /boot/grub/grub.cfg, sync.

# Guarded GPU binding passed; shutdown trial needs reboot — 2026-10-07

Current boot 7.1.13-m4rch-gpu-contract, build ID
1c0b2b5b48a59316f75940aa4049a5f671eca95c. Owner reports peripherals normal;
WFI Y. T6040 normal-start guard refused before MMIO/firmware builders. Three
powered Rust identification cycles bound successfully, returned ID 0x0a031100,
counts 0011020a/00040404, clusters 400c0c02. Each released device, driver,
resource overlay and GFX power normally; suspend result 0. No firmware startup
in those three cycles. Captured masks remain metadata, not new native fuse reads.

Then a bounded buffer-free shutdown probe negotiated HELLO12 and both endpoint
maps. AP QUIESCED request received no response within two seconds; IOP SLEEP
was not attempted. Core stop readback control0/status6e passed. asc_shutdown is
intentionally pinned with power/mappings retained. REBOOT REQUIRED. Never force
module removal or attempt a second start in this boot. No endpoint starts, buffer
addresses, initialization graph or rendering commands were supplied.

NEXT: normal Linux reboot into the same default1 GPU-contract kernel. No new
kernel build or macOS handoff required. Qualify advertised endpoint1/crashlog
lifecycle and IOP ON acknowledgement before retrying AP shutdown. Donor RTKit
starts system endpoints explicitly to complete boot; our minimal exchange omitted
that step. This is a candidate explanation for absent AP ACK, not proven causality.
Keep normal startup gated and validate firmware-requested buffer bounds against
fresh reserved-memory metadata before acknowledging any buffer. Avoid new DMA
addresses until that contract is established. Verified teardown remains priority.

Receipts: docs/evidence/2026-10-07-gravity-gpu-binding.json and
2026-10-07-gravity-gpu-shutdown.json. Experimental source:
experiments/t6040-gpu/asc-shutdown; logs out/gpu-gravity-contract/native-boot
and asc-shutdown. Earlier staged checkpoint remains below for rollback details.

# Guarded Gravity GPU framework — staged reboot checkpoint, 2026-10-07

NEXT BOOT: 7.1.13-m4rch-gpu-contract, isolated linux-m4rch-gpu-contract package.
GRUB default 1 selects /GPUC001/vmlinuz and matching initramfs.img. Normal
maintained 7.1.13-m4rch-gravity remains entry 0. No GPU node added and no GPU
firmware/application startup allowed on T6040. Probe-only defaults to 1 and
normal startup is explicitly refused before donor board-specific builders.

Full LLVM/Rust Image/modules build and modpost passed. One upstream unused
Rust RTKit import warning. All 39 files in the maintained baseline patch are
byte-identical, including USB, WFI, framebuffer, NVMe and CPU changes. Native
package installation generated the separate NVMe initramfs. Its root UUID,
partition/bounds, release, package identity and NVMe dependencies were inspected.
Package hooks also regenerated the normal initramfs; normal kernel is unchanged.
No native trial boot or stability claim yet.

After the previous handshake reboot: retained probe resources cleared; WFI Y.
Read-only reserved TEXT/DATA samples captured and helpers unloaded normally.
Loaded TEXT contains RTKit-3255.160.4.release, matching recorded 25G83 candidate.
This is version-string evidence, not full-container byte identity or ABI proof.
Seven candidate byte-codec tests and six existing topology/voltage tests pass.
Candidate codec is independent of the live driver; unknown main fields preserved,
queue prefetch/completion separated, cluster voltage columns distinct. Reference
machine has 20 cores; retain our native 16-core masks 3db/3db.

NEXT: reboot Linux normally; check maintained peripherals and WFI/SME on this
Rust-enabled trial. Then load the guarded framework and qualify dynamic resource
metadata/identification before planning RTKit crashlog/application startup and
initialization graph. Do not jump to donor bootstrap or advertise acceleration.
Verified teardown is a priority: completed donor Bootstrap Drop calls shutdown;
raw Rust RtKit Drop only frees. Audit post-start constructor errors and test AP
QUIESCED / IOP SLEEP shutdown before relying on reload without reboot. Old bounded
ASC experiment intentionally retains resources after startup; never force unload.

Rollback: copy /boot/GPUC001/grub-before.cfg to /boot/grub/grub.cfg and sync;
normal maintained entry 0 remains present. No automatic reboot performed.
Source recipe: experiments/t6040-gpu/gravity-contract; candidate codecs g16s_abi.rs.
Receipts: docs/evidence/2026-10-07-gravity-gpu-contract-trial.json and
2026-10-07-gravity-gpu-loaded-firmware.json. Build/logs out/gpu-gravity-contract.
Earlier checkpoints below are historical.

# GPU resumed: upgraded-firmware handshake passed — 2026-10-07

Owner reports peripherals working after the promoted 7.1.13-m4rch-gravity
kernel reboot. Continuous shallow WFI remains enabled. Internal NVMe remains
the boot/root device; normal GRUB default 0 is retained.

Fresh boot ADT confirms stage-two mBoot-18000.161.10 (26.6.2 / 25G83).
ASC addresses, mailbox geometry and reserved TEXT/DATA extents match the
previous capture. This is metadata evidence, not a payload-byte identity check.
New standalone Discord ABI reference has unchanged numeric values but clearly
separates channel-state and queue-pointer objects. Treat its layouts as candidate
25G83/G16S contracts; author machine has 20 cores, ours has 16 (3db/3db).

Current-kernel-built bounded ASC probe negotiated protocol 12 and received
endpoint maps for 0, 1, 32, 33; both ACKs completed. No application endpoints
started, no DMA addresses supplied, no GPU work submitted. Stop readback was
control=0/status=0x6e. This does not prove DMA quiescence: power, mappings and
module remain pinned until reboot. Never force module removal.

NEXT: normal Linux reboot (not macOS required). Then qualify the 25G83 firmware
payload/reserved mappings and prepare explicit G16S ABI serializers with
separate channel-state/queue-pointer types, correct unaligned fields and our
16-core topology. Before full rendering, establish RTKit crashlog/application
endpoint lifecycle and firmware-accessible buffer teardown. Keep normal startup
gated until those contracts are validated. Current maintained kernel has Rust
GPU driver disabled; later integration requires a separately built trial kernel.
Do not transplant donor single-cluster constants or claim acceleration yet.

Evidence: docs/evidence/2026-10-07-gravity-gpu-handshake.json and
2026-10-07-gpu-abi-reference.json. Raw logs and matching helper build are retained
in ignored out/gpu-gravity-20261007. Earlier next-step notes below are historical.

# Maintained Gravity kernel promoted; USB fixed — 2026-10-07

Owner requested promotion despite first-boot USB regression. linux-m4rch is now
7.1.13-3, release 7.1.13-m4rch-gravity, on Gravity commit 3b85d81f6. Separate
linux-m4rch-gravity-trial package removed in the same transaction. Internal
NVMe normal GRUB default 0 now boots the promoted kernel and matching generated
initramfs; stage-two boot.bin unchanged. Kernel/initramfs package identity and
NVMe root UUID/bounds/storage dependencies verified. GPU work remains paused.

USB regression diagnosed and fixed live:
- Gravity required a DWC3 reset-control absent from T6040's live DT; reset is
  provided by the exercised PHY path. Optional reset lookup restored for T6040
  only; mandatory requirement retained on other boards.
- Gravity parent Type-C Makefile used renamed TPS6598X_CORE config, omitting
  our retained TPS6598X transport. Parent build wiring corrected.
Three host controllers initialize successfully. Owner's left-front YubiKey
1050:0407 enumerates, including HID/FIDO interface. Other ports/orientations
not physically tested this round. USB service restart passes with persistent
installed modules. First raw Type-C insmod lacked core dependency; loading
Type-C core resolved it; normal modprobe resolves that dependency.

NEXT: normal Linux reboot to verify maintained kernel/initramfs and automatic
USB loading. Confirm left-front key and optionally other ports, input/network,
SME/WFI and NVMe mounts. No revert requested. Earlier 7.1.3 boot files and module
archive are in ignored out/gravity-kernel-alignment/boot-backup and
maintained-modules-before.tar.gz, not an active menu fallback. Old GRAVK001
initramfs expects removed trial pkgbase: do not select it after promotion.

Receipt: docs/evidence/2026-10-07-gravity-kernel-promotion-usb.json. USB compile
and live logs in out/gravity-kernel-alignment. Reproducible fixed source recipe:
experiments/kernel-alignment. make kernel-gravity builds this profile;
make packages-gravity creates maintained package in a fresh workspace.
Historical generic image/kernel/package pipeline retains old pins and must
not be used to rebuild this promoted installation pending full image-pipeline
integration. Source patch replay and hash match verified on fresh checkout.

Earlier checkpoints follow and are historical.

# Gravity kernel alignment — staged reboot checkpoint, 2026-10-07

NEXT BOOT: 7.1.13-m4rch-gravity, separate linux-m4rch-gravity-trial 7.1.13-1
package. Gravity source 3b85d81f656af14d0fc4bea3eef87fe040c424f9, current default
upstream revision verified. GPU work paused at owner's request; optional Apple
display/SIO driver excluded, maintained software framebuffer retained.

Internal NVMe GRUB default 1 selects /GRAVK001/vmlinuz and initramfs.img.
Working 7.1.3 kernel/initramfs remain unchanged at entry 0. m1n1, U-Boot, Apple
stub and enrollment unchanged. Rollback from macOS: mount internal M4RCHESP,
copy GRAVK001/grub-before.cfg over grub/grub.cfg, sync. This is an internal
kernel fallback, with no SD dependency. Do not automatically reboot.

Full Image/modules build and modpost passed. Final pass had no compiler warnings
or errors. Source patch applies to fresh pinned Gravity checkout. WFI, early
fault handling, framebuffer, USB2 PHY and SPMI/Type-C files retain exercised
sources. DockChannel/HID transport and shared power/NVMe/CPU APIs reconciled.
Two compile/link issues fixed: PMGR skip-auto-enable field restored; optional
Apple display module lacks exports and was excluded. Native packaging required
because sandbox fakeroot rejected ownership preservation. Logs retained locally.

NVMe trial initramfs verified: exact root UUID, PARTUUID/bounds, kernel release,
trial package identity and Apple NVMe/SART module dependencies. Working boot
artifacts matched backup hashes after installation; grub-script-check passed.
Receipt: docs/evidence/2026-10-07-gravity-kernel-trial.json. Reproducible source
recipe/config/patch: experiments/kernel-alignment. Local build/logs/package:
out/gravity-kernel-alignment. No native trial boot or hardware stability claim yet.

After reboot: verify release and NVMe mounts, collect dmesg/config, WFI activity,
SME/SME2, CPU capacities/frequency, input, USB/YubiKey, Wi-Fi/Bluetooth and usual
audio. Check failures against maintained baseline. Once stable, restore default
0 while deciding package promotion. Do not resume GPU work until the aligned
kernel baseline is verified; then use supplied Discord ABI document and saved
handshake evidence. Loader cold and warm boot checks previously passed.

Earlier checkpoint notes follow; their next-task states are superseded.

# Native loader validation — 2026-10-07

This cold boot passed: owner reports desktop, input, USB, Bluetooth and usual
audio all work normally. Both root and boot are internal NVMe; maintained kernel
7.1.3-m4rch unchanged. Continuous shallow WFI Y; SME and SME2 are advertised.
No failed services. Native collector completed; return archive is
/boot/loader-alignment/return-20261007T095925Z-lHqhGP.tar.gz.
Kernel log retains ANS PANICLOG-not-written and PCIe timeout-mask messages;
these are not evidence of an observed storage I/O failure.

NEXT: one ordinary Linux reboot to validate the new stage-two chain on warm boot.
Keep kernel/firmware fixed for this remaining loader comparison. After that,
resume owner's requested Gravity kernel-version alignment using the updated
repo's protected T6040/NVMe/USB/SME/WFI stack. Earlier GPU/native handover is
preserved at docs/evidence/2026-10-07-pre-loader-handover.md.

# Gravity bootloader alignment

The owner has booted Linux successfully without an SD card using the split
m1n1 chain and the upgraded 26.6.2/25G83 Apple stub. This trial replaces only
ESP `/boot.bin`; Apple firmware, enrolled stage 1, GRUB, kernel and rootfs stay
as they were. No Recovery enrollment is required.

Sources are pinned in `/boot/loader-alignment/profile.json`:

- Gravity m1n1 `a49e1e170f917038206cf9ed9ad66f9581808575`.
- Gravity U-Boot `a2f6913694ff26908c16948af3f8372429782263`, from
  `gravity-alpha-20260925` (U-Boot 2026.07).

J614s changes retain the separate NVMMU aperture, complete ANS power-domain
mapping, checked firmware shutdown, MTP-only DAPF initialization and internal
ESP selection by PARTUUID. Gravity's CTRR reservation now covers T6040.
The U-Boot bridge remains read-only and has no SD fallback. GPU enablement is
outside this trial; the desktop should continue using software rendering.

## Native check

1. Boot M4RCH with the SD removed. Confirm `/` and `/boot` are on internal NVMe.
2. Check desktop, keyboard/trackpad, USB, Bluetooth, existing audio, CPU idle
   and SME for regressions. Do not change firmware or install another kernel
   during this comparison.
3. Run `sudo sh /boot/loader-alignment/collect.sh`. Add observations and any
   errors to the returned directory's `HANDOVER.md`, then recreate its archive:
   `sudo tar -czf DIRECTORY.tar.gz -C /boot/loader-alignment DIRECTORY_BASENAME`.
4. Test one shutdown/cold boot and one reboot. Return the archive on the
   internal ESP, together with the final observations. If boot fails, photograph
   the last complete screen and return to macOS.

## Rollback from macOS

Deployment prints a verified Mac-local backup under `out/split-boot-backups/`.
Mount the internal ESP, then restore that backup's `boot.bin` to
`/Volumes/M4RCHESP/boot.bin` with `sudo cp`, followed by `sync`. Restore only the
ESP bundle; stage 1 and the Apple stub do not need re-enrollment for this rollback.
