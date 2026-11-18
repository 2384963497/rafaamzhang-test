"""清洗归一：去重、单位换算、异常隔离、时区对齐（tech-design §4.5）。

本阶段是流水线中唯一有状态的阶段（已见 UUID 集合 + 隔离计数）。
"""

from __future__ import annotations

import hashlib
import itertools
import math
from collections import Counter
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Config, UNIT_TO_KCAL
from .models import CleanRecord, CleanStats, EnergyType, RawRecord

# auto 推断时只采样前 N 条记录，避免为统计偏移而全量物化迭代器
_AUTO_TZ_SAMPLE_SIZE = 2000

# 兼容大小写（如 "kj" / "KCAL"）
_UNIT_FACTORS: dict[str, float] = {
    **UNIT_TO_KCAL,
    **{unit.lower(): factor for unit, factor in UNIT_TO_KCAL.items()},
}


def _synthetic_key(record: RawRecord) -> str:
    """无 UUID 时按记录内容生成稳定的合成键。"""
    payload = "|".join(
        (
            record.type,
            record.start.isoformat(),
            record.end.isoformat(),
            repr(record.value),
            record.unit,
            record.source_name or "",
            record.device or "",
        )
    )
    return "synthetic:" + hashlib.sha1(payload.encode("utf-8")).hexdigest()


def resolve_tz(spec: str, records: Iterable[RawRecord]) -> tzinfo:
    """解析目标时区。

    ``spec == 'auto'`` 时取记录 UTC 偏移的众数并返回固定偏移时区
    （已知限制 R3：不处理夏令时）；否则返回 ``ZoneInfo(spec)``。
    无记录或无法确定时回退系统本地时区。
    """
    if spec == "auto":
        offsets: Counter[timedelta] = Counter()
        for record in records:
            offset = record.start.utcoffset()
            if offset is not None:
                offsets[offset] += 1
        if offsets:
            return timezone(offsets.most_common(1)[0][0])
    else:
        try:
            return ZoneInfo(spec)
        except ZoneInfoNotFoundError:
            pass
    local = datetime.now().astimezone().tzinfo
    return local if local is not None else timezone.utc


def clean_records(
    records: Iterable[RawRecord],
    config: Config,
) -> tuple[list[CleanRecord], CleanStats]:
    """按输入顺序清洗记录，返回（保留记录, 清洗统计）。

    规则顺序：UUID 去重 -> 单位归一 -> 值域校验 -> 类型映射 -> 时区对齐。
    """
    stats = CleanStats()
    kept: list[CleanRecord] = []
    seen: set[str] = set()
    iterator = iter(records)

    if config.timezone == "auto":
        # 采样一小段以确定偏移，再把样本放回迭代器，保证每条记录只处理一次
        sample = list(itertools.islice(iterator, _AUTO_TZ_SAMPLE_SIZE))
        tz = resolve_tz("auto", sample)
        iterator = itertools.chain(sample, iterator)
    else:
        tz = resolve_tz(config.timezone, ())

    for record in iterator:
        stats.parsed_total += 1

        # 1) 去重
        key = record.uuid.strip() if record.uuid and record.uuid.strip() else _synthetic_key(record)
        if key in seen:
            stats.duplicate_uuid += 1
            continue
        seen.add(key)

        # 2) 单位归一
        unit = (record.unit or "").strip()
        factor = _UNIT_FACTORS.get(unit)
        if factor is None:
            factor = _UNIT_FACTORS.get(unit.lower())
        if factor is None:
            stats.unknown_unit += 1
            if config.quarantine_unknown_unit:
                continue
            kcal = record.value  # 不隔离时保留原值（调用方需知悉口径）
        else:
            kcal = record.value * factor

        # 3) 值域校验（非正、超限、NaN/Inf 均隔离）
        if not math.isfinite(kcal) or kcal <= 0 or kcal > config.max_kcal_per_record:
            stats.invalid_value += 1
            continue

        # 4) 类型映射（解析阶段已过滤，此处兜底）
        try:
            energy_type = EnergyType(record.type)
        except ValueError:
            stats.wrong_type += 1
            continue

        # 5) 时区对齐到自然日
        local_start = record.start.astimezone(tz)
        kept.append(
            CleanRecord(
                uuid=key,
                type=energy_type,
                date=local_start.date(),
                start=local_start,
                end=record.end.astimezone(tz),
                kcal=kcal,
            )
        )
        stats.kept += 1

    return kept, stats
