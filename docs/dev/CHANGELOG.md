# 变更日志

版本号见 [`version.py`](../../version.py)。

## [1.1.0] - 当前

### 新增

- 「数据导出」标签页（`ui/export_tab.py`）
- 多 ASC 拼接（`multi_file_mode`、`asc_files`）
- `core/`：`conversion_coordinator`、`single_file_processor`、`multi_file_processor`

### 变更

- 转换管道基于 `enhanced_*` 与 `group_extractor`
- `EnhancedConversionService` 为兼容门面
- 文档目录：`docs/user/`、`docs/dev/`、`docs/internal/`

### 说明

- 无 CLI（`main.py`）
- 对比页不支持图表文件导出
- 输出：`Summary.csv`、分组 CSV（如 `BATP3.csv`）、`Others.csv`

## [1.0.0]

- ASC → CSV、多 DBC、BatP 分组、可视化、对比、配置与调试模式
