# ASC to CSV 功能列表

**版本**：v1.1.0 · **入口**：`python main_app.py`

## 数据转换 (ConvertTab)

| 功能 | 描述 |
|------|------|
| ASC 单文件模式 | 选择单个 ASC 转换 |
| ASC 多文件拼接 | 多 ASC 按时间戳排序后拼接 |
| DBC 管理 | 添加/删除多个 DBC |
| 采样间隔 | 可配置（秒） |
| 分组规则 | BatP+数字/字母 → 独立 CSV；其余 → `Others.csv` |
| CSV 编码 | utf-8-sig, utf-8, gbk, gb2312 |
| 调试模式 | 详细日志 |
| 配置 | 保存/加载 `config.json` |

## 数据可视化 (VisualizeTab)

| 功能 | 描述 |
|------|------|
| CSV 选择 / 刷新 | 输出目录下文件列表 |
| 列搜索 | 过滤列名 |
| 缩放 / 滚动 | 滑块、滚轮、拖拽 |
| 十字参考线 | 显示坐标 |

## 数据对比 (CompareTab)

| 功能 | 描述 |
|------|------|
| 多文件 / 多列 | 叠加曲线对比 |
| 图表交互 | 缩放、滚动（与可视化类似） |

**不支持**：对比图导出为图片文件。

## 数据导出 (ExportTab)

| 功能 | 描述 |
|------|------|
| 列选择 | 从 CSV 多选列 |
| 预览 | 所选列样本数据 |
| 导出 | 自定义文件名、路径、编码 |

## 数据流

```
ASC → [ConvertTab] → CSV → [VisualizeTab] → 图表
                      ├→ [ExportTab] → 子集 CSV
                      └→ [CompareTab] → 对比图（仅界面）
```

## 模块结构（简）

```
main_app.py
core/   conversion_coordinator, csv_loader, chart_manager, ...
ui/     convert_tab, visualize_tab, compare_tab, export_tab
```

详见 [../dev/ARCHITECTURE.md](../dev/ARCHITECTURE.md)。
