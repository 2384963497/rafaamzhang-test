"""流式 XML 解析：产出热量类型的 RawRecord（tech-design §4.4）。

使用 ``ET.iterparse`` + ``elem.clear()`` 实现常量级内存占用（R2）。
本阶段只做类型筛选与字段抽取，不做单位换算、去重或时区转换。
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .config import ENERGY_TYPES
from .errors import ParseError
from .models import RawRecord

# Apple Health: "yyyy-MM-dd HH:mm:ss ZZZZ"（如 2016-03-05 08:00:00 -0800）
_DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S %z",
    "%Y-%m-%d %H:%M:%S.%f %z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f%z",
)


def _parse_datetime(raw: str | None) -> datetime | None:
    """解析 Apple Health 日期；兼容空格/T 分隔及 ISO 8601，失败返回 None。"""
    if not raw:
        return None
    text = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def iter_energy_records(
    xml_path: Path,
    *,
    out_stats: dict[str, int] | None = None,
) -> Iterator[RawRecord]:
    """惰性流式读取 XML，逐条产出热量类型记录。

    ``out_stats`` 为可选计数器字典，迭代完成后包含：
    ``total_records``（全部 Record 数）、``energy_records``（热量类型数）、
    ``invalid_value``（数值/日期无法解析而被隔离的条数）。
    """
    if out_stats is not None:
        out_stats.setdefault("total_records", 0)
        out_stats.setdefault("energy_records", 0)
        out_stats.setdefault("invalid_value", 0)

    try:
        context = ET.iterparse(str(xml_path), events=("end",))
        for _, elem in context:
            try:
                if elem.tag != "Record":
                    continue
                if out_stats is not None:
                    out_stats["total_records"] += 1

                record_type = elem.get("type", "")
                if record_type not in ENERGY_TYPES:
                    continue
                if out_stats is not None:
                    out_stats["energy_records"] += 1

                start = _parse_datetime(elem.get("startDate"))
                end = _parse_datetime(elem.get("endDate"))
                value = float(elem.get("value", ""))
                if start is None or end is None:
                    raise ValueError("startDate/endDate 无法解析")

                yield RawRecord(
                    uuid=elem.get("UUID", ""),
                    type=record_type,
                    start=start,
                    end=end,
                    value=value,
                    unit=elem.get("unit", ""),
                    source_name=elem.get("sourceName"),
                    device=elem.get("device"),
                )
            except (TypeError, ValueError):
                # value 非法 / 日期非法：隔离并计数，不污染后续聚合
                if out_stats is not None:
                    out_stats["invalid_value"] += 1
            finally:
                elem.clear()

        # 释放 iterparse 构建的根元素，进一步降低峰值内存
        try:
            context.root.clear()
        except (AttributeError, ValueError):  # pragma: no cover - 空文档等极端情况
            pass
    except ET.ParseError as exc:
        raise ParseError(f"XML 解析失败：{exc}") from exc
    except OSError as exc:
        raise ParseError(f"无法读取 XML 文件 {xml_path}：{exc}") from exc
