# Native idle recovery reaches host pre-phase, then faults

Boot `e3501874-8c10-47f2-92e1-a8de666e7caf`, kernel
`7.1.13-m4rch-gpu-contract`. Module SHA256
`6a436db0a234d53db22ab7353a9d7f98974908278dbc2408c15af6a2e38468e3`.
The new application-recovery experiment ran once and returned. It did not repeat
START/INIT, power-held INIT, or any prior wake experiment.

All twelve root work rings/cursors were empty. Initial control refresh0x16
records reached32/32/32. All four completion ring configurations were installed,
with zero statuses; no initial mailbox activity or active TA recovery records.
The helper retained all174 joined allocations and sentEP33
`0x0086000000000000` with token0.

Firmware accepted the request: counter48f0 advanced0->1, phase4900 became1,
host-stop4910 became1, and the recovery request object became state2/flag1.
After the host wrote phase2, firmware emitted an endpoint1 crash notification.
The helper issued no additional recovery request or fresh control. Completed
cycles0/2; final control cursors remain32/32/32.

The newly written, structurally valid2592-byte crashlog reports task6,
PC`fffffc00000301a8`, FAR0, ESR`96000004`, stack301a8/cbf0/39260/38f9c.
At301a4 the firmware loads a pointer atx27+a38;301a8 dereferences it. Captured
x27=`fffffc2000133118` identifies the missing pointer as owned power+3b50.
The current power fixture leaves that native initialization field zero.
Native producer and resource initialization are being traced before a replacement
candidate; assigning an arbitrary nonzero pointer is not a qualified fix.

AP QUIESCED and IOP SLEEP ACKs were absent after the fault. ASC final control0,
status4e passed the existing core-stop readback, but all resources and the joined
context remain pinned, module refcount1. All three SPMI USB power controllers
remain bound after the trial. No automatic reboot, force unload or wake issued.
A new cold boot is needed before another module candidate can run.

The powered identification read d04018 was consistently`0x01320311`. The native
readChipInfo formula gives counts2/3/3 and masks3/7/7 for hardware254c/2550/2554.
These and the native f30 vector[0,1,1,0] are concrete missing initialization
fields to combine with the recovery-pointer correction in the next batch.

Raw capture: `out/recovery-idle/live-candidate/asc-graph-init/boot-e3501874-8c10-47f2-92e1-a8de666e7caf`.
Decoded crash: `out/recovery-idle/crash.json`. Companion JSON contains exact
phase logs and register evidence. This establishes request routing and the first
native recovery phase, not complete recovery, DMA retirement, unload safety,
GPU execution or rendering.
