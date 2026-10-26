# Native descriptor and provider integration

The actual kernel-facing implementation is `g16_t6040_descriptor_v10.rs` plus `g16_t6040_descriptor_provider_v9.rs`. Use `prepare_into` with retained KVec-backed arrays; it does not allocate an 18 KiB temporary on the kernel stack. The host `prepare` wrapper calls the same borrowed implementation.

Qualification is `out/gpu-gravity-native-descriptor-provider-v9-v3/named-qualification.json`: compiled/run0; 40 varied renders, 80 native semantic producer executions, 2,280 exact named-register comparisons, 80 borrowed writer output comparisons, 360 refusals. Original descriptor/control field observations are targeted actual native execution in `out/gpu-gravity-native-descriptor-policy-v9/dependency-trace.json`. Arithmetic/provider source comparison to actual native producer instructions is inherited from the prior 96-case native RCE qualification; this new test does not repeat that audit.

## Actual per-phase bindings

| Value | TA source | Fragment source |
|---|---|---|
| admission | descriptor u32 1218 | descriptor u32 900 |
| cycle | scene u64 28, low4 masked | same |
| gate | descriptor u64 1128 low32 -> register high32, low00400020 | descriptor u64 7f0 same |
| lifecycle high32 | descriptor u32 86c | same |
| lifecycle low32 | command u32 8ce | command u32 2168 |
| work stamp | context u32 8 low6 OR descriptor u32 1274 <<8 | context low6 OR descriptor u32 144 <<8 |
| completion control | descriptor u32 13f8 | descriptor u32 b60 |
| status | map158 status page base + descriptor u32 1430; mask7ffffffffc0 OR1 | map158 status page base + descriptor u32 b98, same mask/bit |

`Providers.parameter_gpu` is the mapped status-resource base for that phase. It is not a generic parameter-manager GPU pointer. Each phase may supply a different status mapping. CPU-only lookups are bounded immutable provider buffers, not published GPU addresses.

The scene header is an explicitly supplied leased native scene provider word; no donor scene-index inverse is invented. Workstamp bits6/7 cannot be represented and are refused. Gate lowword must match00400020; native zero selector means highword60, so an explicit zero highword is refused. Status addresses must fit the native mask and be64-byte aligned.

## Address correction

The earlier v9 partial report inferred a global firmware alias from resource getter slot160. That inference was wrong. The actual IOGPU base getter tailcalls slot158; Secure/Legacy subclasses optionally subtract the owning aperture base. Root qualified the concrete converter in `g16_t6040_resource_address_v9.rs` with128 actual native cases. New `UserAddresses::from_mappings` consumes `Address.user`; fragment consumes `Address.device`. Do not allocate global firmware aliases on the basis of the previous report. The caller must bind the actual retained owning mapping/aperture.

## Explicit experimental policy and caller boundary

Lifecycle lowword copies the existing Linux preencoded lifecycle policy only when `experimental_linux_lifecycle=true`; the native field combination is proven, but those donor lowword policy values are not claimed to be Apple's initialized construction policy. Native scene header, initial barrier, timestamp suppress flags and raw113b/1141/1142 bits are explicit caller inputs. Unknown textured sampling and special context mode refuse before publication. `process_empty_tiles` maps to native descriptor88c; generic raw PPP/sample/tile controls cannot be inverted merely from a matching register identity.

The controller's SKU writer remains responsible for VDM dependency/barrier, TVB growth, fragment synchronization, sampler/sample-size construction and native optional flags. Nonzero sampler inputs currently refuse. Arbitrary donor `ppp_control` requires a native typed policy conversion; it must not be described as automatically preserved by this builder. Main/partial pipeline addresses are mapped from the saved common/processRenderSetup copier contracts, but enabling partial phases remains a SKU/controller decision.

The code is ready for a concrete caller join and module compile. No firmware/GPU acceptance or complete normal startup is established, and frozen v8/v24 stages were not changed.

## Ordinary Mesa policy follow-up (v10)

Use `g16_t6040_descriptor_provider_v10.rs` and `g16_t6040_render_policy_v9.rs` for the current caller join. The previous assertion that PPP had no proven inverse is superseded for ordinary Mesa modes. Source-native TA PPP is `(113a.lowbit ? 600e : 2) | 1140.lowbit | ((accelerator6d0 >>7)&200)` for the accepted ordinary context. Mesa `CR PPP Control` defines OpenGL bit0, W-clamp bit1, default-point-size bit8, fixed-point-format bit9; the saved Vulkan caller explicitly chooses W-clamp and fixed-point-format, yielding202. Ordinary2/3/202/203 convert to113a=0,1140=OpenGL and explicit native provider `ppp_bit9`. Disabled W-clamp and bit8 have no ordinary native encoding and refuse. The native RCE provider admits only two explicit accelerator flags, bit47 and bit16; it does not admit arbitrary flag words.

`required_ppp_bit9(params)` returns the fixed-point provider requirement. The caller must validate it against its device policy and set `Providers.ppp_bit9`; preparation and execution must agree. The provider expansion is compared against96 actual native executions in `out/gpu-gravity-native-rce-typed-v9-qualification-v2`.

Mesa sample_size_B is padded to8 bytes; Gravity computes TIB blocks as ceil(sample_size * utile_width * utile_height * samples /2048). The typed ordinary converter rederives this with checked arithmetic, refuses mismatch or more than64 blocks, and writes the native common field740. It preserves the existing sample/bank encoding, qualified against native register10051. Tile-config must equal280 plus layered bit0 and process-empty bit16. The primary native process-empty source is descriptor88d bit0 (not88c); this correction is qualified against register10039. Separate partial-phase88e/88f remain with the controller.

Current bounded policy qualification is `out/gpu-gravity-native-descriptor-provider-v10-qualification-v4/named-qualification.json`. It exercises40 varied renders,80 producer runs,2,400 named register checks,80 borrowed whole-output checks and600 refusals. Nonzero samplers remain an explicit ordinary-first-draw restriction. Full native caller/SKU integration and live rendering are separate claims.

Connected lifecycle correction: prepare_into seeds descriptor e10 (TA) and100 (fragment) as well as command8ce/2168. The native envelope copies these descriptor fields over the command seed; RCE does not populate them. Correct ordering is prepare_into→RCE→envelope→SKU. The v4 qualifier runs RCE→envelope and verifies all2,400 register expectations plus80 exact lifecycle-lowword preservation checks. Descriptor/provider v10 is the current integration source.
