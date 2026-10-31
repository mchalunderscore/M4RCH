# m1n1 source record — m1n1-m4rch 20261031-1 / -2

Aurora `aurora-wip` commit `6918c029cc0919015844839fee3505b3a4e65e46`,
archive SHA-256 `0a912b8acb0149937927eea3dfb4ca9215ed9d50e21ea9e92273727d2f87052b`,
plus the ordered J614s `upstream-integration` series. The original patch has
SHA-256 `74c072c21dc165831198503be533d36d9a7452c033833e5721e2679501a25870`.
Replay on the new archive matched all 745 regular source files used to build.
Build options: `RELEASE=1 CHAINLOADING=1 BUILDSTD=1 USE_CLANG=1
BUILTIN_LOGO=bootlogo`. Binary SHA-256
`fe9571af510cec542852e88a21928be29a855c66b2937fc3938a6cdedb3fc501`.
The owner reported a successful combined J614s boot. This is not a claim of
reproducible output or complete display qualification.

The `-2` recipe retains the same booted binary and adds the upstream
component license and credit records under `licenses/`. The installed `-1`
package predates that notice update. The binary was built with
`BUILTIN_LOGO=bootlogo`; the embedded bootlogo assets match Asahi artwork
references. The artwork's separate terms have not been established. The code
license is not evidence of the artwork's terms. The retained notices do not
by themselves establish a complete audit of all binary components.
