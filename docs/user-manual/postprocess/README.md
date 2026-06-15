# postprocess — 后处理(用户手册)

> v0.15.0 起,`inp_tool` 提供 CFD++ 算例后处理能力:从 mcfd.info1 提取气动力 → 计算 CD/CL/CM → 输出 Excel 报告 + 收敛曲线图。

---

## 1. 章节目录

| # | 章节 | 一句话简介 |
|---|---|---|
| 01 | [快速开始](01-quickstart.md) | 5 分钟跑通第一份后处理 |
| 02 | [输出格式说明](02-output-formats.md) | Excel 28 列 + 收敛报告 + 收敛图各列含义 |

---

## 2. 谁应该读

- **CFD 工程师**:用 `inp_tool sweep` 跑了一批算例,要从 mcfd.info1 提取系数 + 生成报告
- **GUI 用户**:用 `inp-tool-gui` 的 "后处理(&P)" tab,可视化操作
- **流水线维护者**:用 `inp-tool post all` 集成进 batch / make / CI

---

## 3. 3 种使用方式

| 方式 | 适合场景 | 起点章节 |
|---|---|---|
| CLI(`inp-tool post`)| shell / SSH / 流水线 | [01-quickstart.md#cli](01-quickstart.md) |
| Python API | 脚本 / Jupyter / 自动化 | [01-quickstart.md#python-api](01-quickstart.md) |
| GUI tab | 桌面交互式 | [01-quickstart.md#gui](01-quickstart.md) |

---

## 4. 可选依赖

后处理子包默认是**零依赖**。但生成 Excel 或收敛曲线 png 需要装 `[post]` extras:

```bash
pip install inp-tool[post]
```

会装 `openpyxl>=3.1,<4` + `matplotlib>=3.5,<3.8` + `numpy>=1.22,<2.0`(都兼容 Python 3.8 / Win7)。
