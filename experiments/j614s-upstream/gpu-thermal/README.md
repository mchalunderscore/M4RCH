# Experimental GPU thermal trips

`gpu-thermal-two-trip-experiment.patch` is a hardware-tested exploration, not
an upstream-ready thermal policy. It applies on Aurora Linux #795 head
`dc054fb02bfb002e41f2dd8f43a3dce2983cf537` and the installed PR-stack source.
The 100 C switch-on is provisional. Read the detailed investigation and
hot-load limitations in [the report](../../../docs/j614s-smc-thermal-investigation.md)
before testing or proposing it upstream.

The change is open for discussion as draft [Aurora Linux #852](https://github.com/aurora-silicon/linux/pull/852).
Its actual 100 C behavior and the J616s hardware remain unqualified.

`transition_trial.py` performs a guarded, real GPU and CPU workload with one
zone's trips temporarily lowered, then restores them. It uses an independent
restoration watchdog and must only be used on the specifically checked trial
configuration; its lower temperatures test controller transitions, not safe
operating limits.

The trial is running and the normal loader has been restored for the next boot;
a recovery copy is at `/boot/efi/m1n1/boot.bin.m4rch-before-gpu-thermal`.
No firmware or private SMC data is included here.
