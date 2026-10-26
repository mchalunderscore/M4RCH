# Independent bounded admission-drain source review

The distinct `prepared-owner-v2` source has no remaining source blocker for
a separate fresh cold experiment. This review performed no hardware action or
module build. It independently checks root's finalized compiled-owner receipt
and its exact join to the selected source.

Boot d841's actual terminal request stopped at admission before202. Its capture
does not identify whether STATUS48 was invalid, RX114 was invalid/nonempty or
TX110 was full. The new source addresses that uncertainty by logging CTRL44,
STATUS48, RX114 and TX110 on each admission sample, and by reporting the exact
refusal condition. It does not present a pending EP32 frame as an observed cause.

After durable terminal intent, the new bounded admission path removes and logs
each frame with its status operands. Only endpoint32 with exact notification
`0x0042000000000000` reaches the unchanged receive service. That service copies
qualified records into the retained journal and publishes only their receive
consumer cursors; it preserves firmware producer cursors. Any preexisting EP0,
invalid, crash or unknown frame seals without a management request. A removed
preexisting EP0 is never saved as the new request's ACK.

Admission has a nominal11ms jiffies deadline, at most12 empty-RX/TX wait polls
and at most64 removed frames. The 64th qualified frame seals, so successful
admission may service at most63 frames. The receive service is finite and checked
again after return; this is not a guaranteed11ms wall-clock bound. Fresh four
operands immediately before202 must still show START set, valid reads, RXEMPTY
and available TX; late RX, full TX or elapsed deadline seals before publication.

The sole request, native type7/low8{1,2} ACK, fresh empty RX after ACK and before
CPU writes, native idle check, two fresh CTRL44 clears/readbacks and paired OFF
retain their original order. Invalid RX during the post-request poll now returns
EIO before removing a frame. The actual CPU-stop, terminal-attempt and typed
dispatcher functions are byte identical to the frozen source; startup retention
differs only in its distinct log marker. Paired OFF and receive-service sources
are byte identical. All174 pages, maps, context, consumer and module remain
retained on every result, with no retry or retirement/restart permission.

All26 input-source and25 output-source pins verify. The preparer's exact
transformations reproduce the selected Makefile, ASC source and recovery include.
Compared with frozen PWRGATE v5, only those three common files change and the new
header replaces the old unused header; graph and render fixtures remain exact.

Independent execution of the actual new header and transformed startup labels
passes85 cases under AddressSanitizer and UndefinedBehaviorSanitizer. The replay
receipt is byte identical to the author's final receipt. New cases cover exact
four-operand refusals, EP32 copy before202,63/64-frame boundaries, every staleEP0,
wrong/invalid/crash frames, service/journal failures, deadline and stalled-clock
bounds, late RX/TX/START changes, and invalid RX during ACK polling. Existing
native ACK, CPU readback, paired OFF, retry and retained-startup cases remain
included. Frozen provider/receive helpers are mocked at this header boundary;
their unchanged source and original55-case/native qualification are separately
pinned. No live ACK, physical OFF, cessation, retirement, restart or pixels are
established by this replay.

The actual finalized candidate passes its pure candidate validator. All10
artifacts,18 owner sources,16 preparation inputs, both dormant analysis inputs
and exact graph metadata verify; compiled source bytes match selected v2.
The root build log has no warning or error, and the94-case wrapper receipt is
pinned. Owner SHA256 is `de75ef4b8c772a56de3026ceb622b940206ed7d0a1ac660a25cae323216681f3`;
candidate receipt SHA256 is `393049662c9966922fda7f66cbfa1c762efc2f0840492042b581e96271a7b6a5`.
This is an offline receipt check, not a fresh-boot preflight or GPU access.

The [bound JSON](2026-10-09-gfx-native-powergate-drain-independent-review.json)
pins the source receipt (`e55cf8f6…`), header (`f3f4429f…`), actual85-case replay
(`041aed9b…`), prior native evidence and actual d841 terminal outcome. The current
consumed owner remains a retained diagnostic context; this review authorizes no
second control action or source mutation on that owner.
