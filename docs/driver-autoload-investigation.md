# Driver autoload

The normal GRUB entry allows device and udev discovery to load the display,
GPU, audio and camera drivers. Speaker amplifier modules remain blacklisted.
`asahi-scripts-m4rch 20261026-3` removed the old explicit module-loading service;
`mbpfan-m4rch 2.4.0-4` removed its dependency on that service.

The attended autoload trial loaded the drivers, showed accelerated graphics,
Wi-Fi and a PipeWire microphone source, and had both fans tracking targets.
The owner reported a normal desktop and lid sleep/wake; the journal recorded
about 35 seconds of s2idle. Firmware reported VRR after wake; the KDE toggle
is intentionally hidden, and physical variation has not been independently
measured. The normal entry subsequently booted on 28 October. External display
output under autoload remains to be tested.

See [maintenance and recovery](installation-maintenance.md) for current boot
settings. The trial service, rollback scripts and historical ESP backups were
retired; a copy of the prior notes is in
`out/documentation-before-condensing-20261028.tar.gz`.
