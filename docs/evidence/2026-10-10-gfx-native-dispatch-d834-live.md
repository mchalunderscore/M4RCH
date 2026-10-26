# Native dispatch trial d834: captured, no triangle

The v15 cold initialization, control33, trace restore and one TA/3D draw completed on boot `d83451f8-42c7-4466-9983-f1b3fbea5963`. All18 capture pins and final full DATA/page-table captures are verified. The target remains all0xa5, and software plus four hardware completion buffers show no writes. Firmware accepted the draw; rendering and execution remain unproved.

The native PID/subpriority correction did not repair execution. Against eff8, the draw backing has the four intended metadata differences plus one runtime TA-context byte at0xc0204 (20→15). Only backing pages48/50/51 change12/3/1 bytes from their own recipe; roots are1/1/1 and control33/33/33.

The trace change had a concrete missing step: opcode22 copied shared mask0 into cached firmware18eecc, then the host restored only shared3. No later config snapshot refreshed the cache. All1097 trace records precede control-ready; none describe the draw. Stats continue through15s. The next candidate must preserve3 through the existing control33, or explicitly refresh the firmware cache before drawing.

The matched host driver's external-kill opcode0x2c is unsupported by this actual firmware and reaches its fatal handler. Supported IdlePowerOff0x0a only grants idle permission. Neither supplies an established submitted-queue cancellation contract.

The next combined hypothesis adds one retained native202 shutdown/rejoin after immutable full draw capture. It must observe its own management ACK, native idle and checked CPU stop before paired OFF/PMput, independently verify physical OFF, then separately qualify one ON and carried-AP20 management rejoin. All174 pages, mappings and context stay pinned. Application/root reuse, DMA retirement and rebootless render recovery remain open.

Current owner GNU `040000001400000003000000474e55008dc112b50b29062ff40b1ccf093a070b4d1c998d`, ref1. Last logged state is sealed/software-stopped/running0, PMheld1/usage1/active1 with retained identities. No post-trial GPU controls, owner unload/OFF/PMput/free/retry occurred. Existing kernel and GRUB are unchanged. Do not replay v15 on this consumed boot.

Session: `/home/alice/Desktop/m4rch/out/gfx-native-dispatch-contract/candidate/asc-graph-init/boot-d83451f8-42c7-4466-9983-f1b3fbea5963`. Full target PNG: `/home/alice/Desktop/m4rch/out/gfx-native-dispatch-contract/candidate/asc-graph-init/boot-d83451f8-42c7-4466-9983-f1b3fbea5963/target-after.png`. The JSON companion pins the complete capture and source-bound agent analyses; private binaries remain local.
