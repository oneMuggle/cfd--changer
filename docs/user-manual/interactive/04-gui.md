# 04. inp-tool-gui 桌面编辑器

> **版本:** v0.10.0 新增
> **平台:** Windows 7 SP1+ / Windows 10+ / Linux
> **GUI 框架:** PySide2 5.15.2.1(Qt for Python,LGPL)

---

## 1. 概述

`inp-tool-gui` 是 cfd--changer 的桌面 GUI 版本,基于 PySide2(Qt 5.15)+ inp_tool core。

| 项 | 说明 |
|---|---|
| **入口** | `inp-tool-gui` / `python -m inp_tool_gui` |
| **核心** | 复用 inp_tool zero-dep core(parser / writer / model / diff / sweep) |
| **打包** | `pip install ".[gui-build]"` + `pyinstaller inp_tool_gui.spec` → 73 MB EXE |
| **Win7 兼容** | Qt 5.15 是 Qt 公司承诺支持 Win7 的最后版本(2020-12 EOL) |

**适用场景:**
- 不熟悉 CLI 的 CFD 工程师(从 CFD++ MFC 老 GUI 切入)
- 改单个 .inp 来流参数(可视化树形浏览)
- 批量生成攻角 / 马赫 sweep(表单化配置,实时预览笛卡尔积规模)
- 对比两版 .inp 差异(unified diff 高亮)

---

## 2. 安装

### 2.1 装 release wheel

```bash
pip install "inp-tool[gui]==0.10.0"
```

`[gui]` extras 只装 PySide2(零依赖核心不被污染)。

### 2.2 装 dev 版本(本地)

```bash
git clone https://github.com/.../cfd--changer
cd cfd--changer/inp_tool
conda create -n cfdchanger python=3.8 -y
conda activate cfdchanger
pip install -e ".[gui,dev]"
inp-tool-gui
```

### 2.3 装打包工具链(出 EXE)

```bash
pip install -e ".[gui-build]"
pyinstaller --clean --noconfirm inp_tool_gui.spec
# Linux:  ./dist/inp-tool-gui
# Windows: dist\inp-tool-gui.exe
```

---

## 3. 启动与基本操作

### 3.1 启动

```bash
# 装好后直接调
inp-tool-gui

# 或 python -m
python -m inp_tool_gui
```

主窗口:**4 个标签页 + 菜单 / 工具栏 / 状态栏**。

### 3.2 菜单 / 工具栏

| 菜单项 | 快捷键 | 行为 |
|---|---|---|
| 文件 → 打开 | Ctrl+O | `QFileDialog` 选 .inp,解析 |
| 文件 → 保存 | Ctrl+S | 写回原路径 |
| 文件 → 另存为 | Ctrl+Shift+S | 选新路径保存 |
| 文件 → 退出 | Ctrl+Q | 关闭主窗口 |
| 编辑 → 撤销 | Ctrl+Z | undo 栈弹栈,值恢复 |
| 编辑 → 重做 | Ctrl+Y | redo 栈弹栈,值重写 |
| Sweep → 批量算例 | — | 跳到 Sweep 标签页 |
| 检测 → 方程/湍流 | — | 跳到检测标签页 + 立即跑 |

### 3.3 状态栏

| 区 | 内容 |
|---|---|
| 左 | 当前文件路径(未打开显示"(未打开文件)") |
| 中右 | dirty 标志:`●` 有未保存改动 |
| 最右 | 总行数(打开文件后更新) |

标题栏:有未保存改动时文件名后加 ` *`,如 `mcfd.inp * — inp-tool-gui`。

---

## 4. 标签页详解

### 4.1 文件 — InpTreeWidget

树形展示 InpFile 三层结构:

```
Root
├── 顶层语句
│   ├── title  → "Hello"
│   └── runtype → "default"
└── 块
    ├── physics (block_idx=0)
    │   ├── reftem → 300.0
    │   └── reynolds → 1.0e6
    └── chemistry [1]  (同名第 2 个)
        └── model → "air7"
```

**操作:**

- **双击 value 单元格** → 弹 `ValueEditorDialog` → 改值 → 保存(走 undo 栈)
- **同名块**自动加 ` [N]` 后缀区分(0-indexed)
- 顶层语句的 value 双击 → `block_idx = -1` 走单独的 `_edit_top_stmt_value`

**字段类型推断:** 按 typed 值 → bool / int / float / str;bool 接受 `T/F/True/False/.true./.false./1/0`(大小写不敏感)。

### 4.2 检测 — DetectPanel

点击"检测 → 方程/湍流"菜单或"检测"标签页的"运行检测"按钮。

UI 结构(自顶向下):

1. **运行检测** + 3 个 Preset 按钮(应用 SST k-ω / 双温度(2T) / 多组分)
2. **摘要标签** — 中文一行(✓ 标记各项)
3. **检测报告表** — reftem / reynolds / 湍流关键字 / chemistry 块数 / 2T
4. **警告 / 提示** — 缺字段、字段冲突等提示
5. **推荐字段** — 缺的关键字段,点"应用"按钮写入(走 undo 栈)

**Preset 行为(v0.10 简化版):**

| Preset | 写入字段 |
|---|---|
| SST k-ω (`turb`) | reynolds=1e6 / turbi=0.01 / turbk=0.01 / turbw=0.01 |
| 双温度 (`2t`) | reftem=300 / vibtem=300 / turbe=0 |
| 多组分 (`species`) | 占位(等 v0.9.1 `SpeciesPreset.apply`) |

> v0.9.1 完整 `detect_equations()` 上线后,DetectPanel 直接调它,API 不变。

### 4.3 Sweep — SweepForm

加载 YAML/JSON 配置,运行 sweep,展示结果。

**加载方式:**
- 点"加载 YAML..." / "加载 JSON..." 按钮选文件
- 配置缺 `template` / `output_dir` → 弹错误对话框

**运行:**
- "运行(Dry)" — 只摊开 specs,不写盘
- "运行" — 实际生成子目录
- "强制覆盖" — 复选框;勾上后覆盖已存在的 case 子目录

**结果表:** `case_id / path / params / applied` 四列,CaseSweep.generate 的产物。

> 简化版:同步跑 sweep(后续可加 QThread 后台)。

### 4.4 对比 — DiffViewer

选两个 .inp 文件,看 unified diff。

- "加载 A..." / "加载 B..." 按钮选两个文件
- 选完后自动 diff + 渲染
- 主区 `QTextBrowser`:行首 `+`(绿)/ `-`(红)/ `@@`(蓝) 高亮
- 变更数标签:`变更数: N`

适用于:**两版 .inp 改了哪些字段**(评审 / git-style 改动展示)。

---

## 5. Win7 自测 Checklist(打包后)

```markdown
## inp-tool-gui v0.10.0 Win7 自测

环境:
- [ ] OS: Windows 7 SP1 x64
- [ ] SimSun 字体存在
- [ ] Python 3.8.x 已装

安装:
- [ ] pip install "inp-tool[gui]==0.10.0"
- [ ] python -c "from PySide2.QtWidgets import QApplication; QApplication([]); print('OK')" 不报错

打包:
- [ ] pip install ".[gui-build]==0.10.0"
- [ ] pyinstaller --clean --noconfirm inp_tool_gui.spec
- [ ] dist\inp-tool-gui.exe 双击启动:<3s,内存 <200MB

核心:
- [ ] 打开 examples/mcfd_v2_modified.inp(<3s)
- [ ] 树形展示所有 blocks
- [ ] 双击 physics.reftem 改 300,保存 → 重开值一致
- [ ] Ctrl+Z 撤销
- [ ] 检测标签页:报告显示 2T / species 标志
- [ ] Sweep 标签页:加载 sweep_demo.yaml 运行,生成 4 个子目录

DPI:
- [ ] 100% / 125% / 150% 窗口不糊
```

报告:所有勾完 + 截图 → 发回项目方。

---

## 6. 故障排查

| 现象 | 排查 |
|---|---|
| 启动报 `Qt platform plugin could not be initialized` | Win7 缺 VC++ 2015 redistributable;装 vcredist_x64.exe |
| 中文显示为方块 | Win7 简体默认有 SimSun;缺字体时 QSS 退到系统字体 |
| 打包后 EXE 启动慢(>10s) | 杀软实时扫描;把 dist\ 目录加白名单 |
| 杀软报毒 | PyInstaller bootloader 偶发误报;提交误报 + 用 `--onedir` 模式替代 |
| 树形双击 value 无反应 | InpFile 没 value 字段(空 .inp);先检查 parse 是否成功 |

---

## 7. 退出 / 后续

- 退出:`Ctrl+Q` 或 文件 → 退出
- 残留:关闭时若有未保存改动,**当前版本不弹确认**(v0.10 简化),请先 Ctrl+S
- 反馈:GitHub Issues / 项目方