# ASC to CSV 转换与可视化工具

将 CAN 总线 ASC 日志（Vector CANoe/CANalyzer 格式）按 DBC 解码为 CSV，并提供可视化、对比与列导出功能。

**当前版本**：v1.1.0（见 [`version.py`](version.py)）

## 功能概览

| 模块 | 说明 |
|------|------|
| **数据转换** | 单 ASC / 多 ASC 拼接、多 DBC、BatP 智能分组、空值填充 |
| **数据可视化** | 曲线图、缩放/滚动、十字参考线、列搜索 |
| **数据对比** | 多 CSV、多信号叠加（**不支持**图表文件导出） |
| **数据导出** | 从 CSV 选择列导出子集 |

## 快速开始

```bash
git clone <repository-url>
cd asc_to_csv
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
python main_app.py
```

复制 [`config.example.json`](config.example.json) 为 `config.json` 并按需修改（可选；GUI 中也可配置并保存）。

> **说明**：本仓库**不提供**独立 CLI 入口（无 `main.py`）。程序化调用请使用 `ConversionCoordinator` 或兼容门面 `EnhancedConversionService`（见 [架构文档](docs/dev/ARCHITECTURE.md)）。

## 系统要求

- Python >= 3.8（推荐 3.11，与 CI 一致）
- 内存建议 4GB+
- **GUI**：Windows 10/11 为主要测试平台；Linux/macOS 需安装中文字体以保证图表中文显示

## 依赖

- 运行时：[`requirements.txt`](requirements.txt)（`cantools`、`matplotlib`、`numpy`）
- 开发/打包：[`requirements-dev.txt`](requirements-dev.txt)（`pytest`、`pyinstaller` 等）

## 配置 (`config.json`)

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `asc_file` | string | `""` | 单文件模式下的 ASC 路径 |
| `asc_files` | list | `[]` | 多文件模式下的 ASC 列表 |
| `multi_file_mode` | bool | `false` | 是否启用多 ASC 按时间戳拼接 |
| `dbc_files` | list | `[]` | DBC 路径列表 |
| `output_dir` | string | `""` | CSV 输出目录 |
| `sample_interval` | float | `0.1` | 采样间隔（秒） |
| `group_size` | int | `5` | 写入相关分组参数 |
| `csv_encoding` | string | `utf-8-sig` | CSV 编码 |
| `debug` | bool | `false` | 调试日志 |

环境变量 `ASC_TO_CSV_CONFIG` 可指定配置文件路径。

## 输出文件

| 文件 | 说明 |
|------|------|
| `Summary.csv` | 转换汇总 |
| `BATP1.csv`、`BATP3.csv`… | 按 BatP 规则分组（组名**大写**） |
| `Others.csv` | 未匹配 BatP 规则的信号 |

不包含 `All_Signals.csv`。

## 架构（简图）

```
main_app.py (GUI)
    → ui/* (Convert / Visualize / Compare / Export)
    → enhanced_conversion_service (facade)
        → core/conversion_coordinator
            → single_file_processor | multi_file_processor
    → core/csv_loader, core/chart_manager
```

详见 [docs/dev/ARCHITECTURE.md](docs/dev/ARCHITECTURE.md)。

## 开发与测试

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

详见 [docs/dev/CONTRIBUTING.md](docs/dev/CONTRIBUTING.md)。

## Windows 打包

```bash
pip install -r requirements-dev.txt
build.bat
# 或: python convert_icon.py && pyinstaller main_app.spec --clean
```

产物：`dist/ASCtoCSV.exe`。可选：放置 `resource/icon.png` 后运行 `convert_icon.py` 生成 `icon.ico`。

## 文档索引

| 文档 | 读者 |
|------|------|
| [docs/README.md](docs/README.md) | 文档总览 |
| [docs/user/QUICKSTART.md](docs/user/QUICKSTART.md) | 快速上手 |
| [docs/user/USER_GUIDE.md](docs/user/USER_GUIDE.md) | 完整用户指南 |
| [docs/user/FEATURES.md](docs/user/FEATURES.md) | 功能清单 |
| [docs/dev/ARCHITECTURE.md](docs/dev/ARCHITECTURE.md) | 技术架构 |
| [docs/dev/CONTRIBUTING.md](docs/dev/CONTRIBUTING.md) | 贡献与 CI |
| [docs/dev/CHANGELOG.md](docs/dev/CHANGELOG.md) | 版本历史 |

## 许可证

MIT License
