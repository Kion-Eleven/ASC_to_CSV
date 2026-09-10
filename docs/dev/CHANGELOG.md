# 变更日志

版本号见 [`version.py`](../../version.py)。

## [1.1.1] - 2026-09-10

### 修复

- ASC 编码探测：GBK 文件头部为纯 ASCII 时，读到中文字符中途崩溃导致整个文件解析失败；改为完整解析重试机制（`asc_parser._parse_with_encoding`）
- CI/CD：测试矩阵移除 Python 3.9（`cantools>=41` 要求 >= 3.10）；最低版本要求提升为 Python 3.10
- CI/CD：构建产物路径与 onedir 打包模式对齐（`dist/ASCtoCSV/` 文件夹）
- CI/CD：`main_app.spec` 纳入版本控制（此前被 `.gitignore` 的 `*.spec` 忽略，CI 构建找不到文件）

### 新增

- CI/CD：推送到 `main` 后自动发布/更新 `latest` 预发布版（`ASCtoCSV-latest.zip`），产物永久可下载
- `main_app.spec` 已加入仓库，打包配置（排除模块、onedir 模式）与 CI 一致

### 移除

- `ASCParser.parse_multiple`（无调用方的死代码，多文件模式走 `MultiASCConverter` 架构）

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
