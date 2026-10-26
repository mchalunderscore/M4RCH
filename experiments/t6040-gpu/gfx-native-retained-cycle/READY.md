# Ready for one fresh-boot native-ordered management cycle

Candidate: `out/gfx-native-retained-cycle/candidate`, built, finalized,
independently reviewed and never loaded. Read the [final prepared evidence](../../../docs/evidence/2026-10-09-gfx-native-retained-cycle-prepared.md)
and `/boot/GPUC003/ASTRA-RESTART.md` before hardware access. Root alone operates
hardware; subagents stay offline.

Owner SHA256: `4f9d6ea85df700166583e6992e57d935a8b68ea19b695cde07e1a93bb783d062`.
Receipt SHA256: `969692c5ee0880197cda6349bf8b04e1c580ecb32aa374e6533f713d0447c3d4`.
Preparation SHA256: `162c04373f72999f5f62a5948e7ed2ec57504a585c98ce9ef31a27a86fb60ea9`.

W=1 build is clean;115 actual C sanitizer cases and69 targeted Python cases
pass. Complete state log rows measure at most422 bytes. These offline checks
do not establish a live retained cycle. Current5bf0 owner stays pinned with both
intents consumed and its second PM reference held; no retry is admitted. Four
consumed boots are refused. Keep GRUB default5 and the installed native-reset
kernel. Never reboot through tools.

On a normal fresh user boot, first verify candidate/kernel/USB/PD/roles/resources
and absence of a prior owner:

```sh
sudo -n python experiments/t6040-gpu/gfx-native-retained-cycle/preflight-fresh.py out/gfx-native-retained-cycle/candidate out/gfx-native-retained-cycle/fresh-preflight.json
```

Only a successful preflight admits one cold no-work trial:

```sh
sudo -n python experiments/t6040-gpu/gfx-native-retained-cycle/run-root-powergate.py out/gfx-native-retained-cycle/candidate --graph --run
```

Only qualified startup admits baseline and one first shutdown:

```sh
sudo -n python experiments/t6040-gpu/gfx-native-retained-cycle/run-powergate.py out/gfx-native-retained-cycle/candidate gfx-snapshot
sudo -n python experiments/t6040-gpu/gfx-native-retained-cycle/run-powergate.py out/gfx-native-retained-cycle/candidate gfx-powergate
```

Save the returned first-OFF raw capture. Only its exact proof and fresh kernel
gates admit one native-ordered retained cycle:

```sh
sudo -n python experiments/t6040-gpu/gfx-native-retained-cycle/run-powergate.py out/gfx-native-retained-cycle/candidate gfx-native-retained-cycle
```

The cycle requires actual first202/strictOFF/newACTIVE, known6a/6c, separate paired
ON and fresh guards before one START/autonomous HELLO/map/own202/checkedstop/
pairedOFF/secondput/strictOFF. No status value proves restart. Unknown or failed
results retain all resources and seal further controls; after second intent only
typed `sample` and `gfx-snapshot` remain admitted. Unknown startup admits none.
No fallback wake/reset/control, new publication, app rejoin/work, free or unload.
Use the existing pure byte parser for loaded notes; in-place objcopy is forbidden
on frozen artifacts.
