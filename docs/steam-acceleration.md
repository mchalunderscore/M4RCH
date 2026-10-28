# Steam and graphics

`steam-m4rch 1.0.0.81-11` starts the native ARM64 Steam client using the
`userpages` helper and requires `user4k=on`. The client and its support
libraries remain in the user's Steam directory, so the package alone does
not create a fresh Steam installation. Proton can use its own FEX translation
for Windows games; this is separate from the retired Linux-user FEX/muvm
launcher and guest packages. The installed custom
`Proton 11.0-2e ARM64 (SME fix)` retains [source notes](../packages/proton-arm64-sme/README.md).

The owner reported Steam and Shinri performance and stability to be about as
good as macOS after sustained use. That is practical experience, not a claim
that all games or configurations have been qualified. Native graphics uses the
Aurora-derived Mesa/Asahi stack.

The GMod CEF patch was applied to the game after a verified isolated test; the
original game files and old x86 Proton prefix remain in the private
`out/steam-arm64-experiment/recovery-before-arm64/`. The former `steam-x86`
launcher is retired, so the old restoration instructions must be revalidated
before use. Full historical evidence is available through
`git show e7baa0e:docs/steam-acceleration.md`.
