#![no_std]
#![allow(dead_code)]
#[macro_use] mod float;
mod power;
mod properties;
use core::slice;
#[panic_handler]
fn panic(_: &core::panic::PanicInfo) -> ! { unsafe { m4rch_full_power_panic() } }
unsafe extern "C" { fn m4rch_full_power_panic() -> !; }
#[unsafe(no_mangle)]
pub unsafe extern "C" fn m4rch_native_power_validate(primary:*const u32,secondary:*const u32)->i32 {
    if primary.is_null() || secondary.is_null() {return -22;}
    let pm=unsafe {&*primary.cast::<[u32;8]>()};let sm=unsafe {&*secondary.cast::<[u32;8]>()};
    let valid=(|| {let maps=power::PerfStateMaps::from_register_words(pm,sm)?;
        power::PowerData::from_adt(properties::ROWS)?.with_perf_state_maps(&maps)})();
    if valid.is_some(){0}else{-22}
}
#[unsafe(no_mangle)]
pub unsafe extern "C" fn m4rch_native_power_write(
    primary: *const u32, secondary: *const u32, native_ticks: u64,
    power_out: *mut u8, hw_out: *mut u8, region_out: *mut u8, aon_out: *mut u8,
    support: u64, qos: u64, aon: u64) -> i32 {
    if primary.is_null() || secondary.is_null() || power_out.is_null() || hw_out.is_null()
        || region_out.is_null() || aon_out.is_null() { return -22; }
    let result = (|| {
        let p: &[u32;8] = unsafe { &*primary.cast() };
        let s: &[u32;8] = unsafe { &*secondary.cast() };
        let maps=power::PerfStateMaps::from_register_words(p,s)?;
        let data=power::PowerData::from_adt(properties::ROWS)?.with_perf_state_maps(&maps)?;
        let policy=power::LinuxBootPolicy { maximum_power_mw:20000, native_absolute_ticks:native_ticks };
        let po=unsafe { slice::from_raw_parts_mut(power_out,power::LOGICAL_BYTES) };
        let hw=unsafe { slice::from_raw_parts_mut(hw_out,power::HARDWARE_LOGICAL_BYTES) };
        let rc=unsafe { slice::from_raw_parts_mut(region_out,power::REGION_C_LOGICAL_BYTES) };
        let ao=unsafe { slice::from_raw_parts_mut(aon_out,power::AONPTD_LOGICAL_BYTES) };
        let providers=power::LifecycleProviders::capture(po,&policy,
            power::PowerOwnedAliases {support26_gpu:support,qos_gpu:qos,aonptd_gpu:aon})?;
        data.write_lifecycle_component(po,&providers)?;
        data.write_hardware_component(hw,&providers)?;
        data.write_region_c_component(rc,&providers)?;
        data.write_aonptd_component(ao)?;
        Some(())
    })();
    if result.is_some() { 0 } else { -22 }
}
