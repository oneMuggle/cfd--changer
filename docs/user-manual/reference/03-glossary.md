# 15 — 术语表(A–Z)

> 本章是 `inp_tool` 与 CFD++ `mcfd.inp` 涉及的术语 / 类名 / 配置键的速查索引。
> 按 A–Z 字母排序,每个词条 1–3 句定义 + 引用(章节号或文件名)。遇到陌生词条,先 Ctrl+F 搜这里。
> 阅读路径:首次接触 → [01-介绍](../basics/01-introduction.md);想了解内部实现 → [../technical/](../technical/)。

---

## A

- **alpha(攻角)**:飞行器气动研究里的"迎角",单位是度(deg)。`inp_tool` 中作为 sweep 轴名,自动写进 `guiopts.aero_alpha` 并参与几何分解。详见 [04-扫描参数 §2](../sweep/01-sweeping.md)。
- **aero_***:`guiopts` 块下的一组 GUI 友好字段(`aero_alpha/beta/ma/u/v/w/temp/pres/re/altid/...`),是 sweep 主要修改的目标集。详见 [12-字段参考 §3.6](01-mcfd-inp-field-reference.md)。
- **ASCII**:`mcfd.inp` 是纯 ASCII 文本,无 BOM,无 UTF-16。Windows 下保存时务必用 ANSI / UTF-8 no BOM,否则 `inp-tool parse` 报编码错。详见 [10-FAQ](../sweep/07-faq.md)。
- **AMR(Adaptive Mesh Refinement)**:自适应网格细化。`mcfd.inp` 的 `octree` 块管 AMR 参数;`inp_tool` 不自动改它,需走 [07-字段覆盖](../sweep/04-overrides.md)。详见 [12-字段参考 §3.7](01-mcfd-inp-field-reference.md)。
- **auto_***:`guiopts` 块下另一组"自动推断"字段(`auto_pres/temp/u/v/w/tlvl/...`),求解器在某些场景会自动用它们覆盖 `aero_*`。`inp_tool` 默认不动 `auto_*`,需用户手动 [04-overrides](../sweep/04-overrides.md)。

## B

- **beta(侧滑角)**:飞行器相对气流的侧向角,单位度。sweep 轴名之一,默认 0;`beta` 影响 `aero_v`(几何分解的"侧滑分量")。详见 [04-扫描参数 §2](../sweep/01-sweeping.md) / [06-几何分解 §4](../technical/sweep/04-sweep-freestream.md)。
- **Block(块)**:`mcfd.inp` 的核心数据结构,`begin <name>` / `end` 包起来的一组语句。`inp_tool` 的 `model.Block` 暴露 `statements` / `name` / `idx` 等属性。详见 [13-CLI/API §3.2](02-cli-api-reference.md)。
- **begin / end(块定界符)**:`mcfd.inp` 顶层块语法,`begin <block_name>` 起始、`end` 结束,必须配对。块名大小写不敏感(`guiopts` = `GuiOpts`)。详见 [12-字段参考 §1.1](01-mcfd-inp-field-reference.md)。
- **bash / zsh / fish**:三种支持 shell 补全的 shell。`inp-tool completion {bash|zsh|fish}` 输出对应脚本。详见 [08-多入口 §6](../sweep/05-multiple-uis.md)。
- **binary / standalone(单文件可执行)**:PyInstaller 打包出的独立可执行文件(`inp-tool` / `inp-tool.exe`),不需要 Python 环境。详见 [11-standalone](../advanced/01-packaging.md) / [01-cli-packaging](../technical/release/01-cli-packaging.md)。

## C

- **Cartesian product(笛卡尔积)**:sweep 的核心展开方式,N 个 sweep 轴的值表做"全配对",得到 `len(ax1) × len(ax2) × ...` 个 case。详见 [04-扫描参数 §4](../sweep/01-sweeping.md)。
- **case_id**:单个 case 的唯一标识,默认 = 输出文件名(已渲染 naming 模板)。`SweepReport.cases[i].case_id` 与 `manifest.cases[i].case_id` 都用此。详见 [13-CLI/API §3.1](02-cli-api-reference.md)。
- **CFL / cflbot / cfller**:`tsteps` 块的时间步相关字段。`cflbot` = CFL 下限(启动用,默认 0.001),`cfller` = CFL 增长率(每步 × 此数,默认 0.75)。sweep 不直接扫它们,需 [04-overrides](../sweep/04-overrides.md)。详见 [12-字段参考 §3.3](01-mcfd-inp-field-reference.md)。
- **conda**:推荐的环境管理工具。本项目环境名 `cfdchanger`,Python 3.8(LTS 兼容 Win7)。详见 [02-安装](../basics/02-installation.md) / [CLAUDE.md §1](../../CLAUDE.md)。
- **CaseSweep / CaseResult / SweepReport**:Python API 的三个核心 dataclass。`CaseSweep` = 配置聚合,`CaseResult` = 单 case 结果(`case_id/path/params/applied`),`SweepReport` = 整批报告(`total/cases/template`)。详见 [13-CLI/API §3.2](02-cli-api-reference.md) / [04-架构 §2](../technical/sweep/02-sweep-architecture.md)。
- **CI / CD(持续集成 / 持续部署)**:本项目用 GitHub Actions:PR 触发测试,tag 触发 3 平台打包并发 GitHub Release。详见 [11-CI/CD](../technical/release/02-ci-cd.md)。

## D

- **diff(差异比较)**:两个 `.inp` 文件之间的关键字级差异。CLI `inp-tool diff a.inp b.inp`,Python `from inp_tool import diff`。详见 [13-CLI/API §1](02-cli-api-reference.md)。
- **dry-run(试运行)**:sweep 跑全部流程(笛卡尔积展开、命名、生成 manifest)但**不写盘**的开关。CLI `--dry-run`,Python `generate(cs, dry_run=True)`。详见 [03-快速开始](../basics/03-quickstart.md)。
- **Dataclass**:Python 3.7+ 的"装饰器式数据类"。`CaseSweep` / `SweepReport` 等都是 `@dataclass`,可 `from_dict()` 反序列化。详见 [04-架构 §2](../technical/sweep/02-sweep-architecture.md)。
- **DOE(Design of Experiments)**:实验设计方法学(全因子 / LHS / Sobol)。`inp_tool` 自己不做采样,但 `sweeps` 的值列表可以从 SALib 等输出拼出来。详见 [09-例 3](../sweep/06-examples.md)。

## E

- **e2e(端到端)**:End-to-End 测试。`tests/test_sweep_*.py` 里有多个 e2e 用例(走 CLI / API 真实路径)。详见 [08-测试 §5](../technical/sweep/06-sweep-testing.md)。
- **exit code**:CLI 退出码。`inp-tool` 约定 `0` = 成功,`1` = 内部异常,`2` = 输入/解析错。详见 [13-CLI/API §1.2](02-cli-api-reference.md)。
- **EVAL_TYPE_BACKPORT**:Py3.8 上让 Pydantic v2 能评估 PEP 604 / 585 注解的辅助包,装 `[api]` extras 时自动拉。详见 [09-风险 R6](../technical/sweep/07-sweep-risks-roadmap.md)。

## F

- **FreestreamPreset(来流预设)**:根据 `(alpha, beta, mach, T)` 自动算 `(U, V, W, refvel)` 并写进 `guiopts.aero_u/v/w` 与 `physics.refvel` 的模块。默认开,设 `enabled: false` 关闭。详见 [06-几何分解](../technical/sweep/04-sweep-freestream.md)。
- **FastAPI**:`inp_tool` 的 Web 后端框架(可选,`[api]` extras)。入口 `inp-tool-api`,默认端口 8765。详见 [13-CLI/API §2](02-cli-api-reference.md)。
- **format(str.format 命名模板)**:Python `str.format(**params)` 风格的命名占位符,占位符名 = sweep 字段名。`{alpha:02.0f}` / `{mach:.2f}` 等格式说明符与 Python 一致。详见 [06-命名规则](../sweep/03-naming.md)。
- **file_id**:FastAPI `/api/files/load` 后端为已加载文件生成的 8 字符 UUID,后续 `set` / `append` / `save` 操作用它做 key。**仅在内存中,服务重启失效**。详见 [13-CLI/API §2.1](02-cli-api-reference.md)。

## G

- **gamma(比热比) / R(气体常数)**:FreestreamPreset 公式 `a = sqrt(γ·R·T)` 的两个参数。默认 `γ=1.4` / `R=287.05`(干空气)。详见 [06-几何分解 §2](../technical/sweep/04-sweep-freestream.md)。
- **guiopts**:mcfd.inp 顶层 10 块之一,存 GUI 友好的"高阶"参数(`aero_*` / `auto_*` / `incomp_*` / `turbi_*`)。**sweep 主要改的块**。详见 [12-字段参考 §3.6](01-mcfd-inp-field-reference.md)。
- **GUI / Web GUI(浏览器界面)**:本项目特指 FastAPI + 静态 HTML 提供的浏览器界面(端口 8765)。`pip install -e .[api]` 后用 `inp-tool-api` 启动。详见 [08-多入口 §5](../sweep/05-multiple-uis.md) / [13-CLI/API §2](02-cli-api-reference.md)。
- **GitHub Release**:发布产物的渠道。`release.yml` workflow 推 tag 后自动上传 3 平台 binary 并创建 draft Release。详见 [11-CI/CD §5](../technical/release/02-ci-cd.md)。

## H

- **HTTPS_PROXY**:公司代理下 `pip install` 失败时设的环境变量(`set HTTPS_PROXY=http://your-proxy:8080`)。详见 [10-FAQ §安装](../sweep/07-faq.md)。
- **HPC(High Performance Computing)**:超算集群环境。`inp_tool` 不直接调 SLURM/PBS/LSF,生成 `.inp` 后由用户/调度器跑。详见 [14-教程 5](../advanced/02-software-tutorial.md)。

## I

- **InpFile(整个 .inp)**:Python API 的顶层 dataclass,包含 `block_list` + `top_stmts`。`parse_file()` 返回的就是它。详见 [13-CLI/API §3.2](02-cli-api-reference.md) / [04-架构](../technical/sweep/02-sweep-architecture.md)。
- **infer_type(类型推断)**:把字符串 `"4.0"` 解析为 `float` / `"on"` 保守为 `str` 的工具函数。`Value.typed` 字段在 parse 阶段被自动填。详见 [13-CLI/API §3](02-cli-api-reference.md)。
- **inp-tool / inp_tool**:`inp-tool`(连字符) = CLI 命令;`inp_tool`(下划线) = Python 包名。两者等价入口,底层同一套代码。详见 [01-介绍](../basics/01-introduction.md)。
- **info set(复合语句)**:`mcfd.inp` 顶层允许的"复合语句"形式(`begin info set <id>` / `values v1 v2 v3` / `end`),用于给某些字段一个有序取值序列。`inp_tool v0.4` 视其为普通块,不消费。详见 [12-字段参考 §5](01-mcfd-inp-field-reference.md)。
- **iofiles**:顶层 10 块之一,定义 14 类输入 / 14 类输出 `.bin` 文件基名(32 条 `*_fn` 语句)。详见 [12-字段参考 §3.2](01-mcfd-inp-field-reference.md)。
- **interactive(交互式 CLI)**:`inp-tool sweep -i`,走 prompt 序列让用户一步步填配置,所有字段有 default,回车接受。详见 [08-多入口 §3](../sweep/05-multiple-uis.md)。

## J

- **JSON**:sweep 配置的默认格式(`sweep.json`),标准库自带,无需 extras。**适合 CI / 自动化 / 复现**。详见 [05-配置文件 §2](../sweep/02-config-files.md)。
- **Jupyter Notebook**:交互式 Python 环境,`inp_tool` Python API 的常用舞台。详见 [09-例 5](../sweep/06-examples.md)。

## K

- **keyword(字段关键字)**:`mcfd.inp` 块内每条语句的左值(例如 `aero_alpha`、`ntstep`)。`Stmt.keyword` 暴露给 Python API。详见 [12-字段参考 §1](01-mcfd-inp-field-reference.md) / [13-CLI/API §3](02-cli-api-reference.md)。

## L

- **LHS / Sobol(Latin Hypercube / Sobol 序列)**:DOE 采样方法。`inp_tool` 自己不做,但 SALib 等库的结果可直接喂进 `sweeps` 的值列表。详见 [09-例 3](../sweep/06-examples.md)。
- **loader**:CFD++ 求解器的"加载器"阶段,对应 `iofiles.lm_type` / `lm_cells_limit` 等字段。`inp_tool` 不解析 loader 内部。详见 [12-字段参考 §3.2](01-mcfd-inp-field-reference.md)。

## M

- **Mach / Ma(马赫数)**:来流速度与当地声速之比,无量纲。sweep 轴名 `mach` / `ma` 通用,默认写进 `guiopts.aero_ma`。详见 [04-扫描参数](../sweep/01-sweeping.md)。
- **manifest(索引文件)**:sweep 跑完后生成的 `manifest.json`,记录每个 case 的 `case_id / path / params / applied` 以及模板的 SHA-256。供下游脚本消费 / 审计。详见 [04-架构 §6](../technical/sweep/02-sweep-architecture.md) / [03-快速开始](../basics/03-quickstart.md)。
- **mcfd.inp**:CFD++ 求解器的输入文件名约定(也作"整个 mcfd 输入文件格式"的代称)。本工具围绕这个文件的批量生成设计。详见 [01-介绍](../basics/01-introduction.md) / [12-字段参考](01-mcfd-inp-field-reference.md)。
- **template_sha256**:manifest 中的模板 SHA-256 字段,供下游校验"样例被改后 manifest 是否过期"。详见 [04-架构 §6](../technical/sweep/02-sweep-architecture.md)。
- **mg_* / fg_*(多重网格 / 细网格)**:`options` 块下的多重网格参数簇(`mg_meth/type/vers/aggl/step` 等),求解器内部收敛加速用。sweep 不动,需 [04-overrides](../sweep/04-overrides.md)。详见 [12-字段参考 §3.4.5](01-mcfd-inp-field-reference.md)。

## N

- **naming(命名模板)**:sweep 配置的可选字段,`str.format` 风格,占位符 = sweep 字段名。**多值轴必须出现,单值轴可省略**。详见 [06-命名规则](../sweep/03-naming.md)。
- **naming_ext**:输出文件扩展名,默认 `.inp`(可在 config 里改)。详见 [05-配置文件 §4](../sweep/02-config-files.md)。
- **ntstep / ntoutfv / ntplot / ntout1..29**:`tsteps` / `options` 块下的"时间步"和"输出频率"字段,数字后缀表示"第 N 个输出"或"步数"。常见改法见 [07-覆盖 §3.1](../sweep/04-overrides.md)。
- **Nuitka**:PyInstaller 之外的另一种 Python→exe 编译工具(性能更好,配置复杂)。本项目暂未用,留作 v0.5+ 备选。详见 [10-打包 §3](../technical/release/01-cli-packaging.md)。

## O

- **overrides(字段覆盖)**:在 `freestream` preset 之外,手动改任意 `block.keyword` 的机制。两种风格(嵌套 / 点号 key)。详见 [07-字段覆盖](../sweep/04-overrides.md) / [04-架构 §4](../technical/sweep/02-sweep-architecture.md)。
- **options**:顶层 10 块之一,167 条语句,数值格式 / 隐式 / 多重网格 / 输出频率的"大杂烩"。详见 [12-字段参考 §3.4](01-mcfd-inp-field-reference.md)。
- **octree**:顶层 10 块之一,10 条语句,AMR / Octree 网格细化容差。详见 [12-字段参考 §3.7](01-mcfd-inp-field-reference.md)。
- **onefile / onedir**:PyInstaller 两种打包模式。`onefile` = 单文件(本项目当前);`onedir` = 多文件目录(启动快,留 v0.5+)。详见 [10-打包](../technical/release/01-cli-packaging.md)。

## P

- **parser(解析器)**:`inp_tool.parser` 模块,把 `.inp` 文本解析成 `InpFile` 对象。CLI / Python API 入口都是它。详见 [04-架构 §1](../technical/sweep/02-sweep-architecture.md) / [13-CLI/API §3.2](02-cli-api-reference.md)。
- **physics**:顶层 10 块之一,200 条语句,工质 / 输运 / 湍流 / 化学反应 / 辐射。`sweep` 通过 preset 改 `refvel / reftem / refpre`。详见 [12-字段参考 §3.5](01-mcfd-inp-field-reference.md)。
- **preserve_format(保留原空白)**:v0.4 计划中(v0.4 尚未实现)的 writer 选项,用于保留原文件的缩进 / 注释风格。详见 [10-FAQ](../sweep/07-faq.md) / [09-风险 R2](../technical/sweep/07-sweep-risks-roadmap.md)。
- **PyInstaller**:本项目用的 Python→exe 打包工具,钉死 5.13.2(最后一个支持 Py3.8 + Win7)。详见 [10-打包 §3](../technical/release/01-cli-packaging.md)。
- **prompt(交互式)**:交互式 CLI 的每一步输入(`inp-tool sweep -i` 的 prompt 序列)。详见 [08-多入口 §3](../sweep/05-multiple-uis.md)。
- **probe / debug**:顶层 10 块中的两个可选块,本项目 2 个样例均为空块。详见 [12-字段参考 §3.8–3.9](01-mcfd-inp-field-reference.md)。
- **PEP 585 / 604**:Python 3.9+ 的内建下标泛型 / 联合类型语法。本项目 Py3.8 + Pydantic 环境下用 `eval_type_backport` 兼容。详见 [CLAUDE.md §1.4](../../CLAUDE.md) / [09-风险 R6](../technical/sweep/07-sweep-risks-roadmap.md)。

## Q

- **quickstart(快速开始)**:专指 [03-quickstart](../basics/03-quickstart.md),5 分钟跑通第一个批量生成的教程。详见 [03-快速开始](../basics/03-quickstart.md)。

## R

- **refpre(参考压强) / reftem(参考温度) / refvel(参考速度) / refden / reflen / refmwt / refpgf**:`physics` 块下的"无量纲化参考量"。`sweep` 通过 preset 改 `refvel / reftem / refpre`,其余默认固定。详见 [12-字段参考 §3.5.5](01-mcfd-inp-field-reference.md) / [06-几何分解 §3](../technical/sweep/04-sweep-freestream.md)。
- **round-trip**:parse → modify → write → re-parse 整个链路,值不丢。本项目测试里大量用 round-trip 验证。详见 [08-测试 §4.2](../technical/sweep/06-sweep-testing.md)。
- **Reynolds(雷诺数)**:无量纲数,`Re = ρ·v·L/μ`。`inp_tool` **不自动算**(不知参考长度),需 [04-overrides](../sweep/04-overrides.md) 手动给 `aero_re`。详见 [10-FAQ §几何分解](../sweep/07-faq.md)。
- **refmuu / refkap(粘性 / 导热参考)**:Sutherland 公式中的参考粘度 / 参考导热系数。详见 [12-字段参考 §3.5.5](01-mcfd-inp-field-reference.md)。

## S

- **Stmt(语句)**:`mcfd.inp` 块内一行 `keyword value1 value2 ...` 的 dataclass。暴露 `keyword` / `values` / `set(idx, val)` / `append(*vals)`。详见 [13-CLI/API §3.2](02-cli-api-reference.md)。
- **sweep(批量算例生成)**:v0.4 起新增的声明式批量生成器,基于 1 个模板生成 N 个变体 + manifest。CLI / Python / FastAPI 三入口。详见 [04-扫描参数](../sweep/01-sweeping.md) / [03-快速开始](../basics/03-quickstart.md) / [03-总览](../technical/sweep/01-sweep-overview.md)。
- **SweepSpec**:单 sweep 轴的数据结构 `{axis: [values]}`,多个 SweepSpec 用 `expand_cartesian()` 笛卡尔积展开。详见 [04-架构 §2](../technical/sweep/02-sweep-architecture.md)。
- **standalone(单文件可执行)**:同 `binary`,指 PyInstaller 出的 `.exe` / ELF 文件。详见 [11-standalone](../advanced/01-packaging.md)。
- **SmartScreen**:Windows Defender 的"未签名应用"拦截。本项目 binary 未签名,首次运行需"仍要运行"。详见 [11-standalone §5.2](../advanced/01-packaging.md)。
- **Sutherland(粘性律)**:CFD 中常用的温度-粘性经验公式 `μ ~ T^1.5 / (T + S)`。对应字段 `rmuusl/tmuusl/smuusl`。详见 [12-字段参考 §3.5.5](01-mcfd-inp-field-reference.md)。
- **system**:顶层 10 块之一,文件 / 进程级杂项。**头部 + 尾部各 1 个 `system` 块**在 mcfd v2 样例中并存,CFD++ 接受这种"多 instance"写法。详见 [12-字段参考 §3.1](01-mcfd-inp-field-reference.md)。
- **shell completion(补全)**:`inp-tool completion {bash|zsh|fish}` 生成的 Tab 补全脚本,让 `inp-tool <TAB>` 列出子命令 / 选项。详见 [08-多入口 §6](../sweep/05-multiple-uis.md)。
- **SI(国际单位制)**:本工具所有物理量默认 SI(度 / K / Pa / m/s)。若样例用其它单位,需在 `overrides` 里手动转换。详见 [06-几何分解 §7](../technical/sweep/04-sweep-freestream.md)。

## T

- **T_inf(来流温度) / p_inf(来流压强)**:`inp_tool` 的辅助 sweep 轴(不是 `guiopts` 原生字段),自动转成 `aero_temp / aero_pres` 和 `reftem / refpre`。详见 [04-扫描参数 §5](../sweep/01-sweeping.md)。
- **tsteps**:顶层 10 块之一,33 条语句,时间推进 / CFL / 重启 / 监控策略。详见 [12-字段参考 §3.3](01-mcfd-inp-field-reference.md)。
- **template(模板)**:sweep 入口的"种子" `.inp` 文件路径,所有 case 基于它做 deepcopy + 修改。详见 [05-配置文件 §4](../sweep/02-config-files.md)。
- **turbmodel(湍流模型)**:`options.ifcomp` / `ifmccw` / `ifskar` / `ifpope` 等的统称。sweep 不动,需 overrides。详见 [12-字段参考 §3.5.7](01-mcfd-inp-field-reference.md)。
- **tqdm**:进度条库(v0.6 计划加入 sweep)。详见 [09-roadmap](../technical/sweep/07-sweep-risks-roadmap.md)。

## U

- **U / V / W(X / Y / Z 速度分量)**:来流速度在三个轴上的分量。`U` 沿 X(气流主方向),`V` 沿 Y(侧滑),`W` 沿 Z(法向 / 垂直)。`FreestreamPreset` 用公式自动算。详见 [06-几何分解 §1](../technical/sweep/04-sweep-freestream.md)。
- **uvicorn**:ASGI 服务器,跑 FastAPI 应用的标准方式。`uvicorn inp_tool.api:app --port 8765`。详见 [13-CLI/API §2.1](02-cli-api-reference.md) / [08-多入口 §5](../sweep/05-multiple-uis.md)。
- **upx**:二进制压缩工具(可执行体积 -50% 但杀软误报多),本项目打包**关掉**。详见 [10-打包 §5.2](../technical/release/01-cli-packaging.md)。

## V

- **Value(mcfd.inp 单值)**:`Stmt.values` 列表里的单个值,带 `raw`(原文) + `typed`(推断后类型)。详见 [13-CLI/API §3.2](02-cli-api-reference.md) / [12-字段参考 §1.4](01-mcfd-inp-field-reference.md)。
- **v0.4.0(项目当前版本)**:本项目当前版本号,匹配 `inp_tool/__init__.py` 中的 `__version__`。后续 v0.5+ 见 roadmap。详见 [10-打包 §3](../technical/release/01-cli-packaging.md) / [CLAUDE.md §1.1](../../CLAUDE.md)。
- **verbose(`-v` / `--verbose`)**:CLI 选项,>20 case 时强制列出每个 case 的完整参数。详见 [08-多入口 §2.2](../sweep/05-multiple-uis.md)。
- **venv / conda**:两种 Python 虚拟环境方案。本项目**推荐 conda**(环境名 `cfdchanger`,Python 3.8)。详见 [02-安装](../basics/02-installation.md) / [CLAUDE.md §1](../../CLAUDE.md)。

## W

- **writer(序列化)**:`inp_tool.writer` 模块,把 `InpFile` 对象写回 `.inp` 文本 / 文件。提供 `to_text()` / `write()` / `write_bytes()` 三个公开入口。详见 [13-CLI/API §3.1](02-cli-api-reference.md) / [13-CLI/API §3.2](02-cli-api-reference.md)。
- **Web GUI(浏览器界面)**:FastAPI + 静态 HTML 提供的浏览器界面(端口 8765),`pip install -e .[api]` 后用 `inp-tool-api` 启动。详见 [08-多入口 §5](../sweep/05-multiple-uis.md) / [13-CLI/API §2](02-cli-api-reference.md)。
- **WARN / WARNING**:运行时非致命警告(块不存在 / 字段被 append 等)。CLI 默认不显示,`--verbose` 或 Python `logging.basicConfig(level=logging.WARNING)` 开启。详见 [07-覆盖 §5](../sweep/04-overrides.md)。
- **web/(目录)**:`inp_tool/web/` 静态资源目录,PyInstaller 打包时通过 `datas` 一起进 binary。详见 [10-打包 §5.3](../technical/release/01-cli-packaging.md)。

## X / Y / Z

- **X / Y / Z(空间坐标)**:CFD++ 约定的三个空间方向。`aero_u` 对应 X(气流主向),`aero_v` 对应 Y(侧滑),`aero_w` 对应 Z(法向)。详见 [06-几何分解 §4](../technical/sweep/04-sweep-freestream.md)。
- **YAML(配置格式)**:`[yaml]` extras 后支持,人类友好,便于 review;CI / 自动化推荐 JSON。详见 [05-配置文件 §3](../sweep/02-config-files.md) / [07-友好入口 §1](../technical/sweep/05-sweep-friendly-uis.md)。
- **ZOC(Zone of Communication)**:CFD++ 的多区通信机制,对应 `zobcdb` / `zobcty` / `tolzco` 等字段。`inp_tool` 不动。详见 [12-字段参考 §3.4.2](01-mcfd-inp-field-reference.md)。

---

## 速查:首字母 → 章节

| 字母 | 数量 | 涉及章节示例 |
|---|---|---|
| A | 5 | [04](../sweep/01-sweeping.md) / [12](01-mcfd-inp-field-reference.md) |
| B | 5 | [04](../sweep/01-sweeping.md) / [12](01-mcfd-inp-field-reference.md) / [13](02-cli-api-reference.md) |
| C | 6 | [04](../sweep/01-sweeping.md) / [11-CI](../technical/release/02-ci-cd.md) / [13](02-cli-api-reference.md) |
| D | 4 | [13](02-cli-api-reference.md) / [03](../basics/03-quickstart.md) |
| E | 3 | [13](02-cli-api-reference.md) / [08-测试](../technical/sweep/06-sweep-testing.md) |
| F | 4 | [06-几何分解](../technical/sweep/04-sweep-freestream.md) / [06-命名](../sweep/03-naming.md) / [13](02-cli-api-reference.md) |
| G | 4 | [12](01-mcfd-inp-field-reference.md) / [11-CI](../technical/release/02-ci-cd.md) |
| H | 2 | [10-FAQ](../sweep/07-faq.md) / [14](../advanced/02-software-tutorial.md) |
| I | 6 | [13](02-cli-api-reference.md) / [12](01-mcfd-inp-field-reference.md) / [01](../basics/01-introduction.md) |
| J | 2 | [05](../sweep/02-config-files.md) / [09](../sweep/06-examples.md) |
| K | 1 | [12](01-mcfd-inp-field-reference.md) / [13](02-cli-api-reference.md) |
| L | 2 | [09](../sweep/06-examples.md) / [12](01-mcfd-inp-field-reference.md) |
| M | 5 | [04-架构](../technical/sweep/02-sweep-architecture.md) / [01](../basics/01-introduction.md) / [12](01-mcfd-inp-field-reference.md) |
| N | 4 | [06](../sweep/03-naming.md) / [07](../sweep/04-overrides.md) / [10-打包](../technical/release/01-cli-packaging.md) |
| O | 4 | [07](../sweep/04-overrides.md) / [12](01-mcfd-inp-field-reference.md) / [10-打包](../technical/release/01-cli-packaging.md) |
| P | 7 | [04-架构](../technical/sweep/02-sweep-architecture.md) / [12](01-mcfd-inp-field-reference.md) / [10-打包](../technical/release/01-cli-packaging.md) |
| Q | 1 | [03](../basics/03-quickstart.md) |
| R | 4 | [12](01-mcfd-inp-field-reference.md) / [08-测试](../technical/sweep/06-sweep-testing.md) / [10-FAQ](../sweep/07-faq.md) |
| S | 9 | [04-架构](../technical/sweep/02-sweep-architecture.md) / [13](02-cli-api-reference.md) / [11-standalone](../advanced/01-packaging.md) / [12](01-mcfd-inp-field-reference.md) |
| T | 5 | [12](01-mcfd-inp-field-reference.md) / [04](../sweep/01-sweeping.md) / [09-roadmap](../technical/sweep/07-sweep-risks-roadmap.md) |
| U | 3 | [06-几何分解](../technical/sweep/04-sweep-freestream.md) / [13](02-cli-api-reference.md) / [10-打包](../technical/release/01-cli-packaging.md) |
| V | 4 | [13](02-cli-api-reference.md) / [10-打包](../technical/release/01-cli-packaging.md) / [02](../basics/02-installation.md) |
| W | 4 | [13](02-cli-api-reference.md) / [08](../sweep/05-multiple-uis.md) / [10-打包](../technical/release/01-cli-packaging.md) |
| X / Y / Z | 3 | [06-几何分解](../technical/sweep/04-sweep-freestream.md) / [12](01-mcfd-inp-field-reference.md) |

> 词条约 80+,覆盖了 `inp_tool` CLI/Python API 概念、CFD++ mcfd.inp 字段、配置键、术语/工具等。如有遗漏,提 issue。
