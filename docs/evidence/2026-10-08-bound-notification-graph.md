# Owned notification graph binding passed — 2026-10-08

The allocation-only gate now reads root+b0, resolves the status_b object through owned graph leaves, checks four backing pages and the full0xe440 native allocation extent, then places owned state/ring VAs at status_b+48e0/+48e8. It clears48f0/4900/4910 and both state cursors following native cold initialization. It verifies both pointers resolve to the actual allocated physical notification pages and an initially empty ring. Only after those checks does it prepare35 mapping records and tail35.

Running7.1.13-m4rch-gpu-contract passed:111 unique owned pages,64 command candidates,35 independently checked native mapping descriptors,206 graph leaves, cold head0/tail0 followed by prepared head0/tail35. Normal unload released backing; module absent. This is CPU-side preparation and shadow-table validation, not firmware consumption or GPU translation proof. No live roots, contexts or job publication occurred.

Source command-pool-map.h and evidence2026-10-08-bound-notification-graph.json/-dmesg.txt record this trial. Native root binding evidence2026-10-08-native-notify-root.json identifies the target. Next connect actual device-context lifecycle and shader/target/parameter/event/queue backing; live init must precede notification enqueue. No reboot or macOS handoff currently needed.
