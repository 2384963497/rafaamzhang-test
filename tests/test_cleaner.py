"""清洗阶段单测：AC3。"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from iwatch_calories.cleaner import clean_records, resolve_tz
from iwatch_calories.models import EnergyType, RawRecord

_APPLE_FMT = "%Y-%m-%d %H:%M:%S %z"


def _raw(
    uuid: str = "x",
    record_type: str = "ActiveEnergyBurned",
    value: float = 100.0,
    unit: str = "kcal",
    start: str = "2016-03-05 08:00:00 -0800",
) -> RawRecord:
    parsed = datetime.strptime(start, _APPLE_FMT)
    return RawRecord(
        uuid=uuid,
        type=record_type,
        start=parsed,
        end=parsed + timedelta(minutes=30),
        value=value,
        unit=unit,
    )


def test_unit_conversion_and_uuid_dedup(make_config):
    records = [
        _raw("u1", value=1, unit="kcal"),
        _raw("u2", value=1000, unit="cal"),
        _raw("u3", value=1000, unit="kJ"),
        _raw("u1", value=999, unit="kcal"),  # 重复 UUID
    ]
    clean, stats = clean_records(records, make_config("dummy.xml"))

    assert stats.parsed_total == 4
    assert stats.kept == 3
    assert stats.duplicate_uuid == 1
    assert [round(item.kcal, 3) for item in clean] == [1.0, 1.0, 239.006]
    assert all(item.type is EnergyType.ACTIVE for item in clean)


def test_unknown_unit_is_quarantined_by_default(make_config):
    records = [_raw("u1", unit="Count"), _raw("u2", unit="kcal")]
    clean, stats = clean_records(records, make_config("dummy.xml"))
    assert [item.uuid for item in clean] == ["u2"]
    assert stats.unknown_unit == 1
    assert stats.kept == 1


def test_unknown_unit_can_be_kept_when_configured(make_config):
    records = [_raw("u1", unit="Count", value=42), _raw("u2", unit="kcal")]
    config = make_config("dummy.xml", quarantine_unknown_unit=False)
    clean, stats = clean_records(records, config)
    assert len(clean) == 2
    assert stats.unknown_unit == 1
    assert next(item.kcal for item in clean if item.uuid == "u1") == pytest.approx(42.0)


def test_invalid_values_are_isolated(make_config):
    records = [
        _raw("zero", value=0),
        _raw("negative", value=-3),
        _raw("huge", value=6000),
        _raw("valid", value=200),
    ]
    clean, stats = clean_records(records, make_config("dummy.xml", max_kcal_per_record=5000))
    assert [item.uuid for item in clean] == ["valid"]
    assert stats.invalid_value == 3


def test_missing_uuid_uses_synthetic_key(make_config):
    duplicates = [_raw("", value=10), _raw("", value=10)]
    clean, stats = clean_records(duplicates, make_config("dummy.xml"))
    assert len(clean) == 1
    assert stats.duplicate_uuid == 1
    assert clean[0].uuid.startswith("synthetic:")


def test_timezone_alignment_to_local_day(make_config):
    moment = datetime.fromisoformat("2016-03-05T23:30:00-08:00")
    record = RawRecord(
        uuid="tz", type="ActiveEnergyBurned",
        start=moment, end=moment,
        value=100, unit="kcal",
    )
    clean, _ = clean_records([record], make_config("dummy.xml", timezone="Asia/Shanghai"))
    assert clean[0].date.isoformat() == "2016-03-06"


def test_auto_timezone_uses_offset_mode():
    records = [
        _raw("a", start="2016-03-05 08:00:00 -0800"),
        _raw("b", start="2016-03-05 08:00:00 -0800"),
        _raw("c", start="2016-03-05 08:00:00 +0000"),
    ]
    tz = resolve_tz("auto", records)
    assert tz.utcoffset(None) == timedelta(hours=-8)


def test_explicit_iana_timezone():
    tz = resolve_tz("Asia/Shanghai", [])
    assert isinstance(tz, ZoneInfo)
    assert tz.key == "Asia/Shanghai"
