#!/usr/bin/env python3
"""Join native shared RAM/channel ownership, queue policy and power in Gravity.

This creates a distinct source stage from the frozen compiled v6. Source-bound
components are composed; their previous broad qualifications are never rerun.
The resulting normal-driver build is not an installed hardware candidate.
"""
import argparse
import json
from pathlib import Path
import re
import shutil

from stage_v4 import pin

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[3]


def change(files, name, before, after, count=1):
    text = files[name]
    if text.count(before) != count:
        raise ValueError('Integration insertion differs: ' + name + ': ' + before[:80])
    files[name] = text.replace(before, after)


def wiring(files):
    change(files, 'asahi_m4.rs', 'mod g16_t6040_power;\n',
           'mod g16_t6040_power;\nmod g16_t6040_shared;\nmod g16_t6040_queue;\nmod g16_t6040_qos;\nmod g16_transport;\nmod g16_queue_owner;\n')
    change(files, 'g16_fw.rs', 'pub(crate) struct RootPointers {',
           '#[derive(Clone, Copy)]\npub(crate) struct RootPointers {')
    change(files, 'g16_platform.rs', '    pub(crate) native_hardware: Option<crate::g16_t6040::Hardware>,',
           '    pub(crate) native_hardware: Option<crate::g16_t6040::Hardware>,\n    pub(crate) native_power: Option<crate::g16_t6040_power::PowerData>,')
    change(files, 'g16_platform.rs', '            native_hardware: None,',
           '            native_hardware: None, native_power: None,')
    change(files, 'g16_platform.rs', '''        let maximum_power: u32 = node.get_property(c_str!("apple,m4-max-power-mw"))?;
        if maximum_power == 0 || maximum_power > i32::MAX as u32 { return Err(EINVAL); }''',
           '''        // Native final maximum comes from the chip-fuse/voltage provider;
        // an artificial OF maximum is not accepted by this constructor.
        // Provider-independent power is constructed now; complete lifecycle
        // must receive the owned provider result before startup can open.
        let maximum_power = 0;''')
    change(files, 'g16_platform.rs', 'registers, mcc: KVec::new(), gpc, native_hardware: Some(native) })',
           'registers, mcc: KVec::new(), gpc, native_hardware: Some(native), native_power: Some(power) })')
    text = files['g16_platform.rs']
    start = text.index('    /// Original ADT raw period inputs,')
    stop = text.index('    fn build_registers(', start)
    properties = re.search(r'OPTIONAL_WORD_PROPERTIES:.*?= &\[(.*?)\];', files['g16_t6040_power.rs'], re.S)
    names = re.findall(r'"([^"]+)"', properties.group(1))
    names = ['perf-state-count', 'perf-state-table-count', 'perf-states'] + names
    body = ['    /// Consume exact original SGX byte aliases; the raw bridge retains absence.',
            '    fn native_power_inputs(node: &of::Node) -> Result<crate::g16_t6040_power::PowerData> {',
            '        let mut storage: KVec<(&str, KVec<u8>)> = KVec::new();',
            '        macro_rules! append { ($name:literal) => {',
            '            if let Some(raw) = node.get_opt_property::<KVec<u8>>(c_str!(concat!("apple,sgx-", $name)))? {',
            '                storage.push(($name, raw), GFP_KERNEL)?;',
            '            }',
            '        }; }']
    for name in names:
        if name == 'gpu-power-sample-period':
            body.append('        if !storage.iter().any(|(name, _)| *name == "gpu-pwr-sample-period-aic-clks") {')
            body.append('            append!("' + name + '");')
            body.append('        }')
        else:
            body.append('        append!("' + name + '");')
    body += ['        let mut properties: KVec<(&str, &[u8])> = KVec::new();',
             '        for (name, raw) in &storage { properties.push((*name, raw.as_slice()), GFP_KERNEL)?; }',
             '        crate::g16_t6040_power::PowerData::from_adt(&properties).ok_or(EINVAL)',
             '    }', '',
             '    pub(crate) fn sgx_physical(&self) -> Result<u64> {',
             '        let cells: KVec<u32> = self.node.get_property(c_str!("reg"))?;',
             '        if cells.len() != 8 { return Err(EINVAL); }',
             '        Ok((u64::from(cells[4]) << 32) | u64::from(cells[5]))',
             '    }', '']
    files['g16_platform.rs'] = text[:start] + '\n'.join(body) + '\n' + text[stop:]
    # Shared clearing and native channel pointers precede HW and power writers.
    change(files, 'g16_power.rs', '''        let mut out = zeroed(crate::g16_t6040_bundle::BACKING_BYTES)?;
        let hardware''', '''        let mut out = zeroed(crate::g16_t6040_bundle::BACKING_BYTES)?;
        let shared = crate::g16_t6040_shared::NativeTopology::new(
            layout.base(), 0xffff_fc20_0003_0000, crate::g16_fw::ROOT_ADDRESS,
            0xffff_fc20_0010_8000, 0xffff_fc20_000f_8000).ok_or(EINVAL)?;
        shared.write_bundle_component(&mut out).ok_or(EINVAL)?;
        let hardware''')
    change(files, 'g16_power.rs', '''        let power = crate::g16_t6040_power::PowerData {
            period_aic_clocks: self.period_clocks, period_ms: self.period_ms,
        };''', '''        let power = self.native_power.as_ref().ok_or(EINVAL)?;''')
    change(files, 'g16_power.rs', '''        layout.write_component(&mut out).ok_or(EINVAL)?;
        Ok(out)''', '''        // Native control storage is separate child22. Initial opcode16 is
        // published at this selected ring, never at donor Main+4c0.
        let control = crate::g16_t6040_bundle::CHILDREN[22];
        out[control.offset..control.offset + 4].copy_from_slice(&0x16u32.to_le_bytes());
        Ok(out)''')
    change(files, 'g16_vm.rs', '    pub(crate) fn read_u32(&self, va: u64) -> Result<u32> {',
           '''    /// Packed native counter read without creating an unaligned u32 reference.
    /// The selected counter stays within one cache line and one owned page.
    pub(crate) fn read_packed_u32(&self, va: u64) -> Result<u32> {
        if va & 63 > 60 { return Err(EINVAL); }
        let region = self.region(va, 4)?;
        let offset = (va - region.va) as usize;
        region.pages[offset / UAT_PGSZ].with_pointer_into_page(offset & (UAT_PGSZ - 1), 4, |p| {
            // SAFETY: Four byte reads stay in the verified owned allocation;
            // cache invalidation precedes them, with no alignment assumption.
            unsafe {
                core::arch::asm!("dc ivac, {addr}", "dsb sy", addr = in(reg) p);
                Ok(u32::from_le_bytes(core::array::from_fn(|i| p.add(i).read_volatile())))
            }
        })
    }

    pub(crate) fn read_u32(&self, va: u64) -> Result<u32> {''')
    change(files, 'g16.rs', '_sgx: Pin<KBox<Devres<IoMem<0x4000000>>>>,',
           '_sgx: Pin<KBox<Devres<IoMem<0x3758000>>>>,\n    transport: crate::g16_transport::Transport,')
    change(files, 'g16.rs', '.iomap_sized::<0x4000000>(),', '.iomap_sized::<0x3758000>(),')
    change(files, 'g16.rs', '''        let pointers = crate::g16_fw::RootPointers::bootstrap_for_platform(native_t6040)
            .ok_or(EINVAL)?;''', '''        let transport = crate::g16_transport::Transport::for_platform(native_t6040).ok_or(EINVAL)?;
        let pointers = transport.roots;
        let sgx_physical = platform.sgx_physical()?;''')
    change(files, 'g16.rs', '            _sgx: sgx,', '            _sgx: sgx, transport,')
    change(files, 'g16.rs', '''        firmware_space.write(
            crate::g16_fw::ROOT_ADDRESS,
            &pointers.encode(native_t6040),
        )?;''', '''        let root = if native_t6040 {
            let layout = crate::g16_t6040_shared::NativeTopology::new(
                crate::g16_fw::BUNDLE_ADDRESS, 0xffff_fc20_0003_0000,
                crate::g16_fw::ROOT_ADDRESS, pointers.region_a, pointers.region_c).ok_or(EINVAL)?;
            // Linux owns the actual 43-bit/16KiB UAT geometry. Transfer its
            // explicit payload to the native root writer, which never builds
            // its own donor descriptor. Mapping/cache policy remains a gate.
            let linux_root = pointers.encode(true);
            let payload: [u8; 104] = linux_root[0x30..0x98].try_into().map_err(|_| EINVAL)?;
            layout.root_pointers().encode(&payload)
        } else { pointers.encode(false) };
        firmware_space.write(crate::g16_fw::ROOT_ADDRESS, &root)?;''')
    change(files, 'g16.rs', '''        for va in [pointers.status_a, pointers.status_b] {
            firmware_space.write(va + 4, &1u32.to_le_bytes())?;
        }''', '''        if native_t6040 {
            let layout = crate::g16_t6040_shared::NativeTopology::new(
                crate::g16_fw::BUNDLE_ADDRESS, 0xffff_fc20_0003_0000,
                crate::g16_fw::ROOT_ADDRESS, pointers.region_a, pointers.region_c).ok_or(EINVAL)?;
            let mut support = crate::g16_platform::zeroed(crate::g16_t6040_shared::SUPPORT_BACKING_BYTES)?;
            // Explicit Linux active-session policy after successful RTKit boot;
            // native FW94c is dynamic, rather than a constructor constant.
            layout.write_support_component(&mut support, 3).ok_or(EINVAL)?;
            firmware_space.write(layout.support.base(), &support)?;
            let mut region_a = crate::g16_platform::zeroed(0x4000)?;
            crate::g16_t6040_shared::write_region_a_component(&mut region_a).ok_or(EINVAL)?;
            firmware_space.write(pointers.region_a, &region_a)?;
        } else {
            for va in [pointers.status_a, pointers.status_b] {
                firmware_space.write(va + 4, &1u32.to_le_bytes())?;
            }
        }''')
    start = files['g16.rs'].index('        // Work-channel cursor pages use shared attributes,')
    stop = files['g16.rs'].index('        for (va, size) in [', start)
    files['g16.rs'] = files['g16.rs'][:start] + '''        // Native work/control cursors are owned support RAM, already mapped.
        // Only the donor backend requires these two physical SGX cursor aliases.
        if !native_t6040 {
            firmware_space.map_external(0xffff_fc20_0002_0000,
                sgx_physical + 0xd60000, PAGE_SIZE as usize,
                crate::pgtable::prot::PROT_FW_SHARED_RO)?;
            firmware_space.map_external(0xffff_fc20_0002_8000,
                sgx_physical + 0xd64000, PAGE_SIZE as usize,
                crate::pgtable::prot::PROT_FW_SHARED_RW)?;
        }
''' + files['g16.rs'][stop:]
    change(files, 'g16.rs', '''        let main = crate::g16_fw::MainConfig::bootstrap(crate::g16_fw::BUNDLE_ADDRESS);
        for channel in &main.channels[..12] {
            for va in channel.state {
                let offset = if va >= 0xffff_fc20_0002_8000 {
                    0xd64000 + (va - 0xffff_fc20_0002_8000) as usize
                } else {
                    0xd60000 + (va - 0xffff_fc20_0002_0000) as usize
                };
                sgx.try_write32(0, offset)?;
                if sgx.try_read32(offset)? != 0 {
                    return Err(EIO);
                }
            }
        }
        // Slot zero (opcode 0x16) is already embedded in the main object.
        for (offset, value) in [(0xd640c0, 0), (0xd640c8, 0), (0xd60060, 1)] {
            sgx.try_write32(value, offset)?;
            if sgx.try_read32(offset)? != value {
                return Err(EIO);
            }
        }''', '''        let firmware_space = self._firmware_space.as_mut().ok_or(EINVAL)?;
        for channel in 0..12 {
            for ordinal in 0..3 {
                write_cursor(&self.transport, firmware_space, sgx, channel, ordinal, 0)?;
                if read_cursor(&self.transport, firmware_space, sgx, channel, ordinal)? != 0 { return Err(EIO); }
            }
        }
        // The selected native child22 owns slot0, independently of Main.
        for (ordinal, value) in [(0, 0), (1, 0), (2, 1)] {
            write_cursor(&self.transport, firmware_space, sgx, 12, ordinal, value)?;
            if read_cursor(&self.transport, firmware_space, sgx, 12, ordinal)? != value { return Err(EIO); }
        }''')
    # The original immutable FW-space reference in publish would overlap its
    # selected native cursor writes; reborrow after publication has completed.
    change(files, 'g16.rs', '        let firmware_space = self._firmware_space.as_ref().ok_or(EINVAL)?;\n        let res = dev',
           '        let res = dev')
    change(files, 'g16.rs', '        dev_info!(dev, "G16: published Linux-built initialization graph\\n");',
           '        let firmware_space = self._firmware_space.as_ref().ok_or(EINVAL)?;\n        dev_info!(dev, "G16: published Linux-built initialization graph\\n");')
    change(files, 'g16.rs', 'crate::g16_fw::RootPointers::bootstrap().status_a + 0x14',
           'self.transport.roots.status_a + 0x14')
    # Helpers only access verified selected cursor owners. Native writes do
    # not perform SGX writes; donor behavior still uses its selected aliases.
    files['g16.rs'] += '''
pub(super) fn read_cursor(transport: &crate::g16_transport::Transport,
    firmware: &crate::g16_vm::FirmwareSpace, sgx: &IoMem<0x3758000>,
    channel: usize, ordinal: usize) -> Result<u32> {
    if transport.native_t6040 {
        firmware.read_u32(transport.cursor(channel, ordinal).ok_or(EINVAL)?)
    } else {
        sgx.try_read32(transport.donor_sgx_cursor_offset(channel, ordinal).ok_or(EINVAL)?)
    }
}
pub(super) fn write_cursor(transport: &crate::g16_transport::Transport,
    firmware: &mut crate::g16_vm::FirmwareSpace, sgx: &IoMem<0x3758000>,
    channel: usize, ordinal: usize, value: u32) -> Result {
    if transport.native_t6040 {
        firmware.write_live(transport.cursor(channel, ordinal).ok_or(EINVAL)?, &value.to_le_bytes())
    } else {
        sgx.try_write32(value, transport.donor_sgx_cursor_offset(channel, ordinal).ok_or(EINVAL)?)
    }
}
/// One serialized native class assertion, after record copy/cache publication
/// and before producer publication. Assertion does not prove command processing.
pub(super) fn assert_control(transport: &crate::g16_transport::Transport,
    firmware: &mut crate::g16_vm::FirmwareSpace, opcode: u32) -> Result {
    if !transport.native_t6040 { return Ok(()); }
    if !crate::g16_transport::device_control_power_class(opcode).ok_or(ENOTSUPP)? { return Ok(()); }
    let address = transport.roots.region_c + 0xe51;
    let before = firmware.read_packed_u32(address)?;
    let after = before.wrapping_add(1);
    firmware.write_live(address, &after.to_le_bytes())?;
    crate::mem::sync();
    if firmware.read_packed_u32(address)? != after { return Err(EIO); }
    Ok(())
}
'''
    runtime(files)
    startup(files)
    queue_ownership(files)
    teardown(files)


def teardown(files):
    change(files, 'g16.rs', '''        if let Err(e) = self._rtkit.as_mut().shutdown() {''', '''        let shutdown = self._rtkit.as_mut().shutdown();
        if self.transport.native_t6040 || shutdown.is_err() {''')
    change(files, 'g16.rs', '''                "G16: shutdown failed {:?}; retaining GPU mappings\\n",
                e''', '''                "G16: shutdown {:?}; retaining mappings until GPU OFF retirement\\n",
                shutdown''')
    change(files, 'g16.rs', '''            core::mem::forget(self._opening_client.take());''', '''            core::mem::forget(self._opening_client.take());
            // Native ASC/RTKit stop is not GPU DMA retirement. Outstanding
            // client references, scratch and TVB leases must survive as well.
            core::mem::forget(core::mem::replace(&mut self.flights, KVec::new()));
            core::mem::forget(core::mem::replace(&mut self.tvb_pools, KVec::new()));''')


def queue_ownership(files):
    change(files, 'g16.rs', '    render_publication: u64,', '''    render_publication: u64,
    native_leases: crate::g16_queue_owner::LeasePool,
    native_qos_manager: crate::g16_t6040_qos::ManagerState,''')
    change(files, 'g16.rs', '            render_publication: *crate::module_parameters::fw_counter_start.value(),', '''            render_publication: *crate::module_parameters::fw_counter_start.value(),
            native_leases: crate::g16_queue_owner::LeasePool::new(),
            native_qos_manager: crate::g16_t6040_qos::ManagerState::new(),''')
    change(files, 'g16_drm.rs', '''                    // Firmware priority runs in the opposite direction:
                    // public low/medium select native classes 3/2.
                    kernel::new_mutex!(crate::g16::FirmwareQueues::new(3 - data.priority)),''', '''                    // Retain the actual creating process and public owner;
                    // the backend derives its native priority policy.
                    kernel::new_mutex!(crate::g16::FirmwareQueues::new(
                        data.priority, data.vm_id, id)),''')
    change(files, 'g16_runtime.rs', '    priority: u32,\n    events:', '''    priority: u32,
    public_priority: u32,
    task: kernel::sync::aref::ARef<kernel::task::Task>,
    vm_id: u32,
    queue_id: u32,
    allocation: Option<u64>,
    leases: Option<crate::g16_queue_owner::Leases>,
    qos: crate::g16_t6040_qos::QueueState,
    events:''')
    change(files, 'g16_runtime.rs', '''    pub(crate) fn new(priority: u32) -> Self {
        Self {
            lanes: None,
            priority,''', '''    pub(crate) fn new(public_priority: u32, vm_id: u32, queue_id: u32) -> Self {
        Self {
            lanes: None,
            priority: 3 - public_priority,
            public_priority,
            task: kernel::sync::aref::ARef::from(kernel::current!().group_leader()),
            vm_id, queue_id, allocation: None, leases: None,
            qos: crate::g16_t6040_qos::QueueState::new(),''')
    change(files, 'g16_runtime.rs', '''            let base = self.next_work_va;
            self.next_work_va = base.checked_add(0x24000).ok_or(ENOSPC)?;
            let lanes''', '''            let base = if let Some(base) = owner.allocation { base } else {
                let base = self.next_work_va;
                self.next_work_va = base.checked_add(0x24000).ok_or(ENOSPC)?;
                owner.allocation = Some(base);
                base
            };
            if self.transport.native_t6040 && owner.leases.is_none() {
                owner.leases = Some(self.native_leases.reserve_initial_owner(
                    crate::g16_queue_owner::Owner { allocation: base,
                        process_id: owner.task.pid() as u32,
                        vm_id: owner.vm_id, queue_id: owner.queue_id }).ok_or(EBUSY)?);
            }
            let lanes''')
    before = '''                let mut descriptor = q::Queue {
                    pointers: lane.pointers,
                    ring: lane.ring,
                    jobs,
                    private: lane.queue + 0xb0,
                    context,
                    uuid: ((lane.queue - 0xffff_fc22_0000_0000) >> 14) as u32 + 2,
                }
                .encode_priority(owner.priority)
                .ok_or(EINVAL)?;'''
    after = '''                let (mut descriptor, pointers) = if self.transport.native_t6040 {
                    let leases = owner.leases.ok_or(EIO)?;
                    let images = crate::g16_queue_owner::Inputs {
                        process_id: owner.task.pid() as u32,
                        public_priority: owner.public_priority,
                        pointers: lane.pointers, ring: lane.ring, timestamp_list: jobs,
                        scheduler: crate::g16_t6040_queue::SchedulerInputs {
                            firmware_slot: context, hardware_buffer_id: leases.hardware_buffer_id,
                            owner_byte_120: 2 }, capacity: 0x500, producer: 0,
                    }.images().ok_or(EINVAL)?;
                    if images.lane != owner.priority { return Err(EINVAL); }
                    fw.write(context, &images.scheduler)?;
                    (images.state, images.pointers)
                } else {
                    let donor = q::Queue { pointers: lane.pointers, ring: lane.ring, jobs,
                        private: lane.queue + 0xb0, context,
                        uuid: ((lane.queue - 0xffff_fc22_0000_0000) >> 14) as u32 + 2,
                    }.encode_priority(owner.priority).ok_or(EINVAL)?;
                    let mut state = [0; crate::g16_t6040_queue::STATE_BYTES];
                    state[..donor.len()].copy_from_slice(&donor);
                    let donor = q::pointers(0x500, 0);
                    let mut pointers = [0; crate::g16_t6040_queue::POINTER_MIN_BYTES];
                    pointers[..donor.len()].copy_from_slice(&donor);
                    (state, pointers)
                };'''
    change(files, 'g16_runtime.rs', before, after)
    change(files, 'g16_runtime.rs', '                if stage == 2 {\n                    descriptor[0x30..0x34]',
           '                if stage == 2 && !self.transport.native_t6040 {\n                    descriptor[0x30..0x34]')
    change(files, 'g16_runtime.rs', '                fw.write(lane.pointers, &q::pointers(0x500, 0))?;',
           '                fw.write(lane.pointers, &pointers)?;')
    change(files, 'g16_runtime.rs', '''                fw.alloc(lane.pointers, 0x8000, PROT_FW_SHARED_RW)?;''', '''                fw.alloc(lane.pointers, 0x8000, PROT_FW_SHARED_RW)?;
                if self.transport.native_t6040 {
                    // AGXKSMKickQueue+80/+88 are two task mappings of the
                    // same IOGPUSysMemory backing. Own that alias concretely.
                    let device_ring = 0x72_0000_0000 + (lane.ring - 0xffff_fc22_0000_0000);
                    let pa = fw.physical(lane.ring)?;
                    self._address_space.as_mut().ok_or(EIO)?.map_work_alias(device_ring, pa)?;
                }''')
    change(files, 'g16_runtime.rs', '            fw.write(context, &q::context())?;',
           '            if !self.transport.native_t6040 { fw.write(context, &q::context())?; }')
    # QoS RAM is its own owned page, not an alias into the support allocation.
    change(files, 'g16.rs', '''            0xffff_fc20_0012_8000,
            0xffff_fc20_0013_0000,''', '''            0xffff_fc20_0012_8000,
            0xffff_fc20_0012_c000,
            0xffff_fc20_0013_0000,''')
    change(files, 'g16.rs', '''        // Shared support version and read-only resume records also serve the''', '''        if native_t6040 {
            let mut qos = [0u8; crate::g16_t6040_qos::RESOURCE_BYTES];
            crate::g16_t6040_qos::write_initial(&mut qos).ok_or(EINVAL)?;
            firmware_space.write(crate::g16_queue_owner::QOS_GPU, &qos)?;
        }
        // Shared support version and read-only resume records also serve the''')
    # Use a real Linux raw monotonic clock through the explicit 24MHz policy.
    files['g16_runtime.rs'] += '''
impl Bootstrap {
    /// Joined native resource publication under the exclusive runtime owner.
    /// Firmware-visible bytes are read freshly before touching the exact native
    /// willSubmit fields; no unrelated firmware-owned bytes are rewritten.
    fn publish_native_qos(&mut self, owner: &mut FirmwareQueues, stages: &[usize]) -> Result {
        if !self.transport.native_t6040 { return Ok(()); }
        let leases = owner.leases.ok_or(EIO)?;
        let allocation = owner.allocation.ok_or(EIO)?;
        let fw = self._firmware_space.as_mut().ok_or(EIO)?;
        let base = crate::g16_queue_owner::QOS_GPU;
        let mut resource = [0u8; crate::g16_t6040_qos::RESOURCE_BYTES];
        for offset in (0..resource.len()).step_by(8) {
            resource[offset..offset + 8].copy_from_slice(&fw.read_u64(base + offset as u64)?.to_le_bytes());
        }
        // SAFETY: The kernel raw monotonic time service has no pointer inputs.
        let raw_ns = u64::try_from(unsafe { kernel::bindings::ktime_get_raw() }).map_err(|_| EINVAL)?;
        let native_ticks = u64::try_from(u128::from(raw_ns) * 24_000_000 / 1_000_000_000).map_err(|_| EINVAL)?;
        for &stage in stages {
            let previous = resource;
            owner.qos.write_submission(&mut self.native_qos_manager, &mut resource,
                crate::g16_t6040_qos::SubmissionInputs {
                    hardware_buffer_id: leases.hardware_buffer_id,
                    work_queue_id: leases.work_queue_id[stage], data_master: stage as u32,
                    scheduler_slot: allocation + 0x4140,
                    weight: crate::g16_queue_owner::initial_weight(owner.public_priority).ok_or(EINVAL)?,
                    share_ratio: 8192, native_ticks,
                }).ok_or(EINVAL)?;
            for offset in (0..resource.len()).step_by(4) {
                if resource[offset..offset + 4] != previous[offset..offset + 4] {
                    fw.write_live(base + offset as u64, &resource[offset..offset + 4])?;
                }
            }
        }
        crate::mem::sync();
        Ok(())
    }
}
'''
    change(files, 'g16_runtime.rs', '''        queue: &FirmwareQueues,
        initbm: bool,''', '''        queue: &mut FirmwareQueues,
        initbm: bool,''')
    change(files, 'g16_runtime.rs', '''        let priority = queue.priority;
        let lanes = queue.lanes.as_ref().ok_or(EIO)?;''', '''        self.publish_native_qos(queue, &[1, 0])?;
        let priority = queue.priority;
        let lanes = queue.lanes.as_ref().ok_or(EIO)?;''')
    change(files, 'g16_runtime.rs', '''        let channel = priority as usize * 3 + 2;
        let mut pending_lane''', '''        self.publish_native_qos(queue, &[2])?;
        let channel = priority as usize * 3 + 2;
        let mut pending_lane''')
    scheduler_config(files)
    experimental_startup(files)


def experimental_startup(files):
    change(files, 'asahi_m4.rs', '    params: {', '''    params: {
        native_t6040_experiment: u32 {
            default: 0,
            description: "Opt in to the source-built T6040 startup experiment; requires probe_only=0",
        },''')
    change(files, 'asahi_m4.rs', 'if !metadata.normal_startup_implemented && *module_parameters::probe_only.value() == 0 {',
           'if metadata.initialization().is_none() && *module_parameters::probe_only.value() == 0 {')
    change(files, 'g16_profile.rs', 'pub(crate) enum Initialization { T8132 }',
           'pub(crate) enum Initialization { T8132, T6040LinuxExperiment }')
    change(files, 'g16_profile.rs', '''        } else {
            None
        }
    }

    /// Do not substitute''', '''        } else if self.chip == 0x6040 && self.variant == Variant::S
            && self.register_bytes == 0x3758000
            && *crate::module_parameters::native_t6040_experiment.value() == 1 {
            Some(Initialization::T6040LinuxExperiment)
        } else {
            None
        }
    }

    /// Do not substitute''')
    change(files, 'g16.rs', '''        use crate::g16_fw::queue as q;
        firmware_space.write(BOOT_POINTERS''', '''        use crate::g16_fw::queue as q;
        if !native_t6040 {
        firmware_space.write(BOOT_POINTERS''')
    change(files, 'g16.rs', '''        firmware_space.sync();
        let mut opening_client''', '''        }
        firmware_space.sync();
        let mut opening_client''')
    change(files, 'g16.rs', '''        session.submit_barrier(pdev)?;''', '''        // Native initialization/ready must retire before any real public
        // queue config15/Work. The donor bootstrap Work is not a native input.
        if !native_t6040 { session.submit_barrier(pdev)?; }''')


def scheduler_config(files):
    # Admission reserves the first persistent config command as well as Work.
    change(files, 'g16_runtime.rs', '        entries: [u32; 3],', '        mut entries: [u32; 3],')
    change(files, 'g16_runtime.rs', '''        let stages: &[usize] = if render { &[0, 1] } else { &[2] };
        let config''', '''        let stages: &[usize] = if render { &[0, 1] } else { &[2] };
        if self.transport.native_t6040 {
            for &stage in stages {
                if queue.lanes.as_ref().is_none_or(|lanes| lanes[stage].new) { entries[stage] += 1; }
            }
        }
        let config''')
    # First command stays in the real queue allocation for its full lifetime.
    files['g16_runtime.rs'] += '''
impl Bootstrap {
    fn write_native_configuration(&mut self, owner: &FirmwareQueues, stage: usize,
                                  descriptor_id: u32) -> Result {
        if !self.transport.native_t6040 { return Ok(()); }
        let lanes = owner.lanes.as_ref().ok_or(EIO)?;
        let lane = lanes[stage];
        if !lane.new { return Ok(()); }
        let allocation = owner.allocation.ok_or(EIO)?;
        let leases = owner.leases.ok_or(EIO)?;
        let input = crate::g16_queue_owner::Inputs {
            process_id: owner.task.pid() as u32, public_priority: owner.public_priority,
            pointers: lane.pointers, ring: lane.ring, timestamp_list: allocation + 0x4100,
            scheduler: crate::g16_t6040_queue::SchedulerInputs {
                firmware_slot: allocation + 0x4140, hardware_buffer_id: leases.hardware_buffer_id,
                owner_byte_120: 2 }, capacity: 0x500, producer: lane.head,
        };
        let device_ring = 0x72_0000_0000 + (lane.ring - 0xffff_fc22_0000_0000);
        // Source-bound codec and aliases, explicit Linux graphics caller
        // transfer: flags0, task callback66=0. Native DM getter is exactly255.
        let command = input.configuration(device_ring, leases.work_queue_id[stage],
            descriptor_id, [0, 0], 0).ok_or(EINVAL)?;
        let fw = self._firmware_space.as_mut().ok_or(EIO)?;
        let address = lane.queue + 0x200;
        fw.write_live(address, &command)?;
        fw.write_live(lane.ring + u64::from(lane.head) * 8, &address.to_le_bytes())?;
        Ok(())
    }
}
'''
    change(files, 'g16_runtime.rs', '''        self.publish_native_qos(queue, &[1, 0])?;
        let priority''', '''        for stage in [1usize, 0] {
            self.write_native_configuration(queue, stage,
                if stage == 0 { a.tiling_uuid } else { a.fragment_uuid } as u32)?;
        }
        self.publish_native_qos(queue, &[1, 0])?;
        let priority''')
    change(files, 'g16_runtime.rs', '''        let firsts = [lanes[0].head, lanes[1].head];''', '''        let firsts = core::array::from_fn::<_, 2, _>(|stage|
            (lanes[stage].head + u32::from(self.transport.native_t6040 && lanes[stage].new)) % 0x500);''')
    change(files, 'g16_runtime.rs', '        let first = lane.head;', '''        self.write_native_configuration(queue, 2, a.identity as u32)?;
        let first = (lane.head + u32::from(self.transport.native_t6040 && lane.new)) % 0x500;''')


def runtime(files):
    change(files, 'g16_runtime.rs', 'let config = g16_fw::MainConfig::bootstrap(g16_fw::BUNDLE_ADDRESS);',
           'let config = self.transport;', count=4)
    change(files, 'g16_runtime.rs', 'g16_fw::MainConfig::bootstrap(g16_fw::BUNDLE_ADDRESS).channels[12].ring',
           'self.transport.channels[12].ring')
    # Admission and epoch reservation now read the selected cursor RAM/alias.
    change(files, 'g16_runtime.rs', '''        let guard = self._sgx.try_access().ok_or(ENODEV)?;
        for &stage in stages {''', '''        let fw = self._firmware_space.as_ref().ok_or(EIO)?;
        let guard = self._sgx.try_access().ok_or(ENODEV)?;
        for &stage in stages {''')
    change(files, 'g16_runtime.rs', '''            let route = &config.channels[channel];
            let read =
                guard.try_read32(0xd64000 + (route.state[0] - 0xffff_fc20_0002_8000) as usize)?;
            let done =
                guard.try_read32(0xd64000 + (route.state[1] - 0xffff_fc20_0002_8000) as usize)?;
            let tail =
                guard.try_read32(0xd60000 + (route.state[2] - 0xffff_fc20_0002_0000) as usize)?;''',
           '''            let read = super::read_cursor(&config, fw, &guard, channel, 0)?;
            let done = super::read_cursor(&config, fw, &guard, channel, 1)?;
            let tail = super::read_cursor(&config, fw, &guard, channel, 2)?;''')
    change(files, 'g16_runtime.rs', '''        let route = &config.channels[channel];
        let guard = self._sgx.try_access().ok_or(ENODEV)?;
        let tail =
            guard.try_read32(0xd60000 + (route.state[2] - 0xffff_fc20_0002_0000) as usize)?;''',
           '''        let fw = self._firmware_space.as_ref().ok_or(EIO)?;
        let guard = self._sgx.try_access().ok_or(ENODEV)?;
        let tail = super::read_cursor(&config, fw, &guard, channel, 2)?;''')
    change(files, 'g16_runtime.rs', '''                    let route = &config.channels[channel];
                    guard.try_write32(
                        tail,
                        0xd60000 + (route.state[2] - 0xffff_fc20_0002_0000) as usize,
                    )?;''', '''                    super::write_cursor(&config, fw, &guard, channel, 2, tail)?;''')
    change(files, 'g16_runtime.rs', '''                for address in &config.channels[channel].state[..2] {
                    done &= reached(
                        guard.try_read32(0xd64000 + (*address - 0xffff_fc20_0002_8000) as usize)?,
                        target,
                        256,
                    );
                }''', '''                for ordinal in 0..2 {
                    done &= reached(super::read_cursor(&config, fw, &guard, channel, ordinal)?, target, 256);
                }''')
    change(files, 'g16_runtime.rs', '''                done &= guard.try_read32(0xd640c0)? == guard.try_read32(0xd60060)?
                    && guard.try_read32(0xd640c8)? == guard.try_read32(0xd60060)?;''',
           '''                done &= super::read_cursor(&config, fw, &guard, 12, 0)? == super::read_cursor(&config, fw, &guard, 12, 2)?
                    && super::read_cursor(&config, fw, &guard, 12, 1)? == super::read_cursor(&config, fw, &guard, 12, 2)?;''')
    change(files, 'g16_runtime.rs', '''        const STATE: u64 = 0xffff_fc20_0003_f1c0;
        const RING: u64 = 0xffff_fc20_0003_f440;''', '''        let state = self.transport.event.state;
        let ring = self.transport.event.ring;''')
    change(files, 'g16_runtime.rs', '''        const STATE: u64 = 0xfffffc200003f1c0;
        const RING: u64 = 0xfffffc200003f440;''', '''        let state = self.transport.event.state;
        let ring = self.transport.event.ring;''')
    # STATE/RING symbols occur only inside the two event service methods.
    for name, replacement in [('STATE', 'state'), ('RING', 'ring')]:
        files['g16_runtime.rs'] = re.sub(r'\b' + name + r'\b', replacement, files['g16_runtime.rs'])
    change(files, 'g16_runtime.rs', '''            let head = sgx.try_read32(0xd640c0)?;
            let ack = sgx.try_read32(0xd640c8)?;
            let tail = sgx.try_read32(0xd60060)?;''', '''            let head = super::read_cursor(&self.transport, fw, sgx, 12, 0)?;
            let ack = super::read_cursor(&self.transport, fw, sgx, 12, 1)?;
            let tail = super::read_cursor(&self.transport, fw, sgx, 12, 2)?;''')
    change(files, 'g16_runtime.rs', '''            let guard = self._sgx.try_access().ok_or(ENODEV)?;
            guard.try_write32(successor, 0xd60060)?;''', '''            super::assert_control(&self.transport, fw, u32::from_le_bytes(reply[..4].try_into().map_err(|_| EINVAL)?))?;
            let guard = self._sgx.try_access().ok_or(ENODEV)?;
            super::write_cursor(&self.transport, fw, &guard, 12, 2, successor)?;''')
    change(files, 'g16_runtime.rs', '''        for (state, capacity) in [
            (0xffff_fc20_0003_f3c0, 512),
            (0xffff_fc20_0003_f400, 256),
            (0xffff_fc20_0003_f200, 256),
            (0xffff_fc20_0003_f230, 256),
            (0xffff_fc20_0003_f260, 256),
            (0xffff_fc20_0003_f290, 256),
            (0xffff_fc20_0003_f2c0, 256),
            (0xffff_fc20_0003_f2f0, 256),
        ] {''', '''        let mut drains = [(0, 256); 11];
        if self.transport.native_t6040 {
            drains[0] = (self.transport.trace.state, self.transport.trace.capacity);
            drains[1] = (self.transport.channels[14].state[2], 256);
            for i in 0..9 { drains[i + 2] = (self.transport.channels[13].state[2] + i as u64 * 0x30, 256); }
        } else {
            drains[..8].copy_from_slice(&[(0xffff_fc20_0003_f3c0, 512), (0xffff_fc20_0003_f400, 256),
                (0xffff_fc20_0003_f200, 256), (0xffff_fc20_0003_f230, 256),
                (0xffff_fc20_0003_f260, 256), (0xffff_fc20_0003_f290, 256),
                (0xffff_fc20_0003_f2c0, 256), (0xffff_fc20_0003_f2f0, 256)]);
        }
        for (state, capacity) in drains {
            if state == 0 { continue; }''')
    change(files, 'g16_runtime.rs', 'if state == 0xffff_fc20_0003_f3c0 {',
           'if state == self.transport.trace.state {')
    change(files, 'g16_runtime.rs', 'let base = 0xffff_fc20_000e_5c40 + u64::from(cursor) * 0x48;',
           'let base = self.transport.trace.ring + u64::from(cursor) * self.transport.trace.record_bytes as u64;')


def startup(files):
    # All startup work/control cursor accesses also consume the selected owner.
    text = files['g16.rs']
    mapping = {0xd64040: (1,0), 0xd64048:(1,1), 0xd60020:(1,2),
               0xd640c0:(12,0), 0xd640c8:(12,1), 0xd60060:(12,2)}
    for offset, (channel, ordinal) in mapping.items():
        text = text.replace('sgx.relaxed().read32(' + hex(offset) + ')',
            f'read_cursor(&self.transport, firmware, sgx, {channel}, {ordinal})?')
    text = text.replace('sgx.relaxed().write32(1, 0xd60020);',
        'write_cursor(&self.transport, firmware, sgx, 1, 2, 1)?;')
    text = text.replace('sgx.relaxed().write32(3, 0xd60060);',
        '// Producer publication is deferred until mapping metadata is ready.')
    text = text.replace('crate::g16_fw::BUNDLE_ADDRESS + 0x16240,', 'self.transport.channels[1].ring,')
    text = text.replace('crate::g16_fw::BUNDLE_ADDRESS + 0x1df40,', 'self.transport.channels[12].ring + 0x40,')
    text = text.replace('0xffff_fc20_0003_f19c', 'self.transport.roots.status_a + 0x1c')
    text = text.replace('0xffff_fc20_0003_f190', 'self.transport.roots.status_a + 0x10')
    text = text.replace('0xffff_fc20_0003_f194', 'self.transport.roots.status_a + 0x14')
    text = text.replace('0xffff_fc20_0003_f198', 'self.transport.roots.status_a + 0x18')
    text = text.replace('''        for addr in [self.transport.roots.status_a + 0x10, self.transport.roots.status_a + 0x18] {
            firmware.write_live(addr, &0u32.to_le_bytes())?;
        }''', '''        // Native statusA+10/+18 are firmware-owned GPUoff/generation words.
        if !self.transport.native_t6040 {
            for addr in [self.transport.roots.status_a + 0x10, self.transport.roots.status_a + 0x18] {
                firmware.write_live(addr, &0u32.to_le_bytes())?;
            }
        }''')
    # Native pointer parent and offsets are source-bound, not donor aliases.
    start = text.index('        for (address, value) in [\n            (0xffff_fc20_0003_4f88,')
    stop = text.index('        crate::mem::tlbi_asid(1);', start)
    text = text[:start] + '''        if self.transport.native_t6040 {
            firmware.write_live(self.transport.roots.status_b + 0x48e0,
                &0xffff_fc21_8100_0000u64.to_le_bytes())?;
            firmware.write_live(self.transport.roots.status_b + 0x48e8,
                &0xffff_fc21_8100_8000u64.to_le_bytes())?;
            firmware.write_live(self.transport.roots.status_b + 0x48f0, &0u64.to_le_bytes())?;
            firmware.write_live(self.transport.roots.status_b + 0x4900, &0u32.to_le_bytes())?;
            firmware.write_live(self.transport.roots.status_b + 0x4910, &0u32.to_le_bytes())?;
        } else {
            for (address, value) in [(0xffff_fc20_0003_4f88, 0xffff_fc21_8100_0000u64),
                                    (0xffff_fc20_0003_4f90, 0xffff_fc21_8100_8000u64)] {
                firmware.write_live(address, &value.to_le_bytes())?;
            }
            firmware.write_live(0xffff_fc20_0003_4fd4, &1u32.to_le_bytes())?;
        }
''' + text[stop:]
    text = text.replace('''        crate::mem::tlbi_asid(1);
        crate::mem::sync();
        kernel::time::delay::fsleep(kernel::time::Delta::from_millis(100));''',
        '''        crate::mem::tlbi_asid(1);
        crate::mem::sync();
        let guard = self._sgx.try_access().ok_or(ENODEV)?;
        if (read_cursor(&self.transport, firmware, &guard, 12, 0)?,
            read_cursor(&self.transport, firmware, &guard, 12, 1)?,
            read_cursor(&self.transport, firmware, &guard, 12, 2)?) != (1,1,1) { return Err(EIO); }
        // Records and all mapping metadata are published before the one class1
        // assertion, then the selected producer and finally EP33 notification.
        assert_control(&self.transport, firmware, 0x20)?;
        write_cursor(&self.transport, firmware, &guard, 12, 2, 3)?;
        crate::mem::sync();
        drop(guard);
        kernel::time::delay::fsleep(kernel::time::Delta::from_millis(100));''')
    text = text.replace('''            if cursors == (3, 3, 3) && firmware.read_u32(self.transport.roots.status_a + 0x1c)? == 1 {''',
        '''            let admitted = if self.transport.native_t6040 {
                firmware.read_u32(self.transport.roots.status_a + 0x14)? == 1
                    && firmware.read_u32(self.transport.roots.status_b + 0xe438)? == 1
            } else { firmware.read_u32(self.transport.roots.status_a + 0x1c)? == 1 };
            if cursors == (3, 3, 3) && admitted {''')
    files['g16.rs'] = text


def stage(destination):
    frozen_path = ROOT / 'docs/evidence/2026-10-11-gravity-native-t6040-components-v6.json'
    frozen = json.loads(frozen_path.read_text())
    for row in frozen['pins']:
        if pin(row['path']) != row:
            raise ValueError('Frozen v6 input changed: ' + row['path'])
    baseline = ROOT / 'out/gpu-gravity-normal-boot-v6'
    old = json.loads((baseline / 'stage-receipt.json').read_text())
    for row in old['source_files']:
        if pin(row['path']) != row:
            raise ValueError('Frozen v6 source changed: ' + row['path'])
    base = baseline / 'source/linux/drivers/gpu/drm/asahi'
    files = {str(Path(row['path']).relative_to(base)): Path(row['path']).read_text()
             for row in old['source_files']}
    components = {'g16_t6040_power.rs': 'g16_t6040_power_v7.rs',
                  'g16_t6040_shared.rs': 'g16_t6040_shared_v7.rs',
                  'g16_t6040_queue.rs': 'g16_t6040_queue_v7.rs',
                  'g16_t6040_qos.rs': 'g16_t6040_qos_v7.rs',
                  'g16_transport.rs': 'g16_transport_v7.rs',
                  'g16_queue_owner.rs': 'g16_queue_owner_v7.rs'}
    for name, component in components.items():
        files[name] = (KIT / component).read_text()
    wiring(files)
    destination = Path(destination).resolve()
    destination.relative_to(ROOT / 'out')
    destination.mkdir(parents=True, exist_ok=False)
    source = destination / 'source/linux/drivers/gpu/drm/asahi'
    for name, contents in files.items():
        output = source / name
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(contents)
    shutil.copytree(source, destination / 'build-owner')
    report = {'schema': 'm4rch.gravity-native-t6040-components.stage.v7',
              'base_stage_receipt': pin(baseline / 'stage-receipt.json'),
              'inputs': [pin(p) for p in [Path(__file__), frozen_path] + [KIT / v for v in components.values()]],
              'source_files': [pin(p) for p in sorted(source.rglob('*')) if p.is_file()],
              'native_selected_topology_used_by_startup_and_runtime': True,
              'native_work_control_cursors_are_owned_RAM': True,
              'native_queue_policy_integrated': False,
              'native_power_component_integrated': True,
              'native_notification_pointers_integrated': True,
              'native_class1_assertion_order_integrated': True,
              'native_statusA_gpu_off_word_remains_firmware_owned': True,
              'normal_startup_enabled': False, 'system_installed': False, 'hardware_actions': [],
              'startup_barriers': ['complete native power/provider policy and ARM tails',
                  'complete native UAT/mapping policy and firmware-loader reservations',
                  'native queue/QoS registration and config-before-Work integration',
                  'native Work/register/dependency publication and retirement',
                  'qualified GPU OFF/teardown before releasing submitted storage']}
    (destination / 'stage-receipt.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination')
    result = stage(parser.parse_args().destination)
    print(json.dumps({'source_files': len(result['source_files']),
                      'normal_startup_enabled': result['normal_startup_enabled']}))
