from pathlib import Path

import pytest

from agent import analysis as A
from agent import report_agent as R

DATA = Path(__file__).resolve().parent.parent / "data" / "marketing_eu_weekly.csv"


@pytest.fixture(scope="module")
def df():
    return A.load(DATA)


def test_kpi_totals_match_raw_data(df):
    k = A.kpi_summary(df)
    last = df[df["week"] == A.weeks(df)[-1]]
    assert k.loc["revenue_eur", "this_week"] == pytest.approx(last["revenue_eur"].sum(), abs=0.01)
    assert k.loc["roas", "this_week"] == pytest.approx(last["revenue_eur"].sum() / last["spend_eur"].sum(), abs=0.01)


def test_planted_cac_spike_is_found(df):
    anom = A.anomalies(df, "cac_eur")
    segments = set(zip(anom["country"], anom["channel"]))
    assert ("FR", "Paid Social") in segments


def test_driver_split_names_conversion_for_fr_paid_social(df):
    d = A.driver_split(df, "FR", "Paid Social")
    assert d["main_driver"] == "conversion"
    assert d["cvr_change_pct"] < 0


def test_bad_inputs_raise(df):
    with pytest.raises(ValueError):
        A.breakdown(df, "city")
    with pytest.raises(ValueError):
        A.top_movers(df, "profit")
    with pytest.raises(ValueError):
        A.segment_trend(df, "XX", "Email")


def test_fact_check_flags_invented_numbers(df):
    R.TOOL_LOG.clear()
    R._out("get_kpi_summary", {}, A.kpi_summary(df))
    real = A.kpi_summary(df).loc["cac_eur", "this_week"]
    assert R.fact_check(f"CAC rose to EUR {real:.2f}.") == []
    assert R.fact_check("CAC rose to EUR 41.37.") == ["41.37"]
