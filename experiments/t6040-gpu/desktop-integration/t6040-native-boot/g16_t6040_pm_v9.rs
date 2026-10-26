// SPDX-License-Identifier: GPL-2.0-only
//! Native PM/HWPB wire owners; never copy exported research fixture bytes.
//! Caller retains and aliases every Resource through its actual Linux VM owner.
//! Numeric producers:89fc740..89fd040,89fefb0..89ff3a4,89fb720..89fb8f4,
//! 89fea44..89feafc,89fb414..89fb658; final PM binding8a225bc..8a225cc.

#[derive(Clone, Copy, Debug)]
pub(crate) struct Resource {
    pub device: u64,
    pub user: u64,
    pub firmware: u64,
    pub bytes: usize,
}
impl Resource {
    fn at(&self, offset: usize, width: usize) -> Option<(u64, u64, u64)> {
        if self.device == 0
            || self.user == 0
            || self.firmware == 0
            || offset.checked_add(width)? > self.bytes
        {
            return None;
        }
        Some((
            self.device.checked_add(offset as u64)?,
            self.user.checked_add(offset as u64)?,
            self.firmware.checked_add(offset as u64)?,
        ))
    }
}
/// These are different retained resources, except aliases of each resource's
/// same physical backing. Never treat host CPU pointers as one of these views.
#[derive(Clone, Copy, Debug)]
pub(crate) struct OwnedRoles {
    pub hw_state: Resource,
    pub counter: Resource,
    pub config: Resource,
    pub aux: Resource,
    pub scenes: Resource,
    pub block_frames: Resource,
    pub page_list: Resource,
    pub discard: Resource,
    pub scene_payload: Resource,
    pub pool_a: Resource,
    pub pool_b: Resource,
}
#[derive(Clone, Copy, Debug)]
pub(crate) struct Geometry {
    pub scene_count: u32,
    pub state_count: u32,
    pub capacity: u32,
    pub initial_blocks: u32,
    pub page_factor: u32,
    pub registration_stride: u64,
    pub scene_stride: u64,
    pub extra_scene_stride: bool,
    pub parameter_field_1d4: u32,
    pub native_count_154: u32,
    pub native_count_15c: u32,
    pub support_count: u32,
}
#[derive(Clone, Copy, Debug)]
pub(crate) struct SceneBudget {
    pub memory_bytes: u64,
    pub divisor_units: u64,
    pub fixed_bytes: u64,
    pub bytes_per_unit: u64,
    pub alignment: u64,
    pub groups: u32,
    pub group_shift: u32,
    pub group_allowance: bool,
}
impl SceneBudget {
    /// 89ff* rounds memory in32KiB units, adds the native optional group
    /// allowance, then aligns the scene payload stride. Checked Linux policy
    /// refuses overflow rather than adopting native wraparound at huge sizes.
    pub(crate) fn stride(self) -> Option<u64> {
        if self.divisor_units == 0 || !self.alignment.is_power_of_two() {
            return None;
        }
        let mut units = (self.memory_bytes.checked_add(0x7fff)? >> 15)
            .checked_add(self.divisor_units - 1)?
            / self.divisor_units;
        if self.groups >= 2 && self.group_allowance {
            let extra = self
                .groups
                .checked_add(self.groups.checked_shl(self.group_shift & 31)?)?;
            units = units.checked_add(u64::from(extra))?;
        }
        let value = self
            .fixed_bytes
            .checked_add(self.bytes_per_unit.checked_mul(units)?)?;
        Some(value.checked_add(self.alignment - 1)? & !(self.alignment - 1))
    }
}
#[derive(Clone, Copy, Debug)]
pub(crate) struct Extents {
    pub aux: usize,
    pub scenes: usize,
    pub block_frames: usize,
    pub page_list: usize,
    pub scene_payload: usize,
    pub registration_pool: usize,
}
impl Geometry {
    pub(crate) fn extents(self) -> Option<Extents> {
        if self.scene_count == 0
            || self.scene_count > 64
            || self.state_count == 0
            || self.capacity < 2
            || self.initial_blocks == 0
            || self.initial_blocks >= self.capacity
            || self.page_factor != 4
            || self.scene_stride == 0
            || self.scene_stride & 3 != 0
            || self.registration_stride < 4
            || !self.registration_stride.is_power_of_two()
            || self.native_count_154 > u32::MAX / 4
            || self.native_count_15c > u32::MAX / 4
        {
            return None;
        }
        let n = self.scene_count as usize;
        let c = self.capacity as usize;
        let scene_stride = usize::try_from(self.scene_stride).ok()?;
        let states =
            (self.state_count as usize).checked_add(usize::from(self.extra_scene_stride))?;
        Some(Extents {
            aux: n.checked_mul(0x80)?.checked_add(0x40)?,
            scenes: n.checked_mul(0x80)?,
            block_frames: c.checked_mul(8)?,
            page_list: c.checked_mul(self.page_factor as usize)?.checked_mul(4)?,
            scene_payload: scene_stride.checked_mul(states)?,
            registration_pool: n.checked_mul(usize::try_from(self.registration_stride).ok()?)?,
        })
    }
}
fn q(b: &mut [u8], o: usize, v: u64) {
    b[o..o + 8].copy_from_slice(&v.to_le_bytes());
}
fn w(b: &mut [u8], o: usize, v: u32) {
    b[o..o + 4].copy_from_slice(&v.to_le_bytes());
}
/// Borrowed buffers are fresh owned RAM; initialize all logical bytes before
/// publication. Unused/tail allocation bytes remain the caller's responsibility.
pub(crate) struct Images<'a> {
    pub hw_state: &'a mut [u8],
    pub counter: &'a mut [u8],
    pub config: &'a mut [u8],
    pub aux: &'a mut [u8],
    pub scenes: &'a mut [u8],
    pub block_frames: &'a mut [u8],
    pub page_list: &'a mut [u8],
}
#[derive(Clone, Copy, Debug)]
pub(crate) struct SceneViews {
    pub firmware_state: u64,
    pub counter_device: u64,
    pub counter_firmware: u64,
    pub record_user: u64,
    pub record_firmware: u64,
    pub aux_user: u64,
    pub aux_firmware: u64,
    pub aux_end_user: u64,
    pub aux_end_firmware: u64,
    pub header: u64,
    pub payload_device: u64,
}
impl OwnedRoles {
    fn valid(self, g: Geometry) -> Option<Extents> {
        let e = g.extents()?;
        for (r, n) in [
            (self.hw_state, 0xc0),
            (self.counter, 4),
            (self.config, 0x80),
            (self.aux, e.aux),
            (self.scenes, e.scenes),
            (self.block_frames, e.block_frames),
            (self.page_list, e.page_list),
            (self.discard, 0x8000),
            (self.scene_payload, e.scene_payload),
            (self.pool_a, e.registration_pool),
            (self.pool_b, e.registration_pool),
        ] {
            r.at(0, n)?;
        }
        // Logical resources may share larger allocations, but their logical
        // byte intervals must be disjoint in all three address domains.
        let roles = [
            (self.hw_state, 0xc0),
            (self.counter, 4),
            (self.config, 0x80),
            (self.aux, e.aux),
            (self.scenes, e.scenes),
            (self.block_frames, e.block_frames),
            (self.page_list, e.page_list),
            (self.discard, 0x8000),
            (self.scene_payload, e.scene_payload),
            (self.pool_a, e.registration_pool),
            (self.pool_b, e.registration_pool),
        ];
        for i in 0..roles.len() {
            for j in i + 1..roles.len() {
                let (a, n) = roles[i];
                let (b, m) = roles[j];
                for (x, y) in [
                    (a.device, b.device),
                    (a.user, b.user),
                    (a.firmware, b.firmware),
                ] {
                    if !(x.checked_add(n as u64)? <= y || y.checked_add(m as u64)? <= x) {
                        return None;
                    }
                }
            }
        }
        Some(e)
    }
    pub(crate) fn scene(self, g: Geometry, index: u32) -> Option<SceneViews> {
        self.valid(g)?;
        if index >= g.scene_count {
            return None;
        }
        let off = (index as usize).checked_mul(0x80)?;
        let (_, record_user, record_firmware) = self.scenes.at(off, 0x80)?;
        let (_, aux_user, aux_firmware) = self.aux.at(off, 0x80)?;
        let (_, aux_end_user, aux_end_firmware) =
            self.aux.at(g.scene_count as usize * 0x80, 0x40)?;
        let pooloff = (u64::from(index)).checked_mul(g.registration_stride)?;
        let header = self.pool_a.firmware.checked_add(pooloff)?;
        let payload_device = self.scene_payload.device.checked_add(
            g.scene_stride
                .checked_mul(u64::from(index % g.state_count))?,
        )?;
        Some(SceneViews {
            firmware_state: self.hw_state.firmware,
            counter_device: self.counter.device,
            counter_firmware: self.counter.firmware,
            record_user,
            record_firmware,
            aux_user,
            aux_firmware,
            aux_end_user,
            aux_end_firmware,
            header,
            payload_device,
        })
    }
}
/// Native reset plus initial concrete block/page preparation. Input blocks are
/// fresh actual device mappings returned by the retained Linux block allocator,
/// not CONTEXT_BASE-relative donor frame numbers. Native address25-bit clamp
/// is source-proven89fea*; Linux rejects mappings that lose address bits.
pub(crate) fn initialize(
    g: Geometry,
    r: OwnedRoles,
    blocks: &[u64],
    out: &mut Images<'_>,
) -> Option<()> {
    let e = r.valid(g)?;
    if blocks.len() != g.initial_blocks as usize
        || out.hw_state.len() != 0xc0
        || out.counter.len() != 4
        || out.config.len() != 0x80
        || out.aux.len() != e.aux
        || out.scenes.len() != e.scenes
        || out.block_frames.len() != e.block_frames
        || out.page_list.len() != e.page_list
    {
        return None;
    }
    for &a in blocks {
        if a == 0 || a & 0x7fff != 0 || a.checked_add(0x20000)? > 1u64 << 40 {
            return None;
        }
    }
    out.hw_state.fill(0);
    out.counter.fill(0);
    out.config.fill(0);
    out.aux.fill(0);
    out.scenes.fill(0);
    out.block_frames.fill(0);
    out.page_list.fill(0);
    // Concrete creator advances config0 once per retained block. Config8 is
    // completed0 and one ring slot stays free. Native reset sets config60=1.
    w(out.config, 0, g.initial_blocks);
    w(out.config, 0x60, 1);
    let s = &mut *out.hw_state;
    w(s, 0x10, g.parameter_field_1d4);
    q(s, 0x20, r.page_list.firmware);
    q(s, 0x28, r.page_list.device);
    w(s, 0x30, g.support_count);
    w(s, 0x38, g.capacity);
    q(s, 0x44, r.block_frames.firmware);
    q(s, 0x4c, r.config.firmware);
    w(s, 0x54, u32::MAX);
    w(s, 0x58, 0x20000);
    q(s, 0x64, r.counter.firmware);
    w(s, 0x7c, g.native_count_15c * 4);
    w(s, 0x80, g.native_count_154 * 4);
    q(s, 0x84, r.discard.device);
    // Actual builder89fb414: capacity factor and staged/completed cursors.
    let page_count = g.initial_blocks.checked_mul(g.page_factor)?;
    w(s, 0x34, page_count);
    w(s, 0x54, page_count - 1);
    w(s, 0x3c, g.initial_blocks);
    w(s, 0x40, 0);
    for (i, &a) in blocks.iter().enumerate() {
        let frame = u32::try_from(a >> 15).ok()?;
        w(out.block_frames, i * 8, frame);
        for j in 0..4 {
            w(out.page_list, (i * 4 + j) * 4, frame.checked_add(j as u32)?);
        }
    }
    for index in 0..g.scene_count {
        let v = r.scene(g, index)?;
        let off = index as usize * 0x80;
        q(out.scenes, off, v.header);
        q(
            out.scenes,
            off + 8,
            r.pool_b
                .firmware
                .checked_add(u64::from(index).checked_mul(g.registration_stride)?)?,
        );
        q(out.scenes, off + 0x28, v.payload_device);
        q(out.scenes, off + 0x40, r.config.device.checked_add(0x40)?);
        if g.extra_scene_stride {
            q(
                out.scenes,
                off + 0x30,
                r.scene_payload
                    .device
                    .checked_add(g.scene_stride.checked_mul(u64::from(g.state_count))?)?,
            );
        }
    }
    Some(())
}
/// Actual final caller8a225bc..cc binds manager58's mappedHWstate to1220/908.
/// Actual PM vectorA andaux-end feed1228/1250 and910/938. Firmware translation
/// maps those USER addresses to these aliases of the identical Linux backing.
pub(crate) fn bind_descriptor(
    d: &mut [u8; 0x1800],
    g: Geometry,
    r: OwnedRoles,
    index: u32,
) -> Option<SceneViews> {
    let v = r.scene(g, index)?;
    for (o, a) in [
        (0x1220, r.hw_state.user),
        (0x908, r.hw_state.user),
        (0x1228, v.aux_user),
        (0x910, v.aux_user),
        (0x1230, v.record_user),
        (0x918, v.record_user),
        (0x1250, v.aux_end_user),
        (0x938, v.aux_end_user),
    ] {
        q(d, o, a);
    }
    w(d, 0x1258, g.parameter_field_1d4);
    w(d, 0x948, g.parameter_field_1d4);
    w(d, 0x1268, index);
    // descriptor940 is the native HOST counterCPU pointer; never serialize a
    // fake GPU substitute. Linux tracks that PM-operation count in Tvb state.
    Some(v)
}
pub(crate) fn translations(v: SceneViews) -> [u64; 3] {
    [v.firmware_state, v.aux_firmware, v.aux_end_firmware]
}

/// Allocation geometry only: every role gets its own16KiB-aligned subrange.
/// Padding is fresh zeroed Linux backing; logical resource sizes stay native.
#[derive(Clone, Copy, Debug)]
pub(crate) struct PlannedRole {
    pub offset: usize,
    pub logical_bytes: usize,
    pub mapped_bytes: usize,
}
#[derive(Clone, Copy, Debug)]
pub(crate) struct AllocationPlan {
    pub roles: [PlannedRole; 11],
    pub mapped_bytes: usize,
}
impl AllocationPlan {
    pub(crate) fn new(g: Geometry) -> Option<Self> {
        let e = g.extents()?;
        let sizes = [
            0xc0,
            4,
            0x80,
            e.aux,
            e.scenes,
            e.block_frames,
            e.page_list,
            0x8000,
            e.scene_payload,
            e.registration_pool,
            e.registration_pool,
        ];
        let mut roles = [PlannedRole {
            offset: 0,
            logical_bytes: 0,
            mapped_bytes: 0,
        }; 11];
        let mut offset = 0usize;
        for (i, n) in sizes.into_iter().enumerate() {
            let mapped = n.checked_add(0x3fff)? & !0x3fff;
            roles[i] = PlannedRole {
                offset,
                logical_bytes: n,
                mapped_bytes: mapped,
            };
            offset = offset.checked_add(mapped)?;
        }
        Some(Self {
            roles,
            mapped_bytes: offset,
        })
    }
    pub(crate) fn views(
        self,
        firmware_base: u64,
        device_base: u64,
        user_base: u64,
    ) -> Option<OwnedRoles> {
        if firmware_base == 0
            || device_base == 0
            || user_base == 0
            || (firmware_base | device_base | user_base) & 0x3fff != 0
        {
            return None;
        }
        firmware_base.checked_add(self.mapped_bytes as u64)?;
        device_base.checked_add(self.mapped_bytes as u64)?;
        user_base.checked_add(self.mapped_bytes as u64)?;
        let r = |i: usize| {
            let p = self.roles[i];
            Resource {
                device: device_base + p.offset as u64,
                user: user_base + p.offset as u64,
                firmware: firmware_base + p.offset as u64,
                bytes: p.logical_bytes,
            }
        };
        Some(OwnedRoles {
            hw_state: r(0),
            counter: r(1),
            config: r(2),
            aux: r(3),
            scenes: r(4),
            block_frames: r(5),
            page_list: r(6),
            discard: r(7),
            scene_payload: r(8),
            pool_a: r(9),
            pool_b: r(10),
        })
    }
}
