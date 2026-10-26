// SPDX-License-Identifier: GPL-2.0-only
//! One runtime-PM usage reference owned by one native firmware session.
use kernel::{bindings, device::Core, platform, prelude::*, sync::aref::ARef};

pub(crate) struct Session {
    dev: ARef<platform::Device>,
    held: bool,
    exposed: bool,
    coordinate: *mut core::ffi::c_void,
}

impl Session {
    pub(crate) fn acquire(dev: &platform::Device<Core>) -> Result<Self> {
        let raw = dev.as_ref().as_raw();
        // SAFETY: The platform device remains live throughout acquisition.
        // Enable once under probe ownership; devm supplies the disable action.
        if !unsafe { bindings::pm_runtime_enabled(raw) } {
            kernel::error::to_result(unsafe { bindings::devm_pm_runtime_enable(raw) })?;
        }
        // SAFETY: This helper balances the usage increment on resume failure.
        kernel::error::to_result(unsafe { bindings::pm_runtime_resume_and_get(raw) })?;
        let mut session = Self { dev: dev.into(), held: true, exposed: false,
            coordinate: core::ptr::null_mut() };
        // SAFETY: The helper creates a private, exclusively claimed owner.
        session.coordinate = kernel::error::from_err_ptr(unsafe {
            bindings::native_gpu_coordinate_acquire()
        })?;
        Ok(session)
    }

    pub(crate) fn mark_exposed(&mut self) { self.exposed = true; }
    pub(crate) fn held(&self) -> bool { self.held }

    pub(crate) fn coordinate(&mut self, on: bool) -> Result {
        if !self.held { return Err(EINVAL); }
        self.exposed = true;
        // SAFETY: This session owns the non-null handle, serialized by the
        // Bootstrap mutex. The helper retains it after any external intent.
        kernel::error::to_result(unsafe {
            bindings::native_gpu_coordinate_transition(self.coordinate, on)
        })
    }

    pub(crate) fn provider_snapshot(&self) -> Result<(u32, bool)> {
        let mut word = 0u32;
        let mut on = false;
        // SAFETY: Both output slots are live and the provider locks its state.
        kernel::error::to_result(unsafe {
            bindings::native_gpu_provider_snapshot(&mut word, &mut on)
        })?;
        Ok((word, on))
    }

    pub(crate) fn put_once(&mut self) -> Result {
        if !self.held { return Err(EINVAL); }
        // Runtime-PM decrements even when suspend fails. Consume the reference
        // before calling; an error cannot authorize a second decrement.
        self.held = false;
        // SAFETY: ARef owns the live device and this session owns the reference.
        kernel::error::to_result(unsafe {
            bindings::pm_runtime_put_sync_suspend(self.dev.as_ref().as_raw())
        })
    }

    pub(crate) fn get_once(&mut self) -> Result {
        if self.held { return Err(EBUSY); }
        // SAFETY: ARef keeps the device live and failed resumes are balanced.
        kernel::error::to_result(unsafe {
            bindings::pm_runtime_resume_and_get(self.dev.as_ref().as_raw())
        })?;
        self.held = true;
        Ok(())
    }
}

impl Drop for Session {
    fn drop(&mut self) {
        // Only prepublication acquisition may unwind automatically. Once ASC
        // can DMA, shutdown must explicitly consume the PM reference in order.
        if !self.exposed {
            // SAFETY: This handle has never had an external coordinate intent.
            unsafe { bindings::native_gpu_coordinate_release_unexposed(self.coordinate) };
            if self.held { let _ = self.put_once(); }
        }
    }
}

// SAFETY: The handle belongs exclusively to Session and all operations run
// through the Bootstrap mutex; MMIO mappings and the owned ARef are movable.
unsafe impl Send for Session {}
