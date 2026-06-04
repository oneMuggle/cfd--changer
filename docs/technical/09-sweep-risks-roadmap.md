# 09 — 风险登记与后续工作

---

## 1. 风险登记

### R1: 几何分解方向假设与 CFD++ 版本差异

| 项 | 内容 |
|---|---|
| 等级 | **HIGH** |
| 描述 | `FreestreamPreset` 假设 `α` 影响 W(垂直)、`β` 影响 V(侧滑)。某些 CFD++ 版本可能用不同约定(如 α 影响 V)。 |
| 影响 | 算例初始速度方向错误,数值结果与预期不符 |
| 检测 | 抽查 `manifest.applied` 字段值,对比 v=0/α=2 时的 aero_u/v/w 是否符合预期 |
| 缓解 | (1) `freestream.enabled=false` 跳过 preset,只用 `overrides` 手动给 aero_u/v/w;(2) `speed_of_sound` 显式给值;(3) manifest 记录 `applied` 字段供人工核对 |
| 状态 | 已记录,无法在本模块解决(需要 CFD++ 软件知识) |

### R2: round-trip 空白/缩进重构造

| 项 | 内容 |
|---|---|
| 等级 | MEDIUM |
| 描述 | `inp_tool` v0.2 已知限制:`to_text` 不保留原文件空白风格。`sweep` 写出的文件与原模板 diff 会有大量"删除/添加"行(实际只是空白不同)。 |
| 影响 | diff 工具报大量误报 |
| 缓解 | (1) `diff` 用 keyword/value 级别而非行级别比较,已实现;(2) 未来 `writer.py` 加 `preserve_format` 选项 |
| 状态 | inp_tool 全局限制,本模块未引入新问题 |

### R3: 大批量算例 IO 慢

| 项 | 内容 |
|---|---|
| 等级 | LOW |
| 描述 | 10000 case 写盘约 50s |
| 影响 | 单次扫描几小时不算罕见 |
| 缓解 | (1) 进度条(`tqdm` 可选);(2) 异步写盘(未来 v0.6);(3) 模板拆分 / 并行(未来 v0.7) |
| 状态 | 当前实现是同步串行,够用 |

### R4: 命名模板字段名拼错

| 项 | 内容 |
|---|---|
| 等级 | LOW |
| 描述 | `naming: "case_{alph:.0f}"` 中 `{alph}` 不是 sweep 字段名 |
| 影响 | `KeyError` 渲染时崩溃 |
| 缓解 | `_check_naming_against_sweep` 在 `from_dict` 时校验,**多值** sweep 字段必须在 naming 中 |
| 状态 | 已实现 |

### R5: 模板缺 guiopts / physics 块

| 项 | 内容 |
|---|---|
| 等级 | LOW |
| 描述 | 老版本 CFD++ 的 mcfd.inp 可能没有 `guiopts` / `physics` 块 |
| 影响 | `FreestreamPreset.apply` 找不到目标块 |
| 缓解 | preset 缺块时 `WARN` 但不抛,继续写其它块 |
| 状态 | 已实现 |

### R6: Pydantic 在 Python 3.8 注解求值失败

| 项 | 内容 |
|---|---|
| 等级 | LOW |
| 描述 | Pydantic v2 在 Python 3.8 评估 PEP 585/604 注解时失败 |
| 缓解 | `[api]` extras 加 `eval_type_backport>=0.2.0`(仅 `python_version<3.9` 时安装) |
| 状态 | 已解决 |

### R7: Shell 补全脚本不通用

| 项 | 内容 |
|---|---|
| 等级 | LOW |
| 描述 | 当前是手写补全脚本,未用 `argcomplete` 等专业库 |
| 影响 | 添加新子命令 / 新选项时需手动更新三份脚本 |
| 缓解 | (1) 短期:补全脚本集中维护,加测试防遗漏;(2) 长期:迁移到 `shtab` / `argcomplete`(v0.5+) |
| 状态 | 短期可接受 |

### R8: Web GUI 无文件上传(模板必须本地可访问)

| 项 | 内容 |
|---|---|
| 等级 | MEDIUM |
| 描述 | 浏览器填的路径必须能被**服务器**读到(浏览器与服务器不是同一台时模板需先上传到服务器) |
| 影响 | 远程部署时用户体验差 |
| 缓解 | (1) v0.5 加文件上传 input;(2) 服务器共享网络盘 |
| 状态 | 本地部署没问题,远程部署需手动 |

## 2. 后续工作(roadmap)

### v0.5(下一个小版本)

- [ ] **完整 YAML schema** — 字段类型校验(`schema` 文件)
- [ ] **`pyyaml` 进核心依赖** — 移除 `[yaml]` extras(目前只是过渡)
- [ ] **Web GUI 文件上传** — `multipart/form-data` 接收 .inp 上传到服务器临时目录
- [ ] **CLI 进度条** — `tqdm` 可选依赖
- [ ] **从 manifest 反向** — `inp-tool sweep --from-manifest path.json` 重放历史扫描

### v0.6

- [ ] **流式生成 + 任务取消** — generator + Ctrl-C 优雅退出
- [ ] **并行写盘** — `concurrent.futures.ThreadPoolExecutor`(IO bound)
- [ ] **错误恢复** — 已写盘的 case 写进 manifest,失败 case 重试
- [ ] **per-case 独立 manifest** — 调度器读取更细粒度

### v0.7(集成方向)

- [ ] **CFD++ 求解器集成** — 批量提交作业,`mcrun` 包装
- [ ] **DOE 集成** — `from SALib.sample import salt` → 直接接入 sweep
- [ ] **结果回读** — 扫描结束后,合并每个 case 的 `*.plt` / `*.out` 到 DataFrame
- [ ] **可视化** — `inp-tool sweep --plot alpha-vs-CL.png` 自动出图

### v1.0(API 稳定)

- [ ] **冻结公共 API** — `inp_tool.sweep` 的公开函数/类标 `@stable`
- [ ] **semver** — 后续小版本保持向后兼容
- [ ] **发布到 PyPI** — `pip install inp-tool` 直接装

## 3. 不在 roadmap 的事

- **GUI 应用** — 不做桌面 GUI(已有 Web GUI)
- **CFD++ 求解器内置** — 仍是"生成 .inp"工具,不是求解器包装
- **实时监控** — 不在扫描运行时监控 CFD++ 进程(交由外部调度器)

## 4. 贡献指南(供未来贡献者)

### 4.1 提 PR 前

- [ ] 跑 `pytest tests/ --cov=inp_tool` 全过,覆盖率不下降
- [ ] 新功能有对应测试(AAA 模式)
- [ ] 公共 API 改动讨论后(在 issue / PR 描述)
- [ ] `git status` 自检无 `.bak` / `__pycache__` / 临时文件
- [ ] commit 信息用 conventional commits

### 4.2 修 bug

1. 先写一个失败的测试(red)
2. 实现让它过(green)
3. 重构
4. 跑全套测试

### 4.3 加功能

1. 写 `docs/plans/<date>_<feature>.md` 计划
2. TDD 实施
3. 完成后归档到 `docs/technical/`,删 plan
4. 提 PR

## 5. 已知非 bug(用户问得多的"问题")

| 现象 | 实际 |
|---|---|
| `diff` 显示大量 modify | 空白/缩进被重构造,值未变(用 `inp-tool diff -u` 看实际差异) |
| `naming` 自动生成长文件名 | 默认包含所有 sweep keys,设 `naming` 覆盖 |
| 几何分解与样例值差很大 | 检查 CFD++ 版本对 alpha/beta 的方向假设,可能需 `enabled=false` |
| 模板 `aero_u` 已存在但 `apply` 没更新 | `set()` 找不到则 `append()`,会重复;先 `inp_tool.cli set` 删除旧行 |
