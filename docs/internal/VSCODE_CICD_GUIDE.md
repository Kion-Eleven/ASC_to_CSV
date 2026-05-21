# VSCode运行调试配置与CI/CD部署指南

本文档详细说明ASC to CSV项目的VSCode运行调试配置和CI/CD流程部署方案。

---

## 第一部分：VSCode运行与调试功能配置

### 一、运行和调试功能的核心作用与价值

#### 1.1 核心功能概述

VSCode的运行和调试功能是软件开发过程中不可或缺的工具，提供以下核心能力：

| 功能类别 | 具体功能 | 作用说明 |
|----------|----------|----------|
| **代码执行控制** | 断点设置、单步执行、继续运行、暂停 | 精确控制程序执行流程，在关键位置暂停检查 |
| **变量状态监控** | 变量查看、监视表达式、变量修改 | 实时观察变量值变化，验证数据状态 |
| **程序流程跟踪** | 调用堆栈、线程管理、模块追踪 | 理解程序执行路径，定位逻辑问题 |
| **异常处理** | 异常断点、条件断点、日志断点 | 在异常发生时自动暂停，快速定位错误源 |
| **内存分析** | 内存快照、对象引用追踪 | 分析内存使用情况，排查内存泄漏 |

#### 1.2 调试功能的核心价值

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         调试功能价值链                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   问题发现 ──→ 问题定位 ──→ 问题分析 ──→ 问题验证 ──→ 问题解决           │
│       │           │           │           │           │                    │
│       ▼           ▼           ▼           ▼           ▼                    │
│   异常捕获    断点暂停     变量检查     代码修改     继续运行               │
│   日志输出    堆栈追踪     条件判断     逻辑验证     结果确认               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**核心价值量化**：

| 指标 | 无调试工具 | 有调试工具 | 效率提升 |
|------|-----------|-----------|----------|
| 问题定位时间 | 30-60分钟 | 5-10分钟 | 80%+ |
| 代码理解时间 | 数小时 | 数十分钟 | 70%+ |
| Bug修复准确率 | 60% | 95% | 35%+ |
| 回归问题率 | 20% | 5% | 75%- |

---

### 二、主要应用场景分析

#### 2.1 开发阶段应用场景

| 场景 | 描述 | 调试技术应用 |
|------|------|--------------|
| **功能开发** | 新功能编码过程中验证逻辑 | 断点+变量监视 |
| **单元测试** | 验证测试用例执行过程 | 测试调试配置 |
| **接口对接** | 调试与外部系统的交互 | 条件断点+日志 |
| **算法实现** | 验证算法逻辑正确性 | 单步执行+变量追踪 |

#### 2.2 测试阶段应用场景

| 场景 | 描述 | 调试技术应用 |
|------|------|--------------|
| **Bug复现** | 重现并定位问题 | 异常断点+堆栈分析 |
| **边界测试** | 验证边界条件处理 | 条件断点 |
| **性能分析** | 定位性能瓶颈 | 性能分析工具 |
| **回归测试** | 验证修复效果 | 测试覆盖率分析 |

#### 2.3 维护阶段应用场景

| 场景 | 描述 | 调试技术应用 |
|------|------|--------------|
| **线上问题** | 分析生产环境问题 | 远程调试+日志分析 |
| **代码审查** | 理解他人代码逻辑 | 调试执行流程 |
| **重构验证** | 确保重构后功能正确 | 测试+调试验证 |

---

### 三、对开发效率的具体提升

#### 3.1 效率提升量化分析

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    开发效率提升矩阵                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   传统调试方式:                                                              │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐               │
│   │ 添加日志 │ → │ 运行程序 │ → │ 分析输出 │ → │ 修改代码 │ → 循环...      │
│   └──────────┘   └──────────┘   └──────────┘   └──────────┘               │
│   时间消耗: 每次循环 5-15 分钟                                               │
│                                                                             │
│   VSCode调试方式:                                                           │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐                               │
│   │ 设置断点 │ → │ 调试运行 │ → │ 直接定位 │                               │
│   └──────────┘   └──────────┘   └──────────┘                               │
│   时间消耗: 单次 2-5 分钟                                                    │
│                                                                             │
│   效率提升: 60-80%                                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 3.2 具体提升点

| 提升维度 | 具体表现 | 量化指标 |
|----------|----------|----------|
| **问题定位速度** | 无需反复添加/删除日志 | 减少70%定位时间 |
| **调试复杂度** | 可视化界面直观操作 | 降低80%操作复杂度 |
| **代码准确性** | 实时验证修改效果 | 提高35%首次修复率 |
| **学习成本** | 统一调试体验 | 减少50%学习时间 |

---

### 四、配置文件创建方法

#### 4.1 配置文件存储位置

```
项目根目录/
├── .vscode/
│   ├── launch.json    # 调试配置文件
│   ├── tasks.json     # 任务配置文件
│   └── settings.json  # 工作区设置
├── main.py
└── ...
```

#### 4.2 通过界面向导创建

**步骤一**：打开VSCode，加载项目文件夹

**步骤二**：进入调试视图
- 快捷键：`Ctrl+Shift+D`
- 或点击左侧活动栏调试图标

**步骤三**：创建配置文件
1. 点击"创建launch.json"
2. 选择调试类型（Python）
3. 选择配置模板

**步骤四**：编辑配置
- 自动生成的配置文件会在编辑器中打开
- 根据需要修改配置参数

#### 4.3 手动创建配置文件

**方法一**：直接创建文件
```bash
# 创建.vscode目录
mkdir .vscode

# 创建launch.json
touch .vscode/launch.json
```

**方法二**：使用VSCode命令面板
1. `Ctrl+Shift+P` 打开命令面板
2. 输入 "Debug: Open launch.json"
3. 选择创建新配置

---

### 五、关键配置参数详解

#### 5.1 launch.json 核心参数

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "配置名称",
            "type": "debugpy",
            "request": "launch",
            "program": "${workspaceFolder}/main.py",
            "console": "integratedTerminal",
            "justMyCode": false,
            "args": [],
            "env": {},
            "cwd": "${workspaceFolder}"
        }
    ]
}
```

#### 5.2 参数详细说明

| 参数 | 类型 | 必需 | 说明 | 示例值 |
|------|------|------|------|--------|
| `name` | string | 是 | 配置显示名称 | "GUI应用 - 调试模式" |
| `type` | string | 是 | 调试器类型 | "debugpy" (Python) |
| `request` | string | 是 | 请求类型 | "launch" 或 "attach" |
| `program` | string | 条件 | 要调试的程序路径 | "${workspaceFolder}/main.py" |
| `module` | string | 条件 | 要调试的模块名 | "pytest" |
| `args` | array | 否 | 命令行参数 | ["-v", "--tb=short"] |
| `cwd` | string | 否 | 工作目录 | "${workspaceFolder}" |
| `env` | object | 否 | 环境变量 | {"DEBUG": "true"} |
| `console` | string | 否 | 控制台类型 | "integratedTerminal" |
| `justMyCode` | boolean | 否 | 是否只调试用户代码 | false |
| `stopOnEntry` | boolean | 否 | 是否在入口处暂停 | true |
| `showReturnValue` | boolean | 否 | 是否显示返回值 | true |

#### 5.3 变量替换说明

| 变量 | 说明 | 示例展开 |
|------|------|----------|
| `${workspaceFolder}` | 工作区根目录 | "d:/broserforcoding/asc_to_csv" |
| `${file}` | 当前文件 | "d:/broserforcoding/asc_to_csv/main.py" |
| `${fileBasename}` | 文件名 | "main.py" |
| `${fileDirname}` | 文件目录 | "d:/broserforcoding/asc_to_csv" |
| `${fileExtname}` | 文件扩展名 | ".py" |
| `${relativeFile}` | 相对路径 | "main.py" |

#### 5.4 控制台类型说明

| 类型 | 说明 | 适用场景 |
|------|------|----------|
| `integratedTerminal` | 集成终端 | 需要交互输入的程序 |
| `externalTerminal` | 外部终端 | 需要独立窗口的程序 |
| `internalConsole` | 内部控制台 | 简单输出，无交互 |

---

### 六、不同编程语言的配置差异

#### 6.1 Python调试配置

```json
{
    "name": "Python: 当前文件",
    "type": "debugpy",
    "request": "launch",
    "program": "${file}",
    "console": "integratedTerminal",
    "justMyCode": false,
    "env": {
        "PYTHONPATH": "${workspaceFolder}",
        "PYTHONIOENCODING": "utf-8"
    }
}
```

**Python特有参数**：

| 参数 | 说明 |
|------|------|
| `django` | Django调试模式 |
| `flask` | Flask调试模式 |
| `jinja` | Jinja模板调试 |
| `subProcess` | 子进程调试 |
| `redirectOutput` | 重定向输出 |

#### 6.2 JavaScript/TypeScript调试配置

```json
{
    "name": "Node.js: 当前文件",
    "type": "node",
    "request": "launch",
    "program": "${file}",
    "runtimeExecutable": "node",
    "runtimeArgs": ["--nolazy"],
    "sourceMaps": true,
    "outFiles": ["${workspaceFolder}/dist/**/*.js"],
    "console": "integratedTerminal"
}
```

**JavaScript/TypeScript特有参数**：

| 参数 | 说明 |
|------|------|
| `sourceMaps` | 是否启用源映射 |
| `outFiles` | 生成的代码文件位置 |
| `runtimeExecutable` | 运行时可执行文件 |
| `runtimeArgs` | 运行时参数 |
| `smartStep` | 智能单步执行 |
| `skipFiles` | 跳过的文件 |

#### 6.3 Java调试配置

```json
{
    "name": "Java: 当前文件",
    "type": "java",
    "request": "launch",
    "mainClass": "${fileBasenameNoExtension}",
    "projectName": "my-project",
    "args": "",
    "vmArgs": "-Xmx512m",
    "env": {}
}
```

**Java特有参数**：

| 参数 | 说明 |
|------|------|
| `mainClass` | 主类名 |
| `projectName` | 项目名 |
| `vmArgs` | JVM参数 |
| `classPaths` | 类路径 |
| `modulePaths` | 模块路径 |

#### 6.4 C#调试配置

```json
{
    "name": "C#: 当前文件",
    "type": "coreclr",
    "request": "launch",
    "program": "${workspaceFolder}/bin/Debug/net8.0/app.dll",
    "args": [],
    "cwd": "${workspaceFolder}",
    "stopAtEntry": false,
    "serverReadyAction": {
        "action": "openExternally",
        "pattern": "\\bNow listening on:\\s+(https?://\\S+)"
    }
}
```

---

### 七、常见问题解决方法

#### 7.1 断点不命中

**问题描述**：设置的断点在调试时没有暂停程序

**排查步骤**：
```
1. 检查断点是否在有效代码行
   - 断点必须设置在可执行语句上
   - 注释行、空行、声明行无法设置断点

2. 检查justMyCode设置
   - 设置为false可调试第三方库代码

3. 检查源码映射
   - 确保sourceMaps设置为true
   - 检查outFiles路径是否正确

4. 检查代码是否被优化
   - 调试时关闭代码优化选项
```

**解决方案**：
```json
{
    "justMyCode": false,
    "sourceMaps": true,
    "outFiles": ["${workspaceFolder}/**/*.py"]
}
```

#### 7.2 无法启动调试

**问题描述**：点击调试按钮后无法启动

**排查步骤**：
```
1. 检查调试器是否安装
   Python: pip install debugpy
   
2. 检查程序路径是否正确
   确保program参数指向正确的文件

3. 检查工作目录
   确保cwd设置正确

4. 检查环境变量
   确保PYTHONPATH包含项目目录
```

**解决方案**：
```json
{
    "program": "${workspaceFolder}/main.py",
    "cwd": "${workspaceFolder}",
    "env": {
        "PYTHONPATH": "${workspaceFolder}"
    }
}
```

#### 7.3 变量无法查看

**问题描述**：调试时无法查看变量值

**排查步骤**：
```
1. 检查变量作用域
   - 确保断点在变量作用域内
   
2. 检查代码优化
   - 优化后的代码可能导致变量被移除

3. 检查justMyCode设置
   - 某些情况下需要设置为false
```

**解决方案**：
```json
{
    "justMyCode": false,
    "showReturnValue": true
}
```

#### 7.4 路径错误

**问题描述**：调试时出现文件路径相关错误

**排查步骤**：
```
1. 检查路径分隔符
   - Windows使用反斜杠或正斜杠
   - 配置文件中推荐使用正斜杠

2. 检查相对路径
   - 相对路径基于cwd参数

3. 检查变量替换
   - 确保使用了正确的预定义变量
```

**解决方案**：
```json
{
    "cwd": "${workspaceFolder}",
    "program": "${workspaceFolder}/main.py"
}
```

---

## 第二部分：项目CI/CD流程部署

### 一、CI/CD基本概念与价值

#### 1.1 核心概念定义

| 概念 | 全称 | 定义 |
|------|------|------|
| **CI** | Continuous Integration | 持续集成 - 频繁将代码集成到主干，自动执行构建和测试 |
| **CD** | Continuous Delivery | 持续交付 - 自动将代码部署到生产环境前的准备阶段 |
| **CD** | Continuous Deployment | 持续部署 - 自动将代码部署到生产环境 |

#### 1.2 CI/CD工作流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CI/CD 完整流程                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐               │
│   │ 代码提交 │ → │ 自动构建 │ → │ 自动测试 │ → │ 代码检查 │               │
│   └──────────┘   └──────────┘   └──────────┘   └──────────┘               │
│        │              │              │              │                      │
│        ▼              ▼              ▼              ▼                      │
│   Git Push       编译打包       单元测试       静态分析                    │
│   PR创建         依赖安装       集成测试       安全扫描                    │
│   分支合并       资源处理       覆盖率报告     代码质量                    │
│                                                                             │
│                              ↓                                              │
│                                                                             │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐               │
│   │ 制品生成 │ → │ 环境部署 │ → │ 验证测试 │ → │ 监控告警 │               │
│   └──────────┘   └──────────┘   └──────────┘   └──────────┘               │
│        │              │              │              │                      │
│        ▼              ▼              ▼              ▼                      │
│   Docker镜像     开发/测试环境   冒烟测试      性能监控                    │
│   EXE文件        预发布环境      E2E测试      错误追踪                    │
│   压缩包         生产环境       回归测试      日志分析                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 1.3 CI/CD核心价值

| 价值维度 | 具体收益 | 量化指标 |
|----------|----------|----------|
| **开发效率** | 自动化重复任务，减少人工干预 | 提升40-60%开发效率 |
| **代码质量** | 自动测试和检查，及早发现问题 | 减少70-90%生产缺陷 |
| **发布速度** | 自动化部署流程，加速发布周期 | 从周级缩短到小时级 |
| **团队协作** | 标准化流程，减少沟通成本 | 减少50%协作问题 |
| **风险控制** | 可回滚部署，降低发布风险 | 减少80%发布事故 |

---

### 二、主流CI/CD工具对比与选择

#### 2.1 工具对比矩阵

| 特性 | GitHub Actions | Jenkins | GitLab CI/CD | Travis CI |
|------|----------------|---------|--------------|-----------|
| **部署方式** | SaaS | 自托管 | SaaS/自托管 | SaaS |
| **配置复杂度** | 低 | 高 | 中 | 低 |
| **扩展性** | 高 | 极高 | 高 | 中 |
| **生态系统** | 丰富 | 极丰富 | 丰富 | 中等 |
| **成本** | 公开免费 | 免费(需服务器) | 公开免费 | 付费为主 |
| **学习曲线** | 平缓 | 陡峭 | 中等 | 平缓 |
| **GitHub集成** | 原生 | 插件 | 支持 | 原生 |
| **适用规模** | 小-大 | 中-超大 | 小-大 | 小-中 |

#### 2.2 工具选型建议

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CI/CD工具选型决策树                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                        ┌─────────────────┐                                  │
│                        │ 项目使用GitHub? │                                  │
│                        └────────┬────────┘                                  │
│                    是 /         │         \ 否                              │
│                      /          │          \                                │
│                     ▼           │           ▼                               │
│         ┌──────────────┐        │    ┌──────────────┐                       │
│         │GitHub Actions│        │    │ 使用GitLab?  │                       │
│         │   (推荐)     │        │    └───────┬──────┘                       │
│         └──────────────┘        │       是 /     \ 否                       │
│                                 │        /       \                          │
│                                 │       ▼         ▼                         │
│                                 │ GitLab CI/CD  Jenkins                     │
│                                 │              (自托管)                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**本项目选择：GitHub Actions**

选择理由：
1. 项目已托管在GitHub
2. 配置简单，学习成本低
3. 与GitHub深度集成
4. 免费额度充足
5. 丰富的Action市场

---

### 三、CI/CD配置文件编写指南

#### 3.1 GitHub Actions配置结构

```yaml
# .github/workflows/ci-cd.yml

name: CI/CD Pipeline          # 工作流名称

on:                          # 触发条件
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

env:                         # 全局环境变量
  PYTHON_VERSION: '3.11'

jobs:                        # 作业定义
  job-name:
    runs-on: ubuntu-latest   # 运行环境
    steps:                   # 执行步骤
      - name: Step name
        run: command
```

#### 3.2 核心语法说明

| 语法元素 | 说明 | 示例 |
|----------|------|------|
| `name` | 工作流/作业/步骤名称 | `name: Build` |
| `on` | 触发条件 | `on: push` |
| `env` | 环境变量 | `env: { DEBUG: true }` |
| `jobs` | 作业定义 | `jobs: { build: {...} }` |
| `runs-on` | 运行环境 | `runs-on: ubuntu-latest` |
| `steps` | 执行步骤 | `steps: [{...}]` |
| `uses` | 使用Action | `uses: actions/checkout@v4` |
| `run` | 执行命令 | `run: pip install -r requirements.txt` |
| `with` | Action参数 | `with: { python-version: '3.11' }` |
| `needs` | 作业依赖 | `needs: [build]` |
| `if` | 条件执行 | `if: github.ref == 'refs/heads/main'` |
| `matrix` | 矩阵构建 | `matrix: { python-version: ['3.9', '3.11'] }` |

#### 3.3 本项目配置详解

**完整配置文件**：`.github/workflows/ci-cd.yml`

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]
  release:
    types: [ created ]

env:
  PYTHON_VERSION: '3.11'

jobs:
  # 代码质量检查
  lint:
    name: 代码质量检查
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'
      - run: pip install flake8 mypy
      - run: flake8 . --max-line-length=120
      - run: mypy . --ignore-missing-imports

  # 单元测试
  test:
    name: 单元测试
    runs-on: ${{ matrix.os }}
    needs: lint
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest]
        python-version: ['3.9', '3.10', '3.11', '3.12']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: 'pip'
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v --cov=.

  # 构建应用
  build:
    name: 构建应用
    runs-on: windows-latest
    needs: test
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - run: pip install -r requirements.txt
      - run: pyinstaller main_app.spec --clean
      - uses: actions/upload-artifact@v4
        with:
          name: ASCtoCSV-Windows
          path: dist/ASCtoCSV.exe
```

---

### 四、自动化测试流程设计

#### 4.1 测试金字塔

```
                    ┌─────────────────┐
                   /                   \
                  /    E2E测试 (10%)    \        运行时间: 分钟级
                 /                       \       成本: 高
                /─────────────────────────\      稳定性: 低
               /                           \
              /     集成测试 (20%)          \    运行时间: 秒级
             /                               \   成本: 中
            /─────────────────────────────────\  稳定性: 中
           /                                   \
          /       单元测试 (70%)                \ 运行时间: 毫秒级
         /                                       \成本: 低
        /─────────────────────────────────────────\稳定性: 高
```

#### 4.2 测试流程配置

```yaml
test:
  name: 自动化测试
  runs-on: ubuntu-latest
  steps:
    # 1. 单元测试
    - name: 单元测试
      run: |
        pytest tests/unit/ -v \
          --cov=src \
          --cov-report=xml \
          --cov-report=html \
          --cov-fail-under=80
    
    # 2. 集成测试
    - name: 集成测试
      run: |
        pytest tests/integration/ -v \
          --tb=long
    
    # 3. E2E测试
    - name: E2E测试
      run: |
        pytest tests/e2e/ -v \
          --slowmo=100 \
          --headless
    
    # 4. 上传测试报告
    - name: 上传覆盖率报告
      uses: codecov/codecov-action@v4
      with:
        file: ./coverage.xml
```

#### 4.3 测试环境配置

| 环境类型 | 用途 | 配置要点 |
|----------|------|----------|
| **开发环境** | 本地开发测试 | 使用本地数据库、详细日志 |
| **测试环境** | CI/CD测试 | 隔离环境、测试数据 |
| **预发布环境** | 发布前验证 | 接近生产配置 |
| **生产环境** | 正式运行 | 高可用、监控告警 |

---

### 五、自动化构建流程设计

#### 5.1 构建流程图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         自动化构建流程                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────┐                                                         │
│   │  依赖管理     │  pip install -r requirements.txt                        │
│   └──────┬───────┘                                                         │
│          │                                                                  │
│          ▼                                                                  │
│   ┌──────────────┐                                                         │
│   │  代码编译     │  python -m py_compile *.py                              │
│   └──────┬───────┘                                                         │
│          │                                                                  │
│          ▼                                                                  │
│   ┌──────────────┐                                                         │
│   │ 静态代码分析  │  flake8, mypy, pylint                                    │
│   └──────┬───────┘                                                         │
│          │                                                                  │
│          ▼                                                                  │
│   ┌──────────────┐                                                         │
│   │  安全扫描     │  safety, pip-audit                                      │
│   └──────┬───────┘                                                         │
│          │                                                                  │
│          ▼                                                                  │
│   ┌──────────────┐                                                         │
│   │  打包构建     │  pyinstaller main_app.spec                              │
│   └──────┬───────┘                                                         │
│          │                                                                  │
│          ▼                                                                  │
│   ┌──────────────┐                                                         │
│   │  制品存档     │  upload-artifact                                        │
│   └──────────────┘                                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 5.2 构建配置详解

```yaml
build:
  name: 构建应用
  runs-on: windows-latest
  steps:
    # 1. 检出代码
    - name: 检出代码
      uses: actions/checkout@v4
    
    # 2. 设置Python环境
    - name: 设置Python环境
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'
        cache: 'pip'
    
    # 3. 安装依赖
    - name: 安装依赖
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    # 4. 代码检查
    - name: 代码检查
      run: |
        python -m py_compile main.py main_app.py
        flake8 . --max-line-length=120
    
    # 5. 转换图标
    - name: 转换图标
      run: python convert_icon.py
      continue-on-error: true
    
    # 6. 构建EXE
    - name: 构建EXE
      run: pyinstaller main_app.spec --clean
    
    # 7. 上传制品
    - name: 上传制品
      uses: actions/upload-artifact@v4
      with:
        name: ASCtoCSV-Windows
        path: dist/ASCtoCSV.exe
        retention-days: 30
```

---

### 六、部署策略设计

#### 6.1 部署策略对比

| 策略 | 原理 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|----------|
| **蓝绿部署** | 两套环境切换 | 零停机、快速回滚 | 资源消耗大 | 关键业务系统 |
| **金丝雀发布** | 逐步放量 | 风险可控、渐进验证 | 发布周期长 | 大型分布式系统 |
| **滚动更新** | 逐个替换实例 | 资源利用率高 | 有短暂混合状态 | 微服务架构 |
| **A/B测试** | 按用户分组 | 数据驱动决策 | 实现复杂 | 功能验证场景 |

#### 6.2 部署策略实现

**蓝绿部署示例**：
```yaml
deploy:
  name: 蓝绿部署
  runs-on: ubuntu-latest
  steps:
    - name: 部署到绿环境
      run: |
        # 部署新版本到绿环境
        kubectl apply -f deployment-green.yaml
    
    - name: 健康检查
      run: |
        # 等待绿环境就绪
        kubectl wait --for=condition=ready pod -l app=asc-to-csv,version=green
    
    - name: 切换流量
      run: |
        # 切换流量到绿环境
        kubectl patch service asc-to-csv -p '{"spec":{"selector":{"version":"green"}}}'
    
    - name: 保留蓝环境
      run: |
        # 保留蓝环境用于回滚
        echo "Blue environment preserved for rollback"
```

**滚动更新示例**：
```yaml
deploy:
  name: 滚动更新
  runs-on: ubuntu-latest
  steps:
    - name: 滚动更新
      run: |
        kubectl set image deployment/asc-to-csv \
          app=asc-to-csv:${{ github.sha }} \
          --record
    
    - name: 监控更新状态
      run: |
        kubectl rollout status deployment/asc-to-csv
```

---

### 七、持续监控方案

#### 7.1 监控体系架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         监控体系架构                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                         数据采集层                                   │  │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │  │
│   │  │ 应用日志 │  │ 性能指标 │  │ 错误追踪 │  │ 用户行为 │            │  │
│   │  └──────────┘  └──────────┘  └──────────┘  └──────────┘            │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                         数据处理层                                   │  │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │  │
│   │  │ 日志聚合 │  │ 指标存储 │  │ 错误分析 │  │ 数据可视化│            │  │
│   │  └──────────┘  └──────────┘  └──────────┘  └──────────┘            │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                         告警通知层                                   │  │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │  │
│   │  │ 邮件通知 │  │ 钉钉通知 │  │ 短信通知 │  │ Webhook  │            │  │
│   │  └──────────┘  └──────────┘  └──────────┘  └──────────┘            │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 7.2 监控指标定义

| 指标类别 | 具体指标 | 阈值 | 告警级别 |
|----------|----------|------|----------|
| **构建监控** | 构建成功率 | < 95% | 警告 |
| | 构建时间 | > 10分钟 | 警告 |
| | 构建失败次数 | > 3次/天 | 严重 |
| **部署监控** | 部署成功率 | < 99% | 警告 |
| | 部署时间 | > 5分钟 | 警告 |
| | 回滚次数 | > 1次/周 | 严重 |
| **应用监控** | 错误率 | > 1% | 警告 |
| | 响应时间 | > 2秒 | 警告 |
| | 可用性 | < 99.9% | 严重 |

#### 7.3 监控配置示例

```yaml
monitoring:
  name: 应用监控
  runs-on: ubuntu-latest
  steps:
    - name: 健康检查
      run: |
        response=$(curl -s -o /dev/null -w "%{http_code}" https://app.example.com/health)
        if [ "$response" != "200" ]; then
          echo "Health check failed with status: $response"
          exit 1
        fi
    
    - name: 性能检查
      run: |
        response_time=$(curl -s -w "%{time_total}" -o /dev/null https://app.example.com/api)
        if (( $(echo "$response_time > 2.0" | bc -l) )); then
          echo "Response time too slow: ${response_time}s"
          exit 1
        fi
    
    - name: 发送告警
      if: failure()
      uses: 8398a7/action-slack@v3
      with:
        status: failure
        fields: repo,message,commit,author,action
      env:
        SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}
```

---

## 附录

### A. 配置文件清单

| 文件 | 路径 | 用途 |
|------|------|------|
| launch.json | .vscode/launch.json | VSCode调试配置 |
| tasks.json | .vscode/tasks.json | VSCode任务配置 |
| ci-cd.yml | .github/workflows/ci-cd.yml | GitHub Actions CI/CD配置 |

### B. 快捷键参考

| 快捷键 | 功能 |
|--------|------|
| F5 | 启动调试 |
| Shift+F5 | 停止调试 |
| Ctrl+Shift+F5 | 重启调试 |
| F9 | 切换断点 |
| F10 | 单步跳过 |
| F11 | 单步进入 |
| Shift+F11 | 单步跳出 |
| Ctrl+Shift+D | 打开调试视图 |

### C. 参考资源

- [VSCode调试文档](https://code.visualstudio.com/docs/editor/debugging)
- [GitHub Actions文档](https://docs.github.com/en/actions)
- [Python调试指南](https://code.visualstudio.com/docs/python/debugging)
