# Weekly marketing report: week of 2026-10-26
_Generated 2026-11-19 by the AI report agent (offline mode). Compared with week of 2026-10-19._

## Headline
Revenue -1.81% week on week (EUR 618,828.46); CAC +3.36% to EUR 30.67.

## Key findings
- **NL / Email**: revenue -54.2% (sessions -60.0%, conversion +10.3%, order value +3.8%); main driver: traffic.
- **FR / Email**: revenue +19.2% (sessions +13.7%, conversion -0.9%, order value +5.8%); main driver: traffic.
- **FR / Paid Social**: revenue -29.2% (sessions +9.1%, conversion -36.8%, order value +2.9%); main driver: conversion.
- **FR / Paid Social**: CAC EUR 68.06 vs usual EUR 35.51 (z-score 12.8).
- **NL / Email**: CAC EUR 20.04 vs usual EUR 7.18 (z-score 12.8).

## Recommended actions
- Marketing: review NL / Email (traffic changed most).
- Marketing: review FR / Email (traffic changed most).
- Marketing: review FR / Paid Social (conversion changed most).

## Watch next week
- Whether the segments above recover or continue.

## Caveats
- Offline mode: rule-based text without the AI agent. Sample data is synthetic.

---
## Appendix: KPI summary (computed by code)

| metric        |   previous_week |   this_week |   change_pct |
|:--------------|----------------:|------------:|-------------:|
| spend_eur     |       131513    |   130008    |        -1.14 |
| sessions      |       349641    |   344320    |        -1.52 |
| orders        |         9102    |     8899    |        -2.23 |
| new_customers |         4432    |     4239    |        -4.35 |
| revenue_eur   |       630258    |   618828    |        -1.81 |
| roas          |            4.79 |        4.76 |        -0.68 |
| cac_eur       |           29.67 |       30.67 |         3.36 |
| cvr_pct       |            2.6  |        2.58 |        -0.72 |
| aov_eur       |           69.24 |       69.54 |         0.43 |

## Fact check
All numbers in the report match a tool result.

## Analyses the agent ran
1. `get_kpi_summary()`
2. `get_anomalies(metric='cac_eur')`
3. `get_top_movers(metric='revenue_eur', n=3)`
4. `get_driver_split(country='NL', channel='Email')`
5. `get_driver_split(country='FR', channel='Email')`
6. `get_driver_split(country='FR', channel='Paid Social')`
