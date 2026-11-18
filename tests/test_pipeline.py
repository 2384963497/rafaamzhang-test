"""端到端与错误场景测试：AC1–AC7。"""

import json
import zipfile
from pathlib import Path

import pytest

from iwatch_calories import pipeline
from iwatch_calories.cli import main
from iwatch_calories.errors import InputError, NoEnergyDataError, ParseError


def test_end_to_end_sample(sample_xml, make_config):
    result = pipeline.run(make_config(sample_xml))

    stats = result.clean_stats
    assert stats.records_total == 13
    assert stats.parsed_total == 12
    assert stats.kept == 8
    assert stats.duplicate_uuid == 1
    assert stats.invalid_value == 2      # 非正值 + 超限
    assert stats.unknown_unit == 1

    assert len(result.daily) == 3
    assert len(result.weekly) == 2
    assert len(result.monthly) == 1
    assert [day.total_kcal for day in result.daily] == [
        pytest.approx(2328.012, abs=1e-2),
        pytest.approx(1800.0),
        pytest.approx(1800.0),
    ]
    for day in result.daily:
        assert abs(day.total_kcal - day.active_kcal - day.basal_kcal) < 1e-2
    assert result.summary.missing_days == 1

    assert len(result.tables) == 4
    assert len(result.charts) == 3
    assert all(chart.is_file() and chart.stat().st_size > 0 for chart in result.charts)
    assert result.report.is_file()
    report_text = result.report.read_text(encoding="utf-8")
    for heading in ("## 1. 数据概览", "## 2. 口径说明", "## 3. 关键统计", "## 4. 图表", "## 5. 质量说明"):
        assert heading in report_text
    assert "charts/daily_trend.png" in report_text
    assert (result.report.parent / "charts" / "daily_trend.png").is_file()

    daily_csv = next(path for path in result.tables if path.name == "daily_calories.csv")
    assert daily_csv.read_text(encoding="utf-8").startswith(
        "date,active_kcal,basal_kcal,total_kcal,active_ratio\n2016-03-05,"
    )
    summary_json = json.loads((result.report.parent / "summary.json").read_text(encoding="utf-8"))
    assert summary_json["clean_stats"]["duplicate_uuid"] == 1


def test_zip_input_is_supported(sample_xml, tmp_path, make_config):
    archive = tmp_path / "export.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.write(sample_xml, arcname="export.xml")
    result = pipeline.run(make_config(archive))
    assert len(result.daily) == 3


def test_missing_input_does_not_create_output(tmp_path, make_config):
    missing = tmp_path / "does-not-exist.xml"
    with pytest.raises(InputError):
        pipeline.run(make_config(missing))
    assert not (tmp_path / "outputs").exists()


def test_corrupt_xml_does_not_create_output(tmp_path, make_config):
    broken = tmp_path / "broken.xml"
    broken.write_text("<HealthData><Record", encoding="utf-8")
    with pytest.raises(ParseError):
        pipeline.run(make_config(broken))
    assert not (tmp_path / "outputs").exists()


def test_no_energy_data_does_not_create_output(record_attrs, write_xml, make_config):
    xml = write_xml([record_attrs(type="HKQuantityTypeIdentifierHeartRate", UUID="hr")])
    with pytest.raises(NoEnergyDataError):
        pipeline.run(make_config(xml))
    assert not (xml.parent / "outputs").exists()


def test_cli_success_and_error_codes(sample_xml, tmp_path):
    output = tmp_path / "cli_outputs"
    assert main(["-i", str(sample_xml), "-o", str(output), "--dpi", "60"]) == 0
    assert (output / "analysis_report.md").is_file()

    assert main(["-i", str(tmp_path / "missing.xml"), "-o", str(tmp_path / "err1")]) == 1
    assert not (tmp_path / "err1").exists()

    assert main([
        "-i", str(sample_xml), "-o", str(tmp_path / "err2"),
        "--timezone", "Not/AZone",
    ]) == 2
    assert not (tmp_path / "err2").exists()

    with pytest.raises(SystemExit) as exc:
        main(["-i", str(sample_xml), "--week-start", "friday"])
    assert exc.value.code == 2


def test_large_xml_streaming(record_attrs, write_xml, make_config):
    """1 万条记录的大文件冒烟：验证流式解析与去重不遗漏（非计时断言）。"""
    records = [
        record_attrs(UUID=f"stream-{index}", value="1", startDate="2016-03-05 08:00:00 -0800")
        for index in range(10_000)
    ]
    xml = write_xml(records)
    result = pipeline.run(make_config(xml))
    assert result.clean_stats.records_total == 10_000
    assert result.clean_stats.kept == 10_000
    assert len(result.daily) == 1
