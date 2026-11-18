"""聚合、统计与表格落盘（tech-design §4.6、§6.1）。"""

from __future__ import annotations

import calendar
import csv
import json
from collections import defaultdict
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median

from .config import DAILY_CSV, MONTHLY_CSV, SUMMARY_JSON, WEEKLY_CSV
from .models import (
    AnalysisResult,
    CleanRecord,
    DailyCalories,
    EnergyType,
    PeriodCalories,
    SummaryStats,
)

_DAILY_HEADER = ("date", "active_kcal", "basal_kcal", "total_kcal", "active_ratio")
_PERIOD_HEADER = (
    "period_start", "period_end", "active_kcal", "basal_kcal", "total_kcal", "active_ratio",
)


def aggregate_daily(records: list[CleanRecord]) -> list[DailyCalories]:
    """按自然日分别求和活动/基础热量；total 由两者相加得到（AC4 不变量）。"""
    buckets: dict[date, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for record in records:
        pair = buckets[record.date]
        if record.type is EnergyType.ACTIVE:
            pair[0] += record.kcal
        elif record.type is EnergyType.BASAL:
            pair[1] += record.kcal

    result: list[DailyCalories] = []
    for day in sorted(buckets):
        active, basal = buckets[day]
        total = active + basal
        result.append(
            DailyCalories(
                date=day,
                active_kcal=active,
                basal_kcal=basal,
                total_kcal=total,
                active_ratio=active / total if total > 0 else 0.0,
            )
        )
    return result


def _period_bounds(day: date, period: str, week_start: str) -> tuple[date, date]:
    """返回 day 所属周期的起止日期。"""
    if period == "month":
        start = day.replace(day=1)
        last_day = calendar.monthrange(day.year, day.month)[1]
        return start, day.replace(day=last_day)
    if period == "week":
        if week_start == "sun":
            start = day - timedelta(days=(day.weekday() + 1) % 7)
        else:
            start = day - timedelta(days=day.weekday())
        return start, start + timedelta(days=6)
    raise ValueError(f"不支持的聚合周期：{period}")


def aggregate_period(
    daily: list[DailyCalories],
    period: str,
    week_start: str = "mon",
) -> list[PeriodCalories]:
    """按周（ISO 周或周日起始）或月聚合；组内 active_ratio 用求和而非均值。"""
    if period not in ("week", "month"):
        raise ValueError(f"不支持的聚合周期：{period}")
    if week_start not in ("mon", "sun"):
        raise ValueError(f"不支持的周起始日：{week_start}")

    buckets: dict[date, dict[str, object]] = {}
    for item in daily:
        start, end = _period_bounds(item.date, period, week_start)
        bucket = buckets.setdefault(
            start,
            {"end": end, "active": 0.0, "basal": 0.0, "total": 0.0},
        )
        bucket["active"] = float(bucket["active"]) + item.active_kcal
        bucket["basal"] = float(bucket["basal"]) + item.basal_kcal
        bucket["total"] = float(bucket["total"]) + item.total_kcal

    result: list[PeriodCalories] = []
    for start in sorted(buckets):
        bucket = buckets[start]
        active = float(bucket["active"])
        total = float(bucket["total"])
        result.append(
            PeriodCalories(
                period=period,
                start=start,
                end=bucket["end"],  # type: ignore[arg-type]
                active_kcal=active,
                basal_kcal=float(bucket["basal"]),
                total_kcal=total,
                active_ratio=active / total if total > 0 else 0.0,
            )
        )
    return result


def summarize(daily: list[DailyCalories]) -> SummaryStats:
    """计算全局统计量；缺失天数 = 日期跨度天数 - 有记录天数。"""
    ordered = sorted(daily, key=lambda item: item.date)
    if not ordered:
        return SummaryStats(
            start_date=date.min, end_date=date.min,
            valid_days=0, missing_days=0,
            active_mean=0.0, basal_mean=0.0, total_mean=0.0,
            total_median=0.0, total_max=0.0, total_min=0.0,
        )

    start, end = ordered[0].date, ordered[-1].date
    totals = [item.total_kcal for item in ordered]
    span_days = (end - start).days + 1
    return SummaryStats(
        start_date=start,
        end_date=end,
        valid_days=len(ordered),
        missing_days=max(0, span_days - len(ordered)),
        active_mean=mean(item.active_kcal for item in ordered),
        basal_mean=mean(item.basal_kcal for item in ordered),
        total_mean=mean(totals),
        total_median=median(totals),
        total_max=max(totals),
        total_min=min(totals),
    )


def _fmt(value: float) -> str:
    """所有表格浮点统一保留 2 位小数。"""
    return f"{float(value):.2f}"


def _write_csv(path: Path, header: tuple[str, ...], rows: list[list[str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def write_tables(result: AnalysisResult, out: Path) -> list[Path]:
    """落盘日/周/月 CSV 与 summary.json，返回生成路径列表。"""
    target = Path(out)
    target.mkdir(parents=True, exist_ok=True)

    daily_csv = _write_csv(
        target / DAILY_CSV,
        _DAILY_HEADER,
        [
            [
                item.date.isoformat(),
                _fmt(item.active_kcal),
                _fmt(item.basal_kcal),
                _fmt(item.total_kcal),
                _fmt(item.active_ratio),
            ]
            for item in result.daily
        ],
    )

    def period_rows(periods: list[PeriodCalories]) -> list[list[str]]:
        return [
            [
                item.start.isoformat(),
                item.end.isoformat(),
                _fmt(item.active_kcal),
                _fmt(item.basal_kcal),
                _fmt(item.total_kcal),
                _fmt(item.active_ratio),
            ]
            for item in periods
        ]

    weekly_csv = _write_csv(target / WEEKLY_CSV, _PERIOD_HEADER, period_rows(result.weekly))
    monthly_csv = _write_csv(target / MONTHLY_CSV, _PERIOD_HEADER, period_rows(result.monthly))

    summary = result.summary
    payload = {
        "start_date": summary.start_date.isoformat(),
        "end_date": summary.end_date.isoformat(),
        "valid_days": summary.valid_days,
        "missing_days": summary.missing_days,
        "active_mean": round(summary.active_mean, 2),
        "basal_mean": round(summary.basal_mean, 2),
        "total_mean": round(summary.total_mean, 2),
        "total_median": round(summary.total_median, 2),
        "total_max": round(summary.total_max, 2),
        "total_min": round(summary.total_min, 2),
        "clean_stats": asdict(result.clean_stats),
    }
    summary_json = target / SUMMARY_JSON
    summary_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return [daily_csv, weekly_csv, monthly_csv, summary_json]
