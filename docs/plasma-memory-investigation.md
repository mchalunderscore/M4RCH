# Plasma memory investigation, 27 October 2026

After Steam/muvm exited, the host had about 10.8 GiB available. Plasma Shell's
memory cgroup carried approximately 1.45 GiB of unevictable memory and KWin's
about 0.55 GiB. These cgroup charges include shared graphics memory and are
not a definitive attribution of the objects to application code. Exported
DRM dma-buf sizes totalled 4.27 GiB; this is not a resident-memory total and
overlaps other counters.

The active wallpaper is the GPU-driven `com.github.arcanorca.konway`. A live
switch to the configured static `org.kde.image` wallpaper for 15 seconds did
not release the accumulated Plasma Shell charge; Konway was restored with
its existing settings. This test does not exclude accumulation triggered by
the animated wallpaper, nor does it establish that it is the cause.

Restarting only `plasma-plasmashell.service` at 16:03 recovered approximately
1.3 GiB of available RAM. Its unevictable cgroup charge fell from 1,585 MB to
244 MB, and the service returned active with Konway selected. At 16:04:10 it
remained at 244 MB. Total exported DRM dma-buf sizes changed only from 4.27 to
4.20 GiB, so that metric should not be used as a proxy for the freed resident
memory. The short observation cannot establish a long-term leak rate or the
source of retained allocations. KWin was not restarted; no permanent wallpaper,
graphics or kernel setting was changed.

Installed Mesa is `1:26.3.0.r20261026.f2c9dc3-5`, which includes the local
attachment lifetime candidate discussed in `kwin-submit-investigation.md`;
its possible memory effect is unmeasured. KDE's [debugging guidance](https://community.kde.org/Plasma/Debugging)
recommends isolating individual widgets when investigating shell memory growth.
Searches of Aurora, Asahi/Mesa and KDE did not identify a confirmed upstream fix
for this exact behavior; direct Aurora PR listings were unavailable, so the
upstream review is incomplete. A controlled longer comparison of a fresh shell
with Konway and a static wallpaper, then (if needed) Mesa package revisions, is
required before proposing a persistent workaround or code change.
