# m1n1 behavior series

Apply `series` in order to Aurora m1n1
`6918c029cc0919015844839fee3505b3a4e65e46`, using the source archive with
SHA-256 `0a912b8acb0149937927eea3dfb4ca9215ed9d50e21ea9e92273727d2f87052b`.
The complete series was applied to that archive and its entire resulting tree
compared byte-for-byte across 745 regular files with the built source tree.

The series groups DAPF readiness and RAM handoff, flat-tree address handling,
display handoff, CPU cooling-reference pruning, PMP tree space, SD power,
GPU calibration tests and MCC admission. The SD power patch describes the
installed binary; the separate SD-removal candidate is not part of this series.
The source comparison does not prove a reproducible binary build.
