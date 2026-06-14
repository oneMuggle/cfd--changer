# GUI Release Pipeline 修复 + Win7 验证 + 图标

**日期:** 2026-06-14
**分支:** `fix/gui-release-pipeline`
**状态:** 进行中
**面向:** 解决"GUI 代码完整可用,但 release pipeline 没把它打出来"的 gap

---

## 背景

2026-06-14 分析 GUI 完整性时发现:

| 项 | 现状 | 问题 |
|---|---|---|
| GUI 代码 | 2209 行,`inp_tool_gui/` 顶层包,Phase 1-7 + v0.13 升级全部合并 | 完整 |
| GUI 测试 | 100 用例,coverage 85%,全 PASS | 完整 |
| 用户/技术手册 | `04-gui.md` + `01-gui-architecture.md` | 完整 |
| CHANGELOG | v0.12.0 段有 GUI 完整条目 | 完整 |
| **PyInstaller spec** | **`inp_tool_gui.spec` 完整** | 完整 |
| **`scripts/build.sh`** | **只支持 onefile/onedir(CLI),无 GUI 分支** | **GAP** |
| **`release.yml` build job** | **只跑 `inp_tool.spec`,不跑 `inp_tool_gui.spec`** | **GAP** |
| **`release.yml` release job** | **files 列表只有 3 个 CLI binary** | **GAP** |
| **GUI 应用图标** | **spec `icon=None`** | 可改进 |
| **Win7 验证** | **无 CI,无 checklist** | 可改进 |

**用户决策(2026-06-14 AskUserQuestion):**
1. GUI 是 roadmap 必备 ✅
2. Win7 硬要求 ✅
3. 框架选 PySide2 5.12.x → 实际已是 5.15.2.1 ✅

**根因分析:**
- `feat(build): inp_tool_gui.spec — PyInstaller Win7 GUI 打包 (Phase 6)`(`12c9407`)只提交了 spec 文件,**没同步**:
  - `scripts/build.sh` 增加 gui mode 分支
  - `release.yml` 增加 gui build matrix 项
  - `release.yml` release job 增加 gui 文件
- 结果:本地 `pyinstaller inp_tool_gui.spec` 可用,但用户文档承诺的"73 MB EXE"从未出现在 GitHub Release

---

## 目标

1. **Phase A (HIGH)** — 修 binary 分发链,GUI EXE 真正进 Release
2. **Phase B (MEDIUM)** — 加 Win7 验证清单 + GUI 应用图标
3. **Phase C (LOW)** — 文档化人工 Win7 验证流程

---

## 涉及文件

| 文件 | 修改类型 |
|---|---|
| `scripts/build.sh` | 加 `--mode gui` case 分支 |
| `.github/workflows/release.yml` | build job + release job 都加 GUI |
| `inp_tool/inp_tool_gui.spec` | 替换 `icon=None` 为 `.ico` 路径(可选) |
| `docs/technical/release/Win7-verification-checklist.md` | 新建 |
| `docs/technical/release/README.md` | 加章节入口(如有) |
| `docs/plans/2026-06-14_gui-release-pipeline.md` | 本文档 |

---

## 实施步骤

### Phase A: 修 binary 分发链(HIGH)

- [ ] **A1**: `scripts/build.sh` 加 `--mode gui` case
  - 复用现有 PyInstaller 检测、build 目录准备、cleanup 逻辑
  - 调 `pyinstaller --clean --noconfirm inp_tool_gui.spec`
  - 验证 `dist/inp-tool-gui` 存在(Linux/macOS)或 `dist/inp-tool-gui.exe`(Windows)
  - 烟雾测试:`./dist/inp-tool-gui --help` 或在 Linux offscreen `QT_QPA_PLATFORM=offscreen` 下跑 `--version`
- [ ] **A2**: `.github/workflows/release.yml` build job 加 GUI matrix
  - 在 `matrix.include` 加 3 项(ubuntu / windows / macos),artifact 命名 `inp-tool-gui-{os}-x86_64`,binary_name `inp-tool-gui` / `inp-tool-gui.exe`
  - install step 加 `[gui-build]` extras
  - build step 按 platform 跑 GUI 打包(参考 CLI 的 Windows `python -c "import PyInstaller.__main__..."` 模式 + Linux/macOS `bash ../scripts/build.sh --mode gui`)
  - smoke test 加 GUI 启动(Windows 跳过 GUI 启动,因为 PySide2 offscreen 在 runner 默认配置下需要 `QT_QPA_PLATFORM=offscreen`)
  - upload artifact 复用现有 `if-no-files-found: error` + `retention-days: 90`
- [ ] **A3**: `.github/workflows/release.yml` release job
  - `Display collected artifacts` 自动列出所有 6 个(3 CLI + 3 GUI)
  - `Create / update GitHub Release` 的 `files:` 列表加 GUI 3 项
  - 同样 rename 加后缀(Linux/macOS),Windows `.exe` 已 unique
- [ ] **A4**: 本地端到端验证
  - `conda run -n cfdchanger ./scripts/build.sh --mode gui`
  - 确认 `dist/inp-tool-gui` 存在,体积 ~73 MB
  - `QT_QPA_PLATFORM=offscreen ./dist/inp-tool-gui --help` 烟雾(注:PySide2 GUI app 可能没 `--help`,但能 import 主窗口不崩)
- [ ] **A5**: commit + push + 开 PR
  - `git add scripts/build.sh .github/workflows/release.yml`
  - `git commit -m "fix(release): GUI binary (inp-tool-gui) 进入 Release pipeline"`
  - `git push -u origin fix/gui-release-pipeline`
  - `gh pr create --base main --title "fix(release): GUI binary 进入 Release pipeline" --body ...`

### Phase B: Win7 验证清单 + 图标(MEDIUM)

- [ ] **B1**: 写 `docs/technical/release/Win7-verification-checklist.md`
  - 适用:Win7 SP1 x64 + Python 3.8.20(或 wheel 自带)
  - 步骤:
    - 下载 `inp-tool-windows-x86_64.exe` 和 `inp-tool-gui-windows-x86_64.exe`
    - 双击 CLI EXE → 验证 `--version` 正常
    - 双击 GUI EXE → 验证主窗口弹出(无 "missing DLL" 错误)
    - GUI 链路:File → Open 选 .inp → Tree 显示 → 双击字段 → Edit Dialog → Save
    - Sweep 链路:Sweep 标签 → 加 alpha 序列 → Preview → Run(dry_run)→ Report
    - Detect 链路:Detect 标签 → Detect → Preset 选择 SST → Accept
    - Diff 链路:Diff 标签 → 选两个 .inp → 显示 unified diff
  - 截图归档:`docs/technical/release/screenshots/win7-gui-{step}.png`
- [ ] **B2**: 跳过(无 Win7 物理机,等用户手动验证)
- [ ] **B3**: GUI 应用图标
  - 准备 `inp_tool/inp_tool_gui/resources/inp-tool-gui.ico`(256x256 多分辨率)
  - 改 spec:`exe.icon = 'inp_tool_gui/resources/inp-tool-gui.ico'`
  - Linux 无 .ico 概念,PyInstaller Linux 构建自动忽略 icon 参数
  - macOS 同上(.icns 才生效,但 spec 没设)
  - 注意:PyInstaller 在 Windows 上要 .ico,在 macOS 上要 .icns(.ico 也能 fallback)

### Phase C: 文档化人工验证流程(LOW)

- [ ] **C1**: 跳过(Win7 CI 自托管成本高)
- [ ] **C2**: `docs/technical/release/Win7-verification-checklist.md` 已包含在 Phase B
- [ ] **C3**: 更新 `docs/README.md` 和 `docs/technical/README.md` 章节目录,加 `Win7-verification-checklist` 入口

---

## 风险评估

| 等级 | 风险 | 缓解 |
|---|---|---|
| HIGH | GUI build 引入新依赖装包失败 | `[gui-build]` extras 已在 pyproject.toml,CI 只需 `pip install -e ".[gui-build]"` |
| MEDIUM | macOS runner 装 PySide2 ARM wheel 缺 | release.yml build job 在 macOS 上跳过 GUI build(参考 ci.yml) |
| MEDIUM | Windows PySide2 offscreen 烟雾失败 | Windows GUI EXE 启动需要桌面 session;release.yml 只 smoke `--version` 不启动 GUI |
| LOW | .ico 文件准备失败 | Phase B 可拆分,binary 分发优先 |
| LOW | CI 矩阵膨胀 | 复用现有 `fail-fast: false`,3 平台并行 |

---

## 验收标准

- [ ] 本地 `./scripts/build.sh --mode gui` 产出 `dist/inp-tool-gui`(Linux)
- [ ] `release.yml` lint 通过(yamllint 或 GitHub Actions schema)
- [ ] PR 推上去后 CI 跑通(测试 + build)
- [ ] 合并后下一个 tag(v0.14.1 或 v0.15.0)release 包含 GUI 3 个 binary
- [ ] CHANGELOG 新版本有 "GUI binary 进入 Release" 条目

---

## 文档归档

完成后:
- 本文件归档到 `docs/technical/release/gui-release-pipeline.md`(作为设计/历史参考)
- 或直接删除(因 release.yml + build.sh + spec + checklist 已自包含)

倾向于**删除**(按 CLAUDE.md "过时文档立即删除" 原则)。

---

## 参考资料

- [inp_tool_gui.spec](../../inp_tool/inp_tool_gui.spec)
- [scripts/build.sh](../../scripts/build.sh)
- [.github/workflows/release.yml](../../.github/workflows/release.yml)
- [docs/user-manual/interactive/04-gui.md](../user-manual/interactive/04-gui.md)
- [docs/technical/ux/01-gui-architecture.md](../technical/ux/01-gui-architecture.md)
- Commit `12c9407 feat(build): inp_tool_gui.spec — PyInstaller Win7 GUI 打包 (Phase 6)`
- Commit `9121d08 feat(gui): DetectController/PresetDialog 升级到真实 detect_equations + preset API (v0.13)`