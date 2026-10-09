# Independent review of the retained GFX power-off live trial

2026-10-09. Boot `339b9e8e-4535-4550-97d6-840301c6baac`. This reviewer read saved files only and performed no module operation, MMIO, sysfs command, runtime-PM operation, mapping change, allocation release or reboot.

**Normal PM reference consumption succeeded, but usable teardown did not.** The one `pm_runtime_put_sync_suspend` returned 0; private usage count changed from 1 to 0 with suspended status and no runtime error. The provider snapshot reported software domain OFF and ACTUAL/TARGET 0 with AUTO cleared. However every one of the 101 bounded observations, and all three later diagnostics through 221.286058 seconds after the terminal result, read `0x0f000b00`. Bit 11 remained set, so `(word & 0x90001cff) == 0` failed with `0x800`. The operation returned `-ETIMEDOUT`, not success. The qualified firmware-owned power field at `+0x652c` continued changing after this attempt. No whole-GPU cessation, drain, recovery, restart, release or rendering is established.

The frozen candidate is `out/gfx-poweroff-scope/candidate`, owner `4b4914b677c15b55718e6e96f4d6683a0dd295f4337659aff709a8ffef931be0`, receipt `8644ae827a06da50d9793199a7c780305cff85abb9c9e826cde41b967971f471`. The kernel remains `7.1.13-m4rch-gpu-native-reset` with notes `85c56f7a3d7409747dd67fe1dcbf8839562aafab16a9124f9304689a14de437d`. Boot preflight binds that kernel and candidate, all 10 artifact and 15 owner source pins, the expected USB glue build identity, three SPMI PD bindings and three USB role providers. The reviewer checked the 10 artifact and 15 owner source file hashes independently and binds 94 actual capture and input files in the JSON companion. All eight captures contain the exact 69-object-page and 174-owned-page extents.

## STOP completion and the narrow metadata confirmation

Only one STOP command was written. At 187.828182 seconds, it cleared START and returned `-EAGAIN` because status `0x4c` did not satisfy the native low-two-bit idle predicate. The C record had `clear_attempted=1`, `start_clear=1`, gate and PM attempt both 0, held reference 1, and no management packet. The later successful read-only snapshot at 204.209464 seconds observed START 0, status `0x4e`, the same retained owner, gate/PM attempt 0 and usage count 1 with enabled active PM and no runtime error.

`confirm-stop.py` reconciled only this exact known returned EAGAIN in host admission metadata under the existing operation lock and loaded-identity validation. It durably preserved the full prior unknown-operation state and pinned both captures before setting the confirmed-stop field. It made no new sysfs or hardware write, kept the recovery-failed state, and did not erase a generic unknown command result. The actual saved pair passed its pure offline qualifier; all 17 targeted negative mutations were rejected, including unknown/interrupted/short-write outcomes, gate or PM attempts, START/idle/usage mismatch, wrong or duplicate C results, intervening commands and OFF/work intent. The helper hash is `ff6aecb9010e81c8bc9474e1913e8a195036d0802f153d0573560a9e745b7b36`. The confirmation record hash is `ee60a2cfebbcfd13a3a64292319e0a5468b6ca18b30c3fbe723a8733fc0e69c0`. No test here exercised hardware.

## Sole normal PM put and independent observations

The power-off command rechecked its C preconditions and a fresh active provider snapshot. At 477.187564 seconds the before-word was `0x1f0003ff`, domain ON, usage 1, active and enabled. After the sole normal put, the record showed usage 0, runtime status 2 (suspended), runtime error 0, active 0 and local held 0. No compensating get or second put was performed. All 101 post-put snapshots succeeded individually, but every word was `0x0f000b00` with software `domain_on=0`. The loop requested 100 delays of at least 1,000 microseconds and returned its terminal `-110` at 477.303094 seconds with `provider_off_observed=0` and `accounting_ok=1`.

The software genpd summary corroborates GFX OFF and the private consumer suspended. It is software bookkeeping and cannot settle physical whole-GPU cessation or drain. The ACTUAL/TARGET fields reaching zero is a narrower hardware observation; BUSY remained unresolved.

## Retained shared-memory observations

The values below come directly from the qualified object and owned binary captures, using `RECOVERY_POWER=196608` and the owned-object prefix of two 16 KiB pages. These reads are not atomic with firmware or with each other.

| Capture | Command | Object `power+0x652c` | Owned `power+0x652c` |
|---|---|---:|---:|
| 0 | initial-owner | 1216 | 1213 |
| 1 | gfx-snapshot | 4234 | 4234 |
| 2 | stop | 5776 | 5776 |
| 3 | gfx-snapshot | 7742 | 7742 |
| 4 | gfx-poweroff | 40513 | 40514 |
| 5 | gfx-snapshot | 45011 | 45012 |
| 6 | sample | 49054 | 49055 |
| 7 | sample | 67067 | 67068 |

From the terminal OFF capture to the final sample, object values changed 40513→67067 and owned values 40514→67068 over 221.286058 seconds. Owned pages 6, 14, 15 changed (72 bytes across those two captures). The final recovery counter remained 1, phase 2, shared host-stop request 1, request state/flag 0/1 and control cursors 32/32/32. All 36 work cursor words stayed zero and all 256 TA records stayed inactive. Application recovery did not complete and no work was submitted.

The host receive journal remained byte-identical across all eight captures with 50,412 records, status 0 and zero doorbells. The receive service was sealed, so its frozen journal does not establish firmware cessation. All post-attempt typed diagnostic ASC records explicitly say `sampled=0`; the frozen owner limits those paths to PMGR snapshots, software accounting and retained DRAM. No ASC/SGX/mailbox register sample was taken after OFF intent.

The permanent OFF gate is consumed and the owner remains pinned. All 174 pages, mappings, device context and private consumer remain retained. Only `sample` and `gfx-snapshot` are admitted by the wrapper now. There was no reset pulse, START retry, warm recovery, control or work publication, backing unmapping/free, consumer destruction, module unload or restart. The unresolved next boundary is whole-GPU access cessation and power/fabric/mapper shutdown coverage; ordinary runtime-PM success and these software OFF observations do not provide that proof.
