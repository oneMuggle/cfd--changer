# postprocess — CFD++ 算例后处理(技术手册)

> v0.15.0 / borrowing reference/code 路线交付。本子目录是 `inp_tool.postprocess` 子包与 `inp-tool post` CLI、GUI panel 的**架构/API/实现细节**文档,面向开发者。
>
> 用户向操作手册见 [`../../user-manual/postprocess/`](../../user-manual/postprocess/)。

---

## 1. 章节目录

| # | 章节 | 一句话简介 |
|---|---|---|
| 01 | [Overview](01-overview.md) | 子包架构、数据流、模块依赖、3 种入口(API/CLI/GUI) |
| 02 | [Atmosphere + Aero Math](02-atmosphere-aero-math.md) | US 1976 大气模型 + 风轴/体轴变换公式与实现 |
| 03 | [info1 + bc Parsing](03-info1-bc-parsing.md) | mcfd.info1 + mcfd.bc 文件格式 + 状态机解析 |
| 04 | [Forces + Convergence](04-forces-convergence.md) | 力矩中心换算 + 气动系数 + CV 收敛判据 |
| 05 | [Excel + Plot Output](05-excel-plot-output.md) | openpyxl/matplotlib 可选依赖边界 + 输出格式 |
| 06 | [CLI + GUI](06-cli-gui.md) | `inp-tool post` 子命令树 + PySide2 panel 实现 |

---

## 2. 与 reference/code 的关系

reference 目录有 3 个独立脚本(2424 行):
- `CFDPlus_V4.py`(1392 行)— 统一前/后处理 argparse CLI
- `CFDPlus_setup.py`(242 行)— 独立 setup 工具
- `CFDPlus_extract.py`(790 行)— 独立 extract + 收敛分析

本子包**借鉴**了 reference 的:
- 🟢 算法 6 项:US 1976 大气模型 / 风轴体轴变换 / mcfd.info1 解析 / mcfd.bc 解析 / 气动力汇总 / CV 收敛分析
- 🟡 输出 4 项:多 Sheet Excel / matplotlib 收敛图 / uvw 反推 αβ / 错误处理风格

并**跳过**:
- ~~setup / copy_base_case~~:已被 `sweep.py` 远胜
- ~~SLURM run-all/end-all/check-all~~:已被 `cluster.py` + `batch.py` + `monitor.py` 覆盖
- ~~txt2xls(xlwt)~~:openpyxl 替代
- ~~BatchCaseSetting_para.txt 行式~~:走 YAML/JSON

并**修复**了 reference 已确认的 2 个 bug(详见 [04-forces-convergence.md](04-forces-convergence.md)):
1. `Atmosphere_US_1976` 压强公式系数错误(h>0 处给出错误的 P/ρ)
2. `read_info1_file` EOF flush bug(最后一个 step 累积值丢失)

---

## 3. 与其他子模块的关系

| 上游 | 本子包用法 |
|---|---|
| `inp_tool.parser` | `build_run_params` 解析 mcfd.inp 取 aero_* 字段 |
| `inp_tool.model.InpFile` | 间接(通过 parser) |
| (无) `inp_tool.sweep` | 不依赖;并列子模块 |
| (无) `inp_tool.cluster` / `batch` | 不依赖;并列子模块 |

`inp_tool.postprocess` 是**叶子**子模块,只依赖 `parser`,不被项目其他业务模块依赖。
