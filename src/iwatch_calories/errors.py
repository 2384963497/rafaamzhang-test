"""自定义异常层次（tech-design §4.2）。"""


class CalorieError(Exception):
    """所有业务异常的基类。"""


class InputError(CalorieError):
    """输入文件不存在、类型不支持、zip 损坏或缺少 export.xml。"""


class ParseError(CalorieError):
    """XML 解析失败或不可读。"""


class NoEnergyDataError(CalorieError):
    """解析后无热量记录，或清洗后无有效记录。"""


class ConfigError(CalorieError):
    """命令行参数非法。"""
