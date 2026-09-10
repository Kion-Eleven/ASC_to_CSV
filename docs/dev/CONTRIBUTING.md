# 贡献指南

## 环境

```bash
python -m venv venv
# 激活 venv
pip install -r requirements-dev.txt
```

## 运行与测试

```bash
python main_app.py
pytest tests/ -v
pytest tests/ -v --tb=short --cov=. --cov-report=term-missing
```

## 代码检查（与 CI 一致）

```bash
pip install flake8 mypy
flake8 . --max-line-length=120 --exclude=venv,build,dist,__pycache__,tests
mypy . --ignore-missing-imports --exclude "venv|build|dist|tests"
```

可选：`ruff check .`（见 `requirements-dev.txt`）

## 版本号

单一来源：[`version.py`](../../version.py)。发布前更新 [`CHANGELOG.md`](CHANGELOG.md)。

## Windows 打包

```bash
pip install -r requirements-dev.txt
python convert_icon.py
pyinstaller main_app.spec --clean
```

或 `build.bat` → `dist/ASCtoCSV/`（onedir 文件夹，内含 `ASCtoCSV.exe`）

## 文档

- 用户变更 → `docs/user/` + `CHANGELOG.md`
- 架构变更 → `docs/dev/ARCHITECTURE.md`
- 勿向 `docs/USER_MANUAL.md` 等废弃路径写正文

## VS Code

使用仓库 `.vscode/launch.json` 调试 `main_app.py`。长文见 `docs/internal/VSCODE_CICD_GUIDE.md`。
