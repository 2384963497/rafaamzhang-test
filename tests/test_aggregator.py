"""聚合与统计阶段单测：AC4 / AC5。"""

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from iwatch_calories.aggregator import aggregate_daily, aggregate_period, summarize, write_tables
from iwatch_calories.config import DAILY_CSV, MONTHLY_CSV, SUMMARY_JSON, WEEKLY_CSV
from iwatch_calories.models import (
    AnalysisResult,
    CleanRecord,
    CleanStats,
    EnergyType,
)


def _clean(day: str, kind: EnergyType = EnergyType.ACTIVE, kcal: float = 100.0) -> CleanRecord:
    parsed = date.fromisoformat(day)
    moment = datetime(2016, 1, 1)
    return CleanRecord(
        uuid=f"{day}-{kind.value}-{kcal}",
        type=kind,
        date=parsed,
        start=moment,
        end=moment,
        kcal=kcal,
    )


def test_daily_totals_and_invariant():
    daily = aggregate_daily([
        _clean("2016-03-06", EnergyType.BASAL, 1600),
        _clean("2016-03-05", EnergyType.ACTIVE, 350),
        _clean("2016-03-05", EnergyType.BASAL, 1978.012),
        _clean("2016-03-06", EnergyType.ACTIVE, 200),
    ])
    assert [item.date.isoformat() for item in daily] == ["2016-03-05", "2016-03-06"]
    assert daily[0].total_kcal == pytest.approx(2328.012, abs=1e-2)
    assert daily[0].active_ratio == pytest.approx(350 / 2328.012, abs=1e-4)
    for item in daily:
        assert abs(item.total_kcal - item.active_kcal - item.basal_kcal) < 1e-2


def test_weekly_grouping_monday_and_sunday_start():
    daily = aggregate_daily([
        _clean(day, EnergyType.ACTIVE, value)
        for day, value in (
            ("2016-03-05", 10), ("2016-03-06", 20),
            ("2016-03-07", 30), ("2016-03-08", 40),
        )
    ])
    weeks = aggregate_period(daily, "week", "mon")
    assert [(w.start.isoformat(), w.end.isoformat()) for w in weeks] == [
        ("2016-02-29", "2016-03-06"),
        ("2016-03-07", "2016-03-13"),
    ]
    assert [w.total_kcal for w in weeks] == [pytest.approx(30), pytest.approx(70)]

    sunday_weeks = aggregate_period(daily, "week", "sun")
    assert [w.start.isoformat() for w in sunday_weeks] == ["2016-02-28", "2016-03-06"]
    assert [w.total_kcal for w in sunday_weeks] == [pytest.approx(10), pytest.approx(90)]


def test_monthly_grouping():
    daily = aggregate_daily([
        _clean("2016-02-29", EnergyType.BASAL, 100),
        _clean("2016-03-01", EnergyType.ACTIVE, 50),
        _clean("2016-03-31", EnergyType.ACTIVE, 70),
    ])
    months = aggregate_period(daily, "month")
    assert [(m.start.isoformat(), m.end.isoformat()) for m in months] == [
        ("2016-02-01", "2016-02-29"),
        ("2016-03-01", "2016-03-31"),
    ]
    assert [m.total_kcal for m in months] == [pytest.approx(100), pytest.approx(120)]


def test_summarize_counts_missing_days_and_stats():
    daily = aggregate_daily([
        _clean("2016-03-05", EnergyType.ACTIVE, 100),
        _clean("2016-03-05", EnergyType.BASAL, 200),
        _clean("2016-03-08", EnergyType.ACTIVE, 300),
    ])
    summary = summarize(daily)
    assert summary.start_date.isoformat() == "2016-03-05"
    assert summary.end_date.isoformat() == "2016-03-08"
    assert summary.valid_days == 2
    assert summary.missing_days == 2
    assert summary.total_median == pytest.approx(300)
    assert summary.total_max == pytest.approx(300)
    assert summary.total_min == pytest.approx(300)
    assert summary.total_mean == pytest.approx(300)


def test_write_tables_matches_expected_daily_csv(tmp_path, fixtures_dir):
    daily = aggregate_daily([
        _clean("2016-03-05", EnergyType.ACTIVE, 350),
        _clean("2016-03-05", EnergyType.BASAL, 1978.012),
        _clean("2016-03-06", EnergyType.ACTIVE, 200),
        _clean("2016-03-06", EnergyType.BASAL, 1600),
        _clean("2016-03-08", EnergyType.ACTIVE, 400),
        _clean("2016-03-08", EnergyType.BASAL, 1400),
    ])
    result = AnalysisResult(
        daily=daily,
        weekly=aggregate_period(daily, "week"),
        monthly=aggregate_period(daily, "month"),
        summary=summarize(daily),
        clean_stats=CleanStats(parsed_total=12, kept=8),
        charts=[], report=Path(), tables=[],
    )
    out = tmp_path / "out"
    written = write_tables(result, out)

    assert {path.name for path in written} == {DAILY_CSV, WEEKLY_CSV, MONTHLY_CSV, SUMMARY_JSON}
    assert (out / DAILY_CSV).read_text(encoding="utf-8") == (
        fixtures_dir / "expected_daily.csv"
    ).read_text(encoding="utf-8")
    summary_payload = json.loads((out / SUMMARY_JSON).read_text(encoding="utf-8"))
    assert summary_payload["valid_days"] == 3
    assert summary_payload["clean_stats"]["kept"] == 8
