"""配置常量与配置对象。

配置合法性由 CLI 层校验，下游模块只消费不校验（见 tech-design §4.1）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """一次分析的不可变配置。"""

    input: Path
    output_dir: Path
    timezone: str = "auto"          # IANA 时区名或 "auto"
    week_start: str = "mon"         # "mon" | "sun"
    max_kcal_per_record: float = 5000.0
    quarantine_unknown_unit: bool = True
    dpi: int = 120


# 单位 -> kcal 换算系数（tech-design §5.1）
UNIT_TO_KCAL: dict[str, float] = {
    "kcal": 1.0,
    "cal": 0.001,
    "kJ": 0.239006,
}

# Apple Health 热量记录类型
ENERGY_TYPES: tuple[str, ...] = ("ActiveEnergyBurned", "BasalEnergyBurned")

# 输出文件名（集中定义，便于替换）
DAILY_CSV = "daily_calories.csv"
WEEKLY_CSV = "weekly_calories.csv"
MONTHLY_CSV = "monthly_calories.csv"
SUMMARY_JSON = "summary.json"
REPORT_MD = "analysis_report.md"
CHARTS_DIR = "charts"
