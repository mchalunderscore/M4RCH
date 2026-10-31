# Working style

The owner prefers decisive progress over overly cautious, incremental work.
Do not be afraid to overshoot when pursuing the requested outcome: use reasonable
judgment, take reversible actions, and carry authorized work through to a
concrete result instead of repeatedly asking to proceed.

Favor tests that can distinguish the leading hypotheses or validate the actual
fix on the affected system. Do not loop through small, effectively useless
tests or ask for repeated reproductions that cannot materially change the next
decision. When a meaningful test needs a reboot, hardware access, or a broader
change, prepare it thoroughly and explain its purpose and recovery path.

The owner accepts experimental kernel and hardware testing, including reboots
and recovery through external media when necessary. Preserve known-working
boot artifacts and user data, communicate material risks and uncertainties, and
follow higher-priority instructions and any explicit constraints for the task.

# Promoting a boot change

When the owner asks to promote a boot change as the new default, complete the
promotion to the normal package-managed boot paths and persistent GRUB default;
do not leave it selected only through a trial or one-shot entry. Once the new
setup is verified, remove other boot entries and superseded trial kernels,
initramfs files, loader copies and GRUB configurations from `/boot`, and clear
obsolete `out/` artifacts. Preserve the information and known-working boot
artifacts needed for recovery and source provenance outside the active boot
menu, verifying backups and accounting for unique modified, untracked or
machine-local material before removing anything. Keep one clear recovery path.
Regenerate and check GRUB, confirm the sole entry selects the intended kernel
and initramfs, and report whether the final default has actually been booted.

# Testing

NEVER perform synthetic tests that prove nothing in reality.

# Keep the active tree current

When code, helpers, experiments, documentation or evidence are superseded or no
longer useful, remove them from the active working tree as part of the same
work. Update references and related tests, and retain the information needed
for current installation, maintenance, provenance and recovery. Confirm any
unique untracked or modified material is preserved before removing it; Git
history alone does not preserve such material. Preserve ignored machine-local
build inputs, firmware and boot backups until their replacements are verified.
Account for concurrent work by other agents before changing shared files.

# Upstream first

Before implementing a feature, fix, or hardware workaround locally, check the
relevant upstream projects, starting with Aurora Silicon. Review current code,
updates, and relevant open, closed, and merged pull requests, including their
discussion and follow-up changes. Check other upstreams involved in the affected
layer as well. Record the relevant findings and prefer adopting or adapting
upstream work where appropriate; explain why a local implementation is needed
when upstream does not cover the requirement. If upstream cannot be checked,
state that limitation rather than assuming no work exists.
