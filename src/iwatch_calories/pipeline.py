"""流水线编排（tech-design §1.2、§4.9、§5.3）。

关键性质：所有计算在内存中完成且校验通过后才落盘；落盘先写入临时暂存目录，
全部产物生成成功后再复制到输出目录，避免中途失败留下误导性空报告。
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from .aggregator import aggregate_daily, aggregate_period, summarize, write_tables
from .cleaner import clean_records
from .config import Config
from .errors import NoEnergyDataError
from .loader import load_export
from .models import AnalysisResult
from .parser import iter_energy_records
from .reporter import render_report
from .visualizer import render_charts


def run(config: Config) -> AnalysisResult:
    """执行完整分析流水线并返回最终产物。"""
    # ---- 阶段 1-2：加载 + 流式解析 + 清洗（全部在内存中）----
    parser_stats: dict[str, int] = {}
    with load_export(config.input) as xml_path:
        raw_records = iter_energy_records(xml_path, out_stats=parser_stats)
        clean, stats = clean_records(raw_records, config)

    if not clean:
        raise NoEnergyDataError("未解析到任何有效热量记录，已中止（未生成输出文件）")

    # 合并解析阶段统计（总记录数 / 热量记录数 / 数值日期异常数）
    stats.records_total = parser_stats.get("total_records", stats.records_total)
    stats.parsed_total = parser_stats.get("energy_records", stats.parsed_total)
    stats.invalid_value += parser_stats.get("invalid_value", 0)

    # ---- 阶段 3：聚合与统计（仍无副作用）----
    daily = aggregate_daily(clean)
    weekly = aggregate_period(daily, "week", config.week_start)
    monthly = aggregate_period(daily, "month")
    summary = summarize(daily)

    result = AnalysisResult(
        daily=daily,
        weekly=weekly,
        monthly=monthly,
        summary=summary,
        clean_stats=stats,
        charts=[],
        report=Path(),
        tables=[],
        config=config,
    )

    # ---- 阶段 4：校验通过后统一落盘（暂存 -> 提交）----
    output_dir = Path(config.output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".iwatch_calories_stage_", dir=output_dir.parent) as stage_name:
        staging = Path(stage_name)
        staged_files = []
        staged_files.extend(write_tables(result, staging))
        staged_files.extend(
            render_charts(result.daily, result.weekly, result.monthly, staging, config.dpi)
        )
        staged_files.append(render_report(result, staging))

        final_files: list[Path] = []
        try:
            for staged in staged_files:
                destination = output_dir / staged.relative_to(staging)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(staged, destination)
                final_files.append(destination)
        except OSError:
            # 复制中途失败时回滚已复制的文件
            for destination in final_files:
                try:
                    destination.unlink()
                except OSError:  # pragma: no cover - 清理失败不掩盖原始异常
                    pass
            raise

    result.tables = [path for path in final_files if path.suffix in (".csv", ".json")]
    result.charts = [path for path in final_files if path.suffix == ".png"]
    result.report = next(path for path in final_files if path.name == "analysis_report.md")
    return result
