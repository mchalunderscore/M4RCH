# m1n1 embedded-component notices

The `upstream/` notice text is from Aurora m1n1 commit
`6918c029cc0919015844839fee3505b3a4e65e46`. The `rust-crates/` texts are
from the exact crates pinned by that revision's `rust/Cargo.lock`, verified
against its checksums. The `rust-toolchain/` notices were recorded from the
Rust 1.99.1 sources installed when this binary was built with
`BUILDSTD=1`; `compiler-builtins-LICENSE.txt` includes the LLVM exception.

The upstream notices are retained together with the original license section
and credit list. The upstream credits mention a separate Aurora logo, but it was not included
in this binary: this package was built with `BUILTIN_LOGO=bootlogo`.
Its embedded bootlogo assets match m1n1's Asahi artwork references. The
artwork's separate license has not been established; the code license does not
establish the artwork's terms. A complete audit of Rust toolchain and binary
components has not been established by this notice bundle.

Crate archive SHA-256 values from the pinned `rust/Cargo.lock`:

- `bitflags-2.13.0`: `b4388bee8683e3d04af747c73422af53102d2bd24d9eadb6cbc100baef4b43f8`
- `log-0.4.33`: `0ceec5bc11778974d1bcb055b18002eba7f4b3518b6a0081b3af5f21666da9ad`
- `sha1_smol-1.0.1`: `bbfa15b3dddfee50a0fff136974b3e1bde555604ba463834a7eb7deb6417705d`
- `uuid-1.23.4`: `bf80a72845275afea99e7f2b434723d3bc7e38470fcd1c7ed39a599c73319a53`

The `rust-toolchain/LICENSE-APACHE` text is the Apache-2.0 text from the
checksum-verified `log-0.4.33` crate; Rust's locally installed source package
provided `COPYRIGHT`, `LICENSE-MIT` and the compiler-builtins notice.
