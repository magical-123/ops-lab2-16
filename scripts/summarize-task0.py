#!/usr/bin/env python3
"""Derive task-0 summaries without modifying any captured command output."""
import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import statistics
from pathlib import Path


def vmstat(path):
    rows, header = [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if parts[:2] == ["r", "b"]:
            header = parts[:-1]
        elif header and parts and parts[0].isdigit() and len(parts) == len(header) + 2:
            row = dict(zip(header, map(float, parts[:-2])))
            row["timestamp"] = "T".join(parts[-2:]) + "+00:00"
            rows.append(row)
    return rows[1:]  # First report is the cumulative average since boot.


def iostat(path, disk):
    rows, header, timestamp = [], None, None
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d{4}", line.strip()):
            timestamp = dt.datetime.fromisoformat(line.strip()).isoformat()
        elif parts[:1] == ["Device"]:
            header = parts[1:]
        elif header and parts[:1] == [disk]:
            assert len(parts) == len(header) + 1
            row = dict(zip(header, map(float, parts[1:])))
            row["timestamp"] = timestamp
            rows.append(row)
    return rows[1:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    run = args.run
    for manifest in run.rglob("SHA256SUMS*"):
        for line in manifest.read_text().splitlines():
            digest, name = line.split(maxsplit=1)
            assert hashlib.sha256((manifest.parent / Path(name).name).read_bytes()).hexdigest() == digest, name
    disk = (run / "disk.txt").read_text().strip()
    with (run / "load-windows.tsv").open() as f:
        windows = list(csv.DictReader(f, delimiter="\t"))
    window = windows[-1]
    phase = window["phase"]
    start, end = float(window["start_epoch"]), float(window["end_epoch"])

    def full_intervals(rows):
        # Printed timestamps have only second precision. Conservatively exclude
        # intervals that could overlap either boundary under any subsecond offset.
        return [row for row in rows
                if dt.datetime.fromisoformat(row["timestamp"]).timestamp() - 1 >= start
                and dt.datetime.fromisoformat(row["timestamp"]).timestamp() + 1 <= end]

    groups = {
        "idle_vmstat": vmstat(run / "idle-vmstat.log"),
        "idle_iostat": iostat(run / "idle-iostat.log", disk),
        "load_vmstat": full_intervals(vmstat(run / f"{phase}-vmstat.log")),
        "load_iostat": full_intervals(iostat(run / f"{phase}-iostat.log", disk)),
    }
    assert all(len(rows) >= 5 for rows in groups.values()), "Not enough full intervals"
    means = [float(re.search(r"mean ([0-9.]+)", (run / f"fsync-{i}.txt").read_text(encoding="utf-8")).group(1))
             for i in (1, 2, 3)]
    mean = statistics.mean(means)
    result = {"phase": phase, "fsync_means_ms": means, "fsync_mean_ms": mean,
              "serial_fsync_per_s": 1000 / mean,
              "mean_range_ms": max(means) - min(means),
              "mean_range_pct": (max(means) - min(means)) / mean * 100,
              "load_duration_s": end - start, "groups": {}}
    for name, rows in groups.items():
        result["groups"][name] = {
            "samples": len(rows), "first_timestamp": rows[0]["timestamp"],
            "last_timestamp": rows[-1]["timestamp"],
            "mean": {key: statistics.mean(row[key] for row in rows)
                     for key in rows[0] if key != "timestamp"}}
        if name.endswith("iostat"):
            result["groups"][name]["io_weighted_ms"] = {
                latency: (sum(row[latency] * row[rate] for row in rows)
                          / sum(row[rate] for row in rows))
                if sum(row[rate] for row in rows) else None
                for latency, rate in (("w_await", "w/s"), ("f_await", "f/s"))}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
