# 技术架构

**版本**：v1.1.1

## 概述

桌面 GUI（Tkinter + Matplotlib），将 ASC 按 DBC 解码、BatP 分组写 CSV，并对 CSV 可视化与对比。

- **GUI 入口**：`main_app.py` → `MainApplication`
- **推荐 API**：`core.conversion_coordinator.ConversionCoordinator`
- **兼容门面**：`enhanced_conversion_service.EnhancedConversionService`（GUI 使用，内部委托 Coordinator）

```python
from config import Config
from core.conversion_coordinator import ConversionCoordinator

config = Config(single_asc_file="in.asc", dbc_files=["b.dbc"], output_dir="out")
result = ConversionCoordinator(config).convert()
```

本仓库**无** `main.py` CLI。

## 分层

```
main_app.py · ui/{convert,visualize,compare,export}_tab
    → EnhancedConversionService (facade)
        → ConversionCoordinator
            → SingleFileProcessor | MultiFileProcessor
                → dbc_loader, asc_parser, enhanced_data_processor,
                   group_extractor, enhanced_csv_writer
    → core/csv_loader, core/chart_manager
```

## 模块

| 模块 | 职责 |
|------|------|
| `config.py` | 配置、`ASC_TO_CSV_CONFIG` |
| `dbc_loader.py` | DBC 映射 |
| `asc_parser.py` | ASC 解析与解码 |
| `group_extractor.py` | BatP 分组 |
| `enhanced_data_processor.py` | 聚合与分类 |
| `enhanced_csv_writer.py` | CSV + `Summary.csv` |
| `core/conversion_coordinator.py` | 流程调度 |
| `multi_asc_converter.py` | 多 ASC 合并 |
| `core/csv_loader.py` | CSV 加载（标准库 `csv`） |
| `core/chart_manager.py` | 图表 |

## 输出

- `Summary.csv`、`<GROUP>.csv`（如 `BATP3.csv`）、`Others.csv`
- 无 `All_Signals.csv`

## 技术栈

Python >= 3.10 · cantools · matplotlib · numpy · tkinter · PyInstaller（dev）

详见 [CONTRIBUTING.md](CONTRIBUTING.md)、[CHANGELOG.md](CHANGELOG.md)。
