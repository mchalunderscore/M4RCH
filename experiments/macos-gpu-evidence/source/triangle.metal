#include <metal_stdlib>
using namespace metal;
vertex float4 vertex_main(uint id [[vertex_id]]) {
    const float2 positions[3] = {float2(-0.75, -0.75), float2(0.75, -0.75), float2(0.0, 0.75)};
    return float4(positions[id], 0.0, 1.0);
}
fragment float4 fragment_main() { return float4(1.0, 0.25, 0.0, 1.0); }
