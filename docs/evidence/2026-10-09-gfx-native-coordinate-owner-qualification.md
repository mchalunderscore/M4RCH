# Paired notification owner adapter qualification

The actual separate adapter and transformed lifetime boundaries pass40
RAM cases under ASan/UBSan. The paired JSON preserves the tested adapter,
transform, core and original source hashes. The source and test kit are in
`experiments/t6040-gpu/gfx-native-coordinate-owner/`.

The checks cover PTD QWord payload/status access and request aperture,
three32-bit rail voter words, partial reservation/mapping failures,
available multi-reg aliases, exported OF iterator reference balance,
snapshot error normalization, successful ON and an idempotent module pin.
Actual transformed cleanup/startup-refusal/later-failure/retirement excerpts
verify retained ownership and absence of an automatic PM put after ON
admission. The protocol core has a separate182-case qualification.

The first full module build exposed an unexported OF iterator. The adapter
now uses exported `of_find_all_nodes()` and balances references. The final
full W=1 module build passes on7.1.13-m4rch-gpu-native-reset with the two
existing unused-function warnings. Neither reset API is imported.

No hardware action follows these tests. LeakSanitizer was unavailable under
host ptrace restrictions; ASan memory checks and UBSan were enabled. The OF
scan remains bounded by translatable descriptions and does not establish
the absence of unregistered writers. Fresh layout guards and resource
reservations remain required. MMIO ordering, scheduling, physical teardown,
DMA/cache/UAT drain, safe retirement, restart and rendering remain unproved.
