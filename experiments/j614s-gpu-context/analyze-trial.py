#!/usr/bin/env python3
"""Summarize the trial without treating overlap or changed bytes as preemption."""
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: analyze-trial.py RESULT_DIRECTORY')
root = Path(sys.argv[1])
summary = re.compile(r'm4gpu: phase=(before|after) pid=(\d+) ctx=(\d+) qid=(\d+) seq=(\d+) region=(\w+) words=(\d+) nonzero=(\d+) digest=([0-9a-f]+)')
regions = {}
for line in (root / 'buffer-summaries.log').read_text().splitlines():
    m = summary.search(line)
    if m:
        phase, pid, ctx, qid, seq, region, words, nonzero, digest = m.groups()
        key = (pid, ctx, qid, seq, region)
        regions.setdefault(key, {})[phase] = (words, nonzero, digest)
pairs = [(key, x['before'], x['after']) for key, x in regions.items()
         if 'before' in x and 'after' in x]
changed = [(key, a, b) for key, a, b in pairs if a[2] != b[2]]
print(f'Comparable idle-boundary region summaries: {len(pairs)}; changed: {len(changed)}')
for key, before, after in changed:
    _, ctx, qid, seq, region = key
    print(f'  ctx={ctx} qid={qid} seq={seq} region={region} nonzero={before[1]}->{after[1]}')

target_queues = {(int(key[1]), int(key[2])) for key in regions}

marker = re.compile(r'M4GPU phase=(\w+) control=(\d+) round=(\d+)')
complete = re.compile(r'asahi_g17_complete:.*qid=(\d+).*ctx=(\d+).*gpu=(\d+)\.\.(\d+)')
cases = []
current = None
for line in (root / 'trace.log').read_text().splitlines():
    m = marker.search(line)
    if m:
        phase, control, round_ = m.groups()
        key = (int(control), int(round_))
        if phase == 'begin':
            current = {'key': key, 'events': [], 'phases': []}
            cases.append(current)
        if current is not None and key == current['key']:
            current['phases'].append(phase)
        continue
    m = complete.search(line)
    if m and current is not None:
        qid, context, start, end = map(int, m.groups())
        if (context, qid) in target_queues:
            current['events'].append((qid, context, start, end))
# The workload calibrates with the background queue alone before the first
# round marker. Changes in this interval are not evidence of interference by
# its later competing queue.
calibration = set()
for line in (root / 'trace.log').read_text().splitlines():
    if 'M4GPU phase=begin' in line:
        break
    m = re.search(r'asahi_g17_complete:.*qid=(\d+).*ctx=(\d+).*seq=(\d+)', line)
    if m:
        qid, context, seq = m.groups()
        calibration.add((context, qid, seq))
solo = [(key, before, after) for key, before, after in changed
        if (key[1], key[2], key[3]) in calibration]
print(f'Changed regions during solo calibration, before the contender: {len(solo)}')
print('Solo-calibration regions:', ', '.join(sorted({key[4] for key, _, _ in solo})) or 'none')

considered = inside = 0
for case in cases:
    if 'contender_submit' not in case['phases']:
        continue
    groups = {}
    for qid, context, start, end in case['events']:
        groups.setdefault((qid, context), []).append((start, end))
    longest = sorted(((max(v, key=lambda x: x[1] - x[0]), k) for k, v in groups.items()),
                     key=lambda x: x[0][1] - x[0][0], reverse=True)
    if len(longest) < 2:
        continue
    (a, b), _ = longest[0]
    (c, d), _ = longest[1]
    considered += 1
    inside += a <= c <= d <= b
    print(f"control={case['key'][0]} round={case['key'][1]} candidate GPU interval inside background: {a <= c <= d <= b}")
print(f'Comparable GPU time intervals: {considered}; nested: {inside}')
print('INCONCLUSIVE for preemption: overlap and buffer changes can have other causes.')
if not pairs:
    raise SystemExit('No comparable buffer snapshots: instrumentation did not capture a usable before/after pair.')
