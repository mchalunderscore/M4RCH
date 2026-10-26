# Checked reset startup admission correction

The explicit reset feature previously required `run_gate=2` and a resident
session for every module initialization. The root runner first loads the same
module with `run_gate=1`, nonresident, to validate its owned allocation shadow.
That required shadow was rejected before allocation, preventing the fresh-boot
experiment from reaching the retained owner.

A small actual-C helper now admits exactly clean gate1/nonresident and clean
gate2/resident. Both reject `request_shutdown`, `warm_restart`, and
`release_on_shutdown`; other gates or mismatched resident flags are rejected.
The invocation remains at the start of `hello_init`, before root allocation,
provider acquisition, PM, or MMIO. The feature guard includes the helper only
for `GFX_RESET_SCOPE_TRIAL`. Existing feature-off startup code and all GPU
command, lifetime, reset, and backing-release contracts remain unchanged.

The new replay includes the unchanged helper, top-level feature guard, and
actual invocation block. ASan/UBSan passed 80 feature-on input combinations:
the two intended clean modes were accepted and 78 were refused before the
allocation recorder. Another 80 feature-off prefix combinations confirmed
that the additional guard imposes no restriction when compiled out. These
feature-off cases cover the new prefix only; later existing startup checks
are not claimed to accept every combination. The actual compile guard also
passed all 16 feature/fixture configurations, retaining its requirement for
joined recovery without startup work. Source inspection verifies that no
function call precedes admission in the actual initialization prefix.

Report: `out/gfx-reset-scope/startup-admission-v2-validation.json`. Its SHA256
is `16f833b2726fa42c4ab628563eb3b4c2c36997b33ad83f2c414bc69a3bb1a192`.
The tests perform no kernel, device, sysfs, MMIO, PM, module, mount, or reboot
operation. No previous candidate was rebuilt or changed. Root separately
corrects the preparer/runner's reset-feature retirement-probe metadata; this
admission fix deliberately keeps shutdown forbidden rather than admitting
that erroneous live parameter.
