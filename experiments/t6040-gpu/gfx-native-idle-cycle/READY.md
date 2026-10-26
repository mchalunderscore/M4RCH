# Offline handoff ready — native idle-cycle version9

Python contract, wrappers, finalizer, targeted tests and these handoff docs are
frozen. The selected source is `out/gfx-native-idle-cycle/prepared-owner-v1`;
source receipt SHA313135beb0a845b461f07398a56072937c8e89f3771f161a30b6c1f13aaa7d5d.
Selected C qualification is `out/gfx-native-idle-cycle/owner-qualification-final-v1.json`,
SHA5f1de50846c2b4b51488e37e103fa1277b17b20547f8a7c1390f288ec5b348f2,135 cases.
Selected Python qualification is `out/gfx-native-idle-cycle/wrapper-qualification-final-v2.json`,
SHA565b4bb2d72eb56f498f8450e3c8f57e27b3aa08460fee4404c9bcb390753a08,74 cases,
four cold-main and ten resident-main flows intercepted in RAM.

Root may clone the stable20-source prepared owner into a distinct candidate,
build with W1, preserve the build log at `out/gfx-native-idle-cycle/owner-build.log`,
and exclusively finalize with:

```sh
python experiments/t6040-gpu/gfx-native-idle-cycle/finalize-powergate.py out/gfx-native-idle-cycle/candidate out/gfx-native-idle-cycle/owner-qualification-final-v1.json
```

Finalizer SHAef0cf7559f3225cbac70bd2dbab14cd82e91d108b6573f4c6af49aa1a86e1e09.
The preparation filename is `native-idle-cycle-preparation.json`. All non-owner
artifacts and dormant analysis metadata retain their frozen v8 bytes; old
candidate receipt/preparation files must not be copied as new finalized files.
Old native header is removed, new idle header added and coordinator byte exact.
A successful finalizer is metadata preparation, not a hardware qualification.

Fresh preflight and one cold owner load remain root-only future operations after
all team inputs are frozen. This kit refuses consumed boots94cb/d841/1686/5bf0/
9626 before native access. Current boot9626 and its consumed v8 owner remain
quarantined. A new cycle additionally requires a fresh successful original
first own202/CPUstop/pairedOFF/strictOFF proof. PreON stays6a/6c; postON permits
6a/6c/6d only with the own second ON and reference conditions. No app work,
INIT220, queue reset, backing release or general restart is admitted.

[Qualification details](WRAPPER-QUALIFICATION.md). New hardware reentry, second
physical OFF, application rejoin, execution, pixels and retirement are unverified.
