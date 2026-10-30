#!/usr/bin/env python3
"""Synthetic fixtures only: no experiment measurements or services are created."""
import csv
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location("summarize_o1", Path(__file__).with_name("summarize-o1.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="o1-synthetic-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.a = self.fixture(100, 1000, 6000, 6)
        self.b = self.fixture(400, 1200, 1500, 3)

    @staticmethod
    def write_json(path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def fixture(self, gogc, start, cycles, p99):
        directory = self.root / f"runs/o1-gogc{gogc}"
        directory.mkdir(parents=True)
        config = {"addr": "127.0.0.1:8080", "work": 200000, "pool": 4, "db_ms": 10,
                  "data": "data", "go_version": "synthetic", "gomaxprocs": 1,
                  "gogc": str(gogc), "pid": gogc + 10,
                  "started": dt.datetime.fromtimestamp(start - 20, dt.timezone.utc).isoformat()}
        meta = (f"enrolld: pid {config['pid']}，绑定的核 1\nloadgen: 绑定的核 0\n"
                "接口: /api/report；SLO 阈值 0.05s\n仓库提交: dab739e，未提交的改动 5 处\n"
                "压测命令: bin/loadgen '-url' 'http://127.0.0.1:8080/api/report?mb=4' '-rates' '100' '-step' '60s'\n"
                "enrolld /config:\n" + json.dumps(config) + "\n")
        (directory / "meta.txt").write_text(meta, encoding="utf-8")
        row = {"step": "1", "target_rps": 100, "start_unix": start, "end_unix": start + 60,
               "sent": 6000, "ok": 6000, "http_err": 0, "timeout": 0, "net_err": 0,
               "dropped": 0, "ok_rps": 100, "error_rate": 0, "mean_ms": 2, "p50_ms": 1,
               "p90_ms": 2, "p99_ms": p99, "max_ms": 10, "slo_good": 1,
               "lag_p99_ms": 1, "gen_cpu_pct": 3, "codes": "", "warn": ""}
        with (directory / "steps.csv").open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=row)
            writer.writeheader()
            writer.writerow(row)
            writer.writerow({**row, "step": "all", "target_rps": ""})
        for name, count, cpu in (("metrics-start.txt", 200, 0.1), ("metrics-end.txt", 200 + cycles, 2.1 if gogc == 100 else .6)):
            (directory / name).write_text(f"go_gc_cycles_total {count}\ngo_gc_cpu_seconds_total {cpu}\n", encoding="utf-8")
        rss = (10 if gogc == 100 else 20) * MODULE.MIB
        values = [[start + 5 + i, str(rss if i < 28 else rss + MODULE.MIB)] for i in range(56)]
        query = {"status": "success", "data": {"resultType": "matrix", "result": [{"metric": {
            "__name__": "process_resident_memory_bytes", "job": "enrolld", "instance": "127.0.0.1:8080"}, "values": values}]}}
        self.write_json(directory / "rss-query.json", query)
        self.write_json(directory / "rss-summary.json", {"gogc": gogc, "start_unix": start + 5,
                        "end_unix": start + 60, "samples": 56,
                        "rss_mean_mib": rss / MODULE.MIB + .5, "rss_peak_mib": rss / MODULE.MIB + 1})
        return directory

    def mutate_query(self, callback):
        path = self.a / "rss-query.json"
        data = json.loads(path.read_text())
        callback(data)
        self.write_json(path, data)

    def test_differences_units_counter_windows_and_raw_unchanged(self):
        hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob("*") if p.is_file()}
        result = MODULE.summarize(self.root)
        a, b = result["runs"]
        self.assertEqual(a["gc"]["delta"]["go_gc_cycles_total"], 6000)
        self.assertEqual(b["gc"]["delta"]["go_gc_cycles_total"], 1500)
        self.assertEqual(a["gc"]["delta"]["go_gc_cpu_seconds_total"], 2)
        self.assertEqual(a["rss"]["mean_mib"], 10.5)
        self.assertEqual(a["rss"]["observed_peak_mib"], 11)
        self.assertEqual(a["rss"]["query_evaluations"], 56)
        self.assertEqual(a["rss"]["consecutive_value_blocks"], 2)
        self.assertEqual(result["comparison_400_vs_100"]["gc_cycles_delta"]["percent_change_from_100"], -75)
        self.assertEqual(result["comparison_400_vs_100"]["client_p99_ms"]["percent_change_from_100"], -50)
        self.assertEqual(json.dumps(result, sort_keys=True), json.dumps(MODULE.summarize(self.root), sort_keys=True))
        self.assertTrue(all(hashlib.sha256(p.read_bytes()).hexdigest() == h for p, h in hashes.items()))

    def test_missing_duplicate_reset_and_nonfinite_counters(self):
        path = self.a / "metrics-end.txt"
        for text in ("go_gc_cycles_total 9999\n", "go_gc_cycles_total 9999\ngo_gc_cycles_total 9999\ngo_gc_cpu_seconds_total 1\n",
                     "go_gc_cycles_total 100\ngo_gc_cpu_seconds_total 1\n", "go_gc_cycles_total 9999\ngo_gc_cpu_seconds_total NaN\n",
                     "go_gc_cycles_total 9999\ngo_gc_cpu_seconds_total 0.01\n"):
            with self.subTest(text=text):
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(MODULE.EvidenceError):
                    MODULE.summarize(self.root)

    def test_rss_labels_multiple_series_and_grid_rejected(self):
        path = self.a / "rss-query.json"
        original = path.read_text()
        for callback in (lambda q: q["data"]["result"][0]["metric"].update(job="wrong"),
                         lambda q: q["data"]["result"].append(q["data"]["result"][0]),
                         lambda q: q["data"]["result"][0]["values"][0].__setitem__(0, 1004),
                         lambda q: q["data"]["result"][0]["values"][1].__setitem__(0, 1005),
                         lambda q: q["data"]["result"][0]["values"][0].__setitem__(1, "Infinity")):
            path.write_text(original, encoding="utf-8")
            self.mutate_query(callback)
            with self.assertRaises(MODULE.EvidenceError):
                MODULE.summarize(self.root)

    def test_existing_rss_summary_must_match_raw(self):
        path = self.a / "rss-summary.json"
        summary = json.loads(path.read_text())
        summary["rss_mean_mib"] += 1
        self.write_json(path, summary)
        with self.assertRaisesRegex(MODULE.EvidenceError, "disagrees with raw query"):
            MODULE.summarize(self.root)

    def test_service_configuration_comparability(self):
        path = self.b / "meta.txt"
        path.write_text(path.read_text(encoding="utf-8").replace('"pool": 4', '"pool": 8'), encoding="utf-8")
        with self.assertRaisesRegex(MODULE.EvidenceError, "parameters/runtime differ"):
            MODULE.summarize(self.root)

    def test_request_count_balance_and_protocol(self):
        path = self.a / "steps.csv"
        original = path.read_text()
        path.write_text(original.replace(",6000,6000,", ",6001,6000,"), encoding="utf-8")
        with self.assertRaisesRegex(MODULE.EvidenceError, "counts do not balance"):
            MODULE.summarize(self.root)
        path.write_text(original.replace(",100,1000,1060,", ",100,1000,1061,"), encoding="utf-8")
        with self.assertRaisesRegex(MODULE.EvidenceError, "60s at 100 RPS"):
            MODULE.summarize(self.root)


if __name__ == "__main__":
    unittest.main()
