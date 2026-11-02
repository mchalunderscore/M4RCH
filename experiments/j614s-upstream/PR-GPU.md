# drm/asahi: admit the observed 16-core T6040 layout

The T6040 GPU configuration currently accepts the 20-core layout on which its
command buffers were measured. A 16-core M4 Pro in a J614s reports the same
two clusters and ten slots per cluster, with masks `0x3db, 0x3db`, and is
refused by that core-count check.

Allow a SoC configuration to identify an additional observed mask layout.
T6040 admits that exact layout using the existing `TWO_BY_TEN` operand-state
and `TWO_CLUSTERS` deflake buffers, and warns that their offsets are still
experimental for this configuration. The measured 20-core path and T8140
configuration are unchanged. Other 16-core masks remain refused.

## Validation

- Booted a J614s M4 Pro with the candidate on the Aurora 9.3 kernel and its
  existing J614s boot, device-tree and calibration handoff. The configured
  alternate-layout warning appeared and the desktop worked.
- A 15-iteration Wayland/Zink shared-surface rendering run completed on the
  M4 Pro. An offscreen Zink compute shader produced 262,144 results matching
  the CPU after 64 arithmetic rounds per result. No matching GPU or DART
  errors appeared in the checked kernel log.
- Built the full trial kernel and modules with the distribution configuration.
  The three files changed by this branch are byte-identical to those used for
  the hardware trial; the tested kernel includes other J614s integration
  patches and is not a build of this exact upstream branch.

The 20-core buffer offsets have not been independently measured on this
16-core configuration. These short render and compute checks do not establish
preemption correctness or cover all workloads. Review is requested on the
admission policy and on whether automatic admission is appropriate before that
additional evidence exists. A separate J614s device-tree proposal is #795.
