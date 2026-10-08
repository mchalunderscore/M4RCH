# Owned GPTBAT and device-root preparation passed — 2026-10-08

Added one zeroed16KiB Linux-owned context-table page to the joined graph allocation test. All128 context encodings covered by the native audit were constructed against the actual owned device-root physical page and logged; independently compared with native_g16_mapping.context_root. The table was then cleared and only candidatecontext1 staged. All other entries and trailing page bytes remain zero. Candidate1 has no live ID reservation and is not yet substituted into prepared job fixtures.

Runtime7.1.13-m4rch-gpu-contract passed:112 unique physical allocations,128 independently matched TTBR0/zeroTTBR1 pairs,35 owned device-page shadow walks,64 command candidates,35 independently native-matched mapping descriptors,206 graph leaves, correct cold notification binding then prepared ring. TablePA102cdff0000,basePPN40b37fc,deviceRootPA1011a054000;candidate1TTBR0101011a054001. These physical values are observations from this trial, not reusable allocations.

BuildW=1 passed without warnings. Normal unload released all backing; module absent. Gate2 remains rejected in this experiment; no root/context/MMU/firmware publication, hardware register access, accepted job or pixels. Parent cache clean includes the new page but does not prove GPU visibility.

Next qualify current live GPTBAT control/base and table acquisition/ownership; connect actual selected job context and full shader,target,parameter,event/queue backing. New table must not overwrite enabled loader contexts. Existing native setup, context invalidation and preserve-versus-zero evidence is bundled. No reboot or macOS currently needed.

Evidence2026-10-08-owned-context-graph.json/-dmesg.txt and source command-pool-map.h/graph-map.h; tested build archived inbuild/owned-context-graph. No Apple instruction bytes embedded.
