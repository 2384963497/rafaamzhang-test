"""图表渲染：3 类静态 PNG（tech-design §4.7、§6.2）。

使用 matplotlib Agg 后端，无 GUI 依赖；图表标签使用英文以规避中文字体缺失（R4），
中文说明放在报告中。
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (必须在 use("Agg") 之后导入)

from .config import CHARTS_DIR  # noqa: E402
from .models import DailyCalories, PeriodCalories  # noqa: E402


def _finish(fig: plt.Figure, path: Path, dpi: int) -> Path:
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


def render_charts(
    daily: list[DailyCalories],
    weekly: list[PeriodCalories],
    monthly: list[PeriodCalories],
    out: Path,
    dpi: int = 120,
) -> list[Path]:
    """生成日趋势、活动/基础占比、周/月对比 3 张图，返回路径列表。"""
    charts_dir = Path(out) / CHARTS_DIR
    charts_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    # C1 日总热量趋势
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(
        [item.date.isoformat() for item in daily],
        [item.total_kcal for item in daily],
        marker="o",
        color="#1f77b4",
    )
    ax.set_title("Daily Total Calories")
    ax.set_xlabel("Date")
    ax.set_ylabel("kcal")
    ax.grid(alpha=0.3)
    ax.tick_params(axis="x", rotation=45)
    paths.append(_finish(fig, charts_dir / "daily_trend.png", dpi))

    # C2 活动 vs 基础占比
    active = sum(item.active_kcal for item in daily)
    basal = sum(item.basal_kcal for item in daily)
    fig, ax = plt.subplots(figsize=(6.5, 6))
    if active + basal > 0:
        ax.pie(
            [active, basal],
            labels=["Active", "Basal"],
            autopct="%1.1f%%",
            startangle=90,
        )
    else:
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
    ax.set_title("Active vs Basal Calories")
    paths.append(_finish(fig, charts_dir / "active_vs_basal.png", dpi))

    # C3 周/月对比
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for ax, periods, title in (
        (axes[0], weekly, "Weekly Totals"),
        (axes[1], monthly, "Monthly Totals"),
    ):
        ax.bar(
            [item.start.isoformat() for item in periods],
            [item.total_kcal for item in periods],
            color="#2ca02c",
        )
        ax.set_title(title)
        ax.set_ylabel("kcal")
        ax.tick_params(axis="x", rotation=45)
    paths.append(_finish(fig, charts_dir / "period_compare.png", dpi))

    return paths
