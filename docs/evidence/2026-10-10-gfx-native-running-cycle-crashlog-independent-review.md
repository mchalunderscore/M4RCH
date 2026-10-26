# Independent retained-cycle crashlog review

The saved buffer at firmware address0x10001de4000 contains a complete crash
record with message `Invalid AP power: 33`. Independent parsing validates the
CLHE header/version0x303/size0x910/flags0x820, ten bounded sections and an exact
repeated32-byte header footer at0x8f0. The2320-byte log fits both the EP1 event's
4KiB descriptor and the original32KiB reserved buffer. The prior preboot32KiB
was all zero. This is a software panic record rather than a harmless initial
buffer request.

The35-entry mailbox history contains cold negotiation, first202/201, then the
new second HELLO/map/Running sequence ending in owned HOSTB20. Its final raw
eight-byte field is0x1de74f5e1; Ctim is0x1de74f7a5, a difference of452 if they
share a64-bit counter. The low32 timestamp and following four bytes are also
preserved separately because the maintained Linux layout labels the latter
unknown. Counter frequency and host-clock offset are unverified. The new
handshake history, matching panic call and postevent EP1 notification support
a new retained-cycle panic; this conclusion does not rest on magic or clock
conversion alone.

The exact captured TEXT confirms that typeB wire0x20 is supported and converts
to internal0x21, decimal33. The handler panics when that requested state equals
the existing AP state field. Its call at0xfffffc0000048368 appears in the
captured14-address stack and references the exact panic format string. The
crashlog Ccdp mapping independently supplies the DATA VA/PA relation; the
saved AP table pointer resolves to rowID0 with current state33. Thus the
evidence supports a duplicate retained AP ON transition. The error does not
mean wire0x20 is an unsupported power value.

Two format details prevent overclaiming compatibility with an old decoder.
The version303 Cver string starts after GUID16 plus eight zero bytes, at
payload offset24, and reads `RTKit: RTKit-3255.160.4.release - Client: not set`.
The old Linux offset16 would print empty. Its generic footer loop also checks
offset+12 as section length before switching on CLHE; here that word is flags
0x820, exceeding the remaining32 bytes. This independent decoder recognizes
only an exact repeated opening header as the footer and bounds it explicitly.
No architectural register section is present and the async-error payload is
all zero; neither fact establishes that every hardware error is absent.

Native retained-buffer semantics and this panic record now explain the EP1
frame as a crash notification. No safe descriptor echo, pending B20 reply,
successful second HOST state or second shutdown is established. Root's saved
capture audit records unchanged owner/state and normal sampler unload, with
no GPU power/mailbox/CPU control commands. The reviewer read saved files only.
Snapshots are non-atomic and firmware-cache freshness is unverified. The next
policy investigation concerns retained AP notification state; no echo/retry
kit, application restart, release or retirement is authorized by this report.
