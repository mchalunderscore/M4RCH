# SPDX-License-Identifier: GPL-2.0-only
"""Exact fresh OF layout after a separately inspected reserved-flash relocation."""
import copy
import hashlib
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BASE_KIT = HERE.parent
sys.path.insert(0, str(BASE_KIT / 'gfx-native-coordinate-trial'))
import gfx_coordinate_contract as frozen
from linux_dt_contract import encoded_layout

CONTRACT = copy.deepcopy(frozen.CONTRACT)
LINUX_DT_SHA = 'e2adc89815e82eba3b67b3d0b466d1c1d4a47ba94f7acbe18773403952de5759'
CONTRACT['linux_dt_layout_sha256'] = LINUX_DT_SHA
qualify_adt = frozen.qualify_adt
qualify_graph_startup = frozen.qualify_graph_startup
qualify_startup_retention = frozen.qualify_startup_retention


def qualify_linux_dt(base='/sys/firmware/devicetree/base'):
    expected = (HERE / 'linux-dt-contract.json').read_bytes()
    frozen.require(hashlib.sha256(expected).hexdigest() == LINUX_DT_SHA,
                   'Fresh layout contract changed')
    frozen.require(encoded_layout(base) == expected,
                   'Fresh Linux OF layout differs; inspect before hardware')


def validate_receipt(receipt):
    trial = receipt.get('graph_recovery_trial', {})
    if 'gfx_coordinated_power_off_scope' not in trial:
        return False
    frozen.require(trial['gfx_coordinated_power_off_scope'] == CONTRACT,
                   'Wrong inspected fresh-layout scope')
    view = copy.deepcopy(receipt)
    view['graph_recovery_trial']['gfx_coordinated_power_off_scope'] = frozen.CONTRACT
    return frozen.validate_receipt(view)
