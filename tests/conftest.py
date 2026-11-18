"""公共测试 fixture：合成 XML 生成器、配置工厂、样例文件路径。"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

# 允许在未执行 pip install -e . 的环境下直接运行 pytest
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from iwatch_calories.config import Config  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

_DEFAULT_ATTRS = {
    "type": "ActiveEnergyBurned",
    "startDate": "2016-03-05 08:00:00 -0800",
    "endDate": "2016-03-05 08:30:00 -0800",
    "value": "100",
    "unit": "kcal",
    "UUID": "default-uuid",
    "sourceName": "Apple Watch",
    "device": "Watch",
}


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def record_attrs():
    """返回构造 Record 属性字典的工厂函数。"""

    def _make(**overrides) -> dict[str, str]:
        attrs = dict(_DEFAULT_ATTRS)
        attrs.update({key: str(value) for key, value in overrides.items()})
        return attrs

    return _make


@pytest.fixture
def write_xml(tmp_path):
    """返回把若干 Record 属性字典写成 export.xml 的工厂函数。"""

    def _write(records: list[dict[str, str]], name: str = "export.xml") -> Path:
        lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<HealthData locale="en_US">']
        for attrs in records:
            rendered = " ".join(f'{key}="{value}"' for key, value in attrs.items())
            lines.append(f"  <Record {rendered} />")
        lines.append("</HealthData>")
        path = tmp_path / name
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    return _write


@pytest.fixture
def sample_xml(tmp_path) -> Path:
    """复制到临时目录的合成样例，覆盖全部清洗规则。"""
    destination = tmp_path / "export.xml"
    shutil.copyfile(FIXTURES_DIR / "sample_export.xml", destination)
    return destination


@pytest.fixture
def make_config(tmp_path):
    """返回 Config 工厂；默认输出目录位于当前测试的 tmp_path 下。"""

    def _make(input_path, **overrides) -> Config:
        options = {"input": Path(input_path), "output_dir": tmp_path / "outputs"}
        options.update(overrides)
        return Config(**options)

    return _make
