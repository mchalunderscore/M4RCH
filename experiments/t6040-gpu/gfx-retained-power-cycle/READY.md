# Ready for one fresh-boot retained management cycle

Candidate: `out/gfx-retained-power-cycle/candidate`, built, finalized, independently
reviewed and never loaded. Read the [final prepared evidence](../../../docs/evidence/2026-10-09-gfx-retained-power-cycle-prepared.md)
and `/boot/GPUC003/ASTRA-RESTART.md` before hardware access. Root alone operates
hardware; subagents stay offline.

Owner SHA256: `abf4ef3c709c3a775db2fa897dbbe1ba7edbb9868000848ac8283417f9fb7608`.
Receipt SHA256: `1762f50dcaa0a321c0003cee3ad63dba83cb50159599bc72bbf9c2444b5afe69`.
Preparation SHA256: `aca3b33c2b35cafe31b1e8d6463f8b56181f0644dc2499a14fc5c4a4fcde7aed`.

The clean W=1 owner build, 102 actual C sanitizer cases and 101 Python checks
qualify the offline candidate. They do not establish a live second cycle.
The preceding owner achieved one strict physical OFF with stable retained bytes;
it stays pinned and cannot use this new API. Current1686 and prior94cb/d841 boots
are refused. Keep GRUB default5 and the existing native-reset kernel.

On a normal fresh user boot, first verify the candidate, kernel, USB/PD roles,
resources and absence of an owner:

```sh
sudo -n python experiments/t6040-gpu/gfx-retained-power-cycle/preflight-fresh.py out/gfx-retained-power-cycle/candidate out/gfx-retained-power-cycle/fresh-preflight.json
```

Only a successful preflight admits one cold no-work trial:

```sh
sudo -n python experiments/t6040-gpu/gfx-retained-power-cycle/run-root-powergate.py out/gfx-retained-power-cycle/candidate --graph --run
```

Only qualified startup admits the baseline and first shutdown:

```sh
sudo -n python experiments/t6040-gpu/gfx-retained-power-cycle/run-powergate.py out/gfx-retained-power-cycle/candidate gfx-snapshot
sudo -n python experiments/t6040-gpu/gfx-retained-power-cycle/run-powergate.py out/gfx-retained-power-cycle/candidate gfx-powergate
```

Save and verify the complete returned first-OFF capture. Only its qualified
raw proof and fresh kernel boundary admit one retained cycle:

```sh
sudo -n python experiments/t6040-gpu/gfx-retained-power-cycle/run-powergate.py out/gfx-retained-power-cycle/candidate gfx-retained-cycle
```

Only typed `sample` and `gfx-snapshot` follow the second intent. Never retry
or fall back to an old wake/reset/STOP/OFF command, load another owner, erase
intent, release pages or unload the pinned owner. No work, triangle, application
rejoin or DMA retirement is admitted. Never reboot through tools.
