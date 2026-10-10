# Native Fender enable transfer, traced draw and retained cycle

The distinct v18 candidate retains v17's Gravity startup prefix, native
PID/subpriority recipe, trace 3, one control33/TA/3D draw, full 15-second raw
capture, and one postcapture native202/NMI/OFF/management-rejoin cycle.

Its one execution change calls the matched Apple AGXFenderChinook enable
operation after fresh control33 and before first draw intent: read SGX+d06030
afresh, write `old & ~6`, verify exact readback and issue the full barrier.
Every other bit remains unchanged. The same exclusive preASC-owned 16K page
at 0x288d04000 supplies the register. Ownership, physical ON, retained identities,
control cursors and original clean work state remain required.

This is an explicit experimental transfer to firmware-mediated EP33 draw.
Apple's native addKicks sequence brackets direct SGX+4090/+4098 stores with
Fender disable/enable; that complete sequence is not reproduced. There are
no direct kick stores, scheduler ACK/coverage writes, teardown clear, helper
replay on rejoin, second draw or second cycle. Any failed/unknown operation
retains the owner and backing. Management rejoin does not prove application
reuse or DMA retirement.

Preparation composes the frozen v17 C64/preASC39/host41/10 receipts without
rerunning unchanged tests. The actual new C helper has 45 sanitizer cases.
The changed host qualification has 21 focused cases, one intercepted full
capture-before-once-cycle flow, and two earliest consumed-e728 refusals. Its
pipeline fixture explicitly composes independently emitted C fixtures; the
production caller placement and inherited source projection are separately
bound to the actual compiled module in the finalizer.

Root finalizes the root-owned candidate after the offline host receipt:

```
sudo -n python3 experiments/t6040-gpu/gfx-native-fender-draw-cycle/finalize-cold-render.py out/gfx-native-fender-draw-cycle/candidate --fender-qualification out/gfx-native-fender-draw-cycle/fender-qualification-v1.json --host-qualification out/gfx-native-fender-draw-cycle/host-qualification-v2.json
```

On one fresh user boot, root follows the prepared guide's read-only admission,
then `run-cold-render.py CANDIDATE --graph --run`. The capture/retained-RAM/
immutable-token/once-only-cycle tail is byte-identical to frozen v17. Current
boot e7288eeb-bc71-46e3-a0c5-831b77bebb1d is consumed and is rejected before
candidate contents or other live state are read. No hardware was accessed by
the offline C or host checks; no rendering or restart result is claimed.
