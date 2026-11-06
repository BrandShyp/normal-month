import math
import random
import unittest

from normal_month import (
    check_latest,
    days_in_month,
    seasonal_index,
)

MONTHS = [f"{2023 + (m // 12)}-{m % 12 + 1:02d}" for m in range(42)]


def poisson(rng, lam):
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


def flat_area(rng, per_day, months=MONTHS, last_multiplier=1.0):
    out = []
    for i, ym in enumerate(months):
        mean = per_day * days_in_month(ym)
        if i == len(months) - 1:
            mean *= last_multiplier
        out.append(poisson(rng, mean))
    return out


class SeasonalIndex(unittest.TestCase):
    def test_february_is_shorter_not_safer(self):
        # A constant 10 events per day. Raw monthly counts dip every February.
        totals = [10 * days_in_month(ym) for ym in MONTHS]
        idx = seasonal_index(MONTHS, totals)
        for mo in range(1, 13):
            self.assertAlmostEqual(idx[mo], 1.0, places=9)

    def test_index_averages_to_one(self):
        rng = random.Random(1)
        totals = [rng.randint(800, 1200) for _ in MONTHS]
        idx = seasonal_index(MONTHS, totals)
        self.assertAlmostEqual(sum(idx.values()) / 12, 1.0, places=9)

    def test_freak_month_is_clamped(self):
        totals = [1000] * len(MONTHS)
        totals[18] = 10000  # one absurd July
        idx = seasonal_index(MONTHS, totals)
        self.assertLessEqual(max(idx.values()), 1.25 / (sum(idx.values()) / 12) + 1e-9)


class CheckLatest(unittest.TestCase):
    def test_pure_noise_is_mostly_normal(self):
        # 200 areas with no change at all. At 3 sigma about 0.5 should flag by chance.
        rng = random.Random(7)
        counts = {f"a{i}": flat_area(rng, rng.uniform(3, 30)) for i in range(200)}
        report = check_latest(MONTHS, counts)
        self.assertIsNone(report.withheld_reason)
        self.assertLessEqual(len(report.flagged), 3)

    def test_real_break_is_flagged(self):
        rng = random.Random(3)
        counts = {f"a{i}": flat_area(rng, 15) for i in range(20)}
        counts["break"] = flat_area(rng, 15, last_multiplier=1.6)
        report = check_latest(MONTHS, counts)
        self.assertEqual([r.area for r in report.flagged], ["break"])
        self.assertEqual(report.flagged[0].verdict, "unusually high")

    def test_small_areas_get_no_verdict(self):
        rng = random.Random(4)
        counts = {f"a{i}": flat_area(rng, 15) for i in range(10)}
        counts["tiny"] = flat_area(rng, 0.3, last_multiplier=5)  # huge % jump, ~9 expected
        report = check_latest(MONTHS, counts)
        self.assertIn("tiny", report.too_small)
        self.assertNotIn("tiny", [r.area for r in report.results])

    def test_partial_month_is_withheld(self):
        rng = random.Random(5)
        counts = {f"a{i}": flat_area(rng, 15) for i in range(30)}
        for series in counts.values():
            series[-1] = series[-1] // 2  # only half the month has been reported
        report = check_latest(MONTHS, counts)
        self.assertEqual(report.results, [])
        self.assertIn("incomplete", report.withheld_reason)

    def test_short_history_is_withheld(self):
        rng = random.Random(6)
        short = MONTHS[:20]
        counts = {"a": flat_area(rng, 15, months=short)}
        report = check_latest(short, counts)
        self.assertIn("not enough history", report.withheld_reason)

    def test_dispersion_never_below_poisson(self):
        counts = {"steady": [15 * days_in_month(ym) for ym in MONTHS]}
        report = check_latest(MONTHS, counts)
        self.assertEqual(report.results[0].dispersion, 1.0)

    def test_misaligned_series_raises(self):
        with self.assertRaises(ValueError):
            check_latest(MONTHS, {"a": [1, 2, 3]})


if __name__ == "__main__":
    unittest.main()
