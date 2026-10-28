# Fan control

The installed `mbpfan-m4rch 2.4.0-4` service controls both fans through macsmc.
The local curve uses an eight-second filtered CPU Die Max reading and a linear
75–90°C range; a raw reading at or above 90°C or an invalid sensor reading
requests full speed immediately. Firmware limits still constrain each fan.
This is not a calibrated copy of Apple's multi-sensor policy.

The kernel carries the [SMC handoff](../patches/experimental-aurora-pr512-fan.patch)
and [retry](../patches/experimental-j614s-fan-unlock-retry.patch) changes.
The retry waits three seconds between attempts and allows up to 30 seconds
after unlock. Both fans tracked their targets during the attended autoload
and wake checks; the owner reports cooling behavior about as good as macOS.
See [the package](../packages/mbpfan-m4rch/) and
[maintenance inventory](installation-maintenance.md). Historical trials are
available in Git at `e7baa0e`.
