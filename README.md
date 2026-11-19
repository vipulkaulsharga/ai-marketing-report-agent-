# AI Marketing Report Agent

An AI agent that analyses weekly marketing performance for an e-commerce business in six EU markets and writes a short, decision-ready report for marketing and operations teams.

It automates a task I did by hand as a Performance and Insights Analyst: every week, find what moved in the numbers, work out why, and turn it into clear recommendations.

## What it does

1. **Reads** a weekly marketing export (one row per week, country and channel: spend, sessions, orders, new customers, revenue).
2. **Decides what to analyse.** Claude calls analysis tools on its own: KPI summary, breakdowns by country and channel, top movers, anomaly detection, segment trends and a driver split (traffic vs conversion vs order value).
3. **Writes the report**: headline, key findings with their drivers, recommended actions per team, what to watch next week, caveats.
4. **Checks its numbers.** Every calculation runs in pandas, not in the model. A fact check then compares each number in the report with the tool results and flags any it cannot find.

```
CSV ──> analysis.py (pandas: all calculations)
            ▲   │ results
 tool calls │   ▼
        Claude (picks analyses, explains, recommends) ──> report.md
                                                            │
                                         fact check: every number traced to a tool result
```

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python data/generate_sample_data.py                # creates the sample dataset
python -m agent.report_agent --offline             # no API key needed: rule-based report
export ANTHROPIC_API_KEY=...                       # then the full AI agent:
python -m agent.report_agent
pytest -q
```

Reports are written to `reports/`. Use `--data your.csv` for your own export (same columns) and `--week YYYY-MM-DD` for a specific week.

## Design choices

- **The model never does arithmetic.** It chooses analyses and explains results; pandas computes. This makes the report reproducible and auditable.
- **Fact check before sharing.** Numbers in the report that no tool returned are listed at the end of the report.
- **Tested analysis layer.** `tests/` checks totals against the raw data, that the planted CAC spike is detected, and that the fact check catches an invented number.
- **Offline mode** produces a rule-based report from the same analyses, so the pipeline can be shown without an API key.

## Sample data

`data/marketing_eu_weekly.csv` is synthetic (8 weeks x 6 countries x 5 channels). It contains three planted changes for the agent to find: a CAC spike in France / Paid Social, better conversion in Germany / Paid Search, and a traffic drop in Netherlands / Email.

## Tech

Python, pandas, Claude API (Anthropic Python SDK tool runner), pytest.

## Next steps

- Connect to a live source (Google Ads / GA4 export, BigQuery) instead of a CSV.
- Run on a schedule and send the report to Slack or email every Monday.
- Add charts to the report.
