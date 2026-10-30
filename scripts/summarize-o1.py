#!/usr/bin/env python3
"""Validate and summarize the two recorded O1 runs; never edit raw evidence."""
import argparse
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
import shlex
import statistics
import sys


MIB = 1024 * 1024
COUNTERS = ("go_gc_cycles_total", "go_gc_cpu_seconds_total")
COUNTS = ("sent", "ok", "http_err", "timeout", "net_err", "dropped")
VALUES = ("ok_rps", "error_rate", "mean_ms", "p50_ms", "p90_ms", "p99_ms",
          "max_ms", "slo_good", "lag_p99_ms", "gen_cpu_pct")
SOURCES = ("meta.txt", "steps.csv", "metrics-start.txt", "metrics-end.txt",
           "rss-query.json", "rss-summary.json")
NOTES = [
    "Each GOGC condition has one recorded run, not repeated or randomized trials; differences are descriptive, not proof of causality or statistical significance.",
    "GC increments subtract each run's own metrics-start/end counters. run.sh snapshots enclose load generation, collector setup, request drain and the final one-second wait; this is not an exact 60-second counter window.",
    "Only meta.txt captures process configuration. Distinct PID/start identities and monotonic counters are consistent with separate processes, but there is no end-of-run configuration or complete proof against an intervening restart.",
    "go_gc_cpu_seconds_total is a runtime GC CPU-time estimate, not pause time or an OS measurement of process CPU time.",
    "RSS statistics are the mean and observed maximum of Prometheus query evaluations in [stage start+5s, stage end]. The 1-second query step does not establish the actual scrape interval or independent samples; repeated values are retained in the mean.",
    "Consecutive equal RSS values are also counted as one block. The block count is only a lower bound on underlying distinct observations/updates, not a count of statistically independent samples; equal values can originate from different scrapes.",
    "RSS observed maximum is not the instantaneous process high-water mark. Bytes are converted to MiB by division by 1048576.",
    "Client p99 covers the full 60-second stage and only successful requests, from scheduled send time through response completion. It already includes send lag; it is not the RSS 55-second window or GC pause latency.",
]


class EvidenceError(ValueError):
    """Missing, inconsistent or malformed experiment evidence."""


def number(value, label, *, integer=False, positive=False):
    if isinstance(value, bool):
        raise EvidenceError(f"{label}: boolean is not numeric evidence")
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise EvidenceError(f"{label}: expected number") from exc
    if not math.isfinite(result) or result < 0 or (positive and result <= 0):
        raise EvidenceError(f"{label}: expected finite {'positive' if positive else 'nonnegative'} number")
    if integer:
        if not result.is_integer():
            raise EvidenceError(f"{label}: expected integer")
        return int(result)
    return result


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise EvidenceError(f"{path}: cannot read JSON: {exc}") from exc


def read_meta(path, gogc):
    text = path.read_text(encoding="utf-8-sig")
    marker = "enrolld /config:\n"
    if marker not in text:
        raise EvidenceError(f"{path}: missing /config block")
    try:
        config = json.loads(text.split(marker, 1)[1])
    except ValueError as exc:
        raise EvidenceError(f"{path}: invalid /config JSON") from exc
    required = {"pid", "started", "gogc", "gomaxprocs", "go_version"}
    if not isinstance(config, dict) or not required.issubset(config):
        raise EvidenceError(f"{path}: incomplete process configuration")
    if number(config["gogc"], "config.gogc", integer=True) != gogc:
        raise EvidenceError(f"{path}: GOGC mismatch")
    if number(config["gomaxprocs"], "config.gomaxprocs", integer=True) != 1:
        raise EvidenceError(f"{path}: expected GOMAXPROCS=1")
    pid = number(config["pid"], "config.pid", integer=True, positive=True)
    try:
        started = dt.datetime.fromisoformat(config["started"])
        if started.utcoffset() is None:
            raise ValueError("missing timezone")
    except (ValueError, TypeError) as exc:
        raise EvidenceError(f"{path}: invalid process start time") from exc
    for pattern in (rf"^enrolld: pid {pid}，绑定的核 1$", r"^loadgen: 绑定的核 0$",
                    r"^接口: /api/report；SLO 阈值 0\.05s$"):
        if not re.search(pattern, text, re.MULTILINE):
            raise EvidenceError(f"{path}: missing expected affinity/interface evidence")
    commit = re.search(r"^仓库提交: ([0-9a-f]{7,40})，未提交的改动 (\d+) 处$", text, re.MULTILINE)
    command = re.search(r"^压测命令: (.+)$", text, re.MULTILINE)
    if not commit or not command:
        raise EvidenceError(f"{path}: missing source/command metadata")
    tokens = shlex.split(command[1])
    expected = ["bin/loadgen", "-url", "http://127.0.0.1:8080/api/report?mb=4",
                "-rates", "100", "-step", "60s"]
    if tokens != expected:
        raise EvidenceError(f"{path}: command differs from recorded 100-RPS 60s protocol")
    return {"config": config, "started_unix_s": started.timestamp(),
            "source_commit": commit[1], "uncommitted_paths_count": int(commit[2]),
            "loadgen_command": tokens, "service_cpus": "1", "loadgen_cpus": "0"}


def read_stage(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        required = {"step", "target_rps", "start_unix", "end_unix", *COUNTS, *VALUES}
        if not required.issubset(reader.fieldnames or []):
            raise EvidenceError(f"{path}: missing CSV columns")
        rows = [row for row in reader if row["step"] != "all"]
    if len(rows) != 1:
        raise EvidenceError(f"{path}: expected one formal stage")
    row = rows[0]
    stage = {key: number(row[key], key, integer=True) for key in ("start_unix", "end_unix")}
    stage["duration_s"] = stage["end_unix"] - stage["start_unix"]
    stage["target_rps"] = number(row["target_rps"], "target_rps", positive=True)
    if stage["duration_s"] != 60 or stage["target_rps"] != 100:
        raise EvidenceError(f"{path}: expected 60s at 100 RPS")
    client = {key: number(row[key], key, integer=True) for key in COUNTS}
    client.update({key: number(row[key], key) for key in VALUES})
    client.update({"codes": row.get("codes", ""), "warn": row.get("warn", "")})
    client["errors_total"] = sum(client[key] for key in ("http_err", "timeout", "net_err"))
    if client["sent"] <= 0 or client["ok"] <= 0:
        raise EvidenceError(f"{path}: no valid successful request measurements")
    if client["sent"] != client["ok"] + client["errors_total"]:
        raise EvidenceError(f"{path}: request counts do not balance")
    if abs(client["ok_rps"] - client["ok"] / 60) > 0.051:
        raise EvidenceError(f"{path}: successful RPS disagrees with count/duration")
    if abs(client["error_rate"] - client["errors_total"] / client["sent"]) > 0.000051:
        raise EvidenceError(f"{path}: error rate disagrees with counts")
    if client["error_rate"] > 1 or client["slo_good"] > 1:
        raise EvidenceError(f"{path}: invalid ratio")
    if not (client["p50_ms"] <= client["p90_ms"] <= client["p99_ms"] <= client["max_ms"]):
        raise EvidenceError(f"{path}: percentiles not ordered")
    return stage, client


def read_counters(path):
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    result = {}
    for name in COUNTERS:
        matches = [m[1] for line in lines if (m := re.fullmatch(re.escape(name) + r"\s+(\S+)(?:\s+\S+)?", line.strip()))]
        if len(matches) != 1:
            raise EvidenceError(f"{path}: missing/duplicate counter {name}")
        result[name] = number(matches[0], name, integer=name == COUNTERS[0])
    return result


def read_rss(directory, stage, gogc):
    query = read_json(directory / "rss-query.json")
    data = query.get("data", {})
    if query.get("status") != "success" or data.get("resultType") != "matrix":
        raise EvidenceError(f"{directory}: unsuccessful/non-matrix RSS query")
    series = data.get("result")
    if not isinstance(series, list) or len(series) != 1:
        raise EvidenceError(f"{directory}: expected exactly one RSS series")
    metric = series[0].get("metric", {})
    for key, value in {"__name__": "process_resident_memory_bytes", "job": "enrolld",
                       "instance": "127.0.0.1:8080"}.items():
        if metric.get(key) != value:
            raise EvidenceError(f"{directory}: RSS label {key} mismatch")
    samples = series[0].get("values")
    if not isinstance(samples, list) or len(samples) != 56:
        raise EvidenceError(f"{directory}: expected 56 RSS query evaluations")
    start, end = stage["start_unix"] + 5, stage["end_unix"]
    timestamps, values = [], []
    for offset, sample in enumerate(samples):
        if not isinstance(sample, list) or len(sample) != 2:
            raise EvidenceError(f"{directory}: malformed RSS sample")
        timestamp = number(sample[0], "RSS query timestamp")
        if timestamp != start + offset:
            raise EvidenceError(f"{directory}: RSS query timestamp outside exact 1s grid/window")
        timestamps.append(timestamp)
        values.append(number(sample[1], "RSS bytes", integer=True, positive=True))
    blocks = 1 + sum(a != b for a, b in zip(values, values[1:]))
    result = {"metric_labels": metric, "start_unix": start, "end_unix": end,
              "query_step_s": 1, "query_evaluations": len(values),
              "consecutive_value_blocks": blocks, "distinct_values": len(set(values)),
              "mean_bytes": statistics.mean(values), "observed_peak_bytes": max(values),
              "mean_mib": statistics.mean(values) / MIB, "observed_peak_mib": max(values) / MIB}
    existing = read_json(directory / "rss-summary.json")
    expected = {"gogc": gogc, "start_unix": start, "end_unix": end, "samples": len(values),
                "rss_mean_mib": result["mean_mib"], "rss_peak_mib": result["observed_peak_mib"]}
    for key, value in expected.items():
        recorded = number(existing.get(key), f"rss-summary.{key}")
        if not math.isclose(recorded, value, rel_tol=1e-12, abs_tol=1e-10):
            raise EvidenceError(f"{directory}: rss-summary.json disagrees with raw query: {key}")
    result["existing_summary_verified"] = True
    return result


def summarize_run(root, gogc):
    directory = root / f"runs/o1-gogc{gogc}"
    meta = read_meta(directory / "meta.txt", gogc)
    stage, client = read_stage(directory / "steps.csv")
    if meta["started_unix_s"] > stage["start_unix"]:
        raise EvidenceError(f"{directory}: process started after stage began")
    before, after = (read_counters(directory / name) for name in ("metrics-start.txt", "metrics-end.txt"))
    delta = {}
    for name in COUNTERS:
        if after[name] < before[name]:
            raise EvidenceError(f"{directory}: counter reset/backwards: {name}")
        delta[name] = after[name] - before[name]
    warnings = []
    if client["errors_total"] or client["dropped"] or client["warn"]:
        warnings.append("Failures/drops/loadgen warnings limit load comparability; inspect raw steps.csv.")
    return {"gogc": gogc, "evidence_directory": directory.relative_to(root).as_posix(),
            "meta": meta, "stage": stage, "client": client,
            "gc": {"start": before, "end": after, "delta": delta},
            "rss": read_rss(directory, stage, gogc), "warnings": warnings,
            "source_sha256": {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in SOURCES}}


def summarize(root):
    root = Path(root).resolve()
    runs = [summarize_run(root, gogc) for gogc in (100, 400)]
    first, second = runs
    exclusions = {"pid", "started", "gogc"}
    configs = [{k: v for k, v in run["meta"]["config"].items() if k not in exclusions} for run in runs]
    if configs[0] != configs[1]:
        raise EvidenceError("Service parameters/runtime differ between GOGC conditions")
    if first["meta"]["source_commit"] != second["meta"]["source_commit"]:
        raise EvidenceError("Source commits differ between GOGC conditions")
    identities = [(r["meta"]["config"]["pid"], r["meta"]["config"]["started"]) for r in runs]
    if identities[0] == identities[1]:
        raise EvidenceError("The two conditions have identical process identities")
    fields = {
        "gc_cycles_delta": ("gc", "delta", COUNTERS[0]),
        "gc_cpu_estimate_delta_s": ("gc", "delta", COUNTERS[1]),
        "rss_mean_mib": ("rss", "mean_mib"),
        "rss_observed_peak_mib": ("rss", "observed_peak_mib"),
        "client_p99_ms": ("client", "p99_ms"),
        "ok_rps": ("client", "ok_rps"),
    }
    differences = {}
    for name, keys in fields.items():
        a, b = first, second
        for key in keys:
            a, b = a[key], b[key]
        differences[name] = {"gogc100": a, "gogc400": b, "absolute_400_minus_100": b - a,
                             "percent_change_from_100": (b / a - 1) * 100 if a else None}
    return {"schema_version": 1, "conditions": [100, 400], "runs_per_condition": 1,
            "notes": NOTES, "runs": runs, "comparison_400_vs_100": differences}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out", type=Path, help="new derived JSON file; default stdout")
    args = parser.parse_args()
    try:
        result = summarize(args.repo_root)
        payload = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.out:
            with args.out.open("x", encoding="utf-8", newline="") as output:
                output.write(payload)
        else:
            sys.stdout.write(payload)
    except (EvidenceError, OSError, TypeError, KeyError) as exc:
        print(f"summarize-o1: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
