# v12 retained management host qualification

Selected qualification: `out/gfx-native-ap-repeat-cycle/wrapper-qualification-v2.json`, SHA256 `924d870f26bb69388c75ae581de50430ddac056d43aad9cb3a5603933fb0b385`. It passes 378 cases, 23 actual cold/preflight guard flows and 131 actual resident main flows. Its 25 input pins were rechecked after completion. All system reads, processes and command writes are intercepted; no hardware action occurred.

The actual new C replay's E1, E2 and E3 log deltas pass the host parsers. The selected source is `prepared-owner-v5`, source receipt `bf52cabe10ab41df883c22907a9a66d4ff338cebc93b3d82d66ea5e27004ffa1`. The selected C qualification is `owner-qualification-v8.json`, SHA256 `68f5f2de51794d7c93cd6c4b077a4e023605b9266266db8b114290769ff99776`, with 172 actual C cases.

The third command rebuilds the original E1 proof and the exact E2 seven-input proof before admission. It uses E2's own operation delta, ACK, checked stop, coordinator, PM put and strict physical OFF/accounting, and preserves the original session, identity and exact cold AP reply. E1 success markers and cumulative historical logs cannot stand in for E2 proof. Lost, altered, mixed, duplicated or interrupted history seals controls. The third intent and both predecessor links are durable before command open; all four intercepted write-boundary faults consume the intent. Diagnostics remain available, and no fourth epoch is defined.

All eight consumed boots are refused by the actual cold, resident and preflight entry points after only the boot-id read. Current boot `911ae710-78af-4702-8dfc-f4145decbd38` retains the consumed v11 owner and is refused by v12.

Wrapper qualification v1 failed because its strict source-profile validator had not yet included the selected bounded E1 progress-row declarations. Its failure record, trace and seven source snapshots are preserved. Selected v2 includes those declarations and passes. Frozen v11 files and evidence were left unchanged.

The candidate is management-only: both retained map ACKs use zero application bitmap. Host/C tests do not prove hardware repeatability, application rejoin, rendering, DMA retirement, backing release or safe unload. Cached transport values carry `guard_jiffies`, `cached=1` and `operand_samples_atomic=0`; the last full guard time is not a coherent timestamp for later control/status updates. Linux runtime-PM callbacks have no asserted hard wall-clock bound.
