# Cold draw followed by one retained native cycle

This distinct v16 candidate keeps shared trace mask 3 through the existing
control 33, submits the preserved TA/3D draw once, and observes it for 15 seconds.
The four native PID/subpriority corrections from v15 remain in the recipe.

Before attempting teardown, the launcher captures the full owned objects,
target image, software and hardware completion pages, receive journal, kernel
log, reserved firmware DATA and page tables. It qualifies the original draw
pipeline, saves `pre-cycle-attempt.json`, verifies its capture pins, and makes
the saved draw files read-only. The SHA256 of that exact manifest is the
admission token for one `postdraw-native-cycle <capture_token>` command.

The C owner binds that command to its own completed and sealed draw, consumes
the intent once, and attempts native 202/ACK/idle/CPU stop, paired coordinate
OFF and PMput, strict physical OFF, then one retained management ON. This
experiments with shutdown after submitted work. It does not free backing,
replay application endpoints/root/work, or establish DMA retirement.

Cycle evidence stays in `cycle-attempt.json` and separate cycle logs. After
cycle intent the launcher reads only the kernel log. A failed write or timeout
never retries the command, and an ambiguous OFF never starts a RAM sampler or
opens live GPU diagnostics. Full draw evidence remains unchanged.

Root finalizes the candidate after the actual C and essential host checks.
On one fresh boot, use:

```sh
sudo -n python3 experiments/t6040-gpu/gfx-postdraw-native-cycle/preflight-fresh.py out/gfx-postdraw-native-cycle/candidate out/gfx-postdraw-native-cycle/fresh-preflight.json
sudo -n python3 experiments/t6040-gpu/gfx-postdraw-native-cycle/run-cold-render.py out/gfx-postdraw-native-cycle/candidate --graph --run
```

The launcher refuses historical consumed boots, including d834, before reading
candidate content or live providers. It retains the owner and all 174 pages.
Successful OFF/ON proves only this management cycle; a rebootless render
restart and an accelerated desktop require additional execution evidence.
