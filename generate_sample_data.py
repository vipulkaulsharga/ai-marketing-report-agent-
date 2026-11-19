"""Generate a synthetic weekly marketing dataset for EU e-commerce markets.

The data is fictional. It mimics the shape of a real marketing export
(one row per week x country x channel) and contains a few planted
"stories" so the agent has real changes to find:

  * France / Paid Social: spend up sharply in the last week, conversion down
    -> customer acquisition cost (CAC) jumps.
  * Germany / Paid Search: conversion rate improves in the last two weeks
    -> more revenue at the same spend.
  * Netherlands / Email: sessions fall in the last week (a send was missed).
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 7
WEEKS = pd.date_range("2026-09-07", periods=8, freq="W-MON")
COUNTRIES = {"DE": 1.6, "FR": 1.3, "ES": 1.0, "IT": 0.9, "NL": 0.6, "PL": 0.5}
CHANNELS = {
    # channel: (weekly spend at scale 1, CPC, conversion rate, avg order value, share new customers)
    "Paid Search": (9000, 0.55, 0.032, 74, 0.55),
    "Paid Social": (7000, 0.40, 0.018, 62, 0.70),
    "Affiliate": (3000, 0.30, 0.025, 68, 0.60),
    "Display": (2500, 0.25, 0.008, 60, 0.65),
    "Email": (400, 0.0, 0.045, 71, 0.15),
}


def build() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    rows = []
    for w_i, week in enumerate(WEEKS):
        last, second_last = w_i == len(WEEKS) - 1, w_i == len(WEEKS) - 2
        for country, scale in COUNTRIES.items():
            for channel, (spend0, cpc, cvr, aov, new_share) in CHANNELS.items():
                noise = lambda s=0.06: rng.normal(1, s)
                spend = spend0 * scale * noise()
                c_cvr, c_aov = cvr * noise(0.05), aov * noise(0.03)

                if channel == "Email":
                    sessions = 9000 * scale * noise()
                else:
                    clicks = spend / (cpc * noise(0.04))
                    sessions = clicks * 0.92

                # Planted stories
                if country == "FR" and channel == "Paid Social" and last:
                    spend *= 1.45
                    sessions *= 1.20
                    c_cvr *= 0.62
                if country == "DE" and channel == "Paid Search" and (last or second_last):
                    c_cvr *= 1.22 if last else 1.12
                if country == "NL" and channel == "Email" and last:
                    sessions *= 0.38

                orders = sessions * c_cvr
                rows.append({
                    "week": week.date().isoformat(),
                    "country": country,
                    "channel": channel,
                    "spend_eur": round(spend, 2),
                    "sessions": int(sessions),
                    "orders": int(orders),
                    "new_customers": int(orders * new_share * noise(0.05)),
                    "revenue_eur": round(orders * c_aov, 2),
                })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    out = Path(__file__).with_name("marketing_eu_weekly.csv")
    df = build()
    df.to_csv(out, index=False)
    print(f"Wrote {len(df)} rows to {out}")
