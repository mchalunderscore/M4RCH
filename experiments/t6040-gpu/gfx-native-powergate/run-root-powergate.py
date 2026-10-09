#!/usr/bin/env python3
"""ONE cold no-work native powergate owner; no automatic powergate or restart."""
import hashlib
from pathlib import Path
import runpy
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'gfx-coordinate-native-status/run-root-native-status.py'
BASE_SHA = 'db99f8fbd4dfada557940be882b306f76fd6b5980c66392c15e44f2410585dc4'
sys.path.insert(0, str(HERE))


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Powergate cold insertion changed: ' + old[:100])
    return source.replace(old, new, 1)


def runner_source():
    if hashlib.sha256(BASE.read_bytes()).hexdigest() != BASE_SHA:
        raise ValueError('Frozen native STATUS cold runner changed')
    source = runpy.run_path(str(BASE))['runner_source']()
    source = source.replace('from gfx_native_status_contract import', 'from gfx_native_powergate_contract import')
    source = replace_once(source,
        'qualify_linux_dt, qualify_graph_startup\n',
        'qualify_linux_dt, qualify_graph_startup, qualify_powergate_startup, REFUSED_BOOT\n')
    source = replace_once(source, "parent/'run-native-status.py'", "parent/'run-powergate.py'")
    source = replace_once(source, "    power_off_scope = validate_receipt(receipt)\n    require(power_off_scope, 'Only the distinct power-off contract is admitted')\n    for name, expected",
        "    power_off_scope = validate_receipt(receipt)\n    require(power_off_scope, 'Only the distinct powergate contract is admitted')\n"
        "    require(sha((work/'asc-graph-init/graph-before.bin').read_bytes()) == receipt['graph_fixture_sha256'], 'Prepared graph fixture changed')\n"
        "    require(sha((work/'asc-graph-init/graph-receipt.json').read_bytes()) == receipt['graph_receipt_sha256'], 'Prepared graph receipt changed')\n    for name, expected")
    source = replace_once(source, "    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()\n",
        "    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()\n"
        "    require(boot != REFUSED_BOOT, 'Old terminal owner boot is refused; fresh normal boot required')\n")
    old = "        retained_graph=('m4rch recovery-session: resident=1 control_ready=1' in delta or 'm4rch recovery-session: diagnostic=1 sealed=1' in delta)\n"
    source = replace_once(source, old,
        "        powergate_startup = qualify_powergate_startup(delta, report, result.returncode, module_refcount)\n"
        "        retained_graph = powergate_startup is not None\n"
        "        report['native_powergate_startup'] = powergate_startup\n"
        "        report['dmesg_after_sha256'] = sha(logs.encode())\n"
        "        report['commands_admitted'] = powergate_startup['commands_admitted'] if retained_graph else []\n")
    source = replace_once(source, "        marker='m4rch gfx-native-coordinate: startup-retained result='\n",
        "        report['dmesg_before_sha256'] = sha(before_log.encode())\n"
        "        report['dmesg_after_sha256'] = sha(logs.encode())\n"
        "        unknown_records = [line for line in delta.splitlines() if 'm4rch gfx-native-powergate-startup-retained: ' in line]\n"
        "        if unknown_records:\n"
        "            report.update(stage='startup-outcome-unqualified',resident_session_active=False,diagnostic_session_active=False,commands_admitted=[],unloaded=False,reboot_required=True,startup_outcome_unknown=True,native_powergate_unknown_records=unknown_records)\n"
        "            (out/'attempt.json').write_text(json.dumps(report,indent=2)+'\\n')\n"
        "            os.sync()\n"
        "            print('Native powergate startup is unknown; preserve the owner and all resources. No typed commands, sampling, cleanup or retry.')\n"
        "            return\n"
        "        marker='m4rch gfx-native-coordinate: startup-retained result='\n")
    source = replace_once(source,
        "        resident=present and result.returncode==0 and 'm4rch recovery-session: resident=1 control_ready=1' in delta\n",
        "        resident=False\n")
    source = replace_once(source,
        "        report['diagnostic_session_active']=present and result.returncode==0 and 'm4rch recovery-session: diagnostic=1 sealed=1' in delta\n",
        "        report['diagnostic_session_active']=present and result.returncode==0 and bool(report.get('native_powergate_startup'))\n")
    source = source.replace(
        'Distinct retained coordinated execution profile. Healthy recovery permits another two idle cycles, native trace-off, then one immutable triangle. Failed idle recovery permits only diagnostics, one STOP and eligible no-work OFF. Work intent closes STOP/OFF and all later publication. No retirement/restart/unload proof.',
        'Distinct no-work native powergate profile. Only sample/gfx-snapshot and one combined gfx-powergate are admitted. Management ACK and checked CPU stop must precede paired OFF. Every terminal intent or unknown result seals the owner; backing remains pinned. No retirement/restart/unload proof.')
    source = source.replace(
        'Distinct coordinator retained. Inspect recovery result: healthy session may complete four idle cycles and trace-off before one triangle; failed recovery remains diagnostic with eligible no-work OFF. All backing pinned; no restart or unload.',
        'Native powergate owner retained. Only sample/gfx-snapshot and one combined gfx-powergate are admitted. All backing pinned; no restart or unload.')
    return source


exec(compile(runner_source(), str(BASE), 'exec'), globals())
