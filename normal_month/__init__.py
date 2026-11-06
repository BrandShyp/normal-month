"""Was this month actually unusual?

A small, dependency-free test for monthly count data (offenses, service requests,
complaints, sales) across many areas at once. It ranks areas by how surprising the
latest month is against each area's OWN recent behavior, and it is built to say
"nothing unusual happened" when that is the true answer.

This is the method behind the "What actually changed" panel on the San Antonio Crime
Map (https://brandshyp.org/san-antonio-crime-map/), rewritten as a standalone library.
"""

from __future__ import annotations

import calendar
import math
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence

__all__ = [
    "Result",
    "Report",
    "days_in_month",
    "seasonal_index",
    "check_latest",
    "SIGMA",
    "BASELINE_MONTHS",
    "MIN_EXPECTED",
    "MIN_BASE",
]

#: Flag an area only beyond this many standard deviations. Not the reflexive 1.96:
#: testing 62 areas at 95% would flag about 3 of them by chance every month. At 3 sigma
#: the expected number of false flags across 62 areas is about 0.17.
SIGMA = 3.0

#: Months of history used to fit each area's baseline level and its dispersion.
BASELINE_MONTHS = 24

#: Below this many EXPECTED events the normal approximation to the Poisson stops
#: holding and a "surprise" is just a small number moving. No verdict is given.
MIN_EXPECTED = 30

#: A year-over-year percent change is only shown when last year's count is at least
#: this large. Percent change on a small denominator is noise with a big number on it.
MIN_BASE = 50

#: If the latest month's total across all areas is below this share of what the
#: baseline expects, the month is treated as incomplete and nothing is reported.
COMPLETENESS_FLOOR = 0.65

#: A seasonal effect stronger than this is not believed from thin data.
SEASON_CLAMP = (0.8, 1.25)


def days_in_month(ym: str) -> int:
    """Days in the month named by a "YYYY-MM" string."""
    year, month = int(ym[:4]), int(ym[5:7])
    return calendar.monthrange(year, month)[1]


def _month_of_year(ym: str) -> int:
    return int(ym[5:7])


def seasonal_index(months: Sequence[str], totals: Sequence[float]) -> Dict[int, float]:
    """Month-of-year seasonal index, multiplicative, averaging exactly 1.

    Ratio to a centered 12-month moving average of the PER-DAY rate, then the median
    ratio for each calendar month. Working per day is the point: on raw monthly counts
    February lands about 8% below average and looks "safer". It is not safer, it is
    shorter.

    With only a few years of history there are 3 or 4 observations per calendar month,
    so the median (not the mean) and a clamp keep one freak month from inventing a
    season. A calendar month with no evidence gets 1.0: no season is assumed rather
    than one invented.
    """
    if len(months) != len(totals):
        raise ValueError("months and totals must be the same length")
    n = len(months)
    per_day = [totals[i] / days_in_month(months[i]) for i in range(n)]

    ratios: Dict[int, List[float]] = {}
    for i in range(6, n - 6):
        window = per_day[i - 6 : i + 6]
        ma = sum(window) / 12
        if ma > 0:
            ratios.setdefault(_month_of_year(months[i]), []).append(per_day[i] / ma)

    lo, hi = SEASON_CLAMP
    idx: Dict[int, float] = {}
    for mo in range(1, 13):
        r = sorted(ratios.get(mo, []))
        if not r:
            idx[mo] = 1.0
            continue
        k = len(r)
        median = (r[k // 2 - 1] + r[k // 2]) / 2 if k % 2 == 0 else r[k // 2]
        idx[mo] = max(lo, min(hi, median))

    # Re-center so the average month is exactly 1. Otherwise the index would quietly
    # rescale every expected value and bias the test in one direction.
    mean = sum(idx.values()) / 12
    if mean > 0:
        idx = {mo: v / mean for mo, v in idx.items()}
    return idx


@dataclass(frozen=True)
class Result:
    """The verdict for one area in the latest month."""

    area: str
    observed: int
    expected: float
    dispersion: float
    z: float
    pct_change: Optional[float]
    flag: bool

    @property
    def verdict(self) -> str:
        if not self.flag:
            return "normal"
        return "unusually high" if self.z > 0 else "unusually low"


@dataclass(frozen=True)
class Report:
    """Everything `check_latest` concluded, including what it refused to judge."""

    month: str
    results: List[Result]
    too_small: List[str]
    withheld_reason: Optional[str] = None

    @property
    def flagged(self) -> List[Result]:
        return [r for r in self.results if r.flag]


def check_latest(
    months: Sequence[str],
    counts: Mapping[str, Sequence[int]],
    *,
    sigma: float = SIGMA,
    baseline_months: int = BASELINE_MONTHS,
    min_expected: float = MIN_EXPECTED,
) -> Report:
    """Test the latest month of every area against that area's own baseline.

    ``months`` is an ordered list of "YYYY-MM" strings. ``counts`` maps each area to a
    list of counts aligned with ``months``.

    For each area::

        expected = (deseasonalized baseline rate per day)
                   x (seasonal index for this month) x (days in this month)

    The observed count is compared to expected as QUASI-Poisson. Counts like these are
    overdispersed (events cluster, so the variance exceeds the mean), and assuming plain
    Poisson would understate the noise and flag a few areas every month for no reason.
    Each area's dispersion is estimated from its own baseline residuals (Pearson
    chi-square over degrees of freedom) and floored at 1, because real data is never
    tighter than Poisson and a dispersion below 1 would make the test hair-trigger.

    A known, deliberate conservatism: an area on a steady multi-year trend shows that
    trend as extra dispersion, which makes it harder to flag. The test catches a real
    break from recent behavior, not a slow drift. It would rather miss a slow trend than
    cry wolf.
    """
    months = list(months)
    n = len(months)
    for area, series in counts.items():
        if len(series) != n:
            raise ValueError(f"{area}: expected {n} counts, got {len(series)}")

    latest = months[-1] if months else ""
    if n < baseline_months + 2:
        return Report(latest, [], [], "not enough history to fit a baseline")

    totals = [sum(series[i] for series in counts.values()) for i in range(n)]
    season = seasonal_index(months, totals)

    cur = n - 1
    base = range(cur - baseline_months, cur)
    mo_cur = _month_of_year(months[cur])
    days_cur = days_in_month(months[cur])

    # Completeness guard: a partly reported month would make every area look low and
    # produce a confident, false "citywide drop". If the total is implausibly far below
    # expectation, assume the data has not landed yet and say nothing.
    base_days = sum(days_in_month(months[m]) for m in base)
    city_rate = sum(totals[m] / season[_month_of_year(months[m])] for m in base) / base_days
    city_expected = city_rate * season[mo_cur] * days_cur
    if city_expected > 0 and totals[cur] < city_expected * COMPLETENESS_FLOOR:
        return Report(
            latest,
            [],
            [],
            f"latest month looks incomplete ({totals[cur]:,} events vs about "
            f"{city_expected:,.0f} expected)",
        )

    results: List[Result] = []
    too_small: List[str] = []
    for area, series in counts.items():
        adj = sum(series[m] / season[_month_of_year(months[m])] for m in base)
        rate = adj / base_days
        expected = rate * season[mo_cur] * days_cur
        if expected < min_expected:
            too_small.append(area)
            continue

        chi, df = 0.0, 0
        for m in base:
            e = rate * season[_month_of_year(months[m])] * days_in_month(months[m])
            if e > 0:
                chi += (series[m] - e) ** 2 / e
                df += 1
        phi = max(1.0, chi / (df - 1)) if df > 1 else 1.0

        sd = math.sqrt(phi * expected)
        observed = int(series[cur])
        z = (observed - expected) / sd

        prev = series[cur - 12] if cur >= 12 else 0
        pct = (observed - prev) / prev * 100 if prev >= MIN_BASE else None

        results.append(Result(area, observed, expected, phi, z, pct, abs(z) >= sigma))

    results.sort(key=lambda r: abs(r.z), reverse=True)
    return Report(latest, results, sorted(too_small))
