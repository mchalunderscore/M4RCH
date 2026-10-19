// SPDX-License-Identifier: GPL-2.0-only
//! Typed per-phase providers for the source-translated native RCE builder.
//! Ordinary first-render policy is explicit: optional draw overrides, external
//! stamp branches and textured sampling are disabled, not silently unbound.
use super::g16_render::Parameters;
use super::g16_t6040_descriptor_v10::{self as fields,UserAddresses};
#[derive(Clone,Copy)] pub(crate) enum Phase { Tiling,Fragment }
#[derive(Clone,Copy)] pub(crate) struct Policy {
    /// True permits copying the caller's preencoded lifecycle low word into
    /// native construction backing. This is an explicit Linux experiment.
    pub(crate) experimental_linux_lifecycle: bool,
    /// Source-native scene record's first word. Caller owns leased scene.
    pub(crate) scene_header: u64,
    pub(crate) context_special_mode: bool,
    pub(crate) tiling_initial_barrier: bool,
    pub(crate) suppress_ta_timestamps: bool,
    pub(crate) suppress_fragment_timestamps: bool,
    /// Raw source policy bits; the controller's native SKU writer consumes them.
    pub(crate) descriptor_113b: u8,
    pub(crate) descriptor_1141: u8,
    pub(crate) descriptor_1142: u8,
}
pub(crate) struct Inputs {
    pub(crate) descriptor:[u8;0x1800],
    pub(crate) command:[u8;0x3000],
    pub(crate) context:[u8;0x100],
    pub(crate) scene:[u8;0x100],
    /// Native map158 callback for the status resource. It is not a PM pointer.
    pub(crate) status_resource_gpu:u64,
}
fn w(out:&mut [u8],o:usize,v:u64)->Option<()> {
    let v=u32::try_from(v).ok()?;out[o..o+4].copy_from_slice(&v.to_le_bytes());Some(())
}
fn q(out:&mut [u8],o:usize,v:u64){out[o..o+8].copy_from_slice(&v.to_le_bytes());}
fn gate_word(encoded:u64)->Option<u32> {
    if encoded as u32 !=0x00400020 {return None;}
    let upper=(encoded>>32) as u32;
    // Native zero means the default 0x60 upper word, so explicit zero cannot
    // represent another gate value. Preserve semantic equality on conversion.
    (upper!=0).then_some(upper)
}
/// Full known first-render RCE inputs. Fields unsupported by this restricted
/// policy fail before publication. Native SKU/PM binding remains caller-owned.
pub(crate) fn prepare_into(descriptor:&mut [u8;0x1800],command:&mut [u8;0x3000],
    context:&mut [u8;0x100],scene:&mut [u8;0x100],
    p:&Parameters,ta:&UserAddresses,phase:Phase,policy:Policy)->Option<u64> {
    if !policy.experimental_linux_lifecycle || policy.context_special_mode
        || p.sampler_array!=0 || p.sampler_count!=0
        || policy.descriptor_113b>1 || policy.descriptor_1141>1 || policy.descriptor_1142>1
        || p.cycle&15!=0 || p.scene_slot>=36 {return None;}
    let (lifecycle,stamp,status,admission,gate)=match phase {
        Phase::Tiling=>(p.tiling_lifecycle,p.tiling_work_stamp,p.ta_status,p.tiling_admission,p.tiling_gate),
        Phase::Fragment=>(p.fragment_lifecycle,p.fragment_work_stamp,p.fragment_status,p.fragment_admission,p.fragment_gate),
    };
    // Native packs six context bits and a descriptor u32 shifted by eight.
    // Bits6/7 cannot be represented by that source expression.
    if stamp&0xc0!=0 || stamp>u32::MAX as u64 || status==0
        || status&63!=0 || status&!0x7ffffffffc0!=0 {return None;}
    fields::build_into(descriptor,p,ta)?;
    command.fill(0);context.fill(0);scene.fill(0);
    w(context,8,stamp&0x3f)?;
    q(scene,0,policy.scene_header);q(scene,0x28,p.cycle);
    w(descriptor,0x86c,lifecycle>>32)?;
    match phase {
        Phase::Tiling=>{
            w(command,0x8ce,lifecycle&0xffff_ffff)?;
            w(descriptor,0x1274,stamp>>8)?;
            w(descriptor,0x1218,admission)?;
            q(descriptor,0x1128,u64::from(gate_word(gate)?));
            w(descriptor,0x13f8,p.completion_control)?;
            w(descriptor,0x1430,status&0x3fff)?;
        },
        Phase::Fragment=>{
            w(command,0x2168,lifecycle&0xffff_ffff)?;
            w(descriptor,0x144,stamp>>8)?;
            w(descriptor,0x900,admission)?;
            q(descriptor,0x7f0,u64::from(gate_word(gate)?));
            w(descriptor,0xb60,p.completion_control)?;
            w(descriptor,0xb98,status&0x3fff)?;
        }
    }
    descriptor[0x1558]=u8::from(policy.tiling_initial_barrier);
    descriptor[0x1138]=u8::from(policy.suppress_ta_timestamps);
    descriptor[0x893]=u8::from(policy.suppress_fragment_timestamps);
    descriptor[0x113b]=policy.descriptor_113b;
    descriptor[0x1141]=policy.descriptor_1141;
    descriptor[0x1142]=policy.descriptor_1142;
    descriptor[0x88c]=u8::from(p.process_empty_tiles);
    // Ordinary single-sample phase flags are explicit Linux policy; bool
    // request_tvb_growth/fragment_sync_grow/VDM dependency are SKU bindings,
    // not fabricated register inverses here. No sampler work is accepted.
    Some(status&!0x3fff)
}

/// Host convenience wrapper; same borrowed implementation as kernel runtime.
pub(crate) fn prepare(p:&Parameters,ta:&UserAddresses,phase:Phase,policy:Policy)->Option<Inputs> {
    let mut out=Inputs{descriptor:[0;0x1800],command:[0;0x3000],context:[0;0x100],scene:[0;0x100],status_resource_gpu:0};
    out.status_resource_gpu=prepare_into(&mut out.descriptor,&mut out.command,&mut out.context,&mut out.scene,p,ta,phase,policy)?;
    Some(out)
}
