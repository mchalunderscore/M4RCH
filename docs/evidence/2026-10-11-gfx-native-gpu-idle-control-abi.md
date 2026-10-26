# Native GPU idle control: opcode0a correction

Saved firmware shows that opcode `0x0a` is an idle-power policy control, not a direct OFF or cancellation command. Native `submitCmdGPUIdlePowerOff(bool)` at `0xfffffe00089c8860` constructs a zeroed64-byte device-control record: u32 opcode10 at+0, u32 bool from `w1` at+4. It submits through the workloop and conditionally waits for device-control completion.

The matched firmware jump table resolves10 to `0x4618`. That handler stores the u32 bool into private `0x18eef8`. Nonzero goes directly to common completion; zero calls `0x33a68`, an activation helper. Its early gate returns when private mainstate `0x18e688` bit1 is already set, as independently established by the saved recovery callback audit. No emulator or hardware trial was repeated.

The policy binding is concrete: `0x35da8` tests `18eef8` after checking the device-control queue is empty and other idle prerequisites. Nonzero admits power event4 at `0x35dbc` and a semaphore wait at `0x35df4`; periodic policy also reads the flag at `0xe5c4` and `0x39850`. This supports bool1 as permitting idle-power policy, while bool0 disables that policy and requests activation. The actual native bool caller and enclosing shutdown order are still unresolved.

The command uses256 records of64 bytes. For a future single transfer after the current capture, exact owned cursors33/33/33 admit slot33, then producer34 and one class84 notification. Firmware completion advances the read cursor and, because opcode0a is power-class1, increments statusB+e438 once before advancing read. A fresh34/34/34 plus baseline counter+1 would prove command processing, not work retirement or GPU OFF.

A future bool1-before202 experiment is a bounded hypothesis that may allow graceful idle quiescence before ASC shutdown. It must preserve the before/after queue and counter evidence, retain the capture/owner on failure, and distinguish command completion from native GPU-off and strict PMGR OFF. Native `waitForFirmwarePowerOff` at `0xfffffe00089bf120` checks firmware+888->u32+10==0; the corresponding Linux shared-object identity is not yet proved here. No direct private flag, arbitrary reset write, retry, or selectedv21 change is proposed.

The JSON companion pins all sources and exact binary ranges. This is offline source-derived work, with no Apple code execution, emulator rerun, qualification rerun, or hardware access.
