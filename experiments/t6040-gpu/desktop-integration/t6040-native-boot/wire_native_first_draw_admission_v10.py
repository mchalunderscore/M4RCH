#!/usr/bin/env python3
"""Admit the joined graphics experiment without claiming full native ABI coverage."""
def wiring(files):
    s=files['g16.rs']
    before='''        // The source-only stage never accesses hardware with unfinished gates.
        if native_t6040 && (!crate::g16_t6040_power::POWER_COMPLETE
            || !crate::g16_t6040_bundle::BUNDLE_COMPLETE) { return Err(ENOTSUPP); }'''
    assert s.count(before)==1
    s=s.replace(before,'''        // Explicit opt-in to the joined, preallocated graphics experiment.
        // Broad native ABI completeness flags remain false. The fallible
        // topology, provider, mapping and geometry constructors still apply.
        if native_t6040 && (!crate::g16_t6040_power::POWER_COMPLETE
            || *crate::module_parameters::native_t6040_experiment.value()!=1) {
            return Err(ENOTSUPP);
        }''',1)
    files['g16.rs']=s
    s=files['g16_runtime.rs']
    start=s.index('    pub(crate) fn submit_compute(')
    marker='    ) -> Result<Receipt> {'
    pos=s.index(marker,start)+len(marker)
    s=s[:pos]+'''
        // Native compute still has no source-integrated producer. Never
        // publish the donor compute ABI through this graphics experiment.
        if self.transport.native_t6040{return Err(ENOTSUPP);}
'''+s[pos:]
    s=s.replace('// This caller is compiled while BUNDLE_COMPLETE remains closed. Named Linux',
                '// This caller uses the explicit graphics experiment admission. Named Linux')
    files['g16_runtime.rs']=s
