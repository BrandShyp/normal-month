"""Command line: python -m normal_month data.csv

The CSV needs three columns: area, month (YYYY-MM) and count. Missing area-months
count as zero.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from typing import Dict, List, Tuple

from . import SIGMA, check_latest


def load(path: str) -> Tuple[List[str], Dict[str, List[int]]]:
    raw: Dict[str, Dict[str, int]] = defaultdict(dict)
    months = set()
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            area, ym = row["area"].strip(), row["month"].strip()[:7]
            raw[area][ym] = raw[area].get(ym, 0) + int(row["count"])
            months.add(ym)
    ordered = sorted(months)
    return ordered, {a: [m.get(ym, 0) for ym in ordered] for a, m in raw.items()}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="normal_month", description=__doc__.splitlines()[0])
    p.add_argument("csv", help="CSV with area, month, count columns")
    p.add_argument("--sigma", type=float, default=SIGMA, help="flag threshold (default 3.0)")
    p.add_argument("--top", type=int, default=10, help="rows to print (default 10)")
    args = p.parse_args(argv)

    months, counts = load(args.csv)
    report = check_latest(months, counts, sigma=args.sigma)

    print(f"{report.month}: {len(counts)} areas")
    if report.withheld_reason:
        print(f"No verdict: {report.withheld_reason}.")
        return 0

    n = len(report.results)
    print(f"Tested {n}; {len(report.too_small)} too small to judge.")
    print(f"Expected false flags by chance at {args.sigma:g} sigma: {n * _two_sided(args.sigma):.2f}\n")
    print(f"{'area':<12}{'observed':>9}{'expected':>10}{'vs last yr':>12}{'z':>7}  verdict")
    for r in report.results[: args.top]:
        pct = f"{r.pct_change:+.0f}%" if r.pct_change is not None else "n/a"
        print(f"{r.area:<12}{r.observed:>9}{r.expected:>10.1f}{pct:>12}{r.z:>7.1f}  {r.verdict}")

    if not report.flagged:
        print("\nNothing unusual happened this month.")
    return 0


def _two_sided(sigma: float) -> float:
    import math

    return math.erfc(sigma / math.sqrt(2))


if __name__ == "__main__":
    sys.exit(main())
