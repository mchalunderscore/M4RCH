# Continuous native register-map acquisition and pointer setup

Private-derived AGX353.14 / Apple25G83; offline only. This extends the prior
probe-mapping audit through the acquisition of the two mapping objects and
executes the native physical-base/offset getter leaves instead of stubbing them.

1024 cases execute `89a1bc4..89a1edc`. The service pointer comes from global
`c6e7908`. Native code calls its virtual `710` with a byte-sized register index
and options zero, first caching the result at global `c6e7938`, then, when the
second-region flag is set, caching the second result at `c6e7940`.
The index bytes are globals `c6e7914` and `c6e7915`. Both index pairs 0/1 and
1/2 are tested. Earlier probe code selects these pairs based on service
virtual `700` (a count-shaped return); the earlier selection is inspected,
not executed by this test. Exact service method identity needs external symbols.

With the direct-mapping flag selected, the native path calls the first and
second mapping objects' virtual `138` address getters, producing accelerator
`358`/`f808` and `f8e8` respectively. It constructs region-45's descriptor
using native G16X virtual `b98` (returns `d00000`) and `b30` (loads global
`c6e7920`). Both actual G16X vtable targets are decoded and asserted from the
binary, and both complete getter leaves execute. The descriptor therefore
has flags=2, segment count=1, physical start `global[c6e7920]+d00000`,
extent from the second mapping's length getter and logical offset `d00000`.

The complete accelerator and global page are compared against exact expected
writes. Synthetic providers remain for service virtual `710` and mapping
address/length getters. PAC is bypassed. Flag settings intentionally skip
optional provider-enable calls, and earlier flag/count selection and final
virtual `11e8` are excluded. Random physical-base values are fixture inputs,
not recovered physical addresses. No hardware accesses or firmware jobs execute.

## Address comparison with captured boot ADT

The existing `out/gpu-gravity-20261007/post-handshake-reboot/linux-boot.adt`
capture (SHA256 `c7b131be827d37c000b53a35a4b6662d40af6fff40d2fc19fc1e6aabd28d5fa9`)
translates the SGX windows to `288000000` with size `3758000` and
`288d00000` with size `16c000`. Their bases differ by exactly `d00000`.
That agrees with the native relative Fender offset. If the service supplies
these windows in this order and global `c6e7920` is the primary base, the
native gate register `d06030` resolves to physical `288d06030`, and bank-9
kick offsets resolve to primary physical `288004090`/`288004098`.
These are conditional derivations, not independently observed native mappings.
The captured ADT is from an earlier boot, not a new capture of this boot.

Next resolve service register-index ordering and the provider behind physical
global `c6e7920`, then check submission visibility and completion on hardware.
The failed warm INIT remains retained in the current boot; a normal reboot is
required before a new GPU hardware trial.

```sh
python experiments/t6040-gpu/audit-private-probe-acquisition.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  docs/evidence/2026-10-08-private-probe-acquisition.json
```
