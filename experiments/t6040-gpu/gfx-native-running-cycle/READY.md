# Offline handoff ready — native Running cycle version10

Python contract, wrappers, finalizer, targeted tests and these handoff docs are
frozen. Selected source: `out/gfx-native-running-cycle/prepared-owner-v2`,
receipt SHA `d5ed3909257d659816e2c23cebe43f72308aa0677efa3660b5e76758b56ee36d`.
Selected C: `out/gfx-native-running-cycle/owner-qualification-final-v2.json`,
SHA `aaf2e76d651fbff245b169a500468b507a105cdbdb1d991b9469ea6c240fd50a`,199 cases.
Selected Python: `out/gfx-native-running-cycle/wrapper-qualification-final-v2.json`,
SHA `bc0a8396c901708854a9036573e54ed52d72d6e21490933170078e3276716d60`,102 cases,
four cold-main and ten resident-main flows intercepted in RAM.

Root may clone the stable20-source prepared owner into a distinct candidate,
build with W1, save `out/gfx-native-running-cycle/owner-build.log`, and exclusively
finalize with:

```sh
python experiments/t6040-gpu/gfx-native-running-cycle/finalize-powergate.py out/gfx-native-running-cycle/candidate out/gfx-native-running-cycle/owner-qualification-final-v2.json
```

Finalizer SHA `a3720bdd9d7356e21111d2e7ccb5f3d5432d65567523bf81288424b4a5301c15`.
The new preparation filename is `native-running-cycle-preparation.json`.
Non-owner artifacts and dormant analysis metadata retain frozen v9 bytes; old
candidate receipt/preparation files must not be copied as new finalized files.
Remove the old idle header, add the selected running header and retain the
coordinator byte exactly. A successful finalizer is metadata preparation.

Fresh preflight and one cold owner load are root-only future operations after
all team inputs are frozen. Consumed boots94cb/d841/1686/5bf0/9626/54e2 are refused
before native access. Current54e2 remains sealed with its second reference held.
Second-cycle admission needs a newly successful original first own202/CPUstop/
pairedOFF/strictOFF proof. PreON stays6a/6c; postON6d needs the separately qualified
second ON/reference. HELLO/map→exact BOOT7/20→one owned B20/fresh exact reply→own202
is mandatory; both20 messages remain distinct from shutdown ACK1/2. Unknown
results retain resources and allow only typed sample/snapshot diagnostics.

No app work, INIT220, data restore, queue reset, backing release or general
restart is admitted. [Qualification details](WRAPPER-QUALIFICATION.md).
Hardware second OFF, application rejoin, execution, pixels and retirement are
unverified.
