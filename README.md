# iWatch 健康数据热量消耗分析（第一期）

离线命令行工具：读取 Apple Health 导出的 `export.zip` / `export.xml`，抽取活动热量（`ActiveEnergyBurned`）与基础热量（`BasalEnergyBurned`），完成清洗、聚合与统计，产出 CSV/JSON 表格、3 类图表和一份 Markdown 分析报告。

## 1. 环境要求

- Python 3.10+
- 依赖：`matplotlib>=3.5`（图表）；开发测试额外需要 `pytest>=7`

## 2. 安装

在仓库根目录执行：

```bash
python3 -m pip install -e .
```

安装开发/测试依赖：

```bash
python3 -m pip install -e '.[dev]'
```

## 3. 运行

```bash
# 直接处理导出的压缩包
python3 -m iwatch_calories --input export.zip --output outputs

# 处理已解压的 export.xml，并显式指定时区与周起始日
python3 -m iwatch_calories -i export.xml -o outputs --timezone Asia/Shanghai --week-start mon
```

安装后也可使用控制台命令 `iwatch-calories`（参数相同）。

### 3.1 参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--input`, `-i` | 必填 | 输入文件：`.zip`（内部需含 `export.xml`）或 `.xml` |
| `--output`, `-o` | `outputs` | 输出目录；计算全部成功后才写入 |
| `--timezone` | `auto` | IANA 时区名（如 `Asia/Shanghai`），或 `auto`（按记录 UTC 偏移众数推断固定偏移；不处理夏令时） |
| `--week-start` | `mon` | 周起始日：`mon` 或 `sun` |
| `--max-kcal-per-record` | `5000` | 单条记录热量上限，超过视为异常并隔离 |
| `--dpi` | `120` | 图表分辨率 |
| `--version` | — | 打印版本号并退出 |

## 4. 输出物

| 文件 | 说明 |
| --- | --- |
| `outputs/daily_calories.csv` | 日明细：`date,active_kcal,basal_kcal,total_kcal,active_ratio` |
| `outputs/weekly_calories.csv` | 周汇总：`period_start,period_end,active_kcal,basal_kcal,total_kcal,active_ratio` |
| `outputs/monthly_calories.csv` | 月汇总（表头同周汇总） |
| `outputs/summary.json` | 时间范围、有效/缺失天数、均值/中位数/极值、清洗统计 |
| `outputs/charts/daily_trend.png` | 日总热量趋势折线图 |
| `outputs/charts/active_vs_basal.png` | 活动 vs 基础热量占比图 |
| `outputs/charts/period_compare.png` | 周/月热量对比柱状图 |
| `outputs/analysis_report.md` | 中文分析报告（数据概览、口径、统计、图表、质量说明） |

浮点数值统一保留 2 位小数。

## 5. 口径与规则

- **总热量** = 活动热量 + 基础热量；**活动占比** = 活动热量 / 总热量（总热量为 0 时取 0）。
- **单位归一**：`kcal` ×1、`cal` ×0.001、`kJ` ×0.239006；未知单位默认隔离并计数。
- **去重**：以 `UUID` 为键；缺失 UUID 时按记录内容生成合成键。
- **异常隔离**：非正值、超过 `--max-kcal-per-record` 的记录不参与聚合。
- **日对齐**：按目标时区将记录起始时间转换为自然日；缺失日不写入日表，但计入 `missing_days` 并在报告中说明。
- **解析**：使用 `xml.etree.ElementTree.iterparse` 流式处理并清空已处理元素，内存占用与文件大小无关。
- **第一期不做**：Workout 维度分析、心率/睡眠等其他指标分析、网络同步、医学结论。

## 6. 测试

```bash
python3 -m pip install -e '.[dev]'
python3 -m pytest -q
```

测试覆盖解析、清洗、聚合核心逻辑以及基于合成 `export.xml` 的端到端流程（含错误场景与输出原子性检查）。

## 7. 错误处理

输入不存在、压缩包损坏/无 `export.xml`、XML 损坏、无有效热量记录等场景会向 stderr 输出中文错误并返回非零退出码；失败时不会在输出目录留下误导性报告。

## 8. 许可与范围

本项目为第一期实现，仅处理单用户本地导出数据，不涉及隐私合规工程或设备直连。
