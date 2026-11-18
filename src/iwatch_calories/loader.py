"""输入加载：接受 ``.zip`` / ``.xml``，返回可读的 XML 路径（tech-design §4.3）。"""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .errors import InputError

_EXPORT_XML = "export.xml"


@contextmanager
def load_export(input_path: Path) -> Iterator[Path]:
    """提供输入 XML 的路径，退出上下文时清理临时目录。

    - ``.xml``：直接返回原路径；
    - ``.zip``：只解压包内的 ``export.xml`` 到临时目录（固定文件名，避免 Zip Slip）。

    Raises:
        InputError: 路径不存在、类型不支持、压缩包损坏或包内缺少 export.xml。
    """
    path = Path(input_path)

    if not path.exists():
        raise InputError(f"输入文件不存在：{path}")
    if not path.is_file():
        raise InputError(f"输入路径不是文件：{path}")

    suffix = path.suffix.lower()
    if suffix == ".xml":
        yield path
        return
    if suffix != ".zip":
        raise InputError(f"不支持的输入类型 '{suffix}'，请提供 .zip 或 .xml 文件：{path}")

    try:
        with tempfile.TemporaryDirectory(prefix="iwatch_calories_") as tmp_dir:
            with zipfile.ZipFile(path) as archive:
                candidates = [
                    name for name in archive.namelist()
                    if name == _EXPORT_XML or name.endswith("/" + _EXPORT_XML)
                ]
                if not candidates:
                    raise InputError(f"压缩包内未找到 {_EXPORT_XML}：{path}")
                # 优先使用包根目录下的 export.xml
                member = _EXPORT_XML if _EXPORT_XML in candidates else candidates[0]
                target = Path(tmp_dir) / _EXPORT_XML
                with archive.open(member) as source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
            yield target
    except InputError:
        raise
    except (zipfile.BadZipFile, OSError) as exc:
        raise InputError(f"无法读取输入压缩包 {path}：{exc}") from exc
