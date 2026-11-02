# Temporary Aurora FEX Mesa bridge

This package retains the signed Aurora FEX guest payload built from Mesa
`c208afc352e9d4c10ee71c883a369a9079dd7d84`, with package dependencies changed
to match the J614s host Mesa and Vulkan `1.1` releases. It does **not** carry
our Zink patch, and using the same source revision does not prove runtime
compatibility. If this overlay is needed for a future FEX workload, assess
whether it needs the local patch and test that workload before replacement.

On 1 November 2026 the owner reported their Proton FEX setup works. On that
boot `aurora-fex-mesa.service` was inactive because
`/usr/share/guestos/fex-mesa` did not exist; no Aurora guest overlay was
mounted. That is evidence this particular integration was not in use then,
not a complete audit of which FEX or graphics libraries Proton uses. Building
a patched guest layer is not currently a prerequisite for the owner's working
Proton setup. Do not remove the installed package without checking the setup
and its future dependencies.

The input `aurora-stock-fex.pkg.tar.zst` is the Aurora repository artifact
with SHA-256 `1bcdc7b033ea89d7f3a315a7f989757650b5500ff818325770c3b34e76c6a38a`;
its detached signature verified against Aurora's package key. The original
`.INSTALL` is retained without changes. `makepkg` produced a locally unsigned
bridge at `cache/fex-stock-bridge/` with SHA-256
`371afd256855e7db5f2c85cc8e291c2f7f209bd5d49d42bb419a712735dfa502`.
A comparison of all 146 extracted payload entries confirmed matching file
contents, modes, types and symlink targets; the installation script also
matched. Rebuilding can produce a different archive hash because of package
metadata.
