#!/usr/bin/env bash
# Group 16 leader baseline. Preserve all command output; never overwrite a run.
set -euo pipefail
export LC_ALL=C S_TIME_FORMAT=ISO TZ=UTC
cd "${LAB2_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
run="runs/task0-$(date -u +%Y%m%dT%H%M%SZ)"
[[ ! -e $run ]]
mkdir -p "$run" data
cleanup() { for pid in "${vm_pid:-}" "${io_pid:-}"; do [[ -z $pid ]] || kill "$pid" 2>/dev/null || true; done; }
trap cleanup EXIT
if pgrep -x enrolld >/dev/null || pgrep -x loadgen >/dev/null; then
  echo 'An experiment is already running; stop and coordinate before baseline.' >&2
  exit 1
fi
fstype=$(findmnt -n -o FSTYPE -T data)
[[ $fstype != tmpfs && $fstype != ramfs ]]
source=$(findmnt -n -o SOURCE -T data)
source=${source%%\[*}
[[ -b $source ]]
parent=$(lsblk -n -o PKNAME "$source" | head -n 1)
disk=${parent:-$(basename "$source")}
printf '%s\n' "$disk" > "$run/disk.txt"
{
  printf 'UTC: '; date -u --iso-8601=seconds
  printf 'Asia/Shanghai: '; TZ=Asia/Shanghai date --iso-8601=seconds
  printf 'Repository commit: '; git rev-parse HEAD
  printf '\n$ lscpu\n'; lscpu
  printf '\n$ lscpu -e\n'; lscpu -e
  printf '\n$ free -m\n'; free -m
  printf '\n$ uname -r\n'; uname -r
  printf '\n$ cat /etc/os-release\n'; cat /etc/os-release
  printf '\n$ findmnt -T data\n'; findmnt -T data
  printf '\n$ lsblk -o NAME,TYPE,SIZE,FSTYPE,MOUNTPOINTS\n'; lsblk -o NAME,TYPE,SIZE,FSTYPE,MOUNTPOINTS
  printf '\n$ go version\n'; go version
  printf '\n$ tools/prometheus --version\n'; if [[ -x tools/prometheus ]]; then tools/prometheus --version; else echo 'Not installed at baseline time; see tools-verification.txt recorded after download'; fi
  printf '\n$ tools/node_exporter --version\n'; if [[ -x tools/node_exporter ]]; then tools/node_exporter --version; else echo 'Not installed at baseline time; see tools-verification.txt recorded after download'; fi
  printf '\n$ iostat -V\n'; iostat -V
  printf '\n$ vmstat -V\n'; vmstat -V
  printf '\n$ ps -eo pid,comm,args (experiment processes only)\n'
  ps -eo pid,comm,args | grep -E '[e]nrolld|[l]oadgen|[p]rometheus|[n]ode_exporter' || true
} > "$run/meta.txt" 2>&1
for i in 1 2 3; do
  bin/enrolld -bench-fsync 2000 > "$run/fsync-$i.txt" 2>&1
done
vmstat -w -t 1 13 > "$run/idle-vmstat.log" &
vm_pid=$!
iostat -dx -t "$disk" 1 13 > "$run/idle-iostat.log" &
io_pid=$!
wait "$vm_pid" "$io_pid"
capture_load() {
  local label=$1 count=$2 start end
  vmstat -w -t 1 > "$run/$label-vmstat.log" & vm_pid=$!
  iostat -dx -t "$disk" 1 > "$run/$label-iostat.log" & io_pid=$!
  sleep 1
  start=$(date +%s.%N)
  bin/enrolld -bench-fsync "$count" > "$run/$label-bench.txt" 2>&1
  end=$(date +%s.%N)
  printf '%s\t%s\t%s\t%s\n' "$label" "$count" "$start" "$end" >> "$run/load-windows.tsv"
  sleep 1
  kill "$vm_pid" "$io_pid" 2>/dev/null || true
  wait "$vm_pid" "$io_pid" 2>/dev/null || true
}
printf 'phase\tfsync_count\tstart_epoch\tend_epoch\n' > "$run/load-windows.tsv"
capture_load fsync5000 5000
read -r label count start end < <(tail -n 1 "$run/load-windows.tsv")
extended=$(python3 - "$start" "$end" <<'PY'
import math, sys
duration = float(sys.argv[2]) - float(sys.argv[1])
print(min(2_000_000, max(5000, math.ceil(5000 * 16 / duration))) if duration < 10 else 0)
PY
)
if (( extended > 0 )); then
  capture_load fsync-extended "$extended"
fi
cat > "$run/commands.txt" <<EOF
Working directory: $PWD
LC_ALL=C S_TIME_FORMAT=ISO TZ=UTC
bin/enrolld -bench-fsync 2000 (three consecutive invocations; fsync-1/2/3.txt)
vmstat -w -t 1 13 (idle-vmstat.log)
iostat -dx -t $disk 1 13 (idle-iostat.log)
vmstat -w -t 1 (each loaded phase)
iostat -dx -t $disk 1 (each loaded phase)
bin/enrolld -bench-fsync 5000 (fsync5000-bench.txt)
If 5000 operations take <10 seconds, an explicitly labelled longer run is added.
Exact counts/start/end timestamps are preserved in load-windows.tsv.
Exclude the initial boot-average report and partial boundary intervals in analysis.
No HTTP/monitoring service or concurrent loadgen was running during these baselines.
EOF
sha256sum "$run"/*.txt "$run"/*.log "$run"/*.tsv > "$run/SHA256SUMS"
printf 'TASK0_RUN=%s\n' "$run"
cat "$run"/fsync-{1,2,3}.txt
cat "$run/load-windows.tsv"
