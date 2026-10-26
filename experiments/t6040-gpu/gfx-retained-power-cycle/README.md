# Distinct retained native power-cycle experiment

This new family retains the successful first native PWRGATE admission-drain
owner and adds one separate management epoch. It is prepared from the immutable
`out/gfx-native-powergate-drain/prepared-owner-v2` source. Selected source v6 is
`out/gfx-retained-power-cycle/prepared-owner-v6` and its actual C qualification
is `out/gfx-retained-power-cycle/owner-qualification-final-v6.json` (102 cases).
The selected compiled candidate/final wrapper receipts are a separate root
handoff; this document alone does not authorize loading any module.

Typed commands are `sample`, `gfx-snapshot`, one initial `gfx-powergate` and one
subsequent `gfx-retained-cycle`. The first request/ACK/CPU stop/paired OFF must
succeed, with a clean captured strict physical OFF and PM accounting witness.
The second command additionally verifies those first C fields, unchanged host
page/root/context identities and a fresh strict OFF snapshot before its sole PM
get. Diagnostics remain available; every uncertain second result seals all
controls without releasing retained memory or compensating PM ownership.

The second epoch has a separate PM reference, coordinator session and static
host protocol journal. It admits one START only at the original exact status6a,
START-clear, RX-empty, TX-available cold boundary. It seeks fresh autonomous
HELLO12 and the exact saved endpoint map sequence, without INIT220, endpoint
starts, root publication or context reattach. The inspected native
HELLO→status5/final-map-ACK→status6/PWRGATE→status7 route motivates one separate
202/ACK/checked CPU stop/paired OFF/PM put. This is a limited management
roundtrip hypothesis; no retained application rejoin or rendering contract is
established by it.

All 174 original pages, installed host root, joined context, consumer, mappings
and module remain pinned on every result. First epoch fields and the first
coordinator session are never cleared or rewritten. The second intent directly
seals the actual copied receive worker. Historical first OFF fields in frozen
diagnostics must be interpreted together with the new `diagnostic-current`
marker; they cannot establish current physical OFF after the second PM get.

Source preparation and actual-header qualification use:

```sh
python experiments/t6040-gpu/gfx-retained-power-cycle/prepare-retained-cycle-owner.py --source out/gfx-native-powergate-drain/prepared-owner-v2 --destination NEW_DESTINATION
python experiments/t6040-gpu/gfx-retained-power-cycle/test-retained-cycle-owner.py --source NEW_DESTINATION --output NEW_QUALIFICATION_JSON
```

Outputs must be new; frozen source and historical artifacts are retained. Only
the root operator performs hardware actions, after the final receipt and fresh
boot qualification. The previous current owner has no reentry API; this family
must not replace that loaded owner or revive its consumed intent.
