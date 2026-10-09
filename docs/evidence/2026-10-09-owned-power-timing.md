# Minimum-power live result and native timing candidate — 2026-10-09

Boot224c79d0-8950-47a1-8b18-a975c4acda10, kernel7.1.13-m4rch-gpu-contract. User confirms desktop/input/USB/networking normal. Minimum-active-state trial module0142d8e64535a75fcc7637416cadc5f51edba5fb0bbb6d05df120beeadd35fb4 ran once and returned. Main asc_graph_init retains backing/GFX power; no force unload/warm INIT.

## Result

Firmware consumed root0/1 cursors1/1/1 and control12 cursors32/32/32. TA control cursors2, fragment3; fragment hold254 cleared. Kick counter4, pending flags3/3, pending mask3. Target and completion unchanged both after return and at all four live1s/5s/15s/before-stop snapshots. Six live fault-info/address samples0/0; pause1/1 became0/0. Startup211c0 became11; live21048/50/58/60 remained zero. No new application messages, crashlog EHLC or verified hardware completion/pixels.

Firmware DATA18fd1c contains the expected sixteen-entry primary frequency array0/338/zeroes, copied by matched2f518. This confirms the new fields reached their consumer; the lowest-active-state/constant correction alone is insufficient. Live observations close the specific possibility that output changed only before quiesce. They do not establish which remaining prerequisite blocks GPU execution.

## Next integrated candidate

Native host initPowerAndPerformanceData at89a86ac stores getSamplePeriodAICClocks into power+4/+8. The pinned G16X virtual slotf68 resolves to89e8b18, loading accelerator+edb0. Hardware+ed8 at89cd1f8 receives getSamplePeriod via slotf60/getter89e8b2c loading accelerator+edac. Current ADT supplies gpu-pwr-sample-period-aic-clks=200000 and gpu-power-sample-period=8. These three fixture fields were zero. Period clocks and whole milliseconds are distinct inputs:200000 is not exactly8*24000; retain both exact ADT values.

Stage those timing fields with the adjacent unconditional native power-prefix constants from89a86d4..89a8708: power+c and5c copy literal712d7d0 (0000000004000000), power+14 stores zero-extended3f800000, power+2c/+30=1/1,50/90=100,64=3f800000,68 copies literal712dd00 (00000000010000000100000000000000). Raw literal bits are preserved; do not mislabel them as floating-point filter gains or infer semantics from the load register class. Native instruction words and private-binary hash are checked by the builder. Dynamic tuning/complete constructor remain unqualified.

The candidate changes exactly19 graph bytes across the stated fields, preserves draw backing and the338MHz cap1 policy, and adds no MMIO override. New runner checks sampling properties against fresh ADT before publication. Matching-kernel LLVM/W=1 build passed; all artifact/source hashes and object/arena hashes verified, exact field bounds/change and unchanged render backing checked. It has NOT run.

Next: normal Linux reboot, then sudo -n python experiments/t6040-gpu/run-root-envelope.py out/owned-power-timing/live-candidate --graph --run. Analyze using out/owned-power-timing/prepared/graph and its new boot capture. Compare live outputs, progress/faults, firmware frequency/period state, queue/context and event/stamps together. No triangle or acceleration verified yet. Current kernel/default boot entry unchanged.

Artifacts: out/owned-minimum-power/result-224c79d0 and live-candidate/asc-graph-init/boot-224c79d0-8950-47a1-8b18-a975c4acda10; next out/owned-power-timing. Full results/change/build receipts in companion JSON. Private implementation-derived research; exclude private binary/full firmware TEXT/disassembly from exports.
