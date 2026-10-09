# Native timing result and four hardware completion queues — 2026-10-09

Bootafbd7878-a13d-4a5c-a283-55344bef5243, kernel7.1.13-m4rch-gpu-contract. User confirms desktop/input/USB/networking normal. Native timing trial returned once. Target/completion changed zero bytes in every live sample and post-return. Queue configs/kicks/release consumed, pending flags3/3 and mask3, live faults0/0. Startup211c0=11 and progress21048/50/58/60 zero. Power4/8 remained200000 and hardwareed8=8 in captured owned graph. Timing/default correction did not unblock execution. Main asc_graph_init retains resources until reboot; no force unload/warm INIT.

## New prerequisite found

Native initFirmwareData calls accelerator virtuald68 with hardware+2620 at89cd420..89cd448. The pinned G16X vtable resolves that slot to89d76c0, AGXAcceleratorG16::populateKSMCompletionQueue. Its previously audited numeric producer fills four32-byte descriptors: resource58 mapping, resource50 mapping, accelerator capacity, stride64, index0..3, zero cursor. Private completion helper preserves that layout. These four descriptors in our fixture were entirely zero.

Matched firmware15ed0..16070 checks the first pointer in each descriptor and programs hardware completion rings. For index0,15f18 loads hardware2620,15f1c masks a43-bit aligned device address,15f20 packs hardware2630 atbit48, and15f24 adds valid bit. Configuration registers21148+8*index and status21168+8*index are read/written by these branches. Firmware15d58..15db4 consults each descriptor and status; other paths drain rings. This establishes a concrete completion-routing initialization gap, not proof it caused the observed execution stall.

## Integrated next trial

Add four Linux-owned pages52..55, each zero initialized and with distinct device and firmware aliases. Descriptors start2620/2640/2660/2680. Device VAs10000d8000/10000dc000/10000e0000/10000e4000; firmware aliasesfffffc2000b28000/b2c000/b30000/b34000. Firmware first-pointer register consumer supports the device-address role; the second firmware alias and exact provider identity remain an explicit hardware hypothesis. Experimental capacity64, stride64 gives4096 active bytes per16KiB owned page. No claim this is Apple's native capacity or fully qualified controller routing.

The graph changes45 bytes. Existing52-page TA/3D/NOP draw backing is byte-identical, with four new zero pages appended. Total174 owned pages, including existing six render tables. Native timing/defaults and lowest-state338MHz cap1 are retained. No direct host ring register write. Firmware handles initialization. All resources remain pinned until reboot because teardown is unqualified.

New bounded live observations read four completion config/status registers and count changed bytes in all four rings at1s/5s/15s/before-stop, alongside target/completion and existing progress/fault samples. Analyzer includes those live readings and post-return ring changes; changed memory or installed configuration alone does not prove a completed shader or triangle.

Matching-kernel LLVM/W=1 build passed. All module/source hashes verified; distinct device/FW pages and no graph/MMIO collision checked, graph/object hashes and existing layout validator passed, four descriptors checked, unchanged draw backing/new zero pages verified. Analyzer remains compatible with prior52-page captures. Full hashes and receipts in companion JSON. Candidate has NOT run. Kernel/default entry unchanged.

Next action: normal Linux reboot, then sudo -n python experiments/t6040-gpu/run-root-envelope.py out/owned-hw-completions/live-candidate --graph --run. Analyze against out/owned-hw-completions/prepared/graph and its new boot capture. Inspect hardware completion configuration/status and live ring activity before drawing execution conclusions.

Artifacts: out/owned-power-timing/result-afbd7878 and live-candidate/asc-graph-init/boot-afbd7878-a13d-4a5c-a283-55344bef5243; next out/owned-hw-completions. Sources: prepare-owned-hw-completions.py, private_completion_queue.py, asc-graph-init.c, prepare-joined-init-trial.py and analyze-owned-work.py. Private implementation-derived research; no private binary/full firmware TEXT/disassembly exported.
