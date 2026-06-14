# 03. Win7 SP1 物理验证清单

> **版本:** v0.14.1 新增
> **面向:** 负责打 tag 发布前的 QA,确认 Win7 SP1 用户能用 GUI
> **不适用:** macOS GUI(无 ARM wheel,自 v0.12.0 已知不支持)

---

## 1. 背景

项目硬性约束(CLAUDE.md §1.4):

- **目标平台**: Windows 7 / Windows 10 / Linux 三平台同代码可运行
- **Python**: ≥ 3.8,≤ 3.12(**3.8 是 Win7 兼容下限**)
- **GUI 框架**: PySide2 5.15.2.1(Qt 5.15 = Qt 公司承诺支持 Win7 的最后版本)

PyInstaller 6.16.0 + PySide2 5.15.2.1 + Python 3.8.20 在 Win7 SP1 上理论可用,但实际需物理验证:
- 无 missing DLL 错误(API-MS-Win-Core-* 系列、vcruntime140.dll 等)
- Qt offscreen 平台能初始化(避免黑屏/卡死)
- inp_tool core 与 inp_tool_gui 的 import 链完整
- 4 个标签页(File/Sweep/Detect/Diff)交互不崩

CI 不能直接验证 Win7(GitHub-hosted runner 最低 Win10),所以**必须人工**。

---

## 2. 环境准备

| 项 | 要求 |
|---|---|
| **OS** | Windows 7 SP1 x64(必须 SP1,Win7 RTM 缺 Platform Update) |
| **账户** | 标准用户(非管理员),无 UAC 弹窗 |
| **Python** | 不需装(`inp-tool-*.exe` / `inp-tool-gui-*.exe` 自包含) |
| **VC++ Redist** | 2015-2022 x64(Win7 默认无,PyInstaller EXE 需 vcruntime140.dll;若用户机器缺,EXE 双击会报"MSVCP140.dll 缺失") |
| **磁盘** | ≥ 500 MB 可用(release 73MB GUI EXE + 缓存) |
| **测试样本** | `examples/` 下任一 `.inp` 文件(cfd--changer 仓库自带) |

### 2.1 安装 VC++ Redist(若缺)

去微软官网下载 [vc_redist.x64.exe](https://aka.ms/vs/17/release/vc_redist.x64.exe),无脑下一步。装完后**重启**。

### 2.2 下载 EXE

从 GitHub Release 页(`v0.14.1` 或更新 tag 的 draft)下载:
- `inp-tool-windows-x86_64.exe`(CLI,~25 MB)
- `inp-tool-gui-windows-x86_64.exe`(GUI,~73 MB)

放到 `D:\qa\win7\` 或类似路径,**避免**:
- 桌面(Windows 资源管理器偶尔会锁定桌面文件)
- 包含空格的路径(防止 PyInstaller bootloader 解析异常)

---

## 3. CLI 验证(必须先过)

| 步骤 | 命令 | 期望 |
|---|---|---|
| 1 | 双击 `inp-tool.exe`(或 cmd 跑) | 弹出 usage 信息(等同 `--help`) |
| 2 | cmd:`inp-tool.exe --version` | `inp 0.14.1`(或对应版本) |
| 3 | cmd:`inp-tool.exe info <path-to-test.inp>` | 列出 .inp 的 top-level statements |
| 4 | cmd:`inp-tool.exe parse <path-to-test.inp>` | 输出解析后的字段(可能很大,重定向到文件) |

**若任一步失败:** 截图 + 把错误码粘到 issue,转给 dev。不要继续测 GUI。

---

## 4. GUI 验证

### 4.1 启动

| 步骤 | 操作 | 期望 |
|---|---|---|
| 1 | 双击 `inp-tool-gui.exe` | 主窗口弹出,标题 `inp-tool-gui v0.10.0-dev` |
| 2 | 检查任务管理器 | `inp-tool-gui.exe` 进程存在,内存 ~80 MB(冷启动) |
| 3 | 不操作,等 5 秒 | 不闪退、不弹"missing DLL"对话框 |

**故障排查(若启动失败):**

| 现象 | 根因 | 修复 |
|---|---|---|
| "MSVCP140.dll 缺失" | 缺 VC++ 2015-2022 Redist | 装 vc_redist.x64.exe |
| "API-MS-Win-Core-Path-L1-1-0.dll 缺失" | Win7 没装 Platform Update | 装 KB2670838 |
| 黑屏、几秒后退出 | Qt offscreen 平台加载失败 | 检查显卡驱动;尝试 `set QT_QPA_PLATFORM=offscreen` |
| 立即弹"Permission denied" | UAC / 写权限问题 | 换到 `D:\qa\win7\` 目录 |

### 4.2 File / Edit 链路

| 步骤 | 操作 | 期望 |
|---|---|---|
| 1 | File → Open → 选 test `.inp` | Tree 显示 top-level statements(foam / aero / chem 等) |
| 2 | 展开某节点(如 `aero`) | 子节点显示具体字段 |
| 3 | 双击某叶子节点(如 `aero_mach = 0.8`) | ValueEditorDialog 弹出,显示当前值 |
| 4 | 改成 `0.85`,Accept | Tree 节点值更新,标题加 `*`(dirty 标记),Edit 菜单 Undo 变可点 |
| 5 | Edit → Undo | 值回到 `0.8`,dirty 标记消失 |
| 6 | Edit → Redo | 值回到 `0.85`,dirty 标记再现 |
| 7 | File → Save As → 改名存 | 新文件存在,内容含修改后的值 |
| 8 | 退出 → 选"不保存" | 直接退出,不弹错误 |

### 4.3 Sweep 链路

| 步骤 | 操作 | 期望 |
|---|---|---|
| 1 | 点 Sweep 标签 | SweepForm 显示(空状态) |
| 2 | 填 variable=`aero_mach`,values=`0.5,0.6,0.7,0.8` | 表格加 1 行 |
| 3 | 再加 variable=`aero_alpha`,values=`2.0,4.0` | 表格加 2 行,Preview 显示 4×2=8 cases |
| 4 | 选 output dir=`D:\qa\win7\sweep-out` | 路径合法,Run 按钮可点 |
| 5 | 勾 dry_run=true | Run 时不写真实文件 |
| 6 | 点 Run | 进度条跑完,Report 显示 8 cases 笛卡尔积清单 |
| 7 | 检查 output dir | **不**应有 `sweep-out/case_*/` 子目录(dry_run) |
| 8 | 取消勾 dry_run,Run | 8 个子目录创建,各含 .inp 文件 |

### 4.4 Detect 链路

| 步骤 | 操作 | 期望 |
|---|---|---|
| 1 | 点 Detect 标签 | DetectPanel 显示 |
| 2 | 点 Detect 按钮 | 跑 detect_equations,显示识别出的方程族(turb / chem 等) |
| 3 | 点 Preset → 选 SST(k-omega) | PresetDialog 弹出,显示 turb 预设字段 |
| 4 | 填 inp 文件路径(用 4.2 第 7 步那个) | Accept 按钮可点 |
| 5 | Accept | inp 文件被修改,加了 SST 预设相关字段 |

### 4.5 Diff 链路

| 步骤 | 操作 | 期望 |
|---|---|---|
| 1 | 点 Diff 标签 | DiffViewer 显示(空) |
| 2 | 选 left=4.2 第 1 步原文件,right=4.2 第 7 步修改文件 | unified diff 高亮显示差异行(背景色 + 或 -) |
| 3 | 滚到差异区 | 字段值 `0.8` → `0.85` 高亮 |

### 4.6 性能与稳定性

| 指标 | 阈值 |
|---|---|
| 冷启动到主窗口 | ≤ 5 秒 |
| 打开 1000 行 .inp | ≤ 2 秒 |
| Sweep 50 cases dry_run | ≤ 10 秒 |
| 内存占用(空闲) | ≤ 150 MB |
| 内存占用(打开 .inp) | ≤ 250 MB |
| 连续操作 30 分钟 | 无内存泄漏迹象(任务管理器看内存平稳) |

---

## 5. 已知 Win7 限制

| 项 | 说明 | 缓解 |
|---|---|---|
| 字体渲染 | Win7 默认无 ClearType 微调,Qt 字体可能略糊 | 调 `QApplication.setStyle("Fusion")`(可选) |
| HiDPI | Win7 不原生支持 per-monitor DPI | 4K 屏可能模糊;1080p 正常 |
| OpenGL | Win7 默认无 OpenGL 4.x,Qt Scene Graph 部分效果降级 | 本项目 GUI 不依赖 OpenGL,不影响 |
| SMBv1 | 默认开(Win7 时代协议),有安全风险 | 用户自己决定;不影响 GUI |

---

## 6. 截图归档

每个验证步骤截图(至少 §4.1 / §4.2 / §4.3 / §4.4 / §4.5 各 1 张):

```
docs/technical/release/screenshots/win7-v0.14.1/
├── 01-startup.png           # 主窗口刚弹出
├── 02-file-edit.png         # File 标签 + Tree 展开
├── 03-sweep-preview.png     # Sweep 标签 + 8 cases preview
├── 04-detect-preset.png     # Detect + Preset SST 对话框
├── 05-diff-viewer.png       # Diff 标签高亮
└── 06-final-state.png       # 全部测完后的状态
```

> **截图技巧:** 用 `Win + Shift + S`(Win10 的截图快捷键在 Win7 不可用),改用:
> - `PrintScreen` 截全屏 → 粘到画图 → 存 PNG
> - 或装 [ShareX](https://getsharex.com/)(Win7 兼容的开源截图工具)

---

## 7. 报告模板

完成后在 issue / PR comment 里粘:

```markdown
## Win7 SP1 验证报告

- [版本]: v0.14.1 (commit <SHA>)
- [测试机]: <OS 版本>+<CPU>+<RAM>
- [EXE 来源]: GitHub Release draft #<id>
- [VC++ Redist]: 装/未装
- [结果]: ✅ 全过 / ❌ <哪步失败,附日志>

| 链路 | 状态 | 备注 |
|---|---|---|
| CLI | ✅ / ❌ | |
| GUI 启动 | ✅ / ❌ | |
| File / Edit | ✅ / ❌ | |
| Sweep | ✅ / ❌ | |
| Detect | ✅ / ❌ | |
| Diff | ✅ / ❌ | |
| 性能 | ✅ / ❌ | 冷启动 X 秒,内存 X MB |
```

---

## 8. 故障上报模板

若验证失败,**立即**在 issue 里填:

```markdown
## Win7 验证失败报告

- **失败步骤**: §4.X 第 Y 步
- **错误信息**: (粘 cmd / GUI 截图)
- **EXE 类型**: CLI / GUI
- **Win7 版本**: SP1 + 补丁级别(`winver` 命令看)
- **重现步骤**: ...
- **期望**: ...
- **实际**: ...
- **严重度**: CRITICAL(无法启动)/ HIGH(主功能挂)/ MEDIUM(次功能挂)/ LOW(显示问题)
```

---

## 9. 历史记录

| 版本 | 验证者 | 日期 | 结果 | 备注 |
|---|---|---|---|---|
| v0.14.1 | (待填) | (待填) | (待填) | 首次 Win7 物理验证 |

---

## 10. 关联文档

- [01-cli-packaging](01-cli-packaging.md) — PyInstaller 配置
- [02-ci-cd](02-ci-cd.md) — release.yml + ci.yml
- [docs/user-manual/interactive/04-gui.md](../../user-manual/interactive/04-gui.md) — GUI 用户手册
- [docs/technical/ux/01-gui-architecture.md](../ux/01-gui-architecture.md) — GUI 架构