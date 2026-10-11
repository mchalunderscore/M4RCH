#!/usr/bin/env python3
"""Bind joined source to this kernel's Rust error and atomic API."""
def wiring(files):
    # These Linux errno values exist in bindings but not this Rust prelude.
    for name in ('g16.rs', 'g16_runtime.rs', 'g16_drm.rs'):
        s=files[name]
        for errno in ('ESTALE', 'EPROTO'):
            s=s.replace(errno, 'kernel::error::Error::from_errno(-(kernel::bindings::'+errno+' as i32))')
        files[name]=s
    s=files['g16_runtime.rs']
    s=s.replace('use kernel::io::Io;\n','')
    s=s.replace('.fetch_update(','.try_update(')
    files['g16_runtime.rs']=s
    s=files['g16.rs']
    # The graph extractor owns these values in build_application_graph now.
    marker='''        let pointers = transport.roots;
        let sgx_physical = platform.sgx_physical()?;
        // The source-only stage'''
    assert s.count(marker)==1
    s=s.replace(marker,'        // The source-only stage',1)
    files['g16.rs']=s
