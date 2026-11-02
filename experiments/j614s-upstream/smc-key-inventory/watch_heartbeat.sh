#!/usr/bin/env bash
# Independent dead-man switch for a particular guarded workload.
set -Eeuo pipefail
pid=$1
trace=$2
report=$3
[[ $pid =~ ^[0-9]+$ && -f $trace && ! -e $report ]] || exit 2
while kill -0 "$pid" 2>/dev/null; do
    age=$(( $(date +%s) - $(stat -c %Y "$trace") ))
    if (( age > 5 )); then
        echo "Guard trace stale for ${age}s; stopping owned workload processes" > "$report"
        if [[ -r /proc/$pid/task/$pid/children ]]; then
            read -r -a children < "/proc/$pid/task/$pid/children" || true
            for child in "${children[@]}"; do
                [[ $child =~ ^[0-9]+$ ]] || continue
                kill -KILL -- "-$child" 2>/dev/null || kill -KILL "$child" 2>/dev/null || true
            done
        fi
        kill -TERM "$pid" 2>/dev/null || true
        exit 1
    fi
    sleep 1
done
