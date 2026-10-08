# Native render-target record initialization and scrub — 2026-10-08

Complete init8a0b3e0..8a0b514 and scrubEvents8a0b300..8a0b3e0 execute offline in Unicorn against matched private AGX353.14 / Apple25G83. Whole0x400-byte object and0x2000-byte record array compare, including untouched bytes. 877 successful initialization cases,147 supplied base-initialization failures,1024 scrubs,18197 event-init calls and21201 event-scrub calls. No hardware or exported Apple executable bytes.

Initialization selects a record count from accelerator u32f528, falling back to718 when the override is zero. Object280=count;278=count*0x58;290=supplied record-array pointer. Clear284/288 (two32-bit cursors). Invoke the external event initializer once per record at array+0x18+i*0x58. Each record therefore reserves24 bytes before the event; its whole stride is88bytes. This does not prove the initializer's extent or resulting event contents: the external implementation is absent and deliberately opaque in this audit.

Also store accelerator/shared at120/128 and retain shared via slot20; clear u3218, u6430, u64260 and140..1bf; set byte2c0 to bool(accelerator u32ecd4); clear130; store the caller's64-bit argument at138 and258; clear1c0/1c8. Untouched fields, including ring capacities/cursors not explicitly written by this method, remain untouched. A real zeroed-object constructor is a separate prerequisite. On supplied base-init failure, return0 without changing target bytes or requesting record allocation. Positive record allocator result supplied; allocation failure is not qualified.

Scrub visits every event via an external call with accelerator140 and record event pointer, then calls resource virtual1a8 on non-null GTP1c0 and ordinary ring130, including the latter tail-call. Service identity/semantics are not inferred from the slot number. The event and resource implementations are argument-checked stand-ins and do not alter fixture bytes.

Next use full fresh update to join initial record selection, sizing, resource allocation and 3D descriptor loading. Event contents/lifetime/waits and actual allocator behavior remain unproved.
