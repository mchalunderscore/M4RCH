# Quarantined speculative bank scan

The initial four reads at secondarySGX+0xa0/+0xa4/+0x1500/+0x1514
returned zero, while GFender+0x10 returned0x11020a. Normal cleanup completed.
Expanding to fifteen candidate banks hung the whole laptop; the user reports
trackpad haptics stopped and an automatic reset followed after about20seconds.
No exact fault address or reset cause survived in the journal/pstore.

The failed source is archived with a disabled extension. The Makefile rejects
builds, and the failed module is preserved as .ko.disabled under out/. Do not
repeat this scan. A read-only access and ADT aperture containment do not establish
that a bank exists, is powered/clocked or is safe to access. Obtain an attributable
Bumper register map and access prerequisites before another physical-bank trial.

See docs/evidence/2026-10-07-gravity-gpu-bumper-scan-hang.json for provenance.
