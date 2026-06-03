# CFD++ Tcl/Tk GUI 深度工程手册

> **版本**: 1.0
> **日期**: 2026-05-28
> **源码目录**: `D:\software\CFD++\METACOMP\mlib\mcfd.18.5\exec\gui_src\`
> **产出**: `E:\ProgrammingData\python\cfd++changer\CFD_GUI_Engineering_Handbook.md`

---

## 目录

- [第一部分：架构总览](#第一部分架构总览)
  - [1.1 入口文件与模块分类](#11-入口文件与模块分类)
  - [1.2 全局变量体系](#12-全局变量体系)
  - [1.3 exe 调用统一入口](#13-exe-调用统一入口)
- [第二部分：模块详解](#第二部分模块详解)
  - [A. 执行与调度](#a-执行与调度)
  - [B. 主GUI配置](#b-主gui配置)
  - [C. 网格与工具](#c-网格与工具)
  - [D. 物理模型](#d-物理模型)
  - [E. 可视化](#e-可视化)
- [第三部分：全局变量索引](#第三部分全局变量索引)
- [第四部分：exe 调用完整索引](#第四部分exe-调用完整索引)

---

# 第一部分：架构总览

## 1.1 入口文件与模块分类

### 1.1.1 核心入口文件

CFD++ GUI 的入口文件是 `gui_src/` 目录下的主控 Tcl 文件，通过 `source` 链加载所有模块。

| 文件 | 行数 | 职责 |
|------|------|------|
| `run_mcfd.tcl` | ~3665 | **核心调度引擎**：单CPU/MPI运行、后处理工具调用 |
| `run_cmd.tcl` | 516 | **命令执行包装器**：GUI输出窗口、进程管理 |
| `infotool.tcl` | 827 | **信息工具对话框**：cellvols/cellnors等工具 |
| `lmtool.tcl` | 224 | **License Manager工具** |
| `forcemom.tcl` | ~1310 | **力/力矩处理器**：后处理统计 |
| `gui_hinit.tcl` | 205 | **帮助系统** |
| `mc_bind.tcl` | 537 | **全局工具库**：对话框/验证函数 |

### 1.1.2 模块分类总览

| 类别 | 文件 | 核心功能 |
|------|------|----------|
| **执行调度** | run_mcfd.tcl, run_cmd.tcl | 求解器启动/工具调度 |
| **主GUI配置** | infoset.tcl, viewinf.tcl, timeint.tcl, topology.tcl, saving.tcl, init_dom.tcl, load_proc.tcl | 信息集管理/时间积分/Overset/保存加载 |
| **网格工具** | gridtools.tcl, gridvel.tcl, probe.tcl, totec.tcl, soltools.tcl, gridblnk.tcl, gridcheck.tcl | 网格处理/运动/探测/Tecplot转换/重插值 |
| **物理模型** | species.tcl, reaction.tcl, turbname.tcl, bcstuff.tcl, bcsort.tcl, gasprop.tcl, disperse.tcl, volsour.tcl, refer.tcl, riemann.tcl, spacdis.tcl | 物种/反应/湍流/边界条件/求解器参数 |
| **可视化** | surface.tcl, cutplane.tcl, isosurf.tcl, partplane.tcl, directb.tcl, lighting.tcl, output.tcl, univtool.tcl, commands.tcl, unit_convert.tcl, inoutfil.tcl, cosim.tcl | 实体管理/切割平面/光照/文件I/O |

### 1.1.3 模块间调用关系总图

```
┌─────────────────────────────────────────────────────────────────┐
│                      GUI 主控 (run_mcfd.tcl)                      │
│  用户 → which_mcfdrun → run_mcfd (单CPU前台) / run_mcfd_back (后台) │
│                      run_multicpu (MPI多CPU)                       │
│                      run_mcfdplt / run_mcfdfft 等后处理工具          │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   run_cmd.tcl   │  │   infoset.tcl   │  │  gridtools.tcl  │
│ (进程管理/GUI)   │  │ (信息集增删改)  │  │ (网格转换工具)   │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    .main.f2.tg1 (Togl/OpenGL)                     │
│  mc_bc_display / mc_cut_plane_display / mc_part_plane_display    │
└─────────────────────────────────────────────────────────────────┘
```

## 1.2 全局变量体系

### 1.2.1 核心标量全局变量

| 变量 | 类型 | 用途 |
|------|------|------|
| `directory_global` | string | 当前工作目录 |
| `infsets` | int | 信息集总数 |
| `mbcons` | int | 边界条件数量 |
| `mcfd_prec` | int | 0=单精度, 1=双精度 |
| `mcpu_machine` | string | MPI机器类型 |
| `loc_proc` | int | 本机CPU数 |
| `use_other` | int | 是否使用其他机器 |
| `method` | int | 1=Explicit, 2=Implicit, 4=IMEX |
| `sim_strat` | int | 0=Transient, 1=Steady-State, 2=Kinematics |
| `osetyp` | int | Overset类型 |
| `osetbr/osetbz/osetll/osetlc` | int | 各Overset配置 |
| `which_grsp` | int | 网格运动类型 |

### 1.2.2 核心数组全局变量

| 数组 | 结构 | 用途 |
|------|------|------|
| `infset(N, title/vals/used/v1...vN)` | 2D数组 | 信息集数据（最核心的数据结构） |
| `mbcon(N, fam/bcname/type/...)` | 2D数组 | 边界条件数据 |
| `other_cpu(i, name/number)` | 2D数组 | 多机配置 |
| `g_cmdtool(N, cmd/args/desc)` | 2D数组 | Grid工具配置 |
| `s_cmdtool(N, cmd/args/desc)` | 2D数组 | Solution工具配置 |
| `force_mom(N, type/xcen/ycen/...)` | 2D数组 | 力/力矩配置 |
| `gui_units(key)` | 1D数组 | GUI单位映射 |

### 1.2.3 信息集数组（infset）详解

信息集是 CFD++ GUI 最核心的数据结构：

```
infset(N, title)     # 信息集类型名称
infset(N, vals)      # 参数个数
infset(N, used)      # 被引用次数
infset(N, v1)        # 第1个参数值
infset(N, v2)        # 第2个参数值
...
infset(N, v${vals})  # 第vals个参数值
```

**主要信息集类型对照表**：

| title | 用途 | 创建proc |
|-------|------|----------|
| `primitive_variables_1` | 原始变量 P,T,u,v,w | `inf_prim` |
| `primitive_variables_2` | 温度基原始变量 | `inf_incomp` |
| `primitive_variables_disturb` | 带扰动原始变量 | `inf_disturb` |
| `pressure_valve` | 压力阀门 | `inf_valp` |
| `timed_valve_gaussian` | 高斯时间阀门 | `inf_valv` |
| `timed_valve_tanh_ptot_ttot_etc` | tanh型阀门 | `inf_valv_pde 276` |
| `timed_valve_risefall_ptot_ttot_etc` | rise-fall型阀门 | `inf_valv_pde 277` |
| `initialize_by_cells` | Cell范围初始化 | `init_infset` |
| `initialize_by_boxes` | XYZ Box初始化 | `init_infset2` |
| `initialize_by_groups` | Cell Group初始化 | `init_infset3` |
| `flointerface1_specification` | 耦合仿真BC接口 | `cos_fluid` |
| `dyninterface1_specification` | 耦合仿真刚体动力学 | `cos_dynam` |

## 1.3 exe 调用统一入口

### 1.3.1 求解器 exe 调用

| 场景 | exe | 参数构造 |
|------|-----|----------|
| 单CPU前台（单精度） | `mcfd` | `mcfd \| mc_stdoutee mcfd.log` |
| 单CPU前台（双精度） | `r4_mcfd` | `r4_mcfd \| mc_stdoutee mcfd.log` |
| 单CPU后台 | `mcfd_background` / `mcfd_background4` | `mcfd_background &` |
| 多CPU Linux mpich | `r4_mpimcfd` | `-p4pg r4_mpimcfd.pg \| mc_stdoutee mcfd.log` |
| 多CPU MPICH2 | `mpiexec` | `-n $totproc -machinefile machine.txt r4_mpimcfd` |
| 多CPU MSMPI | `mpiexec` | `-n $totproc r4_msmpimcfd` |
| 多CPU SGI | `mpirun` | `-np $loc_proc r4_mpimcfd` |
| 多CPU IBM POE | `r4_mpimcfd` | `-procs $tot_cpu \| mc_stdoutee mcfd.log` |

### 1.3.2 后处理工具 exe 调用

| 工具 | exe | 用途 |
|------|-----|------|
| Post-processing | `mcfdplt` / `mcfdtplt` | 结果可视化 |
| FFT分析 | `mcfdfft` | 频域分析 |
| 切片查看 | `mcfdpplt` / `mcfdfplt` | 平面数据查看 |
| 溶液查看 | `mcfdsol` / `mcfdsolx` | 交互式溶液查看 |

---

# 第二部分：模块详解

## A. 执行与调度

### A.1 run_mcfd.tcl — 核心调度引擎

#### A.1.1 文件功能概述

`run_mcfd.tcl` 是 CFD++ GUI 的**核心执行与任务调度引擎**，负责：
1. 单CPU求解器启动（mcfd/r4_mcfd）
2. 多CPU（MPI）并行求解器启动
3. 各类后处理工具的调度（plt/fft/fplt等）
4. 多机器多处理器环境配置

#### A.1.2 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `get_win32_path` | `r4r8` | Windows短路径转换（MPICH2兼容） |
| `which_mcfdrun` | `callwind` | 弹出精度选择对话框 |
| `mcfd_stop` | — | 停止CFD++求解器 |
| `run_mcfd` | — | 单CPU前台运行 |
| `run_mcfd_back` | — | 单CPU后台运行 |
| `run_mcfdplt` | — | 运行mcfdplt后处理 |
| `run_mcfdplt_ps` | — | 运行mcfdplt（restart模式） |
| `run_mcfdtplt` | — | 运行mcfdtplt |
| `run_mcfdfft` | — | 运行mcfdfft |
| `run_mcfdpplt` | — | 运行mcfdpplt |
| `run_mcfdfplt` | — | 运行mcfdfplt |
| `view_log2` / `view_log` | — | 查看日志 |
| `kill_mcfd` | — | 杀死进程 |
| `run_dfcells` | — | 运行dfcells（域分解） |
| `run_multicpu` | — | 多CPU命令中心主UI |
| `run_command_mcpu` | — | 构建并执行MPI命令 |
| `run_multicpu_tool` | `tooln toolargs callwind` | 多CPU模式专用工具 |
| `which_cfluse` | `callwind` | CFL文件读取对话框 |
| `read_file_mcpu` | — | 从.pg文件恢复配置 |

#### A.1.3 关键 proc 详解

**`run_mcfd`**
- 功能：单CPU模式下前台运行CFD++求解器
- 命令构建：
  ```tcl
  if { $mcfd_prec == 1 } {
      set command "mcfd | mc_stdoutee mcfd.log"
  } else {
      set command "r4_mcfd | mc_stdoutee mcfd.log"
  }
  run_cmd $command 1
  ```

**`run_multicpu`**
- 功能：多CPU命令中心主UI构建
- 关键全局变量：
  - `loc_proc`：本机CPU数
  - `use_other`：是否使用其他机器
  - `other_cpu(num/name/number)`：其他机器配置
  - `mcpu_machine`：机器类型（Linux mpich/MPICH2/MSMPI/SGI/IBM POE等）
  - `root_mpich2`：是否从mpiexec启动根进程

**`run_command_mcpu`**
- 根据机器类型构建MPI命令：
  | 机器类型 | 命令 |
  |----------|------|
  | Linux mpich/DEC | `r4_mpimcfd -p4pg r4_mpimcfd.pg` |
  | MPICH2 on WINDOWS | `mpiexec -n $totproc -machinefile machine.txt r4_mpimcfd` |
  | MSMPI | `mpiexec -n $totproc r4_msmpimcfd` |
  | SGI | `mpirun -np $loc_proc r4_mpimcfd` |
  | IBM POE | `r4_mpimcfd -procs $tot_cpu` |

#### A.1.4 全局变量依赖

| 变量 | 读写 | 用途 |
|------|------|------|
| `directory_global` | R/W | 工作目录 |
| `mcfd_prec` | R/W | 精度 |
| `mcfd_cflloc` | R/W | CFL文件读取 |
| `loc_proc` | R/W | 本机CPU数 |
| `use_other` | R/W | 多机标志 |
| `other_cpu` | R/W | 其他机器配置 |
| `mcpu_machine` | R/W | 机器类型 |
| `root_mpich2` | R/W | MPICH2根进程 |
| `mpiqueue_mode` | R/W | MPI队列模式 |

#### A.1.5 exe 调用模式

| 场景 | exe | 调用方式 |
|------|-----|----------|
| 单CPU前台 | `mcfd`/`r4_mcfd` | `run_cmd` (blt::bgexec) |
| 单CPU后台 | `mcfd_background` | `eval exec` |
| 多CPU | 根据类型 | `run_cmd` 或 `eval exec` |

---

### A.2 run_cmd.tcl — 命令执行包装器

#### A.2.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `get_directory_global` | — | 返回全局目录 |
| `run_cmd` | `clt_cmd detach` | 执行命令并显示GUI界面 |
| `get_proc_mem` | `pid` | 读取Linux进程内存 |
| `watch_proc_mem` | `job_name pid` | 周期性内存监控 |

#### A.2.2 `run_cmd` 详解

- **参数**：
  - `clt_cmd`：完整命令行
  - `detach`：0=同步等待，1=detach模式
- **核心逻辑**：
  ```tcl
  set command "blt::bgexec run_status_$job_name \
    -onoutput update_display_$job_name \
    -onerror update_display_$job_name $clt_cmd &"
  catch { set pid [eval $command] }
  tkwait variable run_status_$job_name
  ```
- **返回值**：0=成功，1=失败
- **内存监控（Linux）**：每10秒读取`/proc/$pid/status`

---

### A.3 infotool.tcl — 信息工具对话框

#### A.3.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `cmd_tools` | — | 主信息工具对话框（HierBox列表） |
| `cellvols_w` | — | cellvols工具包装器 |
| `cellnors_w` | — | cellnors工具包装器 |
| `cdepsinf_sp_w` | — | cdegetc1工具包装器 |
| `it_cellvols` | — | cellvols配置UI |
| `it_cellnors` | — | cellnors配置UI |
| `it_cdepsinf_sp` | — | cdegetc1配置UI |

#### A.3.2 exe 调用

| 工具 | exe | 参数 |
|------|-----|------|
| cellvols（双精度） | `cellvols` | `$cellsin_fn $nodesin_fn $chkvol $tolvol` |
| cellvols（单精度） | `r4_cellvols` | 同上 |
| cellnors（双精度） | `cellnors` | `$cellsin_fn $nodesin_fn` |
| cellnors（单精度） | `r4_cellnors` | 同上 |

---

### A.4 forcemom.tcl — 力/力矩处理器

#### A.4.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `force_manage` | `callwind` | 力/力矩处理器主对话框 |
| `bc_frame` | `numb` | 边界/平面选择子对话框 |
| `write_infout1` | — | 写入配置到infout1f.inp |
| `read_infout1` | — | 从infout1f.inp读取配置 |
| `run_infout1` | — | 执行力/力矩处理 |
| `line_add/line_delete` | — | 添加/删除条目 |
| `copy_entities` | `num` | 复制条目配置 |

#### A.4.2 force_mom 数组结构

```
force_mom(num)                    # 条目总数
force_mom($i,type)               # 输出类型 (energy_flux/mass_flux/x_force等)
force_mom($i,dim)                # 有量纲/无量纲
force_mom($i,xcen/ycen/zcen)     # 力矩中心
force_mom($i,pref/rref/uref)     # 参考量
force_mom($i,arfx/arfy/arfz)     # 参考面积
force_mom($i,lxref/lyref/lzref)  # 参考长度
force_mom($i,alfa)               # 攻角
force_mom($i,xyxz)               # 平面 (xy/xz)
```

#### A.4.3 exe 调用

- **工具**：`infout1f`
- **输入**：`mcfd.info1`
- **输出**：`minfo1_e#.log`, `minfo1_e#_vis`, `minfo1_e#_inv`

---

### A.5 mc_bind.tcl — 全局工具库

#### A.5.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `platform_is_windows` | — | Windows平台检测 |
| `dialog_wait` | `wind` | 模态对话框等待 |
| `tk_dialog2` | `w title text bitmap default args` | 自定义对话框 |
| `output_1/output_1a` | `tit tx tt callwind` | 临时提示信息 |
| `exit3/exit2` | — | 退出程序 |
| `isnumb` | `numb` | 数字验证 |
| `verify_real/verify_int` | `val` | 类型验证 |
| `check_v_state` | `infnum ind callwind` | 速度过低检查 |

---

## B. 主GUI配置

### B.1 infoset.tcl — 信息集管理核心（22428行）

#### B.1.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `info_sets` | `callwind` | 主入口：创建信息集管理窗口 |
| `inf_prim` | `undo` | 创建"原始变量"信息集 |
| `inf_disturb` | `undo` | 创建"带扰动原始变量"信息集 |
| `inf_valp` | `undo` | 创建"压力阀门"信息集 |
| `inf_valv` | `undo` | 创建"高斯时间阀门"信息集 |
| `inf_valv_pde` | `undo pdeintyp` | 创建PDE型阀门 |
| `inf_cgrain` | `undo` | 创建"复杂grain燃烧"信息集 |
| `inf_four_sp` | `undo` | 创建质量流量公式型信息集 |
| `inf_zongrp` | `undo` | 创建"Zonal BC to Cell groups"信息集 |

> 注：infoset.tcl 中绝大多数 `inf_xxx` 过程嵌套定义在 `info_sets` 内部

#### B.1.2 数据流

```
info_sets (主窗口)
  ├─ infstat==0 (Add模式) → info2窗口 → inf_list → create_box_inf → inf_xxx
  ├─ infstat==1 (Delete模式) → recon_info → renum_* → altbc_expunge
  └─ infstat==2 (Edit模式) → info2_inf窗口 → general_infoset_edit → viewinf.tcl
```

---

### B.2 viewinf.tcl — 信息集查看（15445行）

#### B.2.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `general_infoset_edit` | `typ bcnum_or_title infn callwind` | 主入口：分发到各view_xxx |
| `getinfo` | `inft infn` | 获取格式化显示字符串 |
| `view_inf` | `number reset callwind` | 查看primitive_variables_1 |
| `view_one/two/three/four` | — | 单/双/三/四参数查看 |
| `view_file` | `number reset typ callwind` | 文件型数据查看 |
| `view_boup/view_boup_new` | — | 边界探测查看 |
| `edit_seq` | `i` | 序列排名编辑 |

#### B.2.2 与 infoset.tcl 的关系

- `infoset.tcl` 负责**编辑**（增删改）
- `viewinf.tcl` 负责**只读查看**
- Edit模式下双击信息集时调用 `general_infoset_edit`

---

### B.3 timeint.tcl — 时间积分控制（6121行）

#### B.3.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `time_int` | `callwind` | 主入口：时间积分主面板 |
| `time_int2` | — | Explicit格式面板 |
| `time_int3` | — | Implicit格式面板（无PC） |
| `time_int4` | — | Implicit格式面板（有PC） |
| `time_int5` | — | IMEX格式面板 |
| `sims_t` | — | 根据sim_strat动态调整布局 |
| `multigrid_t` | `callwind` | 多重网格设置 |
| `read_cflloc` | `callwind` | 读取局部CFL |

#### B.3.2 关键参数

| 参数 | 值 | 含义 |
|------|-----|------|
| `method` | 1/2/4 | Explicit/Implicit/IMEX |
| `sim_strat` | 0/1/2 | Transient/Steady-State/Kinematics |
| `dultim` | 0/1/2 | 双时间步进关闭/开启/快速工具 |

---

### B.4 topology.tcl — Overset网格控制（6466行）

#### B.4.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `overset_type` | — | 主入口：Overset控制面板 |
| `celltype` | `callwind` | Cell Type选择 |
| `bcoffset` | — | BC Offset设置 |
| `group_cell` | `callwind` | Cell Group编辑 |
| `zonal_pairs` | `callwind` | Zonal Pairs设置 |
| `altbc_clnup` | — | 清理alt BC主入口 |
| `renum_seqcutinf` | `altbc_unused nrnks ncuts` | 重编号sequential cutting |

#### B.4.2 关键全局变量

- `osetyp`：Overset类型
- `osetbr/osetbz/osetll/osetlc`：各子类型配置
- `ordrnk/ordcut`：排名/切割信息集编号

---

### B.5 saving.tcl — 配置保存（5249行）

#### B.5.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `save_as` | — | 另存为入口 |
| `save` | `callwind` | 主保存入口 |
| `save_do` | — | 执行实际写出 |
| `what_to_save` | — | 选择保存内容 |
| `save_browse` | — | 文件浏览保存 |

#### B.5.2 save_do 详解

- **输入**：约500+个全局变量
- **输出**：`mcfd.inp`文件
- 与 `load_proc.tcl` 形成完美的逆向关系

---

### B.6 init_dom.tcl — 域初始化（10800行）

#### B.6.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `init_domain` | `callwind` | 主入口：初始化类型选择 |
| `cellr_t` | — | Cell Ranges方式 |
| `groupr_t` | — | Cell Groups方式 |
| `xyzbr_t` | — | XYZ Boxes方式 |
| `cylin_t` | `cyltyp` | 圆柱体方式 |
| `init_con/init_coni` | — | 整域初始化 |
| `init_infset` | `callwind` | 创建initialize_by_cells信息集 |

#### B.6.2 初始化类型映射

| inityp值 | 含义 | 信息集title |
|----------|------|-------------|
| 0 | 整域 | `primitive_variables_1/2` |
| 1 | Cell Ranges | `initialize_by_cells` |
| 2 | XYZ Boxes | `initialize_by_boxes` |
| 3 | Cell Groups | `initialize_by_groups` |
| 4/5/6 | X/Y/Z Cylinder | `initialize_by_x/y/zcyls` |
| 9 | Cell Groups(SBR) | `initialize_by_solbodrot1` |

---

### B.7 load_proc.tcl — 配置加载（5836行）

#### B.7.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `load_proc` | — | 主入口：加载并填充GUI |
| `bcmapper` | `title numb` | BC名称映射 |
| `bcfam_set` | `bct num` | BC Family设置 |
| `set_rieflx_info` | `num` | Riemann边界信息 |
| `set_riejac_info` | `num rief` | Riemann Jacobian信息 |

#### B.7.2 数据流

```
mcfd.inp文件
    ↓
load_proc（解析各信息集类型）
    ↓
infset(N,title/vals/used/v1...vN)填充
    ↓
其他全局变量（species/reactions/eqset等）
```

---

## C. 网格与工具

### C.1 gridtools.tcl — 网格转换工具（~15000行）

#### C.1.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `toaxigr` | — | 2D to Pie-Grid转换 |
| `run_toaxigr` | — | 执行toaxigr转换 |
| `toxax_pie_360` | `chc` | 多平面360度pie-grid |
| `run_toxax_pie_360` | `tlnm` | 执行多平面转换 |
| `tohelixgr` | — | 螺旋extrusion |
| `run_tohelixgr` | — | 执行螺旋extrusion |
| `celretyp` | — | 移除collapse axis |

#### C.1.2 exe 调用

| exe | 用途 |
|-----|------|
| `toxaxigr` / `toyaxigr` | 2D to Pie-Grid |
| `toxaxpie` / `toxax360` | 多平面pie-grid |
| `tohelixgr` | 螺旋extrusion |
| `celretyp` | 单元类型重定义 |

---

### C.2 gridvel.tcl — 网格运动控制（~10000行）

#### C.2.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `grid_speeds` | — | 网格运动主对话框 |
| `gvel_region_1` | `set_num` | Type 1网格速度区域 |
| `gvel_region_7` | `set_num` | Type 7网格速度区域 |
| `grid_speeds_9` | — | 平移/旋转振荡（解析） |
| `grid_speeds_13/14` | — | 任意轴平移/旋转 |
| `grid_speeds_27/29` | — | 基于文件的网格变形 |
| `grid_speeds_30` | — | 带振荡的平移/旋转 |
| `grid_speeds_31` | — | 柔性盘 |
| `sixdof_bodies` | `parent` | Six-DOF体规范 |

#### C.2.2 网格运动类型

| which_grsp | 类型 |
|------------|------|
| 0 | 无 |
| 1 | 平移/旋转速度（数值积分） |
| 7 | 平移/旋转速度（解析） |
| 9 | 平移/旋转振荡（解析） |
| 13 | 任意轴平移/旋转（解析） |
| 14 | 任意轴振荡 |
| 10 | 基于文件的通用平移 |
| 27 | 基于文件的网格变形 |
| 29 | 组合网格变形 |
| 30 | 带振荡的平移或旋转 |
| 31 | 柔性盘 |

---

### C.3 probe.tcl — 探测与残差输出（~8000行）

#### C.3.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `probe_res` | `callwind` | 主对话框 |
| `prob_stat` | `typ` | 详细信息对话框 |
| `ntdsko_t/ntdsks_t` | — | 溶液重启文件控制 |
| `ntplto_t/ntplts_t/ntpltt_t` | — | NPF输出控制 |
| `ntout1_t` ~ `ntout39_t` | — | 各输出类型开关 |
| `ntsave_t` | — | 时间/步平均控制 |

#### C.3.2 主要输出类型

| ntout | 描述 | 输出文件 |
|-------|------|----------|
| ntout1 | 边界通量/力/力矩 | mcfd.info1 |
| ntout2-3 | 边界压力/热传导 | mcfd.info2/3.bcs# |
| ntout4/6 | 内部压力 | mcfd.info4.cel# / mcfd.info6.nod# |
| ntout9 | 内部原始变量 | mcfd.info9.cel# |
| ntout17 | 内部原始变量（步数追加） | mcfd.info17.cel# |
| ntout21 | 内部原始变量(xyz) | mcfd.info21.xyz# |
| ntout35 | 域内最小/最大/平均 | mcfd.info35_* |

---

### C.4 totec.tcl — Tecplot转换（~8400行）

#### C.4.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `totec` | — | Tecplot转换主对话框 |
| `run_quat` | — | 执行转换 |
| `hit_tec` | — | 问题维度变更处理 |
| `plot_primderiv` | — | 主变量/导数绘图 |
| `plot_turb` | — | 湍流变量绘图 |
| `plot_surface` | — | 表面变量绘图 |
| `plot_molemass` | — | 物种/体积分数绘图 |
| `load_pltopts` | `filename` | 从文件加载选项 |

#### C.4.2 exe 调用

| 问题维度 | 单元类型 | exe |
|----------|----------|-----|
| 3D | 六面体 | `hextec` / `r4_hextec` |
| 3D | 四面体/三棱柱 | `tettec` / `r4_tettec` |
| 2D | 四边形 | `quatec` |
| 2D | 三角形 | `tritec` |
| 1D | 线 | `lintec` |

---

### C.5 soltools.tcl — 溶液重插值（~7100行）

#### C.5.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `reintsol` | — | 重插值主对话框 |
| `run_reint` | — | 执行重插值 |
| `reintsol_which_hit` | — | 插值方法选择处理 |
| `reint_extra_vals` | — | 用户指定值对话框 |
| `cdepsmod` | — | 溶液文件修改 |
| `cdepsmog` | — | 按组修改 |
| `dataint` | — | 溶液传输到笛卡尔网格 |

#### C.5.2 重插值方法

| reintsol_which | 方法 | exe |
|----------------|------|-----|
| 1 | Marching（高内存） | `reintsom` / `r4_reintsom` |
| 2 | 最近邻（低内存） | `reintson` / `r4_reintson` |
| 3 | 用户指定值 | `reintsod` / `r4_reintsod` |
| 4 | 报告并停止 | `reintsol` / `r4_reintsol` |

---

### C.6 gridblnk.tcl — 网格去空白

#### C.6.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `grid_blanking` | — | 主对话框 |
| `gblnk_region` | `set_num` | 区域定义 |
| `gblnk_zone` | — | 区域导航 |

#### C.6.2 区域类型

| unblnk_typ | 类型 |
|------------|------|
| 1 | XYZ Boxes |
| 2 | X-Cylinders |
| 3 | Y-Cylinders |
| 4 | Z-Cylinders |

---

### C.7 gridcheck.tcl — 网格质量检查

#### C.7.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `grdqual1_discon` | — | 外推检查和控制 |
| `grdqual2_angcon` | — | 共线性检查 |
| `grdqual3_discon` | — | 负体积检查 |
| `grdqual6_discon` | — | 边界转角控制 |
| `ifnwds_discon` | — | 法向距离计算 |
| `scal_val` | `value` | 比例值回调 |

---

## D. 物理模型

### D.1 species.tcl — 真实气体性质

#### D.1.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `gas_prop2` | — | 真实气体性质GUI |
| `prop_ifkndf` | — | Knudsen数相关 |
| `gas_prop4` | — | 第4类气体性质 |
| `gas_prop3` | — | 第3类气体性质 |

---

### D.2 reaction.tcl — 反应机理

#### D.2.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `read_reactions` | — | 读取反应文件 |
| `write_reactions` | — | 写入反应文件 |
| `read2_reactions` | — | 读取第2组反应 |
| `write2_reactions` | — | 写入第2组反应 |
| `reaction` | — | 反应主GUI |

#### D.2.2 数据结构

```
work_reaction(nr)    # 反应数量
work_reaction(np)    # 产物数量
work_reaction(rc,i)  # 反应i的速率系数
work_reaction(r,i)   # 反应i的指数
```

---

### D.3 turbname.tcl — 湍流模型

#### D.3.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `geturbmod2` | — | 获取湍流模型名称 |
| `geturbmod` | — | 获取湍流模型 |
| `get_turb_type` | — | 获取湍流类型 |
| `turb_mod` | — | 湍流模型GUI |

#### D.3.2 湍流模型类型

| 类型 | 模型 |
|------|------|
| 1-eq | Goldberg, LES, SA, DES97, DDES, IDDES |
| 2-eq | q-L, Realizable k-eps, SST, quad/cubic k-eps, Batten-Goldberg, k-L, R-gam, Hellsten |
| 3-eq | k-eps-Rt, k-eps-fmu |
| 特殊 | Langtry-Menter, 7-equation 2nd-moment closure |

---

### D.4 bcstuff.tcl — 边界条件核心（~2100行）

#### D.4.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `show_ordvarlist` | — | 显示profile文件变量顺序 |
| `bclbresize` | `bclisthandle` | 调整列表框高度 |
| `sp_add` | `pnlstr slen` | 字符串填充 |
| `bcmapp2` | `numb` | BC显示名称映射 |
| `getbcinfo` | `title number` | 获取BC描述 |
| `bctitle` | `title dumm1` | BC标题编号→名称 |
| `change_bc` | `bct numbc callwind` | BC修改主过程 |

#### D.4.2 BC标题编号映射（部分）

| 编号 | BC名称 |
|-----|--------|
| 0 | No boundary condition |
| 1 | All conditions prescribed (P,r,u,...) |
| 2 | Inviscid surface tangency |
| 6 | Symmetry |
| 7 | Adiabatic viscous wall |
| 13 | Isothermal wall |
| 55-59 | Wall functions |
| 61-63 | Axis symmetry (X/Y/Z) |
| 129 | Grain burning inflow |
| 135-136 | Conjugate Heat Transfer |

#### D.4.3 bcmapa数组键

| 键 | 用途 |
|----|------|
| `bcmapa($numb,wall_type)` | 壁面类型 |
| `bcmapa($numb,adia_isot)` | 绝热/等温类型 |
| `bcmapa($numb,walf_solv)` | 壁面函数求解方式 |
| `bcmapa($numb,stat_move)` | 静止/运动类型 |
| `bcmapa($numb,in_out)` | 流入/流出类型 |

---

### D.5 riemann.tcl — Riemann求解器

#### D.5.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `riemann` | — | Riemann求解器主GUI |

#### D.5.2 关键参数

| 变量 | 用途 |
|------|------|
| `eqset(rieflx)` | Riemann流通量算法 |
| `eqset(ac.IT)` | AC(IT)耦合 |
| `mindis` | 最小距离 |
| `prebet` | 压力松弛beta |
| `previs/prevel` | 速度预处理 |
| `pfloor` | 压力下限 |
| `ifshck` | 激波传感器标志 |

#### D.5.3 Riemann求解器选项

| 值 | 算法 |
|----|------|
| 1 | Steger-Warming |
| 2 | Van Leer |
| 3 | AUSM |
| 4 | HLLC |
| 5 | Roe |
| 6 | Phi |

---

### D.6 spacdis.tcl — 空间离散化

#### D.6.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `space_dis` | — | 空间离散化主GUI |

#### D.6.2 关键参数

| 变量 | 用途 |
|------|------|
| `cenpol` | 中心多项式阶数 |
| `celpol` | 单元中心多项式阶数 |
| `tvdvar` | TVD变量选择 |
| `tvdphi` | TVD phi参数 |
| `iblend` | 混合标志 |

#### D.6.3 TVD限制器选项

| 值 | 限制器 |
|----|--------|
| 1 | MinMod |
| 2 | SOUCAT |
| 3 | QUICK |
| 4 | Van Leer |
| 5 | Van Albada |
| 6 | Koren |
| 9 | SuperBee |

---

### D.7 refer.tcl — 单位参考系统

#### D.7.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `get_uspec` | — | 获取单位制规格 |
| `get_gui_units` | — | 构建GUI单位映射 |

#### D.7.2 单位制

| mcfd_dnd | iun | 单位制 |
|----------|-----|--------|
| 1 | — | 非维度 |
| 0 | 0 | SI单位制 |
| 0 | 1 | British英制 |

---

### D.8 gasprop.tcl — 理想气体性质

#### D.8.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `gas_prop` | — | 理想气体性质GUI |
| `nonnewt_param` | — | 非牛顿流体参数 |

---

### D.9 disperse.tcl — 弥散相

#### D.9.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `disperse_prop` | — | 弥散相性质GUI |
| `disperse_prop_col1` | — | 第1列弥散相性质 |
| `disperse_info` | — | 弥散相信息 |

---

### D.10 volsour.tcl / volsoug.tcl — 体积源项

#### D.10.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `ps10_volsour_box` | — | Box方法体积源 |
| `ps10_volsoug_group` | — | Group方法体积源 |

---

### D.11 bcsort.tcl — BC排序辅助

#### D.11.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `clean_bc_array` | — | 清理无效BC条目 |
| `bc_name_compare` | `name1 name2` | 按名称比较BC |
| `clean_fam` | — | 清理家族名称空格 |
| `get_alpha_sorted_bclist` | — | 按字母排序 |
| `get_numeric_sorted_bclist` | — | 按数值排序 |

---

## E. 可视化

### E.1 surface.tcl — 实体管理器

#### E.1.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `surface_manage` | `callwind` | 主入口 |
| `bc_turnon` | — | 刷新BC显示 |
| `all_grid_on` | — | 所有BC网格开关 |
| `sol2d_turnon` | — | 2D解显示更新 |
| `fill_right_entity` | `entity` | 实体特定UI分发 |

#### E.1.2 实体类型分发

| entity前缀 | 右侧面板 |
|------------|----------|
| `BC` | BC controls（网格/Contour/Vector/Streamlines） |
| `2-D` | 2D controls |
| `CP` | CutPlane controls |
| `PT` | Particle controls |

---

### E.2 cutplane.tcl — 切割平面

#### E.2.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `cutting_planes` | `callwind` | 轴对齐切割平面 |
| `do_cut_plane` | — | 执行轴对齐切割 |
| `arb_cutting_planes` | `callwind` | 任意切割平面 |
| `do_arbcut_plane` | — | 执行任意切割 |
| `display_acp` | — | 3点拾取对话框 |
| `acp_select_point` | `x y` | 单点选择处理 |

#### E.2.2 exe 调用

| 工具 | 用途 | 命令格式 |
|------|------|----------|
| `npfcutpl` / `r4_npfcutpl` | 轴对齐切割 | `x=<loc> cellsin pltosout mpf <name> [subcell]` |
| `npfcutp1` | 任意平面 | `a b c d cellsin pltosout mpf <name> [subcell]` |

---

### E.3 isosurf.tcl — 等值面

#### E.3.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `iso_surf` | `callwind` | 等值面对话框 |
| `do_iso_surf` | — | 执行等值面生成 |

#### E.3.2 exe 调用

- **exe**：`npfconsu`
- **命令格式**：`npfconsu <var> <level> cellsin pltosout mpf <name> subcell`
- **输出文件**：`con_<name>.mpf3d`

---

### E.4 partplane.tcl — 粒子显示

#### E.4.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `particle_planes` | — | 粒子平面对话框 |
| `do_part_plane` | — | 保存边界框设置 |
| `erase_part_plane` | — | 擦除粒子平面 |

#### E.4.2 数据结构

`partst(partic, xmin/ymin/zmin/xmax/ymax/zmax)` — 6个边界值

---

### E.5 directb.tcl — 文件浏览器

#### E.5.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `browse` | `filn callwind` | 单文件浏览器 |
| `browse_multiple` | `dir filemask callwind` | 多文件选择 |
| `browse_dir` | `callwind` | 工作目录选择 |
| `browse_subdir` | `callwind` | 子目录选择 |
| `new_project_dir` | — | 项目切换 |

---

### E.6 lighting.tcl — 光照控制

#### E.6.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `lighting_control` | — | 光照控制对话框 |
| `lit_val0/1/2` | `value` | 比例值回调 |

#### E.6.2 参数

| 变量 | 用途 |
|------|------|
| `back_light` | 环境光强度 |
| `reflect_light` | 反射光强度 |
| `spot_angle` | 聚光灯角度 |

---

### E.7 output.tcl — 图形输出

#### E.7.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `prt_to_file` | — | 输出文件对话框 |
| `hit_prn_type` | — | 格式特定选项显示 |
| `scal_val1` | `value` | JPEG压缩回调 |

#### E.7.2 输出格式

| print_file_typ | 格式 |
|----------------|------|
| 0 | JPEG（压缩率1-100） |
| 1 | Postscript（Portrait/Landscape/Un-Scaled） |
| 2 | BMP |

---

### E.8 commands.tcl — 系统命令

#### E.8.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `commands` | — | 命令路径配置 |
| `remove_files` | `callwind` | 文件清理对话框 |
| `run_rmfil` | — | 执行文件删除 |

---

### E.9 unit_convert.tcl — 单位换算

#### E.9.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `unitcal` | — | 单位换算对话框 |
| `convert` | — | 执行换算 |
| `change_units` | — | 重建单位菜单 |

#### E.9.2 换算算法

- 温度：`t_val = f_val * cvalue + afactor`
- 其他：`t_val = f_val * cvalue`

---

### E.10 inoutfil.tcl — 文件I/O

#### E.10.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `cfd_ifile` | `callwind` | 输入文件名对话框 |
| `cfd_ofile` | `callwind` | 输出文件名对话框 |
| `solfil_typ` | — | 解文件格式选择 |
| `copy_file` | — | 文件复制工具 |

#### E.10.2 输入文件

| 变量 | 默认值 | 描述 |
|------|--------|------|
| `mcpusin_fn` | `mcpusin.bin` | CPU分配 |
| `nodesin_fn` | `nodesin.bin` | 节点 |
| `cellsin_fn` | `cellsin.bin` | 单元 |
| `cdepsin_fn` | `cdepsin.bin` | 溶液 |
| `exbcsin_fn` | `exbcsin.bin` | 外部边界 |
| `inbcsin_fn` | `inbcsin.bin` | 内部边界 |

---

### E.11 cosim.tcl — 耦合仿真

#### E.11.1 proc 列表

| proc | 参数 | 功能 |
|------|------|------|
| `cos_fluid` | — | BC接口对话框 |
| `floinf1_bc` | — | BC接口边界选择 |
| `cos_flux` | — | Flux接口对话框 |
| `cos_dynam` | — | RBD接口对话框 |
| `dyninf1_bc` | — | RBD接口体选择 |
| `cosim1_region` | `set_num` | BC修改面板（多zone） |
| `cosim1_region2` | `set_num` | RBD修改面板（多body） |

#### E.11.2 三类接口

| 接口 | 信息集title | 用途 |
|------|-------------|------|
| BC Interface | `flointerface1_specification` | 边界流通量数据 |
| Flux Interface | `flxinterface1_specification` | 通量耦合 |
| RBD Interface | `dyninterface1_specification` | 刚体动力学 |

---

# 第三部分：全局变量索引

## 核心信息集变量

```
infsets              # 信息集总数
infset(N,title)      # 第N个信息集的类型
infset(N,vals)       # 参数个数
infset(N,used)       # 被引用次数
infset(N,v$i)        # 第i个参数值
```

## 边界条件变量

```
mbcons              # BC总数
mbcon(N,fam)        # BC家族
mbcon(N,bcname)     # BC名称
bcmapa(N,wall_type) # 壁面类型
bcmapa(N,adia_isot) # 绝热/等温
bcmapa(N,stat_move) # 运动类型
```

## 执行与调度变量

```
directory_global    # 工作目录
mcfd_prec          # 精度 (0/1)
mcfd_exec_type     # 执行类型
loc_proc           # 本机CPU数
use_other          # 多机标志
other_cpu(i,*)     # 其他机器配置
mcpu_machine       # 机器类型
```

## 时间积分变量

```
method             # 积分格式 (1/2/4)
sim_strat          # 策略 (0/1/2)
dultim             # 双时间步进
ntstep/ntstop      # 时间步数
```

## 网格运动变量

```
which_grsp         # 运动类型
irgrvs_on          # 速度定义开关
prerot             # 预条件
iregrd             # 网格随动
```

## 文件I/O变量

```
cellsin_fn / cellsout_fn     # 单元文件
nodesin_fn / nodesout_fn      # 节点文件
cdepsin_fn / cdepsout_fn     # 溶液文件
exbcsin_fn / exbcsout_fn     # 边界条件文件
```

---

# 第四部分：exe 调用完整索引

## 求解器 exe

| 场景 | exe | 调用方式 | 命令格式 |
|------|-----|----------|----------|
| 单CPU前台 | `mcfd` / `r4_mcfd` | run_cmd | `mcfd \| mc_stdoutee mcfd.log` |
| 单CPU后台 | `mcfd_background` / `mcfd_background4` | eval exec | `mcfd_background &` |
| 多CPU Linux mpich | `r4_mpimcfd` | run_cmd | `-p4pg r4_mpimcfd.pg` |
| 多CPU MPICH2 | `mpiexec` | run_cmd | `-n N -machinefile machine.txt r4_mpimcfd` |
| 多CPU MSMPI | `mpiexec` | run_cmd | `-n N r4_msmpimcfd` |

## 后处理 exe

| 工具 | exe | 用途 |
|------|-----|------|
| Post-processing | `mcfdplt` / `mcfdtplt` | 可视化 |
| FFT | `mcfdfft` | 频域分析 |
| 切片 | `mcfdpplt` / `mcfdfplt` | 平面查看 |
| 溶液查看 | `mcfdsol` / `mcfdsolx` | 交互查看 |

## 网格工具 exe

| 工具 | exe | 用途 |
|------|-----|------|
| 2D→Pie-Grid | `toxaxigr` / `toyaxigr` | 对称轴转换 |
| 多平面Pie-Grid | `toxaxpie` / `toxax360` | 多平面360° |
| 螺旋Extrusion | `tohelixgr` | 螺旋生成 |
| 单元重定义 | `celretyp` | 类型修改 |

## 切割与可视化 exe

| 工具 | exe | 用途 |
|------|-----|------|
| 轴对齐切割 | `npfcutpl` / `r4_npfcutpl` | YZ/XZ/XY平面 |
| 任意切割 | `npfcutp1` | ax+by+cz+d=0 |
| 等值面 | `npfconsu` | 等值面生成 |

## Tecplot 转换 exe

| 维度 | 单元 | exe |
|------|------|-----|
| 3D | 六面体 | `hextec` / `r4_hextec` |
| 3D | 四面体/三棱柱 | `tettec` / `r4_tettec` |
| 2D | 四边形 | `quatec` |
| 2D | 三角形 | `tritec` |
| 1D | 线 | `lintec` |

## 重插值 exe

| 方法 | exe（单/双精度） | 用途 |
|------|-----------------|------|
| Marching | `reintsom` / `r4_reintsom` | 高内存推进 |
| 最近邻 | `reintson` / `r4_reintson` | 低内存最近点 |
| 用户值 | `reintsod` / `r4_reintsod` | 用户指定值 |
| 报告停止 | `reintsol` / `r4_reintsol` | 仅报告 |

---

## 附录：源文件清单

| 类别 | 文件 | 行数 |
|------|------|------|
| 执行调度 | run_mcfd.tcl | ~3665 |
| 执行调度 | run_cmd.tcl | 516 |
| 执行调度 | infotool.tcl | 827 |
| 执行调度 | lmtool.tcl | 224 |
| 执行调度 | forcemom.tcl | ~1310 |
| 执行调度 | gui_hinit.tcl | 205 |
| 执行调度 | mc_bind.tcl | 537 |
| 主GUI配置 | infoset.tcl | 22428 |
| 主GUI配置 | viewinf.tcl | 15445 |
| 主GUI配置 | timeint.tcl | 6121 |
| 主GUI配置 | topology.tcl | 6466 |
| 主GUI配置 | saving.tcl | 5249 |
| 主GUI配置 | init_dom.tcl | 10800 |
| 主GUI配置 | load_proc.tcl | 5836 |
| 网格工具 | gridtools.tcl | ~15000 |
| 网格工具 | gridvel.tcl | ~10000 |
| 网格工具 | probe.tcl | ~8000 |
| 网格工具 | totec.tcl | ~8400 |
| 网格工具 | soltools.tcl | ~7100 |
| 物理模型 | species.tcl | ~1330 |
| 物理模型 | reaction.tcl | ~1438 |
| 物理模型 | turbname.tcl | ~1093 |
| 物理模型 | bcstuff.tcl | ~2100 |
| 物理模型 | gasprop.tcl | ~1193 |
| 物理模型 | disperse.tcl | ~1041 |
| 物理模型 | refer.tcl | ~1000 |
| 物理模型 | riemann.tcl | ~1200 |
| 物理模型 | spacdis.tcl | ~1100 |
| 物理模型 | volsour.tcl | ~530 |
| 物理模型 | volsoug.tcl | ~400 |
| 物理模型 | bcsort.tcl | 47 |
| 可视化 | surface.tcl | ~1600 |
| 可视化 | cutplane.tcl | 1097 |
| 可视化 | isosurf.tcl | 168 |
| 可视化 | partplane.tcl | 336 |
| 可视化 | directb.tcl | 1055 |
| 可视化 | lighting.tcl | 111 |
| 可视化 | output.tcl | 138 |
| 可视化 | univtool.tcl | 37 |
| 可视化 | commands.tcl | 237 |
| 可视化 | unit_convert.tcl | 709 |
| 可视化 | inoutfil.tcl | 842 |
| 可视化 | cosim.tcl | ~1200 |

**总计**：50+个 Tcl 文件，约 **140,000+ 行代码**

---

*本文档由 Mavis Agent 基于 CFD++ GUI 源码自动生成*
*生成日期：2026-05-28*