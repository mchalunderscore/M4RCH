# SPDX-License-Identifier: GPL-2.0-only
"""Read-only transformations of the completed native PWRGATE wrappers."""
import hashlib
from pathlib import Path

FROZEN = Path(__file__).resolve().parent.parent / 'gfx-native-powergate'


def source(name, expected, changes):
    path = FROZEN / name
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('Frozen powergate wrapper changed: ' + str(path))
    text = raw.decode()
    for old, new, count in changes:
        if text.count(old) != count:
            raise ValueError('Drain wrapper insertion changed: ' + old[:80])
        text = text.replace(old, new)
    return text


def execute(name, expected, changes, namespace):
    text = source(name, expected, changes)
    exec(compile(text, str(FROZEN / name), 'exec'), namespace)
