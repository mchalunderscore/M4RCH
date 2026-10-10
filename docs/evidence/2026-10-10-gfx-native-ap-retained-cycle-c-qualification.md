# Native retained AP cycle: selected C qualification

The selected v11 source has a saved **122-case passing C qualification**, with ASan/UBSan and the actual new header, coordinator core, copied worker, cold `power_ack` helper and cold pre-root condition. Independent review verified all 40 qualification pins, 32 selected source pins and 32 frozen baseline pins; it ran no tests or builds.

Selected source receipt: `f8cc352fce19be8a959fdd6c4a386360cbea746934d5cfa09defa09222faf9d1`. Saved C receipt: `aa875ccdecb07b2944dee2066a53d955b613582929e6e232581dd4b4b096d334`. Source: `out/gfx-native-ap-retained-cycle/prepared-owner-v2`.

The cases require an owned exact cold EP0 B20 request/reply before the actual pre-root condition admits publication; missing or changed retained proof refuses before a second PM reference. They cover duplicate B20 panic in the firmware model, queued replies, invalid/late operands, guarded retained skip, mutations after skip and 202 intent logging, ACK capacity, low1/2 shutdown ACKs and stop/OFF/put failures. No second B20 or fallback is executed.

All six second-state log groups remain complete newline records. The measured worst numeric row is **425 bytes**, below the configured 511-byte bound. The immutable 135-case qualification is composed where source remains unchanged, without rerun.

This is RAM qualification, not another GPU trial. PM, CPU, provider, mailbox and DRAM callbacks are mocked. The cold test extracts the real pre-root condition but stubs `crashlog_boot`; it does not execute full cold startup/root publication. Neither repeated physical OFF, application rejoin, rendering nor DMA retirement is proved.
