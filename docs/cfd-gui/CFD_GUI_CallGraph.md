# CFD++ Tcl/Tk GUI 调用关系分析

## 一、入口文件（.tk 文件）

CFD++ GUI 有 10 个独立入口 `.tk` 文件，每个对应一个可执行工具：

| 入口文件 | 窗口标题 | 说明 |
|---|---|---|
| `cfd++.tk` | CFD++ 主GUI | 最核心的入口，加载全部140个.tcl模块 |
| `mcfdsol.tk` | META Visualizer | 后处理可视化 |
| `mcfdplt.tk` | CFD++ Residual Plotter | 残差绘图（简单版） |
| `mcfdplt2.tk` | CFD++ Residual Plotter | 残差绘图（带run_cmd） |
| `mcfdtplt.tk` | CFD++ Residual Plotter | 残差绘图（带工具栏） |
| `mcfdpplt.tk` | CFD++ Probe Plotter | 探针绘图 |
| `mcfdfplt.tk` | CFD++ Flux/Force/Moment Plotter | 力/力矩绘图 |
| `mcfdfft.tk` | CFD++ FFT Tool | FFT分析工具 |
| `mcfd1dp.tk` | CFD++ XY plotting tool | XY曲线绘图 |
| `logview.tk` | CFD++ Log File | 日志查看器 |

每个 `.tk` 文件本质上是 `wish`（Tk窗口Shell）的启动脚本，内部 `source` 加载各 `.tcl` 模块。

---

## 二、cfd++.tk 完整 source 链路

### 核心基础库（所有 .tk 共享）
```
mc_bind.tcl        # 键盘/鼠标绑定、退出对话框、全局exit3/exit2
gui_hinit.tcl       # 帮助系统初始化、浏览器调用（Netscape/firefox/mexplore）
gui_center.tcl      # 窗口居中
bltGraph.tcl        # BLT图表库封装
colormap.tcl        # 颜色映射
```

### 全局变量定义（cfd++.tk 独有）
```
mc_glovar1.tcl      # ~1300行：求解器参数、流场变量、界面工具变量
mc_glovar2.tcl      # ~1000行：网格、边界、渲染选项
mc_glovar3.tcl      # 求解参数、物理模型
mc_glovar4.tcl      # GUI状态、工具运行标记
```

### 主GUI布局
```
gui_image.tcl       # 图标/图片资源
gui_menu.tcl        # 菜单栏定义
gui_buttons.tcl     # 工具栏按钮
gui_center.tcl      # 窗口居中
```

### 求解运行相关
```
run_mcfd.tcl        # ★核心★：运行mcfd/r4_mcfd/msmpimcfd，支持单核/多核/mpiexec
run_reyinf.tcl      # 运行reyinf后处理
run_cmd.tcl         # ★核心★：blt::bgexec异步任务管理，支持job_name、进度回显
ezsetup1.tcl        # 向导安装（调用 xterm -e ez1_sc1.sh）
panic.tcl           # 紧急停止
```

### 信息集（Case参数配置）
```
infoset.tcl         # ★大型★ ~22000行：信息集编辑器（最核心的case参数界面）
viewinf.tcl         # ★大型★ ~15000行：信息集查看器
load_proc.tcl       # 从文件加载case参数
init_dom.tcl        # 域初始化
eqset.tcl           # 方程组定义
```

### 时间/拓扑/网格
```
timeint.tcl          # 时间积分控制
timemark.tcl         # 时间标记
topology.tcl         # 拓扑控制
rotatec.tcl          # 旋转坐标
gridvel.tcl          # ★大型★ ~10000行：网格运动/速度（平移/旋转/振荡/6DOF/网格变形）
gridblnk.tcl         # 网格遮罩
gridtools.tcl        # ★大型★ ~15000行：网格工具（合并/分割/变换/区域映射）
gridcheck.tcl        # 网格检查
```

### 边界/物理
```
bcstuff.tcl         # 边界条件定义
bcsort.tcl           # 边界排序
species.tcl          # 组分/化学反应
reaction.tcl        # 反应机理
turbname.tcl         # 湍流模型名称
gasprop.tcl         # 气体属性（完美气体）
refer.tcl           # 参考值
riemann.tcl          # Riemann求解器
spacdis.tcl          # 空间离散格式
volsour.tcl/volsoug.tcl/volsouc.tcl  # 体积源项
disperse.tcl         # 弥散相
ldpprop.tcl          # 大颗粒属性
mixprop.tcl          # 混合物属性
```

### 输出/保存/探测
```
inoutfil.tcl        # 输入输出文件配置
saving.tcl          # 输出保存控制
probe.tcl           # ★大型★ ~8000行：探测点与残差输出文件配置
trange.tcl          # 时间范围
totec.tcl           # ★大型★ ~8400行：Tecplot格式转换工具
soltools.tcl        # ★大型★ ~7100行：解重插值工具（mcfdsol→新网格）
```

### 后处理/可视化
```
directb.tcl         # 直接边界操作
lighting.tcl         # 光照设置
recon_info.tcl       # 重构信息
surface.tcl          # 表面定义
cutplane.tcl         # 切割平面
isosurf.tcl          # 等值面
partplane.tcl        # 粒子平面
partrac.tcl          # 粒子轨迹
mc_animate.tcl        # 动画生成
dispobj.tcl          # 显示对象
output.tcl           # 输出控制
univtool.tcl         # 通用工具
infotool.tcl         # 信息查询工具（调用infotool_bgexec）
lmtool.tcl           # 极限工具（调用lmtool_bgexec）
lmcontrol.tcl        # 极限控制
```

### 专用工具
```
unit_convert.tcl      # 单位转换
wizards.tcl           # 向导
coking_wizard.tcl     # 结焦向导
sdgui.tcl            # Shape Designer GUI
frpl3d.tcl           # FROMesh3D接口
topl3d.tcl           # TOmesh3D接口
fp3dcg.tcl/fp3dss.tcl/fp3dzc.tcl  # 格式转换
convert10.tcl        # convert10工具
tometis.tcl          # METIS分区（调用tometis/xmetis/reometis）
turbinit.tcl         # 湍流初始化
plasma.tcl           # 等离子体
prtout.tcl           # 投影输出
dimension.tcl        # 无量纲化
mactool.tcl          # Mach-Re工具
infocopy.tcl         # 信息复制
proftool.tcl         # 轮廓工具
forcemom.tcl         # 力/力矩计算
interffm.tcl         # 界面力/力矩
ffm_ntout29.tcl      # 输出格式
soltools.tcl         # 解工具（也是求解后处理）
npfcuts.tcl          # NPF切割
caa++.tcl            # CAA++工具
sixdof.tcl           # 六自由度
miscsetup.tcl        # 杂项设置
cfdinfo.tcl          # CFD++信息文件
cellblnk.tcl         # 单元格遮罩
cfdbyte.tcl          # 字节序
commands.tcl         # 用户命令
convert.tcl          # 通用转换
bltGraph.tcl         # BLT图表
pltdata.tcl          # 绘图数据
mc_draw.tcl           # 绘图工具
point_select.tcl     # 点选
partrac.tcl          # 粒子追踪
cosim.tcl            # 协同仿真
conjheat.tcl         # 共轭换热
porosity.tcl         # 多孔介质
physour.tcl          # 物理源项
gui_reset.tcl        # GUI变量重置
sumo.tcl             # SUMO接口
levelset.tcl         # Level-Set
radmodp1.tcl/radmoddo.tcl  # 辐射模型
overlay.tcl          # 覆盖层
oxygenate.tcl        # 氧化
ps10_volsour.tcl     # PS10体积源
vofmethod.tcl        # VOF方法
special_mode.tcl     # 特殊模式
syscmd.tcl           # 系统命令
interview.tcl        # Interview IDE
syscmd.tcl           # 系统命令执行
```

---

## 三、exec/exe 调用总结

### 3.1 直接 exec 调用（`eval exec $command`）

所有实际调用的 exe 都通过 `eval exec $command` 执行，`$command` 由调用方构建。

**mcfd 主求解器**（`run_mcfd.tcl`）：
- `mcfd` / `r4_mcfd` — 单精度/双精度串行
- `mcfd_background` / `mcfd_background4` — 后台运行
- `mcfdstop` / `mcfdkill` — 停止求解
- `mpiexec -n N [r4_]msmpimcfd` — MPI并行（MSMPI后端）
- `mpiexec -n N [r4_]mpimcfd` — MPI并行（MPICH后端）
- `r4_mcfd | mc_stdoutee mcfd.log` — 管道重定向stdout

**GUI 子工具**（`run_mcfd.tcl`）：
- `mcfdsol` / `mcfdsolx` — META可视化
- `mcfdplt` — 残差绘图
- `mcfdtplt` — 时序残差绘图
- `mcfdpplt` — 探针绘图
- `mcfdfplt` — 力/力矩绘图
- `mcfdfft` — FFT工具
- `mcfd1dp` — XY绘图
- `logview` / `logview2` — 日志查看
- `runb_tail` — 日志尾部监控

**外部工具**（`run_mcfd.tcl`）：
- `dfcells` — 域分解
- `hostname` — 获取主机名（用于MPI）

### 3.2 blt::bgexec 异步任务（`run_cmd.tcl`）

BLT扩展的异步执行，用于长时间运行的任务，带实时stdout回显：
- `blt::bgexec run_status_$job_name -onoutput update_display_$job_name ... $clt_cmd`
- `$clt_cmd` 构建自 `run_mcfd.tcl` 的 `run_cmd` 过程，包裹 `mpiexec` 或单个 exe

**infotool**（`infotool.tcl`）：
- `blt::bgexec infotool_bgexec_status -onoutput it_getinfo -onerror GetInfo $clt_cmd`
- `$clt_cmd` 通常是 `infotool` 系列 exe

**lmtool**（`lmtool.tcl`）：
- `blt::bgexec lmtool_bgexec_status -onoutput lm_it_getinfo -onerror GetInfo $lm_clt_cmd`
- `$lm_clt_cmd` 通常是 `lmtool` 系列 exe

**forcemom**（`forcemom.tcl`）：
- `blt::bgexec infout1f$i infout1f $i` — 力和力矩计算

### 3.3 帮助系统（`gui_hinit.tcl`）

**Linux/Unix**：通过 `$net1_run`（`netscape.run1`）或 `$net2_run`（`netscape.run2`）调用浏览器：
- `$net1_run $fil $netscape_c &` — 浏览器打开帮助HTML

**Windows**：调用 `mexplore`（微软资源管理器，Windows 98/NT时代遗留）打开HTML文件

### 3.4 GUI按钮触发的 exec（`gui_menu.tcl`、`gui_buttons.tcl`、`sol_menu.tcl`、`mc_bind.tcl`）

通过 `$command` 变量构建，典型模式：
```tcl
eval exec $command     # 同步等待
eval exec $command &   # 后台运行
```

来源文件：gui_menu.tcl、gui_buttons.tcl、sol_menu.tcl、mc_bind.tcl、mc_animate.tcl、surface.tcl、graphs.tcl、case01.tcl、probe.tcl 等。

### 3.5 批处理脚本（`ezsetup1.tcl`）

```tcl
exec xterm -e ez1_sc1.sh   # Linux下打开xterm运行安装脚本
```

---

## 四、exec 目录中的 exe 分类

`D:\software\CFD++\METACOMP\mlib\mcfd.18.5\exec\` 下约 600+ 个 exe，主要分类：

**求解器**：`mcfd.exe`、`r4_mcfd.exe`、`msmpimcfd.exe`、`mpimcfd.exe`

**GUI包装**：`mcfdgui.exe`、`sdgui.exe`、`edgui.exe`

**后处理/绘图**：`mcfdplt.exe`、`mcfdtplt.exe`、`mcfdpplt.exe`、`mcfdfplt.exe`、`mcfdsol.exe`、`mcfdfft.exe`、`mcfd1dp.exe`、`logview.exe`、`logview2.exe`

**网格工具**：`dfcells.exe`、`dfnodes.exe`、`toponew1.exe`、`topl3d.exe`、`totgrid.exe`、`mcmetis.exe`、`tometis.exe`、`cuthillmckee.exe`

**格式转换**：`convert1~convert24.exe`（多种格式）、`hextec.exe`、`tritec.exe`、`quatec.exe`、`pltos*.exe`、`infout*.exe`

**信息提取**：`infotool.exe`、`cellsinf.exe`、`nodesinf.exe`、`grdqual*.exe`

**粒子追踪**：`partrac.exe`、`partraj.exe`

**网格变形**：`mcfd_morph1.exe`、`mpi_morph1.exe`

**解重插值**：`reintsol.exe`、`reintson.exe`、`reintsom.exe`（r4_前缀为单精度版本）

**力/力矩**：`forcemom.exe`（GUI包装）、`infout1f.exe`

---

## 五、Tcl 内部 source 依赖图

```
cfd++.tk
├── mc_glovar1~4.tcl          ← 全局变量定义（source顺序: 1→2→3→4）
├── gui_image.tcl
├── gui_menu.tcl
├── gui_buttons.tcl
├── gui_center.tcl
├── gui_hinit.tcl              ← 所有.tk共享
├── gui_binds.tcl              ← 所有.tk共享
├── bltGraph.tcl               ← 所有.tk共享
├── colormap.tcl               ← 所有.tk共享
├── mc_bind.tcl                ← 所有.tk共享
├── mc_edit.tcl
├── bcsort.tcl
├── panic.tcl
├── run_mcfd.tcl               ← ★ exe调用核心：mcfd/mpiexec/hostname
├── run_reyinf.tcl
├── run_cmd.tcl                ← ★ 异步任务：blt::bgexec run_cmd
├── unit_convert.tcl
├── ezsetup1.tcl               ← exec xterm
├── syscmd.tcl
├── infotool.tcl               ← blt::bgexec infotool
├── lmtool.tcl                 ← blt::bgexec lmtool
├── lmcontrol.tcl
├── edit_mcfd.tcl
├── lighting.tcl
├── recon_info.tcl
├── load_proc.tcl
├── init_dom.tcl
├── eqset.tcl
├── trange.tcl
├── probe.tcl
├── inoutfil.tcl
├── directb.tcl
├── infoset.tcl
├── viewinf.tcl
├── timeint.tcl / timemark.tcl
├── topology.tcl
├── rotatec.tcl
├── gridvel.tcl
├── gridblnk.tcl
├── saving.tcl
├── rclickh.tcl
├── interview.tcl
├── wizards.tcl / coking_wizard.tcl / sdgui.tcl
├── dispobj.tcl
├── output.tcl
├── mc_choosefont.tcl
├── conjheat.tcl
├── porosity.tcl
├── physour.tcl
├── gui_reset.tcl
├── frpl3d.tcl / topl3d.tcl / fp3dcg.tcl / fp3dss.tcl / fp3dzc.tcl
├── convert10.tcl
├── totec.tcl
├── hexdec.tcl
├── tometis.tcl               ← exec tometis/xmetis
├── turbinit.tcl
├── plasma.tcl
├── prtout.tcl
├── dimension.tcl
├── mactool.tcl
├── infocopy.tcl
├── proftool.tcl
├── univtool.tcl
├── forcemom.tcl               ← blt::bgexec forcemom
├── interffm.tcl / ffm_ntout29.tcl
├── soltools.tcl
├── npfcuts.tcl
├── caa++.tcl
├── sixdof.tcl
├── miscsetup.tcl
├── gridtools.tcl
├── gridcheck.tcl
├── cfdinfo.tcl
├── cellblnk.tcl
├── cfdbyte.tcl
├── commands.tcl
├── convert.tcl
├── pltdata.tcl
├── mc_draw.tcl
├── point_select.tcl
├── partra c.tcl
├── cosim.tcl
├── levelset.tcl
├── radmodp1.tcl / radmoddo.tcl
├── overlay.tcl
├── oxygenate.tcl
├── ps10_volsour.tcl / ps10_volsoug.tcl
├── vofmethod.tcl
├── special_mode.tcl
├── species.tcl / reaction.tcl
├── turbname.tcl
├── volsour.tcl / volsoug.tcl / volsouc.tcl
├── gasprop.tcl
├── disperse.tcl / ldpprop.tcl / mixprop.tcl
├── refer.tcl
├── riemann.tcl
├── spacdis.tcl
└── sumo.tcl
```

---

## 六、关键结论

1. **主入口是 `cfd++.tk`**，它 source 了全部 140 个 .tcl 文件。翻译 `gui_src/` 时，**只需要替换 `cfd++.tk` 指向的目录**，其余 .tk 工具（mcfdplt 等）各自独立加载少量 .tcl。

2. **GUI 不直接调用 exe** —— exe 调用统一走两条路：
   - `run_mcfd.tcl` → `eval exec $command`（同步/管道）
   - `run_cmd.tcl` → `blt::bgexec`（异步+stdout回显）

3. **翻译后部署**：只需把 `gui_src_cn/` 整体替换 `gui_src/`，或将 `cfd++.tk` 中的 `${metapath}` 指向 `gui_src_cn/` 即可。

4. **帮助系统**（`gui_hinit.tcl`）在 Windows 下调用 `mexplore` 打开 HTML，这是 Windows 98/NT 遗留方式，浏览器支持 `firefox`（`mc_glovar2.tcl` 设置 `netscape_c firefox`）。
