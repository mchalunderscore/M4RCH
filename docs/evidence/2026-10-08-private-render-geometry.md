# Ordinary native G16 render geometry

AGX353.14 / Apple25G83, private-derived offline evidence. No GPU access.
Binary/range hashes and exact qualifications are in the adjacent JSON.

The full ordinary halComputeGeometry function89e5e04..89e63b8 executes in
Unicorn. All bytes in a400-byte source object match an independent numeric model
in1024 cases. Width/height1..16384, samples1/2/4, utiles16/32, q3c1..3 and
q981..4 are covered. The latter fields are labeled numerically until their
caller/topology meaning is independently qualified; neither fixture is live
T6040 topology evidence. A synthetic virtual1050 result1..4 and a nonzero
accelerator11188 memory-size field exclude fallback provider1028. PAC bypassed.

Tiles are ceil(width/32),ceil(height/32). Rounded macrotile factors are
(ceil(tiles/4)+3)&~3. With mx,my and ux/uy=2 for16-pixel utiles, otherwise1,
object18=5*mx*my*ux*uy/4 and object28=2*mx*my*ux*uy.
Object10 is q98*16*5*mx*my*ux*uy; object140 additionally depends on
accelerator4e4 and its separate numeric formula. Source pixel-size100, tile-screen
104/114, macro factors108/10c, sample-control and merge floats are checked.
Some adjacent fields are intentionally retained from the original object;
this geometry helper does not initialize an entire render target.

Another1024 cases pass the native result through the full native target loader,
including three independent synthetic mapping results. Segment-control helper
89e6400..6478 is compared in1024 cases, including provider-derived masks and
unsigned subtractions. Dynamic-min helper6478..6488 merely copies its supplied
x2 to two output addresses; it does not derive a new size. G16X default minimum
89e8204..823c passes1024 numeric cases but still requires genuine topology inputs.

Reproduce:

```sh
python experiments/t6040-gpu/audit-private-render-geometry.py \
 /boot/GPUC003/private-apple/com.apple.AGXG16X NEW_RECEIPT.json
```

No allocation lifetime, complete parameter-manager initialization, hardware
mapping or render validity is established by these numeric tests.
