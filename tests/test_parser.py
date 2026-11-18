"""解析阶段单测：AC1 / AC2 / AC7。"""

from pathlib import Path

import pytest

from iwatch_calories.config import ENERGY_TYPES
from iwatch_calories.errors import ParseError
from iwatch_calories.models import RawRecord
from iwatch_calories.parser import iter_energy_records


def test_parses_energy_records_and_reports_counts(sample_xml):
    stats: dict[str, int] = {}
    records = list(iter_energy_records(sample_xml, out_stats=stats))

    assert stats["total_records"] == 13
    assert stats["energy_records"] == 12
    assert len(records) == 12
    first = records[0]
    assert isinstance(first, RawRecord)
    assert first.uuid == "a1"
    assert first.type == "ActiveEnergyBurned"
    assert first.unit == "kcal"
    assert first.value == pytest.approx(300.0)
    assert first.start.utcoffset().total_seconds() == -8 * 3600
    assert first.source_name == "Apple Watch"


def test_filters_non_energy_types(sample_xml):
    records = list(iter_energy_records(sample_xml))
    assert {record.type for record in records} <= set(ENERGY_TYPES)
    assert all(record.uuid != "c5" for record in records)


def test_invalid_numeric_value_is_isolated(record_attrs, write_xml):
    xml = write_xml([
        record_attrs(UUID="bad", value="abc"),
        record_attrs(UUID="good", value="10"),
    ])
    stats: dict[str, int] = {}
    records = list(iter_energy_records(xml, out_stats=stats))
    assert [record.uuid for record in records] == ["good"]
    assert stats["invalid_value"] == 1
    assert stats["energy_records"] == 2


def test_invalid_date_is_isolated(record_attrs, write_xml):
    xml = write_xml([
        record_attrs(UUID="bad-date", startDate="not-a-date"),
        record_attrs(UUID="good-date"),
    ])
    stats: dict[str, int] = {}
    records = list(iter_energy_records(xml, out_stats=stats))
    assert [record.uuid for record in records] == ["good-date"]
    assert stats["invalid_value"] == 1


def test_iso_datetime_format_is_supported(record_attrs, write_xml):
    xml = write_xml([record_attrs(startDate="2016-03-05T08:00:00-0800")])
    records = list(iter_energy_records(xml))
    assert len(records) == 1
    assert records[0].start.utcoffset().total_seconds() == -8 * 3600


def test_corrupt_xml_raises_parse_error(tmp_path):
    broken = tmp_path / "broken.xml"
    broken.write_text('<HealthData><Record type="ActiveEnergyBurned"', encoding="utf-8")
    with pytest.raises(ParseError):
        list(iter_energy_records(broken))
