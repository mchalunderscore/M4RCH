#!/bin/bash
set -Eeuo pipefail
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_dir=$(cd -- "$source_dir/../.." && pwd)
trial_dir="${M4_GPU_TRIAL_DIR:-$repo_dir/cache/gpu-context-trial}"
expected_release=7.3.0-1-14-gpuobs
if [[ $(uname -r) != "$expected_release" ]]; then
  echo "Refusing: boot $expected_release before running the instrumented workload." >&2
  exit 1
fi
param=/sys/module/aurora/parameters/m4_context_pid
[[ -f $param ]] || { echo 'Instrumented GPU parameter is missing.' >&2; exit 1; }
[[ $(sudo -n cat "$param") == 0 ]] || { echo 'Another GPU observation is active.' >&2; exit 1; }
uid=$(id -u)
gid=$(id -g)
result=$(mktemp -d "$trial_dir/result.XXXXXX")
chmod 700 "$result"
inst="/sys/kernel/tracing/instances/m4gpu-$BASHPID"
sudo -n mkdir "$inst"
cleanup() {
  printf '0' | sudo -n tee "$param" >/dev/null || true
  printf '0' | sudo -n tee "$inst/tracing_on" >/dev/null || true
  sudo -n rmdir "$inst" || true
}
trap cleanup EXIT
printf '4096' | sudo -n tee "$inst/buffer_size_kb" >/dev/null
for event in asahi_g17_publish asahi_g17_complete; do
  printf 'engine == 1' | sudo -n tee "$inst/events/asahi_g17/$event/filter" >/dev/null
  printf '1' | sudo -n tee "$inst/events/asahi_g17/$event/enable" >/dev/null
done
printf '1' | sudo -n tee "$inst/tracing_on" >/dev/null
set +e
timeout 40s sudo -n bash -c '
  inst=$1; param=$2; result=$3; uid=$4; gid=$5; program=$6; shader=$7
  printf "%s\n" "$$" > "$result/workload.pid"
  printf "%s" "$$" > "$param"
  exec 3>"$inst/trace_marker"
  exec setpriv --reuid="$uid" --regid="$gid" --init-groups env HOME=/home/michal M4_GPU_TRACE_FD=3 "$program" "$shader"
' -- "$inst" "$param" "$result" "$uid" "$gid" "$trial_dir/gpu-live-marker" "$trial_dir/live-marker.spv" > "$result/workload.log" 2>&1
workload_status=$?
set -e
printf '0' | sudo -n tee "$param" >/dev/null
printf '0' | sudo -n tee "$inst/tracing_on" >/dev/null
sudo -n cat "$inst/trace" > "$result/trace.log"
if [[ -s $result/workload.pid ]]; then
  pid=$(cat "$result/workload.pid")
  sudo -n journalctl -k -b --no-pager | grep -F "m4gpu: " | grep -F "pid=$pid " > "$result/buffer-summaries.log" || true
fi
printf 'exit_status=%s\nboot_id=' "$workload_status" > "$result/identity.txt"
cat /proc/sys/kernel/random/boot_id >> "$result/identity.txt"
printf 'Result directory: %s\n' "$result"
printf 'Workload status: %s\n' "$workload_status"
tail -4 "$result/workload.log"
printf 'Buffer summary lines: '
if [[ ! -f $result/buffer-summaries.log ]]; then
  echo 'No workload identity was recorded.' >&2
  exit 1
fi
wc -l < "$result/buffer-summaries.log"
if (( workload_status != 0 )); then exit "$workload_status"; fi
python "$source_dir/analyze-trial.py" "$result"
