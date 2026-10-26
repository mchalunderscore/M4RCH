// SPDX-License-Identifier: GPL-2.0-only
//! T6040 native full ARM power startup with explicit experimental Linux providers.
//!
//! Numeric cold-controller defaults come from matched AGX353.14/25G83 native
//! setupConfig and initPowerFirmwareData through their normal returns. Selected
//! input is the original two-table, sixteen-row SGX ADT with its captured optional
//! defaults. Factory leakage services are deliberately fresh zero arrays, the
//! optional AON dictionary service is absent, and the Apple fuse-derived maximum
//! remains unimplemented. Linux supplies 20 W and raw monotonic 24 MHz ticks.
//! This component owns fields, never a zero page standing in for live GPU aliases.
use super::float::F32;

pub(crate) const LOGICAL_BYTES: usize = 0x6578;
pub(crate) const HARDWARE_LOGICAL_BYTES: usize = 0x2718;
pub(crate) const REGION_C_LOGICAL_BYTES: usize = 0xe58;
pub(crate) const AONPTD_LOGICAL_BYTES: usize = 0xe4;
// Whole power/HW/Region C/AON outputs match native RAM execution for identity
// and grouped maps with original ADT and explicit experimental Linux policy.
// This qualifies this writer; full bundle/startup and hardware remain separate.
pub(crate) const POWER_COMPLETE: bool = true;
pub(crate) const APPLE_FUSE_MAXIMUM_COMPLETE: bool = false;
pub(crate) const PERIOD_CLOCKS_PER_MS: u32 = 24000;
pub(crate) const HARDWARE_PERIOD_OFFSET: usize = 0xed8;
pub(crate) const PERF_ROWS: usize = 16;
pub(crate) const PERF_STATE_MAP_REG_OFFSETS: [usize; 2] = [0xe01400, 0xe01480];
pub(crate) const REQUIRED_BYTE_PROPERTIES: &[&str] = &[
    "perf-state-count", "perf-state-table-count", "perf-states",
    "perf-states-sram", "cs-perf-states", "afr-perf-states",
];
pub(crate) const OPTIONAL_WORD_PROPERTIES: &[&str] = &[
    "gpu-pwr-sample-period-aic-clks", "gpu-power-sample-period",
    "gpu-num-perf-states", "gpu-pwr-min-duty-cycle",
    "gpu-device-max-power", "gpu-max-power", "gpu-pwr-filter-time-constant",
    "gpu-pwr-integral-gain", "gpu-pwr-integral-min-clamp",
    "gpu-pwr-proportional-gain", "gpu-perf-base-pstate",
    "gpu-perf-tgt-utilization", "gpu-perf-dz",
    "gpu-perf-filter-time-constant", "gpu-perf-filter-time-constant2",
    "gpu-perf-filter-drop-threshold", "gpu-perf-integral-gain",
    "gpu-perf-integral-gain2", "gpu-perf-integral-min-clamp",
    "gpu-perf-proportional-gain", "gpu-perf-proportional-gain2",
    "gpu-perf-limiter-filter-time-constant",
];

#[derive(Clone, Copy, Debug)]
pub(crate) struct PerfStateMaps { pub primary: [u8; 16], pub secondary: [u8; 16] }
impl PerfStateMaps {
    /// Native 89d6368: low and bit16 nibbles, one pair per register word.
    pub(crate) fn from_register_words(primary: &[u32; 8], secondary: &[u32; 8]) -> Option<Self> {
        let mut p = [0u8; 16]; let mut s = [0u8; 16];
        for i in 0..8 { p[2*i] = (primary[i] & 15) as u8;
            p[2*i+1] = ((primary[i] >> 16) & 15) as u8;
            s[2*i] = (secondary[i] & 15) as u8;
            s[2*i+1] = ((secondary[i] >> 16) & 15) as u8; }
        Some(Self { primary: p, secondary: s })
    }
}

#[derive(Clone, Copy, Debug)]
pub(crate) struct PowerOwnedAliases { pub support26_gpu: u64, pub qos_gpu: u64, pub aonptd_gpu: u64 }
impl PowerOwnedAliases {
    fn valid(&self) -> bool {
        self.support26_gpu != 0 && self.support26_gpu & 7 == 0
            && self.qos_gpu != 0 && self.qos_gpu & 0x3fff == 0
            && self.aonptd_gpu != 0 && self.aonptd_gpu & 0x3fff == 0
            && self.qos_gpu != self.aonptd_gpu && self.support26_gpu != self.qos_gpu
            && self.support26_gpu != self.aonptd_gpu
    }
}

#[derive(Clone, Copy, Debug)]
pub(crate) struct LinuxBootPolicy { pub maximum_power_mw: u32, pub native_absolute_ticks: u64 }
impl LinuxBootPolicy {
    /// Authorized first-render policy, independent of Apple factory-fuse results.
    /// Raw monotonic origin and conversion must be shared by the integration.
    pub(crate) fn t6040_20w_24mhz(ns: u64, enabled_cores: u32, gpu_clusters: u32) -> Option<Self> {
        if enabled_cores != 16 || gpu_clusters != 2 { return None; }
        let ticks = (ns / 1000).checked_mul(24)?.checked_add((ns % 1000) * 24 / 1000)?;
        Some(Self { maximum_power_mw: 20000, native_absolute_ticks: ticks })
    }
}

#[derive(Clone, Copy, Debug)]
pub(crate) struct LifecycleProviders {
    pub policy: LinuxBootPolicy, pub aliases: PowerOwnedAliases,
    pub preserved_6530: [u8; 8], pub preserved_2888: [u8; 48],
}
impl LifecycleProviders {
    pub(crate) fn capture(power: &[u8], policy: &LinuxBootPolicy, aliases: PowerOwnedAliases) -> Option<Self> {
        if power.len() < LOGICAL_BYTES || policy.maximum_power_mw != 20000 || !aliases.valid() { return None; }
        Some(Self { policy: *policy, aliases,
            preserved_6530: power[0x6530..0x6538].try_into().ok()?,
            preserved_2888: power[0x2888..0x28b8].try_into().ok()? })
    }
    fn valid(&self) -> bool { self.policy.maximum_power_mw == 20000 && self.aliases.valid() }
}

#[derive(Clone, Copy, Debug)]
struct Auxiliary { hz: [u32;16], core_mv: [u32;16], sram_mv: [u32;16], count: usize }
#[derive(Clone, Copy, Debug)]
pub(crate) struct PowerData {
    pub period_aic_clocks: u32, pub period_ms: u32,
    pub main_hz: [u32;16], pub maximum_index: u32,
    pub minimum_duty: u32, pub base_index: u32,
    pub intermediate_maximum_property: Option<u32>,
    raw_hz: [u32;16], raw_core: [[u32;2];16], raw_sram: [[u32;2];16],
    primary_rows: [u8;16], secondary_rows: [u8;16],
    pub primary_count: usize, pub secondary_count: usize,
    maps: PerfStateMaps, cs: Auxiliary, afr: Auxiliary, maps_bound: bool,
}
fn put32(out: &mut [u8], off: usize, v: u32) { out[off..off+4].copy_from_slice(&v.to_le_bytes()); }
fn put64(out: &mut [u8], off: usize, v: u64) { out[off..off+8].copy_from_slice(&v.to_le_bytes()); }
fn get32(raw: &[u8], off: usize) -> Option<u32> { Some(u32::from_le_bytes(raw.get(off..off+4)?.try_into().ok()?)) }
fn get64(raw: &[u8], off: usize) -> Option<u64> { Some(u64::from_le_bytes(raw.get(off..off+8)?.try_into().ok()?)) }
fn property<'a>(rows: &[(&str, &'a [u8])], name: &str) -> Option<Option<&'a [u8]>> {
    let mut found = None;
    for &(k,v) in rows { if k == name { if found.is_some() { return None; } found=Some(v); } }
    Some(found)
}
fn word(rows: &[(&str, &[u8])], name: &str, default: u32) -> Option<u32> {
    match property(rows,name)? { Some(raw) if raw.len()==4 => get32(raw,0), Some(_) => None, None => Some(default) }
}
fn mhz(hz: u32) -> u32 { ((hz as u64 * 0x431bde83) >> 50) as u32 }
fn auxiliary(raw: &[u8]) -> Option<Auxiliary> {
    // Native ABI is one SoC table, eight 64-bit microvolt/frequency pairs and
    // one trailing SRAM floor. This geometry is not GPU core/cluster count.
    if raw.len()!=152 || get64(raw,0)?!=1 || get64(raw,8)?!=8 { return None; }
    let floor = u32::try_from(get64(raw,144)? / 1000).ok()?;
    let mut a = Auxiliary { hz: [0;16], core_mv: [0;16], sram_mv: [0;16], count: 8 };
    for i in 0..8 { a.core_mv[i]=u32::try_from(get64(raw,16+i*16)? / 1000).ok()?;
        a.hz[i]=u32::try_from(get64(raw,24+i*16)?).ok()?;
        a.sram_mv[i]=a.core_mv[i].max(floor); }
    Some(a)
}
impl PowerData {
    /// Keep the complete original native raw tables until the one startup map
    /// provider is bound. Unsupported controller overrides fail explicitly.
    pub(crate) fn from_adt(rows: &[(&str, &[u8])]) -> Option<Self> {
        if word(rows,"perf-state-count",0)?!=16 || word(rows,"perf-state-table-count",0)?!=2 { return None; }
        let raw=property(rows,"perf-states")??; let sram=property(rows,"perf-states-sram")??;
        if raw.len()!=256 || sram.len()!=256 { return None; }
        let mut hz=[0u32;16]; let mut core=[[0u32;2];16]; let mut sv=[[0u32;2];16];
        for i in 0..16 { hz[i]=get32(raw,i*8)?;
            if get32(raw,(16+i)*8)?!=hz[i] || get32(sram,i*8)?!=hz[i] || get32(sram,(16+i)*8)?!=hz[i] { return None; }
            for c in 0..2 { core[i][c]=get32(raw,(c*16+i)*8+4)?;
                sv[i][c]=get32(sram,(c*16+i)*8+4)?.max(core[i][c]); }
        }
        if hz[15]==0 || word(rows,"gpu-pwr-sample-period-aic-clks",200000)?!=200000
            || word(rows,"gpu-power-sample-period",8)?!=8 || word(rows,"gpu-num-perf-states",15)?!=15 { return None; }
        for &(name,default) in SELECTED_CONTROLLER_DEFAULTS { if word(rows,name,default)?!=default { return None; } }
        let cs=auxiliary(property(rows,"cs-perf-states")??)?;
        let afr=auxiliary(property(rows,"afr-perf-states")??)?;
        let identity=[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15];
        Some(Self { period_aic_clocks:200000, period_ms:8, main_hz:hz, maximum_index:15,
            minimum_duty:40, base_index:1, intermediate_maximum_property:None,
            raw_hz:hz, raw_core:core, raw_sram:sv, primary_rows:identity, secondary_rows:identity,
            primary_count:16, secondary_count:16, maps:PerfStateMaps { primary:identity, secondary:identity },
            cs, afr, maps_bound:false })
    }
    /// Native mapped rows retain duplicates. Zero secondary indices skip only
    /// secondary copies; disabled primary voltage terminates the mapped table.
    pub(crate) fn with_perf_state_maps(&self, maps: &PerfStateMaps) -> Option<Self> {
        let mut out=*self; out.primary_rows=[0;16]; out.secondary_rows=[0;16];
        let mut p=1; let mut s=1;
        for wire in 1..16 { let pi=maps.primary[wire] as usize; let si=maps.secondary[wire] as usize;
            if pi>=16 || si>=16 { return None; }
            if self.raw_core[pi][0]==0 { break; }
            if pi!=0 { out.primary_rows[p]=pi as u8; p+=1; }
            if si!=0 { out.secondary_rows[s]=si as u8; s+=1; }
        }
        if p<2 || s<1 { return None; }
        out.primary_count=p; out.secondary_count=s; out.maximum_index=(p-1) as u32;
        out.main_hz=[0;16]; for i in 0..p { out.main_hz[i]=out.raw_hz[out.primary_rows[i] as usize]; }
        if out.main_hz[p-1]<=out.main_hz[1] { return None; }
        out.maps=*maps; out.maps_bound=true; Some(out)
    }
    fn valid(&self) -> bool { self.maps_bound && self.primary_count>=2 && self.primary_count<=16
        && self.secondary_count>=1 && self.secondary_count<=16 && self.maximum_index==(self.primary_count-1) as u32 }
    pub(crate) fn write_lifecycle_component(&self, out: &mut [u8], providers: &LifecycleProviders) -> Option<()> {
        if out.len()<LOGICAL_BYTES || !self.valid() || !providers.valid() { return None; }
        out[..LOGICAL_BYTES].fill(0);
        for &(off,v) in POWER_DEFAULT_WORDS { put32(out,off,v); }
        for pair in out[0x1bef..0x1fef].chunks_exact_mut(2) { pair.copy_from_slice(&0x7fffu16.to_le_bytes()); }
        for i in 0..self.primary_count { put32(out,0xc0+i*4,0x3f828f5c); }
        let max=self.maximum_index*100;
        for &off in MAXIMUM_SCALED_FIELDS { put32(out,off,max); }
        put32(out,0x9e0,F32::from(providers.policy.maximum_power_mw as i32).to_bits());
        put32(out,0x9ec,(-F32::from(max)/F32::from(providers.policy.maximum_power_mw)).to_bits());
        put32(out,0xa04,providers.policy.maximum_power_mw);
        put32(out,0xb74,(F32::from((self.maximum_index-1)*100)/F32::from(95i32)).to_bits());
        put32(out,0x21f8,F32::from(max).to_bits()); put32(out,0x21fc,mhz(self.main_hz[self.primary_count-1]));
        put32(out,0x2e64,(self.maximum_index-1)*100);
        put64(out,0x3b50,providers.aliases.support26_gpu); put64(out,0x6318,providers.aliases.aonptd_gpu);
        put64(out,0x63d4,providers.policy.native_absolute_ticks);
        out[0x6530..0x6538].copy_from_slice(&providers.preserved_6530);
        out[0x2888..0x28b8].copy_from_slice(&providers.preserved_2888); Some(())
    }
    fn write_auxiliary(out: &mut [u8], off: usize, a: &Auxiliary) {
        out[off..off+0x148].fill(0); put32(out,off,(a.count-1) as u32); put32(out,off+4,(a.count-1) as u32);
        for i in 0..16 { put32(out,off+8+i*4,mhz(a.hz[i]));
            put32(out,off+0x48+i*8,a.core_mv[i]); put32(out,off+0xc8+i*8,a.sram_mv[i]); }
    }
    pub(crate) fn write_hardware_component(&self, out: &mut [u8], providers: &LifecycleProviders) -> Option<()> {
        if out.len()<HARDWARE_LOGICAL_BYTES || !self.valid() || !providers.valid() { return None; }
        for &(off,v) in HARDWARE_DEFAULT_WORDS { put32(out,off,v); }
        put32(out,HARDWARE_PERIOD_OFFSET,self.period_ms); put32(out,0xfc4,self.maximum_index);
        for i in 0..16 { let pi=self.primary_rows[i] as usize; let si=self.secondary_rows[i] as usize;
            let primary=i<self.primary_count; let secondary=i<self.secondary_count;
            put32(out,0xfc8+i*4,if primary { mhz(self.raw_hz[pi]) } else { 0 });
            put32(out,0x1808+i*4,if secondary { mhz(self.raw_hz[si]) } else { 0 });
            put32(out,0x1848+i*4,if primary { 0x3f828f5c } else { 0 });
            put32(out,0x1888+i*4,0); put32(out,0x18c8+i*4,0);
            for c in 0..16 { let column=if c==1 { 1 } else { 0 };
                put32(out,0x1008+i*64+c*4,if primary { self.raw_core[pi][column] } else { 0 });
                put32(out,0x1408+i*64+c*4,if primary { self.raw_sram[pi][column] } else { 0 }); }
            put32(out,0x19c8+i*4,self.maps.primary[i] as u32); put32(out,0x1a08+i*4,self.maps.secondary[i] as u32);
            put32(out,0x1cdc+i*4,if secondary { mhz(self.raw_hz[si]) } else { 0 });
            // Native secondary voltage copy writes only its two supplied columns.
            for c in 0..2 { put32(out,0x1d1c+i*64+c*4,if secondary { self.raw_core[si][c] } else { 0 });
                put32(out,0x211c+i*64+c*4,if secondary { self.raw_sram[si][c] } else { 0 }); }
        }
        out[0x1908..0x1948].fill(0);
        let base=self.main_hz[1] as u64; let last=self.main_hz[self.primary_count-1] as u64;
        for i in 1..self.primary_count-1 { let value=(self.main_hz[i] as u64).wrapping_sub(base).wrapping_mul(100)/(last-base);
            put32(out,0x1908+i*4,value as u32); }
        put32(out,0x1908+(self.primary_count-1)*4,100);
        Self::write_auxiliary(out,0x1a48,&self.cs); Self::write_auxiliary(out,0x1b90,&self.afr);
        put32(out,0x1cd8,(self.secondary_count-1) as u32); put64(out,0x26b8,providers.aliases.qos_gpu); Some(())
    }
    pub(crate) fn write_region_c_component(&self, out: &mut [u8], providers: &LifecycleProviders) -> Option<()> {
        if out.len()<REGION_C_LOGICAL_BYTES || !self.valid() || !providers.valid() { return None; }
        for &(start,end) in REGION_C_ZERO_RANGES { out[start..end].fill(0); }
        for &(off,v) in REGION_C_DEFAULT_WORDS { put32(out,off,v); }
        let target=mhz(self.main_hz[self.primary_count-1]); let mut upper=self.primary_count-1;
        while upper!=0 && target<=mhz(self.main_hz[upper-1]) { upper-=1; }
        if upper==0 { return None; } let lower=upper-1;
        let delta=mhz(self.main_hz[upper]).checked_sub(mhz(self.main_hz[lower]))?; if delta==0 { return None; }
        let limit=((lower as u32)*100+(target-mhz(self.main_hz[lower]))*100/delta).max(self.minimum_duty);
        put32(out,0x84,providers.policy.maximum_power_mw); for off in [0x88,0x8c,0x98] { put32(out,off,limit); } Some(())
    }
    /// Fresh optional-service policy: own the native one-child logicale4 RAM
    /// allocation; absent AON dictionary means its fresh contents remain zero.
    pub(crate) fn write_aonptd_component(&self, out: &mut [u8]) -> Option<()> {
        if out.len()<AONPTD_LOGICAL_BYTES || !self.valid() { return None; }
        out[..AONPTD_LOGICAL_BYTES].fill(0); Some(())
    }
}

const SELECTED_CONTROLLER_DEFAULTS: &[(&str,u32)] = &[
    ("gpu-pwr-min-duty-cycle",0x28),
    ("gpu-device-max-power",0x0),
    ("gpu-max-power",0x0),
    ("gpu-pwr-filter-time-constant",0x139),
    ("gpu-pwr-integral-gain",0x3ca59586),
    ("gpu-pwr-integral-min-clamp",0x0),
    ("gpu-pwr-proportional-gain",0x40a90fdb),
    ("gpu-perf-base-pstate",0x1),
    ("gpu-perf-tgt-utilization",0x50),
    ("gpu-perf-dz",0x0),
    ("gpu-perf-filter-time-constant",0x5),
    ("gpu-perf-filter-time-constant2",0xc8),
    ("gpu-perf-filter-drop-threshold",0x0),
    ("gpu-perf-integral-gain",0x3f64c986),
    ("gpu-perf-integral-gain2",0x3f64c986),
    ("gpu-perf-integral-min-clamp",0x0),
    ("gpu-perf-proportional-gain",0x403ea7f0),
    ("gpu-perf-proportional-gain2",0x403ea7f0),
    ("gpu-perf-limiter-filter-time-constant",0x5),
];
const MAXIMUM_SCALED_FIELDS: &[usize] = &[0x48,0x88,0x9f4,0x9f8,0xa38,0xaac,0xb7c,0x221c,0x22b4,0x22b8,0x22f8,0x2870,0x2b88,0x2c44,0x2e68,0x2e6c,0x2e78,0x2eac];
const REGION_C_ZERO_RANGES: &[(usize,usize)] = &[(0x2c,0x38),(0x9c,0xe8),(0xec,0x7c4),(0x7f0,0x7fc),(0x998,0x9b0),(0xa00,0xa08)];

// Numeric native cold-default words; graph pointers and variable clocks are typed above.
const POWER_DEFAULT_WORDS: &[(usize, u32)] = &[
    (0x4, 0x00030d40),
    (0x8, 0x00030d40),
    (0x10, 0x00000004),
    (0x14, 0x3f800000),
    (0x2c, 0x00000001),
    (0x30, 0x00000001),
    (0x40, 0x00000064),
    (0x44, 0x00000001),
    (0x50, 0x00000064),
    (0x60, 0x00000004),
    (0x64, 0x3f800000),
    (0x6c, 0x00000001),
    (0x70, 0x00000001),
    (0x80, 0x00000064),
    (0x84, 0x00000001),
    (0x90, 0x00000064),
    (0x9b8, 0x00000271),
    (0x9c4, 0x3f7f2e9f),
    (0x9cc, 0x3b516154),
    (0x9d4, 0x3ca59586),
    (0x9e0, 0x469c4000),
    (0x9e4, 0x40a90fdb),
    (0x9f0, 0x00000028),
    (0xa04, 0x00004e20),
    (0xa70, 0x00000008),
    (0xa7c, 0x3f000000),
    (0xa84, 0x3f000000),
    (0xa8c, 0x3e3bd7b3),
    (0xa98, 0x47800000),
    (0xa9c, 0x3ecf2e49),
    (0xaa8, 0x00000028),
    (0xac8, 0x00000010),
    (0xad0, 0x0005dc00),
    (0xb28, 0x00000050),
    (0xb30, 0x00000055),
    (0xb34, 0x00000032),
    (0xb38, 0x00000006),
    (0xb40, 0x00000006),
    (0xb44, 0x00000001),
    (0xb4c, 0x3f4ccccd),
    (0xb50, 0x3f7eb852),
    (0xb54, 0x3e4ccccd),
    (0xb58, 0x3ba3d70a),
    (0xb5c, 0x3f64c986),
    (0xb60, 0x3f64c986),
    (0xb68, 0x42be0000),
    (0xb6c, 0x403ea7f0),
    (0xb70, 0x403ea7f0),
    (0xb78, 0x00000064),
    (0xb80, 0x00000064),
    (0xb8c, 0x00000050),
    (0xbc0, 0x00000064),
    (0x21f0, 0x47800000),
    (0x21f4, 0x42200000),
    (0x2210, 0x00000028),
    (0x2218, 0x42c80000),
    (0x2224, 0x3f4ccccd),
    (0x2228, 0x3e4ccccd),
    (0x2268, 0x2a222aa2),
    (0x2270, 0x00001f40),
    (0x2278, 0x00000004),
    (0x228c, 0x3f800000),
    (0x2294, 0x414eeeee),
    (0x22a0, 0x47800000),
    (0x22a4, 0x42140000),
    (0x22b0, 0x00000028),
    (0x22c4, 0x00002af8),
    (0x2728, 0xb8520000),
    (0x272c, 0x00003f7e),
    (0x2730, 0xd70a0000),
    (0x2734, 0x00003ba3),
    (0x273c, 0x000043c8),
    (0x2748, 0x00004780),
    (0x274c, 0x000042c8),
    (0x2754, 0x0384bac8),
    (0x2758, 0x03e80000),
    (0x275c, 0x03e80000),
    (0x2764, 0x80000000),
    (0x2768, 0x26ac453b),
    (0x279c, 0x03e80000),
    (0x27b8, 0x00c80000),
    (0x2b4c, 0x00000032),
    (0x2b50, 0x00000001),
    (0x2b58, 0x3f638e39),
    (0x2b5c, 0x3f2aaaab),
    (0x2b60, 0x3de38e39),
    (0x2b64, 0x3eaaaaab),
    (0x2b68, 0xbecccccd),
    (0x2b6c, 0xbecccccd),
    (0x2b74, 0x47800000),
    (0x2b78, 0xc0a00000),
    (0x2b7c, 0xc0a00000),
    (0x2b84, 0x00000064),
    (0x2b8c, 0x00000064),
    (0x2b94, 0x45fa0000),
    (0x2b98, 0x00000578),
    (0x2ba4, 0x00000048),
    (0x2ba8, 0x00000018),
    (0x2bac, 0x001a5e00),
    (0x2bb4, 0x0008ca00),
    (0x2bc0, 0x47800000),
    (0x2be8, 0x00001f40),
    (0x2bec, 0x00000004),
    (0x2bf0, 0x000009c4),
    (0x2bf4, 0x00000258),
    (0x2bf8, 0x00000002),
    (0x2bfc, 0x00000004),
    (0x2c00, 0x00000032),
    (0x2c30, 0x47800000),
    (0x2c40, 0x00000028),
    (0x2e2c, 0x00000004),
    (0x2e38, 0x3f780000),
    (0x2e40, 0x3d000000),
    (0x2e48, 0x40a00000),
    (0x2e54, 0x47800000),
    (0x2e58, 0x41700000),
    (0x2f08, 0x2a222aa2),
    (0x2f10, 0x0000007d),
    (0x2f14, 0x00000001),
    (0x6320, 0x67305452),
    (0x6324, 0x67315452),
    (0x6368, 0x72305452),
];
const HARDWARE_DEFAULT_WORDS: &[(usize, u32)] = &[
    (0xec0, 0x00000000),
    (0xedc, 0x00000000),
    (0xf48, 0x00000000),
    (0xf4c, 0x00000000),
    (0xf70, 0x00000000),
    (0xf74, 0x00000000),
    (0xf78, 0x00000000),
    (0xf7c, 0x00000000),
    (0xf84, 0x00000000),
];
const REGION_C_DEFAULT_WORDS: &[(usize, u32)] = &[
    (0x7ec, 0x00000001),
    (0x9b8, 0x00000002),
    (0x9bc, 0x00000028),
    (0x9c0, 0x00000005),
    (0x9e0, 0x00000001),
    (0x9e4, 0x01020200),
    (0x9e8, 0x010a2801),
    (0x9ec, 0x28020101),
    (0x9f0, 0x0101010a),
    (0x9f4, 0x010a2802),
    (0x9f8, 0x28010101),
    (0x9fc, 0x0001010a),
];
