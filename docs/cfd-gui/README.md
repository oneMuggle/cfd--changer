# cfd-gui — CFD++ GUI 调研材料(静态)

> **本目录用途:** 保留从老项目继承的 CFD++ GUI 工程资料,**只读**,不随本项目迭代更新。
>
> 与 `docs/technical/` 的关系:这些资料描述的是 CFD++ GUI 控件树 / 调用图,**不是 inp_tool 自身的代码**,故独立成目录、不计入 inp_tool 技术手册章节编号。

---

## 文件清单

| 文件 | 行数 | 简介 | 状态 |
|---|---|---|---|
| [`CFD_GUI_Engineering_Handbook.md`](CFD_GUI_Engineering_Handbook.md) | ~720 | CFD++ GUI 控件树 / 接口 / 调用关系(从老项目继承) | 静态 |
| [`CFD_GUI_CallGraph_v2.md`](CFD_GUI_CallGraph_v2.md) | ~2500 | CFD++ GUI call graph 详细(从老项目继承) | 静态 |

> **v1 已废弃**: 早期 `CFD_GUI_CallGraph.md` (396 行) 已被 v2 (2484 行) 取代,见 [2026-06-10 docs-cleanup spec](../superpowers/specs/2026-06-10-docs-cleanup-design.md)。

---

## 维护规则

- **只读 / 不更新** — 这些材料是历史调研产物,本项目 (`cfd--changer`) 不维护其内容
- **不增删** — 新增 cfd-gui 内容属另一项目范围,本目录不接收
- **失效链接扫描** — 若发现文档引用本目录外的过时资料,可在本项目内修复引用,**不动本目录文件本身**
- **删除本目录文件** — 需在 `docs/superpowers/specs/` 写 spec 走 brainstorming 流程,不可直接 `git rm`

---

## 引用本目录的位置

- `docs/technical/README.md` §1 文档组织(指向 `../cfd-gui/`)
- `docs/README.md` §子目录速查(列出本目录)
- 任何需要"理解 CFD++ GUI 控件结构"的章节(若新写)应链接到本目录,**不复制内容**
