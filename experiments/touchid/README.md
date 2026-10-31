# J614s Touch ID

The qualified Aurora-based implementation is now installed as the
`linux-m4rch`, `u-boot-m4rch`, `libfprint-aurora`, `fprintd-aurora`, and
`aurora-sep-m4rch` packages. See the package source records and
[SEP/DCP investigation](../../docs/j614s-sep-dcp-reservations.md) for the
hardware handoff, upstream work, validation, and remaining uncertainty.

One right index finger was enrolled and matched on the guarded trial. The
qualification boot matched that finger and the user confirmed the display,
keyboard and trackpad worked. The packaged default booted and restored the
identity on 31 October 2026. Normal startup uses xART guard level 1 and refuses
to create a missing Linux keybag automatically. The per-machine signed
firmware and sensitive host-state backups are root-only and are not package
inputs. Restore procedures and anti-replay caveats are in
[recovery](../../docs/recovery.md).

`sudo-pam` and `sddm-pam` record the local authentication configuration.
KDE's packaged `kde-fingerprint` PAM stack handles lock-screen fingerprint
requests. SDDM's password-first configuration tries Touch ID after an empty
password submission; fingerprint login does not unlock KWallet. SDDM fingerprint login succeeded at the actual greeter after the promoted default booted. An account-specific sudoers rule requires authentication despite the original passwordless wheel policy; a real sudo command succeeded using Touch ID. Password authentication remains the fallback.

Earlier attended-trial notes are preserved at
`cache/touchid-promotion/provenance/trial-notes-before-promotion.md`. Boot
trial scripts and patch copies in this directory are historical evidence,
not the normal boot setup. The package source records contain the maintained
patch series.
