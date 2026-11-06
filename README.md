# normal-month

[![tests](https://github.com/BrandShyp/normal-month/actions/workflows/tests.yml/badge.svg)](https://github.com/BrandShyp/normal-month/actions/workflows/tests.yml)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)

**Was this month actually unusual?** A small, dependency-free Python test for monthly
counts across many areas (offenses by ZIP code, service requests by district, complaints by
store). It ranks areas by how surprising the latest month is against each area's own recent
behavior, and most months it gives the correct answer: nothing unusual happened.

It is the method behind the "What actually changed" panel on the
[San Antonio Crime Map](https://brandshyp.org/san-antonio-crime-map/), rewritten as a
standalone library.

## Why not percent change?

Most dashboards rank areas by change from last year. That ranks small denominators,
not news. On the demo data, two areas are up sharply on last year. Only one of them is
real:

```
$ python -m normal_month examples/demo.csv --top 6
2026-06: 60 areas
Tested 59; 1 too small to judge.
Expected false flags by chance at 3 sigma: 0.16

area         observed  expected  vs last yr      z  verdict
area-07           214     112.2        +71%    7.2  unusually high
area-06           122      90.6        +58%    2.5  normal
area-29           266     350.9        -28%   -2.4  normal
area-45           199     161.5        +21%    2.2  normal
area-14           543     467.1        +14%    2.2  normal
area-47           508     425.0        +11%    2.1  normal
```

`area-07` has a genuine break planted in it. `area-06` is up 58% only because the same
month last year happened to be low. A percent-change table would print both as headlines.

## What it does, and what it refuses to do

| Rule | Why |
|---|---|
| **Per-day rates before anything else** | February has 28 days. On raw counts it looks about 8% "safer" every year. It is not safer, it is shorter. |
| **A seasonal index, from the median, clamped to ±25%** | A few years of history give only 3 or 4 observations per calendar month. The median and the clamp keep one freak month from inventing a season. |
| **Each area against its own 24-month baseline** | Expected = baseline rate per day × seasonal index × days in the month. |
| **Quasi-Poisson, not Poisson** | Events cluster, so the variance exceeds the mean. Each area's dispersion comes from its own residuals and is never allowed below 1. |
| **3 sigma, not 1.96** | Testing 60 areas at 95% flags about 3 of them by chance every month. At 3 sigma the expected false flags across 60 areas are about 0.16, and the tool prints that number. |
| **No verdict below 30 expected events** | Small numbers move a lot and mean little. Those areas are listed as too small to judge instead of being ranked. |
| **No verdict on a partial month** | If the latest month's total is far below expectation, the data has probably not finished landing. A confident "citywide drop" would be the worst possible false headline, so the tool says nothing. |

One deliberate conservatism: an area on a slow multi-year trend shows that trend as extra
dispersion, which makes it harder to flag. The test catches a break from recent behavior,
not a drift. It would rather miss a slow trend than cry wolf.

## Use it

```bash
git clone https://github.com/BrandShyp/normal-month && cd normal-month
python -m normal_month examples/demo.csv
```

Your CSV needs three columns: `area`, `month` (YYYY-MM) and `count`. Or from Python:

```python
from normal_month import check_latest

report = check_latest(months, {"78205": [412, 398, ...], "78225": [...]})
for r in report.flagged:
    print(r.area, r.verdict, round(r.z, 1))
if report.withheld_reason:
    print("No verdict:", report.withheld_reason)
```

`examples/demo.csv` is synthetic (`examples/make_demo.py`): 60 areas, 42 months, seasonal,
overdispersed, with one planted break and one area too small to judge. No real records are
included.

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests check each refusal on its own: a constant daily rate gives a flat seasonal index,
pure noise across 200 areas stays quiet, a real break is caught, a tiny area gets no verdict,
a half-reported month is withheld.

## About

Built by [BrandShyp](https://brandshyp.org), a software firm in San Antonio. We build
public-data tools and the systems behind them. MIT licensed.
