"""AI agent that analyses weekly EU marketing performance and writes a decision-ready report.

Claude chooses which analyses to run (tool calls) and writes the report.
The analyses themselves are deterministic pandas code in analysis.py, and a
fact check at the end flags any number in the report that no tool returned.

Usage:
    python -m agent.report_agent                 # uses the Claude API
    python -m agent.report_agent --offline       # no API call: rule-based report from the same analyses
    python -m agent.report_agent --data my.csv --week 2026-10-26
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

import pandas as pd

from agent import analysis as A

ROOT = Path(__file__).resolve().parent.parent
MODEL = "claude-opus-5-5"

SYSTEM_PROMPT = """You are a marketing performance analyst for an e-commerce business in several EU markets.
Each week you write a short report for marketing and operations leaders.

Work like this:
1. Start with the overview and the week's KPI summary.
2. Look for what moved: breakdowns by country and channel, top movers, anomalies.
3. For each important change, find the driver (traffic, conversion or order value) with driver_split,
   and check the segment's trend so you do not over-read one noisy week.
4. Stop analysing once you can explain the 3 to 5 changes that matter most.

Rules for numbers: quote only numbers that a tool returned, rounded as the tool rounded them.
Never calculate a number yourself. If something cannot be explained from the data, say so.

Write the report in Markdown, at most about 400 words, with exactly these sections:
## Headline            (one or two sentences: the most important thing this week)
## Key findings        (3 to 5 bullets; each gives the change, its size and its driver)
## Recommended actions (3 to 5 bullets; each starts with the team that should act: Marketing or Operations)
## Watch next week     (1 to 3 bullets)
## Caveats             (data limits, one or two bullets)
Use plain, direct language. No preamble before the headline and nothing after the caveats."""

# ---------------------------------------------------------------- tools

_DF: pd.DataFrame | None = None
_WEEK: str | None = None
TOOL_LOG: list[dict] = []


def _out(name: str, args: dict, result) -> str:
    if isinstance(result, pd.DataFrame):
        text = result.to_csv()
    else:
        text = json.dumps(result, default=str)
    TOOL_LOG.append({"tool": name, "args": args, "result": text})
    return text


def build_tools():
    from anthropic import beta_tool

    @beta_tool
    def get_overview() -> str:
        """Describe the dataset: weeks, countries, channels and available metrics. Call this first."""
        return _out("get_overview", {}, A.overview(_DF))

    @beta_tool
    def get_kpi_summary() -> str:
        """Total KPIs for the report week vs the previous week, with % change.
        Metrics: spend, sessions, orders, new customers, revenue, ROAS, CAC (cost per new customer),
        conversion rate (%) and average order value."""
        return _out("get_kpi_summary", {}, A.kpi_summary(_DF, _WEEK))

    @beta_tool
    def get_breakdown(dimension: str) -> str:
        """KPIs for the report week by one dimension, with % change vs the previous week.

        Args:
            dimension: "country" or "channel".
        """
        return _out("get_breakdown", {"dimension": dimension}, A.breakdown(_DF, dimension, _WEEK))

    @beta_tool
    def get_top_movers(metric: str, n: int = 5) -> str:
        """Country x channel segments with the largest absolute change in one metric vs the previous week.

        Args:
            metric: One of spend_eur, sessions, orders, new_customers, revenue_eur, roas, cac_eur, cvr_pct, aov_eur.
            n: How many segments to return (1-10).
        """
        n = max(1, min(int(n), 10))
        return _out("get_top_movers", {"metric": metric, "n": n}, A.top_movers(_DF, metric, n, _WEEK))

    @beta_tool
    def get_anomalies(metric: str) -> str:
        """Segments whose value in the report week is unusual compared with their own earlier weeks (z-score of 2.5 or more).

        Args:
            metric: One of spend_eur, sessions, orders, new_customers, revenue_eur, roas, cac_eur, cvr_pct, aov_eur.
        """
        return _out("get_anomalies", {"metric": metric}, A.anomalies(_DF, metric, week=_WEEK))

    @beta_tool
    def get_segment_trend(country: str, channel: str) -> str:
        """Weekly KPIs for one country x channel segment across all weeks, to check whether a change is a trend or one noisy week.

        Args:
            country: Country code, e.g. "DE".
            channel: Channel name exactly as in the data, e.g. "Paid Search".
        """
        return _out("get_segment_trend", {"country": country, "channel": channel}, A.segment_trend(_DF, country, channel))

    @beta_tool
    def get_driver_split(country: str, channel: str) -> str:
        """Explain one segment's revenue change vs the previous week as traffic, conversion-rate and order-value changes,
        and name the main driver.

        Args:
            country: Country code, e.g. "FR".
            channel: Channel name exactly as in the data, e.g. "Paid Social".
        """
        return _out("get_driver_split", {"country": country, "channel": channel}, A.driver_split(_DF, country, channel, _WEEK))

    return [get_overview, get_kpi_summary, get_breakdown, get_top_movers,
            get_anomalies, get_segment_trend, get_driver_split]


# ---------------------------------------------------------------- fact check

_NUM = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?")


def fact_check(report: str) -> list[str]:
    """Return numbers in the report that do not appear in any tool result (allowing for rounding)."""
    known: list[float] = []
    for entry in TOOL_LOG:
        for m in _NUM.findall(entry["result"]):
            try:
                known.append(float(m.replace(",", "")))
            except ValueError:
                pass
    flagged = []
    for m in _NUM.findall(report):
        v = float(m.replace(",", ""))
        if abs(v) < 10 and v == int(v):  # small whole numbers: list counts, "3 segments", section numbers
            continue
        if 2000 <= v <= 2100 and v == int(v):  # years in dates
            continue
        if not any(abs(v - k) <= max(0.051, abs(k) * 0.005) or abs(abs(v) - abs(k)) <= 0.051 for k in known):
            flagged.append(m)
    return sorted(set(flagged))


# ---------------------------------------------------------------- runs

def run_claude(prompt: str) -> str:
    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY (or an `ant auth login` profile)
    runner = client.beta.messages.tool_runner(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        tools=build_tools(),
        output_config={"effort": "medium"},
        # If a safety classifier declines, re-run on a fallback model chosen by the API.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        max_iterations=20,
        messages=[{"role": "user", "content": prompt}],
    )
    final = runner.until_done()
    if final.stop_reason == "refusal":
        raise RuntimeError("The model declined to write this report.")
    if final.stop_reason == "max_tokens":
        raise RuntimeError("The report was cut off (max_tokens); raise max_tokens and retry.")
    return "".join(b.text for b in final.content if b.type == "text").strip()


def run_offline() -> str:
    """Rule-based report from the same analyses, for demos without an API key."""
    k = A.kpi_summary(_DF, _WEEK)
    for name, args, res in [("get_kpi_summary", {}, k)]:
        _out(name, args, res)
    rev, cac = k.loc["revenue_eur"], k.loc["cac_eur"]
    anom = A.anomalies(_DF, "cac_eur", week=_WEEK)
    _out("get_anomalies", {"metric": "cac_eur"}, anom)
    movers = A.top_movers(_DF, "revenue_eur", 3, _WEEK)
    _out("get_top_movers", {"metric": "revenue_eur", "n": 3}, movers)
    findings, actions = [], []
    for _, r in movers.iterrows():
        d = A.driver_split(_DF, r["country"], r["channel"], _WEEK)
        _out("get_driver_split", {"country": r["country"], "channel": r["channel"]}, d)
        findings.append(
            f"- **{d['segment']}**: revenue {d['revenue_change_pct']:+.1f}% "
            f"(sessions {d['sessions_change_pct']:+.1f}%, conversion {d['cvr_change_pct']:+.1f}%, "
            f"order value {d['aov_change_pct']:+.1f}%); main driver: {d['main_driver'].replace('_', ' ')}.")
        team = "Marketing" if d["main_driver"] == "traffic" else "Operations" if d["main_driver"] == "order_value" else "Marketing"
        actions.append(f"- {team}: review {d['segment']} ({d['main_driver'].replace('_', ' ')} changed most).")
    for _, r in anom.iterrows():
        findings.append(f"- **{r['country']} / {r['channel']}**: CAC EUR {r['this_week']:.2f} vs usual EUR {r['usual']:.2f} (z-score {r['z_score']}).")
    return "\n".join([
        "## Headline",
        f"Revenue {rev['change_pct']:+.2f}% week on week (EUR {rev['this_week']:,.2f}); CAC {cac['change_pct']:+.2f}% to EUR {cac['this_week']:.2f}.",
        "", "## Key findings", *findings,
        "", "## Recommended actions", *actions,
        "", "## Watch next week", "- Whether the segments above recover or continue.",
        "", "## Caveats", "- Offline mode: rule-based text without the AI agent. Sample data is synthetic.",
    ])


def render(report: str, flagged: list[str], mode: str) -> str:
    k = A.kpi_summary(_DF, _WEEK)
    lines = [
        f"# Weekly marketing report: week of {k.attrs['week']}",
        f"_Generated {date.today().isoformat()} by the AI report agent ({mode}). Compared with week of {k.attrs['previous_week']}._",
        "", report, "", "---", "## Appendix: KPI summary (computed by code)", "",
        k.reset_index().rename(columns={"index": "metric"}).to_markdown(index=False),
        "", "## Fact check",
        "All numbers in the report match a tool result." if not flagged else
        "Numbers not found in any tool result (check before sharing): " + ", ".join(flagged),
        "", "## Analyses the agent ran",
        *[f"{i}. `{e['tool']}({', '.join(f'{a}={v!r}' for a, v in e['args'].items())})`" for i, e in enumerate(TOOL_LOG, 1)],
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    global _DF, _WEEK
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(ROOT / "data" / "marketing_eu_weekly.csv"))
    ap.add_argument("--week", default=None, help="Report week (YYYY-MM-DD). Default: latest week in the data.")
    ap.add_argument("--offline", action="store_true", help="Skip the Claude API and write a rule-based report.")
    ap.add_argument("--out", default=str(ROOT / "reports"))
    args = ap.parse_args()

    _DF = A.load(args.data)
    _WEEK = args.week or A.weeks(_DF)[-1]
    TOOL_LOG.clear()

    if args.offline:
        body, mode = run_offline(), "offline mode"
    else:
        body, mode = run_claude(f"Write this week's report for the week of {_WEEK}."), MODEL

    flagged = fact_check(body)
    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)
    suffix = "_offline" if args.offline else ""
    path = out_dir / f"weekly_report_{_WEEK}{suffix}.md"
    path.write_text(render(body, flagged, mode), encoding="utf-8")
    print(f"Report written to {path}  ({len(TOOL_LOG)} analyses, {len(flagged)} numbers flagged)")


if __name__ == "__main__":
    main()
