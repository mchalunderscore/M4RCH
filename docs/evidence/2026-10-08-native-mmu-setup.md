# Full G16 MMU setup sequence qualified — 2026-10-08

Executed complete native setupMMUConfig89e67f8..89e6d28 and actual G16 descriptor getter89e6dc4..89e6dd0. 512 randomized whole RAM images and complete ordered register events matched:256 direct RAM-register branch cases,256 checked external-register service cases;341 programmed MMU and171 already-enabled early returns. Binary/slot targets and native slice hashes are pinned in JSON evidence.

First read GFXd08000. Any nonzero value skips the entire setup without checking or replacing GPTBAT base. When zero, secureMonitor slot158 getter returns its descriptor field10; the physical-address service is supplied. Native extracts physical bits41:14 for a28-bit page number. Writes, each followed by register readback, occur in this order:
- d0802c = (GPTBAT physical >>14) &0xfffffff
- d08014 =80d8
- d08018 =80d8
- d0800c =0
- d08010 =0
- d0801c =0
- d08020 =0
- d08024 =0
- d08028 =0
- d08008 =1
- d08004 =3ff
- d08000 =1

Physical test values were below2^42, including unaligned values that native silently rounds down. Live owned backing must be16KiB aligned and within the qualified physical range. Register helper calls and physical provider were supplied boundaries; direct branch used RAM surrogate. Readback models return last written values; real hardware acceptance, clocks/power, cache/TLB visibility and GPU translations remain unproved. No extra barrier is inferred beyond actual readbacks in this routine.

This resolves full register setup ordering, not GPTBAT allocation/ownership or current loader MMU state. Before a live trial, qualify GPTBAT allocation and backing, read current control/base with powered register access, preserve existing contexts, and connect the owned device root using the separately qualified clear-invalid-before-invalidate transition. Never assume calling this setup will replace an enabled MMU's base. Existing shader/target/parameter/event/queue backing is still incomplete; no submitted job or pixels.

Source/evidence: experiments/t6040-gpu/audit-native-mmu-setup.py; docs/evidence/2026-10-08-native-mmu-setup.json. No Apple instruction bytes embedded. No hardware changes, reboot or macOS handoff during this audit.
