# Native reset result and distinct retained power-off trial

The native command sequence completed on boot a1f61d61: all five full-word
writes returned0, RESET31 was sampled set then clear, and AUTO was restored.
Application recovery remained counter1/phase2; the firmware-owned power
counter changed19384→31351 about99.73seconds after START was cleared. We have
command delivery and register evidence, without usable teardown, complete
cessation, repeatable recovery, execution or target pixels. All174 pages,
mappings, consumer and the current owner remain pinned. Do not repeat reset,
wake, START/INIT, recovery, work publication or unload on this boot.

Native-driver review found no applicable T6041 retention/AXI workaround
missing from this GFX reset: GFX386 is native RegMap6+0x110, whereas those
specific tables cover Maps0/2. The remaining boundary includes normal
provider power-off and the actual AGX/UAT mapper path. Its terminal isolation
and drain effect remains unresolved; generic DART assumptions do not apply.
The existing driver's PMGR snapshot can observe the provider after OFF.

The distinct future candidate is out/gfx-poweroff-scope/candidate. Its owner
hash is 4b4914b677c15b55718e6e96f4d6683a0dd295f4337659aff709a8ffef931be0, and its receipt hash is
8644ae827a06da50d9793199a7c780305cff85abb9c9e826cde41b967971f471. It uses the installed
7.1.13-m4rch-gpu-native-reset kernel, notes85c56f7a3d7409747dd67fe1dcbf8839562aafab16a9124f9304689a14de437d.
No kernel rebuild, new boot files or GRUB default change was needed. The
candidate has not been loaded and hardware OFF has not been attempted.

The change preserves the existing cold startup and module lifetime pin, and
adds a separate typed terminal gfx-poweroff after confirmed packet-free STOP.
The owner validates all174 retained pages/context/mappings, no work,
empty36cursor words/inactive256TA records, matched consumed controls,
START-clear/native idle and exactly one owned runtime-PM reference. Every
explicit OFF gate is consumed even on refusal. Eligible entry clears local
PM ownership before one pm_runtime_put_sync_suspend, with no compensating
resume or second put. Every allocation, mapping and the consumer stay pinned.

A normal runtime-suspend return0 does not establish provider OFF. Independent
error-free snapshots require domain_on0 and word&0x90001cff==0, alongside
consistent software accounting. Observation is limited to101samples and
at most100 minimum1ms delays; this bounds the polling count, not time spent
inside the synchronous runtime-PM call. Negative PM errors remain recorded
even if OFF is later observed. After gate consumption, including refusal,
only driver-owned PMGR snapshots, software accounting and retained DRAM are
accessed. ASC/SGX/mailbox access, reset, restart, receive draining, work and
memory release are excluded. Stable DRAM plus OFF still does not qualify
cache/fabric drain, fresh firmware DATA, safe restart or backing retirement.

Actual-C ASan/UBSan replay passed592cases. Actual Python wrapper admission and
durable intent tests passed84cases, including open/write/short/interrupted
OFF outcomes and prevention of a second attempt. The W=1 module build passed
with two unused-function warnings from the intentionally excluded output and
trace command routes. All10artifacts and15owner source pins matched, the
other seven helper modules and prepared graph/backing were unchanged, and
the actual module imports snapshot/runtime-suspend with neither reset API.
The companion JSON binds the source qualifications, build, live evidence and
native-driver boundary evidence. Independent review is saved separately.

After a fresh user boot, root must match kernel/notes/candidate identities,
verify all3SPMI PD bindings and3USB role providers, and confirm no GPU owner
or conflicting sampler is loaded. Use only the distinct run-root-poweroff.py
with graph/run, then its run-poweroff.py for baseline/STOP/one OFF and bounded
PMGR/DRAM follow-up samples. The current old owner cannot be replaced safely;
no hardware action from the new candidate is authorized on the retained
current session. Existing default5 selects the required kernel.
