"""共享数据模型（tech-design §3）。

所有模型均为轻量数据结构，不承载行为逻辑；不变量在产出它们的阶段保证。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - 仅用于类型提示，避免运行时循环导入
    from .config import Config


class EnergyType(str, Enum):
    """热量记录的两类口径。"""

    ACTIVE = "ActiveEnergyBurned"
    BASAL = "BasalEnergyBurned"


@dataclass(frozen=True)
class RawRecord:
    """解析阶段产出，尚未清洗。"""

    uuid: str
    type: str                 # 原始 type 字符串，清洗阶段映射为 EnergyType
    start: datetime           # 含时区信息（来自 XML 偏移）
    end: datetime
    value: float
    unit: str
    source_name: str | None = None
    device: str | None = None


@dataclass(frozen=True)
class CleanRecord:
    """清洗后记录，单位已归一为 kcal，日期已对齐到目标时区。"""

    uuid: str
    type: EnergyType
    date: date                # 目标时区下的自然日
    start: datetime
    end: datetime
    kcal: float


@dataclass(frozen=True)
class DailyCalories:
    """单日聚合结果。"""

    date: date
    active_kcal: float
    basal_kcal: float
    total_kcal: float         # = active_kcal + basal_kcal（容差 1e-2）
    active_ratio: float       # = active_kcal / total_kcal，total<=0 时为 0.0


@dataclass(frozen=True)
class PeriodCalories:
    """周/月聚合结果。"""

    period: str               # "week" | "month"
    start: date
    end: date
    active_kcal: float
    basal_kcal: float
    total_kcal: float
    active_ratio: float


@dataclass
class CleanStats:
    """清洗隔离与计数，写入报告与 summary。"""

    parsed_total: int = 0     # 热量类型记录数（含被隔离者）
    kept: int = 0
    duplicate_uuid: int = 0
    invalid_value: int = 0    # 非正 / 超阈值 / 解析阶段数值或日期异常
    unknown_unit: int = 0
    wrong_type: int = 0       # 解析阶段已过滤，保留字段便于审计
    records_total: int = 0    # XML 中全部 Record 元素数（AC1 记录总数）


@dataclass
class SummaryStats:
    """全局统计量。"""

    start_date: date
    end_date: date
    valid_days: int
    missing_days: int
    active_mean: float
    basal_mean: float
    total_mean: float
    total_median: float
    total_max: float
    total_min: float


@dataclass
class AnalysisResult:
    """流水线最终产物。"""

    daily: list[DailyCalories]
    weekly: list[PeriodCalories]
    monthly: list[PeriodCalories]
    summary: SummaryStats
    clean_stats: CleanStats
    charts: list[Path]
    report: Path
    tables: list[Path]
    config: Config | None = None  # 供报告渲染口径说明使用（向后兼容的可选字段）
