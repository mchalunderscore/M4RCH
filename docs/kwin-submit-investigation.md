# KWin and GPU submission

The previous KWin Alt+Tab freeze was reproduced while a GPU mapping was
removed by deferred handle-close cleanup after being rebound. The promoted
`linux-m4rch` package carries
[the deferred-close correction](../patches/linux-asahi-deferred-close-rebind.patch).
The owner reported that Alt+Tab works after promotion. Older mappings can
remain until handle close or VM teardown; the observation does not prove
that every GPU workload is free of faults.

Mesa also retains submission capture and attachment-lifetime patches. The
[package guide](../packages/README.md) describes the installed graphics stack.
The detailed diagnostic history is available in Git at `e7baa0e`.
