# Native firmware-off object and saved v20 observation

The native firmware power-off wait has a concrete shared-object identity. `allocFirmwareData` at `0xfffffe00089aba94..89abaac` installs paired CPU/FW pointers at firmware+888/+890 for a32-byte allocation. `initFirmwareData` converts firmware+890 and writes the result to root+a8 at `0xfffffe00089cda30`. Firmware boot copy at `0x2f2d0..2f2d4` binds root+a8 to private18e3f0. The Linux graph receipt and both raw root pointers map that allocation to owned `status_a`, GPUVA `0xfffffc200013c000`, arena offset245760.

Native `waitForFirmwarePowerOff` at `0xfffffe00089bf120` waits for u32+10==0. Firmware sets the same word to1 at `0x348d0` and clears it at `0x349e8`; it separately updates generation+1c and ready+14. These are a firmware controller/off observation, separate from command processing, GPU job retirement, ASC202 acknowledgement and strict PMGR OFF.

Both saved v19/f4 and v20/09 snapshots have initial statusA u32 words `[3,1,0,0,0,0,0,0]`. Both sealed after-draw snapshots have `[3,1,0,0,1,1,1,0]`: native off-word+10=1, ready+14=1, power-status+18=1 and generation+1c=0. Thus the precycle firmware-off predicate was not satisfied. No postcycle RAM read was performed, so the final power-block state is unknown.

This completes the object identity needed for a future bounded idle-policy-before202 diagnostic. Such a candidate should observe the owned off-word separately from opcode0a queue/counter completion and retain exact before/after operands. It remains an unselected transfer hypothesis; bool1 is not a synchronous OFF or cancellation command, and a zero word does not replace the strict physical OFF criterion.

The JSON companion binds each binary range, graph receipt and raw snapshot by SHA256. No hardware, live sampling, Apple code execution, emulator rerun or selectedv21 change occurred.
