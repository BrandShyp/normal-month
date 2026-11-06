"""Write examples/demo.csv: 60 synthetic areas over 42 months.

No real data. Every area has a season, clustered (overdispersed) noise and its own
size. Two areas are planted to show the point of the method:

  area-07  an area with a genuine 40% break in the latest month
  area-58  a small area: too few events to judge, so it gets no verdict at all

Run:  python examples/make_demo.py
"""

import csv
import math
import random
from pathlib import Path

SEASON = [0.92, 0.90, 1.00, 1.02, 1.06, 1.08, 1.07, 1.05, 1.00, 0.98, 0.95, 0.97]


def poisson(rng: random.Random, lam: float) -> int:
    # Knuth's method, in chunks so exp(-lam) never underflows.
    total = 0
    while lam > 0:
        step = min(lam, 30.0)
        lam -= step
        limit, k, p = math.exp(-step), 0, 1.0
        while True:
            p *= rng.random()
            if p <= limit:
                break
            k += 1
        total += k
    return total


def main() -> None:
    rng = random.Random(5)
    months = [f"{2023 + (m // 12)}-{m % 12 + 1:02d}" for m in range(42)]
    rows = []
    for a in range(60):
        area = f"area-{a:02d}"
        per_day = 0.8 if a == 58 else rng.uniform(2.5, 25.0)
        for i, ym in enumerate(months):
            mo = int(ym[5:])
            days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mo - 1]
            if ym == "2024-02":
                days = 29
            mean = per_day * SEASON[mo - 1] * days
            if a == 7 and i == len(months) - 1:
                mean *= 1.4
            # Gamma-Poisson mixing gives clustered, overdispersed counts.
            mean = rng.gammavariate(150.0, mean / 150.0)
            rows.append((area, ym, poisson(rng, mean)))

    out = Path(__file__).with_name("demo.csv")
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["area", "month", "count"])
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
