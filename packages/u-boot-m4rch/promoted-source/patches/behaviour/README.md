# U-Boot behavior series

Apply `series` in order to Aurora U-Boot
`01f255b636737bc783b581b04584d1224ab06cf4`, using the source archive with
SHA-256 `b1656feb1edcb418d4bf2f83aeb750be94fcd824a20f40259b90f75c67f5300a`.
The complete replay matched all 37,983 regular source files in
the source tree used for the booted candidate.

The patches separate shared-tree and DMA reservation setup, firmware-tree
parsing, AOP/ISP handoff, USB/HDMI tuning, and the board handoff's integration.
They are ordered; intermediate states are not standalone build targets.
The source comparison does not prove a reproducible binary build or complete
hardware qualification.
