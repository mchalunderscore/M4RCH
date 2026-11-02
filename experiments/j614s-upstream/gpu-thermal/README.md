# Experimental GPU thermal trips

[Aurora Linux #852](https://github.com/aurora-silicon/linux/pull/852) is a
hardware-tested exploration, not an upstream-ready thermal policy. It applies on Aurora Linux #795 head
`dc054fb02bfb002e41f2dd8f43a3dce2983cf537` and the installed PR-stack source.
The 100 C switch-on is provisional. Read the detailed investigation and
hot-load limitations in [the report](../../../docs/j614s-smc-thermal-investigation.md)
before testing or proposing it upstream.

The change remains open for discussion as a draft. Its actual 100 C behavior
and the J616s hardware remain unqualified.

`transition_trial.py` performs a guarded, real GPU and CPU workload with one
zone's trips temporarily lowered, then restores them. It uses an independent
restoration watchdog and must only be used on the specifically checked trial
configuration; its lower temperatures test controller transitions, not safe
operating limits.

The trial has ended. See [current recovery](../../../docs/recovery.md) for the
present boot stack and recovery path. No firmware or private SMC data is
included here.
