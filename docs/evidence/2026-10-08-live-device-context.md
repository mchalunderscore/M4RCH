# Live owned-device context insertion and restoration passed — 2026-10-08

An explicitly compiled GRAPH_CONTEXT_LIVE_EXPERIMENT now joins the existing owned graph allocation to a bounded live context trial. Normal builds keep the flag absent. Harness holds existingGFXgenpd. Native gates verify ASCcontrol0/status6a or6e,MMUcontrol1,base105fffb8000,configuration14/18=3680d8,table disjoint from System RAM and entirely zero. No firmware starts and no base/configuration writes.

Current runtime passed:ASCcontrol0/status6a;context1 inserted with actual owned device-rootPA102200a0000 andTTBR010102200a0001 in borrowed reservedtable105fffb8000. Owned pages were cleaned before insertion; table was cleaned/invalidated and CPU-readback verified. Then native removal order cleared valid1, cleaned, DMB, wrote context<<8=100 to physical288d08030 and readback100; zeroed the pair, cleaned/invalidated and checked the entire page zero. Loader control/base/configuration remained unchanged.112 owned pages released, reader/graph/power modules absent, GFX runtime suspend returned0.

A separate reserved-page sampler after the trial independently matched the full16KiB zeroed pre-trial page; SHA2564fe7b59af6de3b665b67788cc2f99892ab827efae3a467342b3bb4e3bc8e5bfe. This verifies restoration independently of the modifying module. Physical allocations above are one-run observations, not reusable resources.

This is a live context-table CPU publication and native-shaped cache invalidation request/readback, not proof that the GPU performed a translation lookup or consumed a drawing job. No firmware root/job publication, DMA work or pixels occurred. Existing graph logs published=0 describe firmware-root publication only; they do not mean this trial lacked a live context-table insertion.

On unverified pair/table restoration the helper retains all owned backing and pins itself; the harness also leaves the GFX power helper loaded. Never force-unload that state. Success restores the table before free. Context1 was admitted only after every table entry was checked zero; future trials must recheck current table and idle firmware state.

Next replace selected context and shader,target,parameter,event/queue fixtures, then prepare a complete mapped job for firmware publication. Device translation remains unproved; a bounded actual lookup/command-completion check is still required. User desktop/input/USB/network smoke confirmation requested asynchronously; not yet recorded here. No reboot required by this successful trial.

Evidence2026-10-08-live-device-context.json/-dmesg.txt; exact build inbuild/live-device-context including post-table.bin. Source device-context-live.h,guarded asc-graph-init.c/graph-map.h and one-shot run-live-device-context.py. No Apple instruction bytes.
