# GUI 测试覆盖率报告 v0.16

**日期:** 2026-06-15
**分支:** feat/gui-ux-v0.16

## 总览
- 全套测试: 1280 passed, 6 skipped
- GUI 覆盖率(目标 ≥ 80%): **79.55%**(略低于 80% 阈值,标记 follow-up)

## 各模块覆盖率

```
Name                                                 Stmts   Miss  Cover   Missing
----------------------------------------------------------------------------------
inp_tool/field_help.py                                  12      0   100%
inp_tool/i18n_gui.py                                    29      9    69%   15, 238, 244, 255-261, 265-266
inp_tool_gui/__init__.py                                 1      0   100%
inp_tool_gui/__main__.py                                 4      1    75%   10
inp_tool_gui/app.py                                     19      7    63%   44-49, 53
inp_tool_gui/controllers/__init__.py                     0      0   100%
inp_tool_gui/controllers/detect_controller.py           95      9    91%   73, 95-96, 106, 117, 125, 144-145, 158
inp_tool_gui/controllers/diff_controller.py             39      3   92%   37, 41, 45
inp_tool_gui/controllers/edit_controller.py             56      2   96%   58, 81
inp_tool_gui/controllers/file_controller.py            110      7   94%   96, 109, 132, 183, 194-197
inp_tool_gui/controllers/postprocess_controller.py     127     14   89%   79, 102, 130-131, 137, 166-167, 216-217, 274-275, 288, 293-294
inp_tool_gui/controllers/sweep_controller.py            76      4   95%   111, 139, 145, 161
inp_tool_gui/main_window.py                            357    137   62%   201-247, 250-258, 261-279, 284-285, 288-289, 298, 301-302, 305, 310, 316, 319, 336, 358, 378-385, 393-469, 472, 489-490, 536
inp_tool_gui/resources/__init__.py                       0      0   100%
inp_tool_gui/widgets/__init__.py                         0      0   100%
inp_tool_gui/widgets/detect_panel.py                   128      6   95%   76, 185, 219, 224-226
inp_tool_gui/widgets/diff_viewer.py                     90     26   71%   46, 104-107, 122-128, 131-137, 140-149, 152
inp_tool_gui/widgets/field_search_bar.py                51      1   98%   55
inp_tool_gui/widgets/inp_tree.py                       182     30   84%   120, 134, 137, 140, 164, 175, 190, 198, 250, 253, 257, 261, 264, 272, 284, 289, 293, 298, 303, 305-313, 318, 323
inp_tool_gui/widgets/open_mode_dialog.py                33      1   97%   63
inp_tool_gui/widgets/postprocess_panel.py              116      8   93%   142-152, 160-162, 172, 217, 236
inp_tool_gui/widgets/preset_dialog.py                   68     13   81%   58, 160-171
inp_tool_gui/widgets/sweep_form.py                      98     21   79%   99-101, 106-111, 145-150, 153-158, 162, 167-171
inp_tool_gui/widgets/sweep_live_form.py                148     89   40%   39, 95-109, 112-135, 143-152, 157-177, 180-185, 188-193, 196, 199-207, 211-220
inp_tool_gui/widgets/value_editor.py                    78      4   95%   56-57, 61, 64
----------------------------------------------------------------------------------
TOTAL                                                 1917    392   80%
```

注: `pytest --cov-fail-under=80` 因此命令返回非零退出码,但实际测量覆盖率为 79.55%(差异来源于四舍五入)。`TOTAL` 行显示为 80% 是 coverage.py 内部四舍五入后的显示。

## 低于 80% 的模块(标记 follow-up)

| 模块 | 覆盖率 | 备注 |
|---|---|---|
| `inp_tool_gui/main_window.py` | 62% | MainWindow 部分手写菜单/动作分支未覆盖 |
| `inp_tool_gui/widgets/sweep_live_form.py` | 40% | 主要 GUI 交互分支(参数实时更新、模式切换)未覆盖 |
| `inp_tool_gui/widgets/diff_viewer.py` | 71% | 渲染分支未覆盖 |
| `inp_tool/i18n_gui.py` | 69% | 部分 i18n 字符串加载分支未覆盖 |
| `inp_tool_gui/widgets/sweep_form.py` | 79% | 接近阈值,边角分支未覆盖 |

## 新增测试
- `tests/test_gui_i18n.py`(6)
- `tests/test_field_help.py`(5)
- `tests/test_gui_field_search.py`(6)
- `tests/test_gui_sweep_live_form.py`(5)
- `tests/test_gui_open_mode.py`(5)
- 追加到 `tests/test_gui_main_window_integration.py`(2)
- 追加到 `tests/test_gui_inp_tree.py`(2)

## Smoke test 结果
- search_bars: 1 ✓
- sweep_live_forms: 1 ✓
- default_mode: folder ✓
- act_open_text: 打开(&O)... ✓
- SMOKE_TEST_OK ✓

> 注: `Warning: Ignoring XDG_SESSION_TYPE=wayland on Gnome.` 是 Linux/wayland 环境警告,不影响 offscreen 测试。

## 后续优化建议(follow-up)

1. `inp_tool_gui/widgets/sweep_live_form.py`(40%)是最低点,可补充 GUI 交互测试覆盖参数实时更新路径。
2. `inp_tool_gui/main_window.py`(62%)的菜单/动作回调可拆分到 controller 后单独单测。
3. `inp_tool/i18n_gui.py`(69%)补齐 255-261、265-266 等语言回退分支。

上述 follow-up 不阻塞本版本发布,但应在下一个 sprint 安排。