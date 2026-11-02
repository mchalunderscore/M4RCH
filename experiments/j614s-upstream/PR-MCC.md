# mcc: admit the observed J614s T6041 layout

Extend the T6041 firmware-cache path to admit J614s when both board ID 4 and
the `J614sAP` ADT compatible match. Preserve the existing J616s admission and
all geometry, register-range and cache-status checks.

## Validation

- Built an Aura stage-two candidate with this `mcc.c` change and the existing
  J614s boot handoff overlay. The unmodified `mcc.c` at the tested source pin
  is byte-identical to this branch's upstream base.
- Verified the candidate bundle and selected it as stage two. After reboot, the
  owner reported Linux booted normally; the default kernel initialized the
  internal display, GPU, PMP, Wi-Fi driver and SEP. The previous loader was
  then restored and its hash verified.

The booted loader included additional J614s handoff patches and was built from
an earlier Aura source pin, not this exact upstream branch. Both builds report
the same Aura version, so the boot log does not independently identify the
candidate binary; no MCC initialization trace was captured. This is a single
combined-stack boot rather than a complete hardware regression run.
