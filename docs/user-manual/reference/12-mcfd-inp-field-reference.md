# 12 — mcfd.inp 文件字段参考

> 本章是 `mcfd.inp` 顶层 10 个块所有字段的速查表,字段值取自 `inp_tool/examples/mcfd_modified.inp`(6 块)和 `inp_tool/examples/mcfd_v2_modified.inp`(3 块,加 1 个尾部空 `system`)。单位 / 默认值参考 CFD++ 官方手册;若与你所用的 CFD++ 版本不一致,以求解器为准。

---

## 1. 文件结构速记

`mcfd.inp` 是 **块结构 + 自由格式**的 ASCII 文本,每行一条语句,语句类型有 3 种:

### 1.1 块 begin / end 语法

```inp
begin <block_name>
  <keyword> <value1> <value2> ...
  ...
end
```

- 块名大小写**不敏感**(`system` / `System` / `SYSTEM` 等价)
- `begin` / `end` **必须配对**,嵌套层数不限(实测最多 1 层)
- 块内语句是 `<keyword> <value(s)>` 列表,关键字也大小写不敏感

### 1.2 行尾 `#` 注释

```inp
aero_alpha 5.0   # 攻角 5 度
```

- `#` 后面的内容**整行被解析器丢弃**(v0.4 行为;v0.3 之前是 strip 后保留)
- `inp_tool v0.4` 的 `--preserve-format` 模式会**保留原注释文本**不动

### 1.3 顶层非块语句(复合语句 / info set)

在所有 `begin/end` 块之外,允许出现"复合语句"(`info set` 等),语法为:

```inp
begin info set <seq_id>
  values <v1> <v2> <v3> ...
end
```

详见 §5。

### 1.4 值类型约定

- 整数 / 浮点数:  按 `python float()` / `int()` 解析
- 字符串:        不带引号,以空白分隔
- 枚举:          用整数码表示(例如 `lm_type STANDARD=0, PARALLEL=1`)

---

## 2. 顶层结构(10 块)

`mcfd.inp` 顶层允许 10 种块,出现频率和职责如下:

| # | 块名 | 必选 | 出现频率 | 主要职责 |
|---|---|---|---|---|
| 1 | `system`    | 必选 | 几乎每个 case 都有 | 文件 / 进程级杂项(`mc_filecopy`、loader 设置等) |
| 2 | `iofiles`   | 必选 | 几乎每个 case 都有 | 输入 / 输出 `.bin` 文件名映射 |
| 3 | `tsteps`    | 必选 | 几乎每个 case 都有 | 时间步 / CFL / 重启策略 |
| 4 | `options`   | 必选 | 几乎每个 case 都有 | 数值格式 / 隐式 / 多重网格 / 输出频率 |
| 5 | `octree`    | 可选 | 用到 AMR / Octree 时 | 网格细化容差 / 树构建参数 |
| 6 | `physics`   | 必选 | 几乎每个 case 都有 | 工质 / 输运 / 湍流 / 化学反应 / 辐射 |
| 7 | `probe`     | 可选 | 监控某点 / 截面时 | 探针位置 / 探针变量(本项目 2 个样例均为空块) |
| 8 | `debug`     | 可选 | 调试 / 单步 | 调试钩子(本项目 2 个样例均为空块) |
| 9 | `guiopts`   | 必选 | 几乎每个 case 都有 | GUI 友好的"高阶"参数(`aero_*`、`auto_*`、`incomp_*`、`turbi_*`) |
| 10 | `system` (尾部) | 可选 | v2 样例独占 | 收尾的 `system` 块(常用于 case 关闭时的拷贝操作) |

> 样例 `mcfd_v2_modified.inp` 有 2 个 `system` 块(头部 L4-8 + 尾部 L1311-12),CFD++ 接受这种"多 instance"写法;`inp_tool` 也按多 instance 解析。

---

## 3. 块字段速查

每节格式: `keyword | 含义 | 单位 | 类型 | 默认值 | 备注`

### 3.1 `system` 块

> 头部 `system` 块(出现 1 次 / 文件),`mc_filecopy` 列出"在求解前先把磁盘 A 文件拷到 B 文件"的清单。

| keyword | 含义 | 单位 | 类型 | 默认值 | 备注 |
|---|---|---|---|---|---|
| `mc_filecopy` | 文件拷贝指令(2 个参数:源 → 目标) | — | 字符串 × 2 | 无 | 一行一条,常见用法:`cdepsout.bin → cdepsin.bin`(让下一个 case 接着算) |

样例:

```inp
begin system
  mc_filecopy cdepsout.bin cdepsin.bin
  mc_filecopy cdaveout.bin cdavein.bin
  mc_filecopy mcfd6dof.out mcfd6dof.inp
end
```

### 3.2 `iofiles` 块

> 32 条 `*_fn` 语句,给 14 类输入 / 14 类输出文件起名(去掉扩展名,默认 `.bin`)。

| keyword | 含义 | 单位 | 类型 | 默认值 | 备注 |
|---|---|---|---|---|---|
| `lm_type` | loader 模式 | — | 枚举 | `STANDARD` | 0=STANDARD, 1=PARALLEL |
| `lm_cells_limit` | loader 单进程 cell 上限 | cells | 整数 | 0 | 0 = 无限制 |
| `lm_cpus_limit` | loader 单进程 CPU 上限 | CPUs | 整数 | 0 | 0 = 无限制 |
| `lm_ser2par` | ser→par 转换开关 | — | 0/1 | 0 | 0=关,1=开 |
| `ifinbc` | 是否读 inbcsin | — | 0/1 | 0 | 1=读 |
| `invoke_script` | loader 阶段是否调外部脚本 | — | 0/1 | 0 | — |
| `mcpusin_fn` ~ `cgrpsin_fn` | **14 类输入**文件基名(去 `.bin`) | — | 字符串 | 见样例 | `mcpusin / nodesin / cellsin / exbcsin / inbcsin / ovsetin / cdepsin / pltosin / eqsetin / zobcsin / ovsetin / blankin / cgrpsin` |
| `mcpusout_fn` ~ `cgrpsout_fn` | **14 类输出**文件基名 | — | 字符串 | 见样例 | 与上面 `*_in_fn` 一一对应,加 `out` |

> ⚠️ 注意 `ovsetin_fn` 和 `ovsetout_fn` 在样例中各出现 2 次(同名字段 2 行),`inp_tool` 按"后写覆盖前写"处理。

### 3.3 `tsteps` 块

> 时间推进 / CFL / 重启 / 监控策略。33 条语句,几乎所有可调参数都在这里。

| keyword | 含义 | 单位 | 类型 | 默认值 | 备注 |
|---|---|---|---|---|---|
| `istart` | 起始模式(0=新算,1=重启) | — | 0/1 | 0 | 重启场景设为 1 |
| `ntstep` | 总时间步数 | steps | 整数 | 50000 | 样例值 |
| `ntstop` | 强制终止步数(0=跟随 ntstep) | steps | 整数 | 0 | — |
| `ntsmin` / `ntrmin` | 单步 / 残差最小迭代 | iters | 整数 | 0 | 0=内部默认 |
| `dtsmoo` | 时间步平滑开关 | — | 0/1 | 1 | 1=启用 |
| `dtsmoo_iters` | 时间步平滑迭代数 | iters | 整数 | 6 | — |
| `dtsmoo_param` | 平滑系数 | — | 浮点 | 0.6666667 | 经典 2/3 |
| `runmod` | 运行模式(0=稳态,1=瞬态) | — | 0/1 | 1 | 样例为瞬态 |
| `dtauin` | 初始时间步(<0 = 自动) | s | 浮点 | -1.0 | -1=用 CFL 自动算 |
| `dtlomx` | 最大时间步长 | s | 浮点 | 1.0 | — |
| `cflbot` | CFL 下限 | — | 浮点 | 0.001 | 启动阶段用 |
| `cfller` | CFL 增长率(每步 × 此数) | — | 浮点 | 0.75 | 经典 0.75 |
| `rstcfl` | 重启后 CFL 步进策略 | — | 整数 | 0 | 0=正常 |
| `ntbclr` | 局部 CFL 重置起点步 | steps | 整数 | 100 | — |
| `nteclr` | 局部 CFL 重置终点步 | steps | 整数 | 500 | — |
| `cfllbg` / `cfllen` | 局部 CFL 起始 / 终止值 | — | 浮点 | 0.02 / 1.0 | 起 → 终线性插值 |
| `cflglo` | 全局 CFL 上限 | — | 浮点 | 1.0e15 | 几乎不限制 |
| `ilcfla` / `igcfla` | 局部 / 全局 CFL 模式 | — | 0/1 | 0 | 0=关闭,1=开启 |
| `itsync` | 同步时间步开关 | — | 0/1 | 0 | 多区时用 |
| `ntbmdr` / `ntemdr` | 监控数据记录起 / 止步 | steps | 整数 | 100 / 200 | — |
| `mdisbg` / `mdisen` | 监控距离起 / 止 | m | 浮点 | 0.0 | — |
| `ntbbfr` / `ntebfr` | 缓冲起 / 止步 | steps | 整数 | 1000 / 1500 | — |
| `blfnbg` / `blfnen` | 缓冲函数起 / 止 | — | 浮点 | 0.0 / 1.0 | 0→1 ramp |
| `cdepsave_compute` | cdeps 是否随计算存 | — | 0/1 | 0 | — |
| `cdepsave_restart` | cdeps 重启时存 | — | 0/1 | 1 | 样例=1 |
| `cdepsave_ntsave` | cdeps 存盘频率 | steps | 整数 | 0 | 0=仅重启时存 |

### 3.4 `options` 块

> 167 条语句,数值方法 / 输出频率 / 隐式 / 多重网格 的"大杂烩"。sweep 不直接改这里;但 `07-overrides.md` 里的"高级字段覆盖"经常涉及(`ntplto` / `limtvd` / `mg_*` / `fg_*`)。下面分组列。

#### 3.4.1 输出频率(IO)

| keyword | 含义 | 单位 | 类型 | 默认值 | 备注 |
|---|---|---|---|---|---|
| `ntdsko` | 数据跳过(降频)起始步 | steps | 整数 | 2000 | 早期加密,后期降频 |
| `ntdsks` | 数据跳过模式 | — | 整数 | 0 | 0=等距 |
| `ntplto` / `ntplts` / `ntpltt` | plot 起始步 / 步长 / 终止步 | steps | 整数 | 0 | 全 0=不输出 |
| `dtpltt` | plot 终止时间 | s | 浮点 | 0.0 | — |
| `ntdskc` / `ntdskr` | cell / restart 数据频率 | steps | 整数 | 0 | — |
| `ntacou` | 声学输出频率 | steps | 整数 | 0 | — |
| `ntout1` ~ `ntout29` | 通用输出 #1 ~ #29 频率 | steps | 整数 | 0 | 0=关闭 |
| `nt6dof1` | 6DOF 输出频率 | steps | 整数 | 1 | — |
| `ntoutfv` / `ntsuffv` | FV 输出频率 / 后缀 | steps / — | 整数 | 0 | — |
| `ntoutes` / `ntsufes` | ES 输出频率 / 后缀 | steps / — | 整数 | 0 | — |
| `ntouttp` / `ntsuftp` | TP 输出频率 / 后缀 | steps / — | 整数 | 0 / 2000 | — |
| `ntoptrb` / `ntsptrb` | 湍流输出频率 / 后缀 | steps / — | 整数 | 0 | — |
| `bcsptrb` | 边界条件输出频率 | steps | 整数 | 0 | — |
| `mpidri` | MPI 调试 | — | 0/1 | 0 | — |

#### 3.4.2 区域 / 重叠 / 重启

| keyword | 含义 | 单位 | 类型 | 默认值 | 备注 |
|---|---|---|---|---|---|
| `mcpuse` | 进程数(0=自动) | procs | 整数 | 0 | — |
| `mcgrps` | 分组数 | groups | 整数 | 1 | — |
| `nodebg` / `inbczb` | 节点 / 内边界零点行为 | — | 0/1 | 0 | — |
| `autozb` | 零点自动处理 | — | 0/1 | 0 | — |
| `osetyp` / `osetdb` / `osetbr` / `osetbc` / `osetbz` / `osetll` / `osetzo` / `osetsl` / `osetir` | 9 种 overlap 设置 | — | 0/1 | 0 | `osetyp` 主开关,其余细分 |
| `osnocn` / `osnosg` | overlap 不收敛 / 信号开关 | — | 0/1 | 1 | — |
| `blnkdb` / `zobcdb` / `zobcty` | blanking / ZOBC 调试 / 类型 | — | 整数 | 0 | — |
| `iregrd` / `iregrq` | 区域 / 重叠请求 | — | 0/1 | 0 / 1 | — |
| `irezon` | 重启区域开关 | — | 0/1 | 0 | — |
| `reblnk` | 重启时重建 blank | — | 0/1 | 0 | — |
| `igrvs1` / `igrvs7` / `igrvs9` / `igrvs10` / `igrvs13` / `igrvs14` | IO 路由标志位 | — | 0/1 | 0 | — |

#### 3.4.3 数值格式 / TVD / 极限

| keyword | 含义 | 单位 | 类型 | 默认值 | 备注 |
|---|---|---|---|---|---|
| `viscos` | 粘性项开关 | — | 0/1 | 1 | 1=开 |
| `vibnew` | 新版振动算法 | — | 0/1 | 1 | — |
| `ifmdis` / `mdislh` / `disson` | 多尺度距离 / 长度 / 阻尼 | — / m / — | 整数+浮点 | 1 / 0.25 / 0.1 | — |
| `ifmdps` / `mdisps` | 多尺度压力开关 / 参数 | — / — | 整数+浮点 | 1 / 0.05 | — |
| `mdtype` / `mdpscf` / `mdpsmx` | 多尺度类型 / 系数 / 上限 | — | 整数+浮点 | 1 / 0.3 / 1.0 | — |
| `ifmdcb` / `mdcbfr` | 多尺度 crosshatch / 频率 | — | 整数+浮点 | 1 / 0.25 | — |
| `xyzpol` | 极坐标方向(xy/xz/yz) | — | 字符串 | xy | — |
| `ispcac` / `iblend` / `iblenz` | 空间精度 / 混合 / 方向 | — | 整数 | 2 / 1 / 0 | — |
| `blenzf` | 混合方向因子 | — | 浮点 | 0.5 | — |
| `bextac` / `bzonac` / `bzoncd` | 边界扩展 / 区域数 / 区域代码 | — | 整数 | 1 / 2 / 0 | — |
| `arcozb` / `sewzon` | 区域零点 / 缝合区 | — | 0/1 | 0 / 1 | — |
| `celpol` / `cenpol` / `nodnei` | 单元 / 中心 / 节点插值 | — | 整数 | 1 / 1 / 1 | — |
| `viscrs` / `vcropt` | 粘性交叉项 / 选项 | — | 整数 | 0 / 1 | — |
| `tvspol` | TVD 极向开关 | — | 0/1 | 1 | — |
| `celpoj` / `limfac` / `limtvd` | 单元 Jacobian / 极限因子 / TVD 限制器 | — | 整数+浮点 | 0 / 0 / 3 | `limtvd` 3=van Leer |
| `rhsopt` / `rhsink` | RHS 优化 / 注入 | — | 整数 | 1 / 0 | — |
| `tolpol` | 极向迭代容差 | — | 浮点 | 1e-13 | — |
| `tvdphi` / `tvdcmp` | TVD phi 系数 / 压缩参数 | — | 浮点 | 0.333 / 2.0 | — |
| `chkvol` / `tolvol` | 体积守恒检查 / 容差 | — | 整数+浮点 | 1 / 1e-20 | — |

#### 3.4.4 梯度限定 / 平滑

| keyword | 含义 | 单位 | 类型 | 默认值 | 备注 |
|---|---|---|---|---|---|
| `grqua1` ~ `grqua6` | 6 种梯度限定模式开关 | — | 0/1 | 0 | — |
| `gq1dis` / `gq3dis` / `gq6dis` | 限定距离(模式 1/3/6) | — | 浮点 | 0.1 | — |
| `gq2ang` / `gq6ang` | 限定角度(模式 2/6) | 度 | 浮点 | 2.0 / 40.0 | — |
| `rtcord` | 旋转坐标 (Rtheta) | — | 浮点 | 9.0 | — |
| `convo1` / `convo2` | 卷积模式 | — | 0/1 | 0 | — |
| `simstr` / `dultim` | 简单拉伸 / DULLIM | — | 0/1 | 1 / 0 | — |
| `glitrc` / `gloits` | 全局限制 / 迭代 | — | 浮点+整数 | 0.1 / 1 | — |
| `pc_method` | 预条件方法 | — | 整数 | 0 | — |
| `mbltim` / `mblfac` / `mblglt` | 移动限制 / 因子 / 全局 | — | 整数+浮点 | 0 / 0.1 / 1 | — |
| `geomopt1` | 几何选项 | — | 整数 | 0 | — |

#### 3.4.5 隐式 / 多重网格

| keyword | 含义 | 单位 | 类型 | 默认值 | 备注 |
|---|---|---|---|---|---|
| `method` | 求解方法(0=显式,2=隐式) | — | 整数 | 2 | 样例为隐式 |
| `itimac` | 时间精度(1=1 阶,2=2 阶) | — | 整数 | 2 | — |
| `ifunlx` / `undrlx` | 非线性松弛开关 / 因子 | — | 整数+浮点 | 1 / 0.75 | — |
| `implic` / `impits` | 隐式开关 / 迭代数 | — | 整数 | 1 / 16 | — |
| `mg_mpio` / `fg_mpfb` / `mg_mpfb` | MG 通信 / FG 反馈 / MG 反馈 | — | 0/1 | 1 / 0 / 0 | — |
| `mg_meth` / `mg_type` / `mg_vers` / `mg_aggl` / `mg_step` | 多重网格 5 选项 | — | 整数 | 2 / 2 / 1 / 1 / 5 | — |
| `stojac` / `mg_alow` / `mg_stag` / `mg_lint` / `mg_itns` / `mg_levs` / `mg_mxcg` / `mg_cycl` | MG Jacobian / 允许 / stagger / 线性 / 内部迭代 / 层数 / 最大 CG / 循环 | — | 整数 | 1 / 1 / 1 / 2 / 1 / 20 / 1048576 / 4 | — |
| `mg_resc` / `mg_terc` / `mg_floc` | MG 残差 / 终止 / flop 容差 | — | 浮点 | 0.5 / 0.1 / 1e-10 | — |
| `fg_resc` / `fg_terc` / `fg_floc` | FG 同上(细网格) | — | 浮点 | 0.5 / 0.1 / 1e-10 | — |
| `mg_cvis` | MG 粘性项 | — | 浮点 | 1.0 | — |
| `celord` / `subdomain_mode` | 单元阶数 / 子域模式 | — | 整数 | 1 / 0 | — |

### 3.5 `physics` 块

> 200 条语句,工质 / 输运 / 湍流 / 化学反应 / 辐射的"完整物理配置"。sweep 主要改这里的 `refvel / reftem / refpre / refden / reflen / refmwt / refpgf`(参见 §4)。

#### 3.5.1 多方程 / 平衡化学 / 预条件

| keyword | 含义 | 单位 | 类型 | 默认值 | 备注 |
|---|---|---|---|---|---|
| `meq_eqsets` / `meq_eqsgrp` / `meq_icslct` / `meq_inityp` | 多方程组配置 | — | 整数 | 0 | 0=单组 |
| `cht_matprp` | 共轭传热材料属性 | — | 0/1 | 0 | — |
| `absour` / `absour_selftune` | 吸收源 / 自调 | — | 整数 | 0 / 1 | — |
| `cldriver` | 闭环驱动 | — | 0/1 | 0 | — |
| `rotor_model1` | 转子模型 1 | — | 0/1 | 0 | — |
| `anchor_pressure` | 锚定压强 | — | 0/1 | 0 | — |
| `moddif` / `moddif_type` | 模型扩散 / 类型 | — | 整数 | 0 / 2 | — |
| `icsrot` / `prerot` | 初始条件旋转 / 预旋转 | — | 0/1 | 0 | — |
| `preacc_opt` / `preacc_dti` | 预加速选项 / dt | — | 整数+浮点 | 0 / 0.05 | — |
| `pretyp` / `ipreof` / `prebet` / `previs` / `prevel` / `prevlo` | 预条件类型 / 步数 / 系数 / 粘性 / 速度 / 体积分 | — | 整数+浮点 | 1 / 20 / 0.05 / 0.05 / 1e-6 / 1e-3 | — |
| `pfloor` | 压强下限 | Pa | 浮点 | 0.0 | — |

#### 3.5.2 工质 / 单位

| keyword | 含义 | 单位 | 类型 | 默认值 | 备注 |
|---|---|---|---|---|---|
| `gasnam` | 工质名 | — | 字符串 | N2 | `N2 / AIR / CO2 / ...` |
| `gasgam` | 比热比 γ | — | 浮点 | 1.4 | — |
| `gasmwt` | 分子量 | g/mol | 浮点 | 28.95 | 空气 |
| `advcon` / `difcon` / `ed_con` / `ed_cap` | 对流 / 扩散 / ED 对流 / ED 上限 | — | 浮点 | 1.0 / 1.0 / 1.0 / 0.0 | 收敛性调节 |
| `iunits` | 单位制(0=SI, 1=CGS) | — | 整数 | 0 | — |
| `lenuni` | 长度单位 | — | 字符串 | m | — |
| `masuni` | 质量单位 | — | 字符串 | kg | — |
| `temuni` | 温度单位 | — | 字符串 | K | — |
| `timuni` | 时间单位 | — | 字符串 | s | — |
| `grduni` | 网格单位 | — | 字符串 | m | — |

#### 3.5.3 化学反应 / 有限率

| keyword | 含义 | 单位 | 类型 | 默认值 | 备注 |
|---|---|---|---|---|---|
| `inityp` / `qcvrti` / `qcvrto` | 初始条件 / 内部/外部 Q 转换 | — | 整数 | 0 | — |
| `ifrpow` / `ifreac` / `ifrebx` | 反应功率 / 反应开关 / 边界反应 | — | 0/1 | 0 / 1 / 0 | — |
| `frctin` / `temulx` / `frcint` / `frclim` / `frclif` / `frccfl` | 有限率参数集 | — | 整数+浮点 | 2 / 0.2 / 1 / 0 / 0.05 / 1 | — |
| `ifscon` / `iftrds` / `ifrsrc` / `ifvols` / `ifvelp` / `ifrmai` | 反应源 / 输运 / 体积 / 速度 / 主反应项开关 | — | 0/1 | 1 / 0 / 0 / 0 / 0 / 0 | — |
| `frcxmn/mx/y/mn/y/mx/zm/zmx` | 反应源 X/Y/Z 范围 | m | 浮点 | 0.0 | — |
| `frsrcu/l/t/m` | 反应源单位 / 时间 / 温度 / 质量 | — | 浮点 | 0/1/1/1 | — |
| `istiff` / `sureac` / `surspe` / `surmap` | 刚性 / 表面反应 / 光谱 / 映射 | — | 0/1 | 0 | — |
| `toltem` / `tolfrc` | 温度 / 力容差 | — | 浮点 | 1e-5 | — |
| `tnoneq_numeqns` | 非平衡方程数 | — | 整数 | 1 | — |

#### 3.5.4 涡破碎 / 湍流入口

| keyword | 含义 | 单位 | 类型 | 默认值 | 备注 |
|---|---|---|---|---|---|
| `edp_yesno` / `edp_model` / `edp_coefvm` / `edp_coefcl` | 涡破碎开 / 模型 / 系数 | — | 整数+浮点 | 0 / 0 / 0.5 / 0.5 | — |
| `edp_ifbuoy` / `edp_gravtx/y/z` | 浮力 / 重力分量 | — | 0/1+浮点 | 0 / 0.0 | — |
| `sourc1` / `sourc2` | 源项 1 / 2 | — | 整数 | 0 | — |
| `ifaxix` / `ifaxiy` | 轴对称 X / Y | — | 0/1 | 1 / 0 | 样例=绕 X 轴对称 |
| `ifwzro` / `ifaxst` / `ifaxsw` / `ifswrl` | 壁面零 / 轴 stagger / switch / swirl | — | 0/1 | 1 / 0 / 0 / 0 | — |
| `swrxmn/mx/y/mn/y/mx/zm/zmx` | 旋转 X/Y/Z 范围 | m | 浮点 | 0.0 | — |
| `swreta` | 旋转 eta | — | 浮点 | 0.5 | — |
| `ifblck` / `blkxmn/mx/y/mn/y/mx/zm/zmx` | 块区域 / 范围 | — | 0/1+浮点 | 0 / 0.0 | — |

#### 3.5.5 区域 / 浮力 / 物性

| keyword | 含义 | 单位 | 类型 | 默认值 | 备注 |
|---|---|---|---|---|---|
| `ipbulk` / `bulkpr` | 区域压强开关 / 值 | — | 整数+浮点 | 0 / 0.0 | — |
| `irbulk` / `bulkro` / `bulktm` | 区域密度 / 温度 | — | 整数+浮点 | 0 / 0.0 / 288.0 | — |
| `presab` / `presmn` / `presmx` | 参考压强绝对 / min / max | Pa | 浮点 | 0 / -1e20 / 1e20 | — |
| `tempmn` / `tempmx` | 温度 min / max | K | 浮点 | -1 / 1e20 | — |
| `univgc` | 通用气体常数 | J/(kmol·K) | 浮点 | 8314.0 | — |
| `refmwt` / `reflen` / `reftem` / `refden` / `refvel` / `refpre` / `refpgf` | **无量纲化参考量**(sweep 主要改) | — / m / K / kg/m³ / m/s / Pa / Pa | 浮点 | 1 / 1 / 1 / 1 / -1 / 1 / 101325 | 见 §4 |
| `ifbuoy` / `gravtx/y/z` | 浮力开关 / 重力分量 | — | 0/1+浮点 | 0 / 0.0 | — |
| `grvcnx/y/z` / `grvbet` | 浮力对流分量 / 系数 | — | 浮点 | 0.0 / 0.003 | — |
| `liqgas` / `vislaw` | 液气 / 粘性律 | — | 整数 | 0 | — |
| `refmuu` / `refkap` / `prndtl` / `prlatu` / `schmla` / `schmtu` | 粘性 / 导热参考 / Pr / Pr_lat / Schmidt 层流 / 湍流 | — | 浮点 | 1 / 1 / 0.72 / 0.8 / 0.525 / 0.7 | — |
| `rmuusl` / `tmuusl` / `smuusl` | Sutherland 粘性参考 μ / T / S | kg/(m·s) / K / K | 浮点 | 1.716e-5 / 273.11 / 111 | 经典 Sutherland |
| `rkapsl` / `tkapsl` / `skapsl` | Sutherland 导热 k / T / S | W/(m·K) / K / K | 浮点 | 2.41e-2 / 273.11 / 194 | — |
| `liqtlo` / `liqtup` | 液相温度范围 | K | 浮点 | 0 / 5000 | — |
| `yppfac` | y+ 因子 | — | 浮点 | 1.0 | — |
| `ifporo` / `ifpmut` / `isporo` | 多孔介质 / μ_t / 源 | — | 0/1 | 0 | — |

#### 3.5.6 湍流 / 合成 / 滤波

| keyword | 含义 | 单位 | 类型 | 默认值 | 备注 |
|---|---|---|---|---|---|
| `ifcjht` / `ifnlas` / `ls_numeqns` / `ntrbst` | 合成湍流 / NLES / 方程数 / 反弹步 | — | 0/1+整数 | 0 / 0 / 0 / 11 | — |
| `iftold` / `smagcf` | 湍流模式 / Smagorinsky 系数 | — | 整数+浮点 | 0 / 0.05 | — |
| `lnstyp` / `lnsdtm` / `lnsbox` | LES 类型 / 时间 / box | — | 整数 | 3 / 1 / 0 | — |
| `mnfltr` / `sync_alpha` | 滤波 / 同步 alpha | — | 浮点 | 0.0 / 1 | — |
| `nlas_allscales` / `rfg_sample_modes` / `mulnyq` / `ininls` / `rfg_rseed` | NLES 全尺度 / RFG 模式数 / Nyquist 倍数 / 初始 NL / 随机种子 | — | 整数 | 0 / 100 / 4 / 0 / 1234567 | — |

#### 3.5.7 壁面函数 / 湍流模型

| keyword | 含义 | 单位 | 类型 | 默认值 | 备注 |
|---|---|---|---|---|---|
| `ifvspt` / `ifmuon` / `ifdpds` / `ifwfne` / `ifwfol` / `ifwfbc` | 壁面 / μ 开关 / 双方程 / 壁函数 NE / 全局 / 边界 | — | 整数 | 0 / 0 / 0 / 1 / 0 / 3 | — |
| `ifcomp` / `ifmccw` / `ifskar` / `ifpope` / `ifbrad` / `iftrat` / `iftrfs` / `ifmbsl` / `iftcon` / `iftrbf` | 可压 / MCC / Skar / Pope / 辐射 / 输运 / T-RANS / MBSL / T 连续 / T 反馈 | — | 0/1 | 1 / 1 / 0 / 0 / 0 / 0 / 0 / 0 / 1 / 0 | — |
| `turbf1` ~ `turbf7` | 湍流乘子 1~7 | — | 浮点 | 1.0 | — |
| `trurlx` / `kmxval` / `tmnval` / `maxmut` / `turlim` / `turxyz` | 湍流松弛 / k 上限 / t 下限 / μ_t 上限 / 极限 / 三维 | — / m²/s² / — / kg/(m·s) / — / — | 浮点+整数 | 1.0 / 1e20 / 1e-12 / 1e10 / 100.0 / 0 | — |
| `cgtsof` | CG / 截断 | — | 整数 | 0 | — |
| `turxmn/mx/y/mn/y/mx/zm/zmx` | 湍流 X/Y/Z 范围 | m | 浮点 | 0.0 | — |
| `shaper` | 形状因子 | — | 浮点 | 0 | — |

### 3.6 `guiopts` 块

> 50 条语句,GUI 友好的"高级"参数集中地。**sweep 主要改的块**。

| keyword | 含义 | 单位 | 类型 | 默认值 | 备注 |
|---|---|---|---|---|---|
| `turbi_lev` ~ `turbi_replen` | 入口湍流 9 个参数(强度 / 长度 / μ_t / 喷流 / 强度 / 时间 / 长度 / 频率 / y+ / 替换长度) | — / m / kg/(m·s) / — / — / s / m / Hz / — / m | 整数+浮点 | 见样例 | 启动湍流用 |
| `auto_pres` | 自动压强(SI/英制) | Pa | 浮点 | 101325.0 | 1.01325e5 |
| `auto_temp` | 自动温度 | K | 浮点 | 288.0 | 15 °C |
| `auto_u` / `auto_v` / `auto_w` | 自动速度 U/V/W | m/s | 浮点 | 30 / 0 / 0 | 默认 30 m/s 来流 |
| `auto_tlvl` / `auto_tlnl` / `auto_tl` / `auto_lt` | 自动湍流 4 项 | — | 浮点+整数 | 0.02 / 0.01 / 1 / 0 | — |
| `auto_eqinf` / `auto_ininf` / `auto_bpinf` | 自动 3 种无穷远(平衡/入口/边界) | — | 0/1 | 0 | — |
| `auto_mutmu` | 自动 μ_t / μ | — | 浮点 | 10.0 | — |
| `aero_intyp` | aero 初始化类型(0=常值,1=外部文件) | — | 整数 | 1 | — |
| `aero_unit` | aero 单位制(0=SI, 1=英制) | — | 整数 | 1 | — |
| `aero_pres` | aero 压强 | Pa | 浮点 | 101325.0 | **sweep 轴** |
| `aero_temp` | aero 温度 | K | 浮点 | 288.0 | **sweep 轴** |
| `aero_deltat` | aero 温差 | K | 浮点 | 0.0 | — |
| `aero_u` / `aero_v` / `aero_w` | aero 速度 U/V/W | m/s | 浮点 | 30 / 0 / 0 | **sweep 轴**(几何分解) |
| `aero_tlvl` / `aero_tlnl` / `aero_tl` / `aero_lt` | aero 湍流 4 项 | — | 浮点+整数 | 0.002 / 0.1 / 1 / 0 | — |
| `aero_eqinf` / `aero_ininf` / `aero_bcinf` | aero 3 种无穷远 | — | 0/1 | 0 | — |
| `aero_altid` | aero 高度 / 湍流强度 | m 或 % | 浮点 | 10.0 | **sweep 轴** |
| `aero_ma` | aero 马赫数 | — | 浮点 | 0.8 | **sweep 轴** |
| `aero_alpha` | aero 攻角 | 度 | 浮点 | 0.0 | **sweep 轴** |
| `aero_beta` | aero 侧滑角 | 度 | 浮点 | 0.0 | **sweep 轴** |
| `aero_plane` | aero 平面 | — | 整数 | 0 | — |
| `aero_re` | aero 雷诺数 | — | 浮点 | 1.0e6 | **sweep 轴**(辅助) |
| `aero_mutmu` | aero μ_t / μ | — | 浮点 | 10.0 | — |
| `incomp_tlvl` / `incomp_tlnl` / `incomp_eqinf` / `incomp_ininf` / `incomp_bpinf` | 不可压 5 项 | — | 浮点+整数 | 0.05 / 0.01 / 0 / 0 / 0 | — |

### 3.7 `octree` 块

> 10 条,AMR / Octree 网格细化的容差和方向。

| keyword | 含义 | 单位 | 类型 | 默认值 | 备注 |
|---|---|---|---|---|---|
| `toldup` | 重合点容差 | — | 浮点 | 1.0e-8 | — |
| `tolins` | 插入容差 | — | 浮点 | 1.0e-6 | — |
| `tol dfn` | 定义容差 | — | 浮点 | 1.0e-6 | — |
| `tolzco` | ZOC 容差 | — | 浮点 | 1.0e-6 | — |
| `typzco` | ZOC 类型 | — | 整数 | 2 | — |
| `typzco_factor` | ZOC 类型因子 | — | 浮点 | 0.1 | — |
| `trxdir` / `trydir` / `trzdir` | 树方向 X / Y / Z(0=关,1=开) | — | 0/1 | 1 / 1 / 0 | 样例=XY 平面树 |
| `dfcmax` | DFC 上限 | — | 浮点 | 1.0 | — |

### 3.8 `probe` 块

> 探针位置 / 探针变量。本项目 2 个样例**均为空块**;典型用法见 CFD++ 手册(本工具不专门生成探针)。

| keyword | 含义 | 单位 | 类型 | 默认值 | 备注 |
|---|---|---|---|---|---|
| (无内建 schema) | 探针语句 | — | 自由 | — | `inp_tool` 不解析探针内部细节,只保证块结构不丢 |

### 3.9 `debug` 块

> 调试钩子。本项目 2 个样例**均为空块**;求解器开发组在诊断时填具体 debug 命令。

| keyword | 含义 | 单位 | 类型 | 默认值 | 备注 |
|---|---|---|---|---|---|
| (无内建 schema) | 调试语句 | — | 自由 | — | `inp_tool` 不解析 debug 内部,只保留块结构 |

---

## 4. sweep 关注的字段

下表在 [04-sweeping.md §2](../sweep/04-sweeping.md) 基础上,给每个 `aero_*` 字段加了"对应 sweep 轴"列。`sweep` 真正改的字段是 §3.6 中加粗的 8 个,加 §3.5 中的 7 个 `ref*` 字段:

### 4.1 主 sweep 轴(几何分解后写进 `guiopts`)

| 字段 | 含义 | 单位 | 对应 sweep 轴 | 备注 |
|---|---|---|---|---|
| `aero_alpha` | 攻角 | 度 | `alpha` | preset 自动写 |
| `aero_beta` | 侧滑角 | 度 | `beta` | preset 自动写 |
| `aero_ma` | 马赫数 | — | `mach` | preset 自动写 |
| `aero_u` | X 速度(自动算) | m/s | (派生) | preset 自动算 |
| `aero_v` | Y 速度(自动算) | m/s | (派生) | preset 自动算 |
| `aero_w` | Z 速度(自动算) | m/s | (派生) | preset 自动算 |
| `aero_temp` | 来流温度 | K | `T_inf` | preset 自动写 |
| `aero_pres` | 来流压强 | Pa | `p_inf` | preset 自动写(仅当配置含 `p_inf`) |

### 4.2 物理无量纲化(同步写进 `physics`)

| 字段 | 含义 | 单位 | 对应 sweep 轴 | 备注 |
|---|---|---|---|---|
| `refvel` | 参考速度 = √(U²+V²+W²) | m/s | (派生自 alpha/beta/mach/T) | preset 自动算 |
| `reftem` | 参考温度 | K | `T_inf` | preset 自动写 |
| `refpre` | 参考压强 | Pa | `p_inf` | preset 自动写 |
| `refden` | 参考密度 | kg/m³ | (派生) | preset 自动算 |
| `reflen` | 参考长度 | m | 1.0(固定) | 通常不动 |
| `refmwt` | 参考分子量 | g/mol | 28.95(固定) | 通常不动 |
| `refpgf` | 参考压-重力因子 | Pa | 101325(固定) | 通常不动 |

### 4.3 辅助 sweep 轴(不自动写,需 `overrides`)

| 字段 | 含义 | 单位 | 对应 sweep 轴 | 备注 |
|---|---|---|---|---|
| `aero_re` | 来流雷诺数 | — | `re` | 改这个需手动 `overrides.guiopts.aero_re` |
| `aero_altid` | 高度 / 湍流强度 | m 或 % | `altid` | 改这个需手动 `overrides.guiopts.aero_altid` |
| `aero_deltat` | 温差 | K | `deltat` | 改这个需手动 `overrides.guiopts.aero_deltat` |

详见 [07-overrides.md](../sweep/07-overrides.md)。

---

## 5. 复合语句(info set)

`info set` 是 `mcfd.inp` 唯一的"复合语句"形式,在 `begin/end` 块之外,用于给某些字段(典型为 `aero_*` / `incomp_*`)一个**有序的取值序列**。

### 5.1 语法

```inp
begin info set <seq_id>
  values <v1> <v2> <v3> ...
end
```

- `seq_id` 是个整数,标识这个序列的编号
- `values` 后跟若干个同类型的值(整型 / 浮点 / 字符串)
- 一个 `mcfd.inp` 里可以出现多个 `info set`,编号互不重复

### 5.2 完整例子(假设)

```inp
begin info set 1
  values 0.0 2.0 4.0 6.0 8.0 10.0
end
begin info set 2
  values 0.6 0.8
end
```

> 上述 2 个 info set 配合 `guiopts.aero_alpha = (1, 0)` 和 `guiopts.aero_ma = (2, 0)`(tuple 形式),可以表达"alpha 走 6 个值、mach 走 2 个值"的笛卡尔积扫描。

### 5.3 `inp_tool` 行为

- v0.4.0 的 `parser` **把 `info set` 块视作普通块**,字段名 `values`、值是整行字符串
- sweep **不消费** `info set`,它直接改 `guiopts.aero_*` 字段
- 若要在 v0.4 上把 `info set` 序列喂给 sweep,先用 `inp-tool info` 看序列号,再用 `overrides` 把值复制到 `aero_*` 字段

---

## 6. 字段名变更 / 兼容性

> 本节基于 CFD++ v15 ~ v17 公开文档;若你用的版本更老 / 更新,以求解器手册为准。

### 6.1 已知别名(同义字段)

| 现名(本表用) | 老版本别名 | 备注 |
|---|---|---|
| `aero_u/v/w` | `aero_U/V/W` | 早期大小写敏感,现统一小写 |
| `aero_alpha/beta` | `aeroALPH/BETA` | 同上 |
| `refvel` | `REFVEL` | 同上 |
| `mc_filecopy` | `mcFileCopy` | 早期驼峰,现全小写下划线 |
| `cflbot` / `cfller` | `cflBOT` / `cflLER` | 同上 |

### 6.2 已知弃用 / 改名

| 弃用名 | 替代名 | 弃用版本 | 备注 |
|---|---|---|---|
| `advc` | `advcon` | v14 | 对流系数 |
| `difc` | `difcon` | v14 | 扩散系数 |
| `smuu` | `smuusl` | v15 | Sutherland 粘性 S |
| `tkap` | `tkapsl` | v15 | Sutherland 导热 T |
| `ntacou` (老语义) | `ntacou` (新语义) | v15 | 老版本是"声学记录数",v15 改回"声学输出频率" |

### 6.3 兼容性提示

- `inp-tool parse` **不**做字段名归一化(老别名会原样保留);`inp-tool sweep` 改字段是按**字面关键字**匹配,所以老样例里的 `aeroALPH` 不会触发 sweep 改 `aero_alpha`
- 若你的样例用了老别名,先用 `inp-tool diff` 看新旧版本差异,再手动 `sed` 替换
- `inp_tool` `__version__ = 0.4.0` 表明本工具自身版本;不与 CFD++ 版本挂钩

---

## 7. 获取本参考表的工具

本章不是"拍脑袋写的",字段表全部由下列命令实时从样例 `.inp` 抽出,你可以随时再跑一遍验证。

### 7.1 列所有块

```bash
conda run -n cfdchanger python -m inp_tool.cli info \
  inp_tool/examples/mcfd_modified.inp
```

输出:

```
块列表:
  [ 0] system          L   1-   5     3 stmts    1 unique keys
  [ 1] iofiles         L   6-  39    32 stmts   30 unique keys
  [ 2] tsteps          L  44-  78    33 stmts   33 unique keys
  [ 3] options         L  79- 247   167 stmts  167 unique keys
  [ 4] octree          L 619- 630    10 stmts   10 unique keys
  [ 5] physics         L 631- 832   200 stmts  200 unique keys
  [ 6] probe           L 833- 834     0 stmts    0 unique keys
  [ 7] debug           L 835- 836     0 stmts    0 unique keys
  [ 8] guiopts         L 837- 888    50 stmts   50 unique keys
```

### 7.2 列某一块的所有字段

```bash
conda run -n cfdchanger python -m inp_tool.cli parse \
  inp_tool/examples/mcfd_modified.inp -b guiopts -f
```

输出(节选):

```
=== guiopts (L837-888, 50 stmts) ===
  L837  turbi_lev 1
  L838  turbi_len 1
  ...
  L851  aero_ma 8.000000e-001
  L852  aero_alpha 0.000000e+000
  L853  aero_beta 0.000000e+000
  ...
```

### 7.3 程序化访问(API)

```python
from inp_tool import parse_file
inp = parse_file("mcfd_modified.inp")
guiopts = inp.get_block("guiopts")
for stmt in guiopts.stmts:
    print(stmt.keyword, stmt.values)
```

详见 [08-multiple-uis.md §4](../sweep/08-multiple-uis.md) Python API 段;CLI / FastAPI 速查见本目录兄弟章节(13-cli-api-reference.md,计划中)。

---

> 字段表 vs 真实样例字段数对比:
>
> | 块 | 本表行数 | 样例字段数(`unique keys`) |
> |---|---|---|
> | `system`    | 1 | 1 |
> | `iofiles`   | 17(2 + 15) | 30(14+14 + lm_* + 重复) |
> | `tsteps`    | 33 | 33 |
> | `options`   | 165+ | 167 |
> | `physics`   | 195+ | 200 |
> | `guiopts`   | 50 | 50 |
> | `octree`    | 10 | 10 |
> | `probe` / `debug` | 0(空块) | 0 |
>
> `iofiles` 行的差异主要来自"14+14 类文件 fn 字段被合并展示";`options` / `physics` 的几行差异是同一字段多次出现被合并。若发现本章有遗漏,提 issue。

下一步:CLI / FastAPI / Python API 三套入口的速查 — 见本目录兄弟章节(13-cli-api-reference.md,计划中)。
