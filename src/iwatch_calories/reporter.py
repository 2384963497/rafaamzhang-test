"""Markdown 分析报告渲染（tech-design §4.8、§6.3）。"""

from __future__ import annotations

from pathlib import Path

from .config import CHARTS_DIR, REPORT_MD
from .models import AnalysisResult


def render_report(result: AnalysisResult, out: Path) -> Path:
    """渲染含 5 个章节的 analysis_report.md，返回报告路径。"""
    summary = result.summary
    stats = result.clean_stats
    config = result.config
    timezone_spec = config.timezone if config else "auto"
    week_start = config.week_start if config else "mon"
    max_kcal = config.max_kcal_per_record if config else 5000.0

    lines: list[str] = [
        "# iWatch 热量消耗分析报告（第一期）",
        "",
        "## 1. 数据概览",
        "",
        f"- 记录总数（XML 中全部 Record）：{stats.records_total}",
        f"- 热量类型记录数：{stats.parsed_total}",
        f"- 清洗后有效记录数：{stats.kept}",
        f"- 时间范围：{summary.start_date.isoformat()} ~ {summary.end_date.isoformat()}",
        f"- 有效天数 / 缺失天数：{summary.valid_days} / {summary.missing_days}",
        "",
        "## 2. 口径说明",
        "",
        "- 总热量 = 活动热量（ActiveEnergyBurned）+ 基础热量（BasalEnergyBurned）。",
        "- 活动占比 = 活动热量 / 总热量；总热量为 0 时取 0。",
        f"- 时区：{timezone_spec}（`auto` 表示按记录 UTC 偏移众数推断的固定偏移，不处理夏令时）。",
        f"- 周起始日：{week_start}；周/月组内占比按组内求和计算。",
        "- 单位归一：kcal ×1、cal ×0.001、kJ ×0.239006。",
        f"- 单条热量上限：{max_kcal:.2f} kcal；非正值与超限记录被隔离。",
        "- 缺失日不写入日明细表，仅计入缺失天数并在图表中形成跨日连线。",
        "",
        "## 3. 关键统计",
        "",
        "| 指标 | 数值 |",
        "| --- | ---: |",
        f"| 起始日期 | {summary.start_date.isoformat()} |",
        f"| 结束日期 | {summary.end_date.isoformat()} |",
        f"| 有效天数 | {summary.valid_days} |",
        f"| 缺失天数 | {summary.missing_days} |",
        f"| 活动热量日均 (kcal) | {summary.active_mean:.2f} |",
        f"| 基础热量日均 (kcal) | {summary.basal_mean:.2f} |",
        f"| 总热量日均 (kcal) | {summary.total_mean:.2f} |",
        f"| 总热量中位数 (kcal) | {summary.total_median:.2f} |",
        f"| 总热量最大值 (kcal) | {summary.total_max:.2f} |",
        f"| 总热量最小值 (kcal) | {summary.total_min:.2f} |",
        "",
        "## 4. 图表",
        "",
        f"![日总热量趋势]({CHARTS_DIR}/daily_trend.png)",
        "",
        f"![活动 vs 基础占比]({CHARTS_DIR}/active_vs_basal.png)",
        "",
        f"![周/月对比]({CHARTS_DIR}/period_compare.png)",
        "",
        "## 5. 质量说明",
        "",
        "| 隔离原因 | 记录数 |",
        "| --- | ---: |",
        f"| 重复 UUID | {stats.duplicate_uuid} |",
        f"| 未知单位 | {stats.unknown_unit} |",
        f"| 异常值（非正/超限/日期数值非法） | {stats.invalid_value} |",
        f"| 非热量类型 | {stats.wrong_type} |",
        "",
        "说明：重复 UUID 按首次出现保留（多来源重叠时间窗的合并为后续迭代范围）；"
        "未知单位默认隔离；被隔离记录不参与任何聚合与统计。",
        "",
    ]

    report_path = Path(out) / REPORT_MD
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
