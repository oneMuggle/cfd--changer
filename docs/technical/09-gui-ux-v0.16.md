# GUI UX 优化(v0.16)

**日期:** 2026-06-15
**分支:** feat/gui-ux-v0.16
**关联计划:** docs/plans/2026-06-15_gui-ux-optimization.md(已删除)

## 变更概览

1. **中文 UI(i18n 化)**: 全 GUI 字符串走 `inp_tool.i18n_gui.tg()`,默认中文,支持 en 切换。
   - 字典覆盖 11 个命名空间(100+ key):menu / act / tab / toolbar / status / dialog / sweep / detect / tree / postprocess / open_mode / case_check
   - 零运行时依赖(纯 stdlib `os` + `typing`)

2. **字段说明 tooltip**: `inp_tool.field_help` 字典(8 blocks, 19 keywords)接入 `InpTreeWidget`,鼠标 hover 显示 "block.keyword + 说明"。
   - 物理量(reftem, reynolds, aero_ma, aero_alpha, aero_beta, aero_temp, aero_pres, aero_Re)
   - 湍流/化学/方程开关 / 输出频率 / 迭代参数 / 网格文件名

3. **树形搜索框**: 新增 `FieldSearchBar` 组件,挂在文件 tab 顶部,实时递归过滤 + 父节点自动保留可见 + 大小写不敏感。

4. **Sweep 实时编辑**: 新增 `SweepLiveForm` tab,与 YAML/JSON 加载并列,共用同一 `SweepController` 实例。
   - `SweepController.update_field(key, value)` 支持 9 类 key: template / output_dir / naming / naming_ext / source_dir / copy_strategy / exclude / sweeps.<axis> / sweeps_dict
   - 表单失焦即同步,支持"保存为 YAML"反向导出

5. **文件夹/文件双模式**: `OpenModeDialog` 默认 folder,`FileController.open_case_dir()` 新入口 + `CaseValidation` 校验。
   - 校验规则:mcfd.inp 必含(error,抛 `CaseValidationError`);PBS 脚本 / 几何文件可选(warning,不抛)
   - 完整性检查结果通过 `QMessageBox.information` 展示

6. **算例完整性检查 UI**: folder 模式打开后自动显示,列出 ok / 错误 / 警告三类信息。

## 涉及文件

**新增(7 个):**
- `inp_tool/inp_tool/i18n_gui.py`(268 行)
- `inp_tool/inp_tool/field_help.py`(73 行)
- `inp_tool/inp_tool_gui/widgets/field_search_bar.py`(88 行)
- `inp_tool/inp_tool_gui/widgets/sweep_live_form.py`(220 行)
- `inp_tool/inp_tool_gui/widgets/open_mode_dialog.py`(70 行)
- 4 个测试文件(`test_gui_i18n.py` / `test_field_help.py` / `test_gui_field_search.py` / `test_gui_sweep_live_form.py` / `test_gui_open_mode.py`)

**修改(5 个):**
- `inp_tool/inp_tool_gui/main_window.py`(~137 行变更)
- `inp_tool/inp_tool_gui/widgets/inp_tree.py`(接入 tooltip + i18n 标签)
- `inp_tool/inp_tool_gui/controllers/sweep_controller.py`(+ update_field)
- `inp_tool/inp_tool_gui/controllers/file_controller.py`(+ open_case_dir)
- `inp_tool/tests/test_gui_main_window_integration.py`(+ 2 测试,2 旧测试微调)
- `inp_tool/tests/test_gui_inp_tree.py`(+ 2 测试)

## 测试

- 全套 inp_tool 测试: 1280 passed, 6 skipped(环境性)
- GUI 单独覆盖率: 79.55%(略低于 80% 阈值,follow-up 清单见 `09-gui-test-coverage.md`)
- 手动 smoke test(QT_QPA_PLATFORM=offscreen): 通过
  - search_bars: 1
  - sweep_live_forms: 1
  - default_mode: folder
  - act_open_text: 打开(&O)...

## 用户使用流程

1. 启动 GUI → 工具栏点"打开" → 弹"选择打开方式"对话框(默认 folder)
2. 选 folder → 弹目录选择 → 选含 mcfd.inp 的目录 → 自动完整性检查并弹结果
3. 切到"文件"标签 → 顶部搜索框输入关键字 → 树实时过滤;hover value item 看 tooltip
4. 切到"Sweep → 实时编辑" → 填模板/输出/轴 → 失焦即同步;点"保存为 YAML"导出
5. 切到"Sweep" → 加载 YAML/JSON 跑 sweep(原流程不变)
6. 切到"后处理" → 选算例目录,跑提取/收敛/Excel/图表(原流程不变)

## 已知限制

- i18n 未覆盖部分 widget 内部字面量(如 detect_panel / postprocess_panel 的 labels),仅在 main_window 入口层做了 i18n。
- field_help 字典未覆盖全部已知 mcfd.inp 字段;未覆盖字段 hover 无 tooltip(不报错)。
- SweepLiveForm 与 SweepForm 共用同一 SweepController,但切换 YAML/JSON 加载后实时表单不会自动 refresh(用户需手动点同步或重新加载)。
- "记住我的选择" checkbox 留 hook,未接 QSettings(下个版本补)。
- 覆盖率 79.55% 略低于 80% 阈值,主要在 sweep_live_form.py(40%)和 main_window.py(62%),后续补 widget 交互测试。

## 后续工作

详见 `09-gui-test-coverage.md` 的 follow-up 章节。