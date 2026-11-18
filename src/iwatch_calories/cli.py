"""命令行入口：参数解析、配置校验、错误码与用户提示（tech-design §4.9）。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import __version__
from . import pipeline
from .config import Config
from .errors import CalorieError, ConfigError


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="iwatch-calories",
        description="分析 Apple Health 导出的热量消耗数据（第一期）",
    )
    parser.add_argument("--input", "-i", required=True, type=Path, help="输入 .zip 或 .xml 文件")
    parser.add_argument("--output", "-o", type=Path, default=Path("outputs"), help="输出目录（默认 ./outputs）")
    parser.add_argument(
        "--timezone",
        default="auto",
        help="IANA 时区名或 auto（默认 auto，按 UTC 偏移众数推断固定偏移）",
    )
    parser.add_argument("--week-start", choices=("mon", "sun"), default="mon", help="周起始日（默认 mon）")
    parser.add_argument(
        "--max-kcal-per-record",
        type=float,
        default=5000.0,
        help="单条记录热量上限，超过则隔离（默认 5000）",
    )
    parser.add_argument("--dpi", type=int, default=120, help="图表分辨率（默认 120）")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _build_config(args: argparse.Namespace) -> Config:
    """校验参数并构造 Config；非法时抛 ConfigError。"""
    if args.max_kcal_per_record <= 0:
        raise ConfigError("--max-kcal-per-record 必须大于 0")
    if args.dpi <= 0:
        raise ConfigError("--dpi 必须大于 0")
    if args.timezone != "auto":
        try:
            ZoneInfo(args.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ConfigError(f"未知时区：{args.timezone}，请使用 IANA 时区名或 auto") from exc
    return Config(
        input=args.input,
        output_dir=args.output,
        timezone=args.timezone,
        week_start=args.week_start,
        max_kcal_per_record=args.max_kcal_per_record,
        dpi=args.dpi,
    )


def main(argv: list[str] | None = None) -> int:
    """程序入口：成功返回 0，参数错误返回 2，运行错误返回 1。"""
    args = build_parser().parse_args(argv)
    try:
        config = _build_config(args)
        result = pipeline.run(config)
    except ConfigError as exc:
        print(f"参数错误：{exc}", file=sys.stderr)
        return 2
    except CalorieError as exc:
        print(f"处理失败（{type(exc).__name__}）：{exc}", file=sys.stderr)
        print("建议：检查输入路径、压缩包内容与 XML 格式后重试。", file=sys.stderr)
        return 1
    except Exception as exc:  # 兜底：任何未预期异常都返回非零码，避免伪装成功
        print(f"未预期错误（{type(exc).__name__}）：{exc}", file=sys.stderr)
        return 1

    stats = result.clean_stats
    print(
        f"分析完成：记录总数 {stats.records_total}，热量记录 {stats.parsed_total}，"
        f"有效记录 {stats.kept}，有效天数 {result.summary.valid_days}"
    )
    print(f"时间范围：{result.summary.start_date.isoformat()} ~ {result.summary.end_date.isoformat()}")
    print(f"报告：{result.report}")
    print(f"表格：{', '.join(str(path) for path in result.tables)}")
    print(f"图表：{', '.join(str(path) for path in result.charts)}")
    return 0
