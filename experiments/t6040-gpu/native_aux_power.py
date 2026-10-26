"""Pinned native CS/AFR performance tables for the captured T6040 board.

This is an offline initializer. Auxiliary domains keep their own ADT state
counts and caps; the main GPU profile's experimental cap is independent.
"""
import hashlib
import struct

from adt import parse


NATIVE_SPANS = (
    (0x896ef08, 0x896ef74, '496ecb15f470be0c380d619a1ba98173ee30e0dcb3c45cab7decd9a9f72a236d'),
    (0x8972024, 0x89720b8, 'dc39af3a9438e65d7020e844f8735891c5d1f10729ce1768242ba0a28e7f004c'),
    (0x897218c, 0x89722c0, '439933112d9a5584e4b6579e7f65c86fe2983a33dcd07ac1dc6b3ac7fb531573'),
    (0x89ac470, 0x89ac4e8, '55a60b253a68b683040dd6b06ef47c28cf550438f72ad9bb8e35d6e9aa9cc1bc'),
    (0x89e7df4, 0x89e7e40, '158b20466355a37e6ce264f03ec65100592f095eccd56674f1e1830f6e0328fb'),
    (0x89cb240, 0x89cb440, 'a9f4d8be0a52c6592945496dbc54dfdb5b7ff77d7ebde9b5abc3ce365eefd776'),
)


def prepare_auxiliary(adt_bytes, native_reader_callable):
    """Return hardware-relative u32 fields and a numeric provenance report.

    The caller supplies its full-file-hash-qualified native reader accepting
    image-relative virtual addresses, and must require the destination blocks
    to be fresh zero before applying the returned fields.
    """
    native = native_reader_callable
    digest = lambda b: hashlib.sha256(b).hexdigest()
    for begin, end, expected in NATIVE_SPANS:
        assert digest(native(begin, end-begin)) == expected, hex(begin)
    assert native(0x713429f, 31) == b'cs-perf-states\0afr-perf-states\0'
    assert struct.unpack('<3Q', native(0x712e058, 24)) == (0x196d0, 0x1a760, 0x1a8a8)
    # AGXAcceleratorG16X's actual getPerfStateCap vtable target.
    encoded_cap = struct.unpack('<Q', native(0x7eaf558, 8))[0]
    assert 0x7004000 + (encoded_cap & 0xffffffff) == 0x89e7df4
    tree = parse(adt_bytes)
    assert int.from_bytes(tree['/device-tree/chosen']['chip-id'], 'little') == 0x6040
    sgx = tree['/device-tree/arm-io/sgx']
    assert int.from_bytes(sgx['has-kf'], 'little') == 1
    fields = {}
    domains = []
    for domain, name, base, accelerator_offset, host_cap in (
            (1, 'cs-perf-states', 0x1a48, 0x1a760, 0xbcc),
            (2, 'afr-perf-states', 0x1b90, 0x1a8a8, 0xbd0)):
        raw = sgx[name]
        table_count, state_count = struct.unpack_from('<2Q', raw)
        # Narrow this candidate to the observed board, without fabricating a
        # second cluster or importing the main profile's sixteen-row policy.
        assert table_count == 1 and state_count == 8, name
        assert len(raw) == 16 + table_count*(16*state_count + 8), name
        entries = [struct.unpack_from('<2Q', raw, 16+16*i)
                   for i in range(state_count)]
        sram_floor_uv = struct.unpack_from('<Q', raw, 16+16*state_count)[0]
        assert all(0 < uv < 2000000 and 0 < hz < 2**32 for uv, hz in entries)
        assert 0 < sram_floor_uv < 2000000
        assert all(entries[i][1] < entries[i+1][1] for i in range(state_count-1))
        for offset in range(base, base+0x148, 4):
            fields[offset] = 0
        cap = state_count-1
        fields[base] = cap
        fields[base+4] = cap
        rows = []
        for i, (uv, hz) in enumerate(entries):
            core_mv = uv//1000
            sram_mv = max(core_mv, sram_floor_uv//1000)
            fields[base+8+i*4] = hz//1000000
            fields[base+0x48+i*8] = core_mv
            fields[base+0xc8+i*8] = sram_mv
            rows.append(dict(index=i, frequency_hz=hz, frequency_mhz=hz//1000000,
                             core_microvolt=uv, core_millivolt=core_mv,
                             sram_millivolt=sram_mv))
        domains.append(dict(domain=domain, adt_property=name, adt_property_sha256=digest(raw),
                            table_count=table_count, state_count=state_count,
                            accelerator_count_offset=hex(accelerator_offset),
                            host_cap_offset=hex(host_cap), hardware_base=hex(base),
                            maximum_state=cap, cap=cap, sram_floor_microvolt=sram_floor_uv,
                            rows=rows, unused_columns_and_rows='zero'))
    report = dict(schema='m4rch-native-aux-power-v1', adt_sha256=digest(adt_bytes),
                  board_chip_id='0x6040', board_has_kf=1,
                  native_cap_vtable_entry='0x7eaf558', native_cap_vtable_encoded=hex(encoded_cap),
                  native_cap_target='0x89e7df4',
                  native_spans=[dict(begin=hex(a), end=hex(b), sha256=h) for a,b,h in NATIVE_SPANS],
                  domains=domains,
                  policy='Each auxiliary maximum and cap is its own ADT state_count minus one. Main GPU cap is independent; firmware clamps requested auxiliary state to the auxiliary cap.',
                  native_feature_gates={'CS': 'accelerator+0x509 bit0', 'AFR': 'accelerator+0x50a bit0'},
                  qualification='has-kf is a board guard, not an asserted alias of the two native capability bytes. Captured CS/AFR ADT ladders supply both enabled-domain native blocks.',
                  destination_requirement='Both 0x148-byte blocks must be fresh zero before applying fields.')
    return fields, report
