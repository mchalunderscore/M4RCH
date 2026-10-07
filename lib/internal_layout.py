"""Explicit receipt extension for the owner's completed NVMe reservation.

Preserves the original stub creation plan. The extension only admits the two
known Linux partitions and the authorized smaller macOS physical store.
"""
import copy
import hashlib
import json
from pathlib import Path
import internal_disk

ESP_UUID = '5FDB35C6-3A66-416D-8358-6555FD99FCC5'
ROOT_UUID = 'E80EE324-C4C5-4F3E-81B7-464ADB71D41A'
EXPECTED = {
    ESP_UUID: ('EFI', 362525229056, 1073741824),
    ROOT_UUID: ('Linux Filesystem', 363598970880, 126880841728),
}


def receipt_hash(receipt):
    return hashlib.sha256(json.dumps(receipt,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def extend(dutil, receipt):
    current,_ = internal_disk._snapshot(dutil)
    plan = copy.deepcopy(receipt['plan'])
    if current['disk'] != plan['disk']:
        raise ValueError('Internal SSD identity changed')
    main = current['main']
    if main['current_bytes'] != 361999998976:
        raise ValueError('Unexpected authorized macOS store size')
    for key in ('container_uuid','store_uuid','system_uuid','data_uuid','vgid'):
        if main[key] != plan['main'][key]:
            raise ValueError('Original macOS identity changed')
    plan['main']['target_bytes'] = main['current_bytes']
    for uuid,expected in EXPECTED.items():
        found = [p for p in current['partitions'] if p['uuid']==uuid]
        if len(found)!=1 or tuple(found[0][key] for key in ('content','offset','bytes'))!=expected:
            raise ValueError('NVMe partition does not match the authorized reservation')
        plan['partitions'].append(found[0])
    result = {**receipt,'plan':plan}
    internal_disk.validate_created(dutil,result)
    return {'schema':1,'base_receipt_sha256':receipt_hash(receipt),'receipt':result}


def resolve(dutil, original, path):
    value = json.loads(Path(path).read_text())
    if (value.get('schema')!=1 or value.get('base_receipt_sha256')!=receipt_hash(original)
            or value.get('receipt')!=extend(dutil,original)['receipt']):
        raise ValueError('Internal layout extension no longer matches the original receipt and current layout')
    return internal_disk.validate_created(dutil,value['receipt'])
