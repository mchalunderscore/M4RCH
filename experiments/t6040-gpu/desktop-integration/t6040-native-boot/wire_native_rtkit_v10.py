#!/usr/bin/env python3
"""Reproducible kernel RTKit G16 API extension, no device operation."""
from pathlib import Path
KIT=Path(__file__).parent

def kernel_wiring(files):
    name='drivers/soc/apple/rtkit-internal.h';s=files[name]
    s=s.replace('#include <linux/module.h>','#include <linux/module.h>\n#include <linux/mutex.h>\n#include <linux/delay.h>')
    s=s.replace('struct apple_rtkit {','struct apple_rtkit_g16_retained;\nstruct apple_rtkit {',1)
    marker='\tstruct completion epmap_completion;'
    assert s.count(marker)==1
    s=s.replace(marker,'''\tstruct mutex g16_lock;
    struct completion g16_ack_completion;
    bool g16_owner, g16_intent, g16_waiting, g16_ack, g16_nmi_attempted;
    bool g16_clear10_attempted, g16_clear20_attempted, g16_cpu_stopped;
    bool g16_rearm_attempted;
    int g16_rx_error;
    struct apple_rtkit_g16_retained *g16_retained;
'''+marker)
    files[name]=s
    name='drivers/soc/apple/rtkit.c';s=files[name]
    marker='\trtk->boot_ap_power = true;';assert s.count(marker)==1
    s=s.replace(marker,marker+'\n\tmutex_init(&rtk->g16_lock);\n\tinit_completion(&rtk->g16_ack_completion);')
    marker='''\tunsigned int new_state = FIELD_GET(APPLE_RTKIT_MGMT_PWR_STATE, msg);

\tdev_dbg(rtk->dev, "RTKit: IOP power state transition:'''
    assert s.count(marker)==1
    s=s.replace(marker,'''\tunsigned int new_state = FIELD_GET(APPLE_RTKIT_MGMT_PWR_STATE, msg);
    if (READ_ONCE(rtk->g16_waiting)) {
        /* Native type7 low1/2 aliases answer the sole202. Running20 is
         * startup state and never power-down acknowledgement. */
        if ((new_state&0xff)==1 || (new_state&0xff)==2) {
            WRITE_ONCE(rtk->g16_ack,true);
            rtk->iop_power_state=APPLE_RTKIT_PWR_STATE_SLEEP;
            complete_all(&rtk->g16_ack_completion);
            return;
        }
        WRITE_ONCE(rtk->g16_rx_error,-EPROTO);
        complete_all(&rtk->g16_ack_completion);
        return;
    }

\tdev_dbg(rtk->dev, "RTKit: IOP power state transition:''')
    # Exclude stock sleep/INIT/reinit/free after native intent. Autonomous fresh
    # boot uses its own explicitly consumed rearm operation instead.
    marker='''int apple_rtkit_reinit(struct apple_rtkit *rtk)
{
''';assert s.count(marker)==1
    s=s.replace(marker,marker+'    if (rtk->g16_intent || rtk->g16_retained) return -EBUSY;\n')
    marker='''void apple_rtkit_free(struct apple_rtkit *rtk)
{
''';assert s.count(marker)==1
    s=s.replace(marker,marker+'''    if (rtk->g16_owner || rtk->g16_intent || rtk->g16_retained) {
        apple_mbox_stop(rtk->mbox);
        flush_workqueue(rtk->wq);
        dev_warn(rtk->dev,"RTKit: retaining native generations until DMA retirement\\n");
        return;
    }
''')
    # All ordinary public power paths ultimately select one of these private
    # functions, so native ownership cannot accidentally fall through SLEEP.
    for function in ('apple_rtkit_set_iop_power_state','apple_rtkit_set_ap_power_state'):
        start=s.index('static int '+function+'(')
        brace=s.index('{',start)
        # Insert after declarations to preserve kernel declaration style.
        ret=s.index('\tint ret;',brace)+len('\tint ret;')
        s=s[:ret]+s[ret:].replace('\n','\n\n    if (rtk->g16_intent) return -EBUSY;\n',1)
    s+='\n'+(KIT/'native_rtkit_lifecycle_v10.c.inc').read_text()
    files[name]=s
    name='include/linux/soc/apple/rtkit.h';s=files[name]
    marker='void apple_rtkit_free(struct apple_rtkit *rtk);';assert s.count(marker)==1
    s=s.replace(marker,marker+'''
/* Explicit G16 retained-generation APIs. Caller owns ASC/runtimePM and must
 * retain all DMA backing. Neither API grants unmap/free permission. */
int apple_rtkit_g16_own_retained(struct apple_rtkit *rtk);
int apple_rtkit_g16_powergate(struct apple_rtkit *rtk, void __iomem *asc, size_t asc_bytes);
bool apple_rtkit_g16_ack_observed(struct apple_rtkit *rtk);
int apple_rtkit_g16_rearm_retained(struct apple_rtkit *rtk, void *fresh_cookie);
bool apple_rtkit_g16_cookie_owned(struct apple_rtkit *rtk, void *cookie);
''')
    files[name]=s
    name='rust/kernel/soc/apple/rtkit.rs';s=files[name]
    s=s.replace('    data: *mut core::ffi::c_void,','    data: *mut core::ffi::c_void,\n    native_owned: bool,',1)
    s=s.replace('            data: ptr,','            data: ptr,\n            native_owned: false,',1)
    drop_marker='        // Free context data.'
    assert s.count(drop_marker)==1
    s=s.replace(drop_marker,'        if self.native_owned { return; }\n\n'+drop_marker)
    marker='    /// Selects the early preallocated crash-buffer exchange used by G16.'
    assert s.count(marker)==1
    s=s.replace(marker,'''    /// Claim native callback and endpoint ownership before first ASC START.
    pub fn g16_own_retained(self: Pin<&mut Self>)->Result {
        let this=unsafe {self.get_unchecked_mut()};
        to_result(unsafe {bindings::apple_rtkit_g16_own_retained(this.rtk)})?;
        this.native_owned=true;
        Ok(())
    }
    /// Native G16202/NMI/freshCPUstop. The caller owns the ASC mapping and
    /// runtime-PM reference, and retains every old GPU generation.
    pub unsafe fn g16_powergate(self: Pin<&mut Self>, asc: usize, size: usize) -> Result<bool> {
        to_result(unsafe {bindings::apple_rtkit_g16_powergate(self.rtk,asc as *mut core::ffi::c_void,size)})?;
        Ok(unsafe {bindings::apple_rtkit_g16_ack_observed(self.rtk)})
    }
    /// Reinitialize protocol state while retaining old system endpoint buffers.
    /// Must follow nativeCPUstop and the owned OFF/ON sequence before START.
    pub fn g16_rearm_retained(self: Pin<&mut Self>, data:T::Data)->Result {
        let pointer=data.into_foreign();
        // SAFETY: Only the opaque callback-data field changes. No pinned Rust
        // allocation moves; C stops mailbox delivery and flushes its workers.
        let this=unsafe {self.get_unchecked_mut()};
        let result=to_result(unsafe {bindings::apple_rtkit_g16_rearm_retained(this.rtk,pointer as *mut core::ffi::c_void)});
        if unsafe {bindings::apple_rtkit_g16_cookie_owned(this.rtk,pointer as *mut core::ffi::c_void)} {
            // Old foreign ownership remains deliberately retained with its
            // generation, rather than running a destructor on GPU uncertainty.
            this.data=pointer;
        } else {unsafe {T::Data::from_foreign(pointer)};}
        result
    }
'''+marker)
    files[name]=s
