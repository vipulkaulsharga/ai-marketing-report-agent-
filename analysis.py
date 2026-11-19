"""Deterministic analysis functions.

Every number in a report comes from these functions, never from the model.
The agent decides which analyses to run and explains the results; pandas
does the arithmetic. That keeps the report "careful with numbers".
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

METRICS = ("spend_eur", "sessions", "orders", "new_customers", "revenue_eur")
DIMENSIONS = ("country", "channel")


def load(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = {"week", *DIMENSIONS, *METRICS} - set(df.columns)
    if missing:
        raise ValueError(f"Data is missing columns: {sorted(missing)}")
    return df


def _ratios(g: pd.DataFrame) -> pd.DataFrame:
    """Add derived KPIs to an aggregated frame."""
    g = g.copy()
    g["roas"] = g["revenue_eur"] / g["spend_eur"].where(g["spend_eur"] > 0)
    g["cac_eur"] = g["spend_eur"] / g["new_customers"].where(g["new_customers"] > 0)
    g["cvr_pct"] = 100 * g["orders"] / g["sessions"].where(g["sessions"] > 0)
    g["aov_eur"] = g["revenue_eur"] / g["orders"].where(g["orders"] > 0)
    return g


def weeks(df: pd.DataFrame) -> list[str]:
    return sorted(df["week"].unique())


def overview(df: pd.DataFrame) -> dict:
    """What the dataset covers."""
    return {
        "weeks": weeks(df),
        "countries": sorted(df["country"].unique()),
        "channels": sorted(df["channel"].unique()),
        "rows": len(df),
        "metrics": list(METRICS) + ["roas", "cac_eur", "cvr_pct", "aov_eur"],
    }


def kpi_summary(df: pd.DataFrame, week: str | None = None) -> pd.DataFrame:
    """Total KPIs for one week vs the previous week, with % change."""
    ws = weeks(df)
    week = week or ws[-1]
    if week not in ws or ws.index(week) == 0:
        raise ValueError(f"Need a week with a previous week; got {week}. Available: {ws}")
    prev = ws[ws.index(week) - 1]
    tot = _ratios(df[df["week"].isin([prev, week])].groupby("week")[list(METRICS)].sum())
    out = tot.T.rename(columns={prev: "previous_week", week: "this_week"})
    out["change_pct"] = 100 * (out["this_week"] / out["previous_week"] - 1)
    out.attrs.update(week=week, previous_week=prev)
    return out.round(2)


def breakdown(df: pd.DataFrame, dimension: str, week: str | None = None) -> pd.DataFrame:
    """KPIs by country or channel for one week vs the previous week."""
    if dimension not in DIMENSIONS:
        raise ValueError(f"dimension must be one of {DIMENSIONS}")
    ws = weeks(df)
    week = week or ws[-1]
    prev = ws[ws.index(week) - 1]
    cur = _ratios(df[df["week"] == week].groupby(dimension)[list(METRICS)].sum())
    old = _ratios(df[df["week"] == prev].groupby(dimension)[list(METRICS)].sum())
    out = cur[["spend_eur", "revenue_eur", "new_customers", "roas", "cac_eur", "cvr_pct"]].copy()
    for m in ("revenue_eur", "roas", "cac_eur", "cvr_pct"):
        out[f"{m}_change_pct"] = 100 * (cur[m] / old[m] - 1)
    return out.round(2).sort_values("revenue_eur", ascending=False)


def top_movers(df: pd.DataFrame, metric: str = "revenue_eur", n: int = 5, week: str | None = None) -> pd.DataFrame:
    """Country x channel segments with the largest absolute change in a metric vs the previous week."""
    allowed = set(METRICS) | {"roas", "cac_eur", "cvr_pct", "aov_eur"}
    if metric not in allowed:
        raise ValueError(f"metric must be one of {sorted(allowed)}")
    ws = weeks(df)
    week = week or ws[-1]
    prev = ws[ws.index(week) - 1]
    keys = ["country", "channel"]
    cur = _ratios(df[df["week"] == week].groupby(keys)[list(METRICS)].sum())
    old = _ratios(df[df["week"] == prev].groupby(keys)[list(METRICS)].sum())
    out = pd.DataFrame({"previous_week": old[metric], "this_week": cur[metric]})
    out["change"] = out["this_week"] - out["previous_week"]
    out["change_pct"] = 100 * (out["this_week"] / out["previous_week"] - 1)
    out = out.reindex(out["change"].abs().sort_values(ascending=False).index).head(n)
    return out.round(2).reset_index()


def segment_trend(df: pd.DataFrame, country: str, channel: str) -> pd.DataFrame:
    """Weekly KPIs for one country x channel segment across all weeks."""
    seg = df[(df["country"] == country) & (df["channel"] == channel)]
    if seg.empty:
        raise ValueError(f"No data for {country} / {channel}")
    t = _ratios(seg.groupby("week")[list(METRICS)].sum())
    return t[["spend_eur", "sessions", "orders", "new_customers", "revenue_eur", "roas", "cac_eur", "cvr_pct"]].round(2)


def driver_split(df: pd.DataFrame, country: str, channel: str, week: str | None = None) -> dict:
    """Explain a segment's revenue change as traffic, conversion and order-value effects.

    revenue = sessions x conversion rate x order value, so the factor with the
    largest log change is reported as the main driver.
    """
    import math

    ws = weeks(df)
    week = week or ws[-1]
    prev = ws[ws.index(week) - 1]
    t = segment_trend(df, country, channel)
    a, b = t.loc[prev], t.loc[week]
    aov_a, aov_b = a["revenue_eur"] / a["orders"], b["revenue_eur"] / b["orders"]
    parts = {
        "traffic": math.log(b["sessions"] / a["sessions"]),
        "conversion": math.log(b["cvr_pct"] / a["cvr_pct"]),
        "order_value": math.log(aov_b / aov_a),
    }
    pct = lambda new, old: round(float(100 * (new / old - 1)), 1)
    biggest = max(parts, key=lambda k: abs(parts[k]))
    return {
        "segment": f"{country} / {channel}",
        "week": week,
        "previous_week": prev,
        "revenue_change_pct": pct(b["revenue_eur"], a["revenue_eur"]),
        "sessions_change_pct": pct(b["sessions"], a["sessions"]),
        "cvr_change_pct": pct(b["cvr_pct"], a["cvr_pct"]),
        "aov_change_pct": pct(aov_b, aov_a),
        "spend_change_pct": pct(b["spend_eur"], a["spend_eur"]),
        "main_driver": biggest,
    }


def anomalies(df: pd.DataFrame, metric: str = "cac_eur", z: float = 2.5, week: str | None = None) -> pd.DataFrame:
    """Segments whose value this week is unusual vs their own earlier weeks (z-score)."""
    ws = weeks(df)
    week = week or ws[-1]
    hist_weeks = ws[: ws.index(week)]
    rows = []
    for (c, ch), seg in df.groupby(["country", "channel"]):
        t = _ratios(seg.groupby("week")[list(METRICS)].sum())[metric]
        hist, now = t.loc[hist_weeks].dropna(), t.get(week)
        if len(hist) < 3 or pd.isna(now) or hist.std() == 0:
            continue
        score = (now - hist.mean()) / hist.std()
        if abs(score) >= z:
            rows.append({"country": c, "channel": ch, "this_week": round(now, 2),
                         "usual": round(hist.mean(), 2), "z_score": round(score, 1)})
    return pd.DataFrame(rows).sort_values("z_score", key=abs, ascending=False) if rows else pd.DataFrame(
        columns=["country", "channel", "this_week", "usual", "z_score"])
