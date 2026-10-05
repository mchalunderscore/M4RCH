# Left USB2 trial

Target: Mac16,8 / J614s. Use MagSafe; both left connectors are fixed USB2
host/source ports for this trial. USB3, charging and role swaps are untested.

macOS socket capture confirms left-front is `usb-drd1`, left-rear `usb-drd0`.
[Mapping receipt](evidence/2026-10-05-usb-socket-map.json) records that evidence.
The HPM mapping is provisional: ADT HPM0/port1 → drd0 and HPM1/port2 → drd1.
The register/resource map comes from this board's ADT and existing device tree.
Reusing the right-port PHY sequence on left PHY instances is an experiment.

`sdboot/left-usb-trial.dtso` adds two PHYs, a0 SPMI and HPM connectors; enables
four existing DARTs and two controllers; and supplies reciprocal role graphs.
`sdboot/left_usb_trial.py` combines it with the normal board overlay, compiles
and merges both against the baseline, and rejects unexpected existing-property
changes. It never deploys. Run where `dtc` and `fdtoverlay` are installed:

```sh
python3 sdboot/left_usb_trial.py \
  --base out/sdboot/hardware/experimental/boot/t6040-j614s.dtb \
  --out out/left-usb-audit/trial
```

An overlay cannot delete inherited `apple,force-device-mode`. The matching
DWC3 patch gives the explicit cable-event marker priority over forced modes.
Build with `make kernel` then `make packages`. Preserve the resident loader;
these are Linux/SD changes. Do not activate the trial with the old driver.

The delivered `left-usb-trial-01` kit includes both overlays, matching-package
receipt, checksums and `activate.py`. After installing its specified update
kit, run `sudo python3 /boot/left-usb-trial-01/activate.py activate`, then reboot.
The helper checks the mounted ESP identity and installed kernel/modules.
`rollback` restores the capacity-only overlay; package rollback is separate.

Test both orientations, preconnected boot and reconnect, with YubiKey then a
thumb drive; retain LED, Type-C, controller and enumeration evidence separately.
Verify right USB still works. Use a new scratch file for checked transfers.
The native `HANDOVER.md` gives the complete capture and return procedure.
