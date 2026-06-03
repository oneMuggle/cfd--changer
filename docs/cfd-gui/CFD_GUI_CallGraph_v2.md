# CFD++ Tcl/Tk GUI 调用关系深度分析 (v2)

> **分析对象**: `D:\software\CFD++\METACOMP\mlib\mcfd.18.5\exec\gui_src\`  
> **分析范围**: 150 个文件 (140 个 .tcl + 10 个 .tk)  
> **分析方法**: 静态分析,基于 Tcl 词法(brace 字符串不做转义、识别 `${var}` 变量引用、re 处理 `source` 行)  
> **分析维度**: ①source 依赖链 ②proc 导出表 ③proc 调用矩阵 ④global 变量依赖 ⑤exe 调用接口 ⑥入口归类  

---

## 一、执行摘要

### 1.1 关键指标

| 指标 | 数值 |
|---|---|
| 文件总数 | **150** |
| .tcl 模块 | 140 |
| .tk 入口 | 10 |
| `source` 声明总数 | **187** |
| `proc` 定义总数 | **1353** |
| 唯一 `proc` 名称 | 1251 |
| 跨文件 `proc` 调用边 | **3871** |
| `exec`/`bgexec` 调用点 | 65 |
| `global` 变量声明 | 28511 |

### 1.2 关键发现

1. **`cfd++.tk` 是核心入口**,通过 **116 次 `source`** 加载了 ~110 个 .tcl 模块,几乎覆盖全部业务逻辑
2. **其他 9 个 .tk 入口**各自只 source 少数模块,定位为独立后处理/绘图工具
3. **GUI 不直接调用 exe**,统一通过两条路径间接执行:
   - `run_mcfd.tcl` → `eval exec $command` (同步)
   - `run_cmd.tcl` → `blt::bgexec` (异步+stdout 回显)
4. **`mc_glovar1.tcl`~`mc_glovar4.tcl`** 是 4 个全局变量定义文件,所有 GUI 状态都通过 `global` 跨 proc 传递
5. **跨文件 proc 调用** 3871 条边,平均每个 proc 被跨文件调用 ~3 次
6. **1251 个唯一 proc** 中,~80% 在单个文件内被调用,~20% 是跨文件共享接口

## 二、入口文件详解 (.tk)

CFD++ GUI 有 **10 个独立 `.tk` 入口** 文件,每个对应一个 GUI 可执行工具:

| 入口 | 窗口标题 | 直接 source 数 | 加载 .tcl 数 | 关键依赖 |
|---|---|---:|---:|---|
| `cfd++.tk` | CFD++ 主GUI | 116 | 116 | `mc_glovar1.tcl`, `mc_glovar2.tcl`, `mc_glovar3.tcl`, `mc_glovar4.tcl`, `gui_image.tcl` |
| `logview.tk` | 日志查看器 | 3 | 3 | `mc_bind.tcl`, `gui_hinit.tcl`, `gui_center.tcl` |
| `mcfd1dp.tk` | XY 曲线绘图 | 9 | 9 | `mc_bind.tcl`, `gui_hinit.tcl`, `gui_center.tcl`, `bltGraph.mcfd1dp.tcl`, `gui_image.tcl` |
| `mcfdfft.tk` | FFT 分析工具 | 4 | 4 | `mc_bind.tcl`, `gui_hinit.tcl`, `gui_center.tcl`, `bltGraph.tcl` |
| `mcfdfplt.tk` | 力/力矩绘图 | 5 | 5 | `mc_bind.tcl`, `gui_hinit.tcl`, `gui_center.tcl`, `colormap.tcl`, `bltGraph.tcl` |
| `mcfdplt.tk` | 残差绘图(简单版) | 3 | 3 | `mc_bind.tcl`, `gui_hinit.tcl`, `gui_center.tcl` |
| `mcfdplt2.tk` | 残差绘图(run_cmd 异步版) | 6 | 6 | `mc_bind.tcl`, `gui_hinit.tcl`, `gui_center.tcl`, `colormap.tcl`, `bltGraph.tcl` |
| `mcfdpplt.tk` | 探针绘图 | 5 | 5 | `mc_bind.tcl`, `gui_hinit.tcl`, `gui_center.tcl`, `colormap.tcl`, `bltGraph.tcl` |
| `mcfdsol.tk` | META Visualizer (后处理可视化) | 29 | 29 | `refer.tcl`, `gui_image.tcl`, `mc_bind.tcl`, `mc_edit.tcl`, `sol_menu.tcl` |
| `mcfdtplt.tk` | 残差绘图(工具栏版) | 5 | 5 | `mc_bind.tcl`, `gui_hinit.tcl`, `gui_center.tcl`, `colormap.tcl`, `bltGraph.tcl` |

### 2.1 `cfd++.tk` 完整 source 链(共 116 次)

`cfd++.tk` 通过 `${metapath}` 路径变量加载模块,加载顺序:

```
L 121: source ${metapath}/mc_glovar1.tcl    → mc_glovar1.tcl
L 125: source ${metapath}/mc_glovar2.tcl    → mc_glovar2.tcl
L 129: source ${metapath}/mc_glovar3.tcl    → mc_glovar3.tcl
L 133: source ${metapath}/mc_glovar4.tcl    → mc_glovar4.tcl
L 150: source ${metapath}/gui_image.tcl    → gui_image.tcl
L 160: source ${metapath}/mc_bind.tcl    → mc_bind.tcl
L 189: source ${metapath}/mc_edit.tcl    → mc_edit.tcl
L 196: source ${metapath}/bcsort.tcl    → bcsort.tcl
L 200: source ${metapath}/gui_menu.tcl    → gui_menu.tcl
L 204: source ${metapath}/panic.tcl    → panic.tcl
L 208: source ${metapath}/gui_hinit.tcl    → gui_hinit.tcl
L 211: source ${metapath}/run_mcfd.tcl    → run_mcfd.tcl
L 212: source ${metapath}/run_reyinf.tcl    → run_reyinf.tcl
L 214: source ${metapath}/run_cmd.tcl    → run_cmd.tcl
L 220: source ${metapath}/unit_convert.tcl    → unit_convert.tcl
L 226: source ${metapath}/ezsetup1.tcl    → ezsetup1.tcl
L 232: source ${metapath}/infotool.tcl    → infotool.tcl
L 237: source ${metapath}/lmtool.tcl    → lmtool.tcl
L 242: source ${metapath}/lmcontrol.tcl    → lmcontrol.tcl
L1117: source ${metapath}/gui_buttons.tcl    → gui_buttons.tcl
L1136: source ${metapath}/gui_center.tcl    → gui_center.tcl
L1141: source ${metapath}/edit_mcfd.tcl    → edit_mcfd.tcl
L1146: source ${metapath}/lighting.tcl    → lighting.tcl
L1151: source ${metapath}/recon_info.tcl    → recon_info.tcl
L1157: source ${metapath}/load_proc.tcl    → load_proc.tcl
L1162: source ${metapath}/init_dom.tcl    → init_dom.tcl
L1168: source ${metapath}/eqset.tcl    → eqset.tcl
L1173: source ${metapath}/trange.tcl    → trange.tcl
L1178: source ${metapath}/probe.tcl    → probe.tcl
L1183: source ${metapath}/inoutfil.tcl    → inoutfil.tcl
L1189: source ${metapath}/directb.tcl    → directb.tcl
L1195: source ${metapath}/syscmd.tcl    → syscmd.tcl
L1201: source ${metapath}/cosim.tcl    → cosim.tcl
L1207: source ${metapath}/species.tcl    → species.tcl
L1212: source ${metapath}/turbname.tcl    → turbname.tcl
L1217: source ${metapath}/reaction.tcl    → reaction.tcl
L1223: source ${metapath}/volsour.tcl    → volsour.tcl
L1224: source ${metapath}/volsoug.tcl    → volsoug.tcl
L1225: source ${metapath}/volsouc.tcl    → volsouc.tcl
L1230: source ${metapath}/gasprop.tcl    → gasprop.tcl
L1238: source ${metapath}/disperse.tcl    → disperse.tcl
L1239: source ${metapath}/ldpprop.tcl    → ldpprop.tcl
L1240: source ${metapath}/mixprop.tcl    → mixprop.tcl
L1246: source ${metapath}/refer.tcl    → refer.tcl
L1254: source ${metapath}/riemann.tcl    → riemann.tcl
L1260: source ${metapath}/spacdis.tcl    → spacdis.tcl
L1264: source ${metapath}/levelset.tcl    → levelset.tcl
L1268: source ${metapath}/radmodp1.tcl    → radmodp1.tcl
L1269: source ${metapath}/overlay.tcl    → overlay.tcl
L1270: source ${metapath}/radmoddo.tcl    → radmoddo.tcl
L1271: source ${metapath}/oxygenate.tcl    → oxygenate.tcl
L1272: source ${metapath}/ps10_volsour.tcl    → ps10_volsour.tcl
L1273: source ${metapath}/ps10_volsoug.tcl    → ps10_volsoug.tcl
L1274: source ${metapath}/vofmethod.tcl    → vofmethod.tcl
L1278: source ${metapath}/special_mode.tcl    → special_mode.tcl
L1283: source ${metapath}/bcstuff.tcl    → bcstuff.tcl
L1289: source ${metapath}/viewinf.tcl    → viewinf.tcl
L1294: source ${metapath}/infoset.tcl    → infoset.tcl
L1300: source ${metapath}/timeint.tcl    → timeint.tcl
L1301: source ${metapath}/timemark.tcl    → timemark.tcl
L1305: source ${metapath}/topology.tcl    → topology.tcl
L1306: source ${metapath}/rotatec.tcl    → rotatec.tcl
L1311: source ${metapath}/sumo.tcl    → sumo.tcl
L1316: source ${metapath}/gridvel.tcl    → gridvel.tcl
L1317: source ${metapath}/gridblnk.tcl    → gridblnk.tcl
L1322: source ${metapath}/saving.tcl    → saving.tcl
L1328: source ${metapath}/rclickh.tcl    → rclickh.tcl
L1334: source ${metapath}/interview.tcl    → interview.tcl
L1340: source ${metapath}/wizards.tcl    → wizards.tcl
L1341: source ${metapath}/coking_wizard.tcl    → coking_wizard.tcl
L1342: source ${metapath}/sdgui.tcl    → sdgui.tcl
L1347: source ${metapath}/dispobj.tcl    → dispobj.tcl
L1348: source ${metapath}/output.tcl    → output.tcl
L1349: source ${metapath}/mc_choosefont.tcl    → mc_choosefont.tcl
L1353: source ${metapath}/conjheat.tcl    → conjheat.tcl
L1359: source ${metapath}/porosity.tcl    → porosity.tcl
L1360: source ${metapath}/physour.tcl    → physour.tcl
L1366: source ${metapath}/gui_reset.tcl    → gui_reset.tcl
L1371: source ${metapath}/frpl3d.tcl    → frpl3d.tcl
L1372: source ${metapath}/topl3d.tcl    → topl3d.tcl
L1373: source ${metapath}/fp3dcg.tcl    → fp3dcg.tcl
L1374: source ${metapath}/fp3dss.tcl    → fp3dss.tcl
L1375: source ${metapath}/fp3dzc.tcl    → fp3dzc.tcl
L1376: source ${metapath}/convert10.tcl    → convert10.tcl
L1381: source ${metapath}/totec.tcl    → totec.tcl
L1386: source ${metapath}/hexdec.tcl    → hexdec.tcl
L1392: source ${metapath}/tometis.tcl    → tometis.tcl
L1398: source ${metapath}/turbinit.tcl    → turbinit.tcl
L1404: source ${metapath}/plasma.tcl    → plasma.tcl
L1410: source ${metapath}/prtout.tcl    → prtout.tcl
L1415: source ${metapath}/dimension.tcl    → dimension.tcl
L1420: source ${metapath}/mactool.tcl    → mactool.tcl
L1425: source ${metapath}/infocopy.tcl    → infocopy.tcl
L1429: source ${metapath}/proftool.tcl    → proftool.tcl
L1434: source ${metapath}/univtool.tcl    → univtool.tcl
L1439: source ${metapath}/forcemom.tcl    → forcemom.tcl
L1440: source ${metapath}/interffm.tcl    → interffm.tcl
L1441: source ${metapath}/ffm_ntout29.tcl    → ffm_ntout29.tcl
L1446: source ${metapath}/soltools.tcl    → soltools.tcl
L1447: source ${metapath}/npfcuts.tcl    → npfcuts.tcl
L1452: source ${metapath}/caa++.tcl    → caa++.tcl
L1458: source ${metapath}/sixdof.tcl    → sixdof.tcl
L1463: source ${metapath}/miscsetup.tcl    → miscsetup.tcl
L1468: source ${metapath}/gridtools.tcl    → gridtools.tcl
L1469: source ${metapath}/gridcheck.tcl    → gridcheck.tcl
L1474: source ${metapath}/cfdinfo.tcl    → cfdinfo.tcl
L1479: source ${metapath}/cellblnk.tcl    → cellblnk.tcl
L1484: source ${metapath}/cfdbyte.tcl    → cfdbyte.tcl
L1489: source ${metapath}/commands.tcl    → commands.tcl
L1494: source ${metapath}/convert.tcl    → convert.tcl
L1498: source ${metapath}/bltGraph.tcl    → bltGraph.tcl
L1499: source ${metapath}/pltdata.tcl    → pltdata.tcl
L1503: source ${metapath}/colormap.tcl    → colormap.tcl
L1504: source ${metapath}/mc_draw.tcl    → mc_draw.tcl
L1508: source ${metapath}/point_select.tcl    → point_select.tcl
L1513: source ${metapath}/partrac.tcl    → partrac.tcl
```

**加载顺序的特点**:

- L121-133: 先加载 4 个全局变量文件 (mc_glovar1-4)
- L150-200: GUI 基础 (image/bind/menu/buttons/center)
- L210-310: 求解运行 + 信息查询工具 (run_mcfd/run_cmd/infotool/lmtool)
- L400+: Case 配置 + 物理模块 (load_proc/init_dom/eqset/infoset/viewinf)
- L500+: 物理/边界/源 (bcstuff/species/reaction/turbname/gasprop/...)
- L800+: 网格/时间/拓扑 (gridvel/gridtools/timeint/topology)
- L1000+: 输出/保存/探测 (saving/probe/inoutfil)
- L1200+: 后处理/可视化 (surface/cutplane/isosurf/partrac/...)
- L1400+: 专用工具 (frpl3d/topl3d/wizards/...)

### 2.2 其他 9 个 .tk 入口的 source 链

**`logview.tk`** (3 次 source)

```
L  84: source ${metapath}/mc_bind.tcl    → mc_bind.tcl
L  89: source ${metapath}/gui_hinit.tcl    → gui_hinit.tcl
L  94: source ${metapath}/gui_center.tcl    → gui_center.tcl
```
**`mcfd1dp.tk`** (9 次 source)

```
L 123: source ${metapath}/mc_bind.tcl    → mc_bind.tcl
L 127: source ${metapath}/gui_hinit.tcl    → gui_hinit.tcl
L 131: source ${metapath}/gui_center.tcl    → gui_center.tcl
L 135: source ${metapath}/bltGraph.mcfd1dp.tcl    → bltGraph.mcfd1dp.tcl
L 139: source ${metapath}/gui_image.tcl    → gui_image.tcl
L 143: source ${metapath}/colormap.tcl    → colormap.tcl
L 147: source ${metapath}/open_file.tcl    → open_file.tcl
L 166: source ${metapath}/onedp_menu.tcl    → onedp_menu.tcl
L 170: source ${metapath}/onedp_buttons.tcl    → onedp_buttons.tcl
```
**`mcfdfft.tk`** (4 次 source)

```
L 153: source ${metapath}/mc_bind.tcl    → mc_bind.tcl
L 158: source ${metapath}/gui_hinit.tcl    → gui_hinit.tcl
L 163: source ${metapath}/gui_center.tcl    → gui_center.tcl
L 165: source ${metapath}/bltGraph.tcl    → bltGraph.tcl
```
**`mcfdfplt.tk`** (5 次 source)

```
L  97: source ${metapath}/mc_bind.tcl    → mc_bind.tcl
L 102: source ${metapath}/gui_hinit.tcl    → gui_hinit.tcl
L 107: source ${metapath}/gui_center.tcl    → gui_center.tcl
L 111: source ${metapath}/colormap.tcl    → colormap.tcl
L 113: source ${metapath}/bltGraph.tcl    → bltGraph.tcl
```
**`mcfdplt.tk`** (3 次 source)

```
L  55: source ${metapath}/mc_bind.tcl    → mc_bind.tcl
L  60: source ${metapath}/gui_hinit.tcl    → gui_hinit.tcl
L  65: source ${metapath}/gui_center.tcl    → gui_center.tcl
```
**`mcfdplt2.tk`** (6 次 source)

```
L 102: source ${metapath}/mc_bind.tcl    → mc_bind.tcl
L 107: source ${metapath}/gui_hinit.tcl    → gui_hinit.tcl
L 112: source ${metapath}/gui_center.tcl    → gui_center.tcl
L 116: source ${metapath}/colormap.tcl    → colormap.tcl
L 118: source ${metapath}/bltGraph.tcl    → bltGraph.tcl
L 123: source ${metapath}/run_cmd.tcl    → run_cmd.tcl
```
**`mcfdpplt.tk`** (5 次 source)

```
L  97: source ${metapath}/mc_bind.tcl    → mc_bind.tcl
L 102: source ${metapath}/gui_hinit.tcl    → gui_hinit.tcl
L 107: source ${metapath}/gui_center.tcl    → gui_center.tcl
L 111: source ${metapath}/colormap.tcl    → colormap.tcl
L 113: source ${metapath}/bltGraph.tcl    → bltGraph.tcl
```
**`mcfdsol.tk`** (29 次 source)

```
L 974: source ${metapath}/refer.tcl    → refer.tcl
L 981: source ${metapath}/gui_image.tcl    → gui_image.tcl
L 991: source ${metapath}/mc_bind.tcl    → mc_bind.tcl
L 999: source ${metapath}/mc_edit.tcl    → mc_edit.tcl
L1005: source ${metapath}/sol_menu.tcl    → sol_menu.tcl
L1011: source ${metapath}/gui_hinit.tcl    → gui_hinit.tcl
L2610: source ${metapath}/sol_buttons.tcl    → sol_buttons.tcl
L2629: source ${metapath}/gui_center.tcl    → gui_center.tcl
L2633: source ${metapath}/lighting.tcl    → lighting.tcl
L2637: source ${metapath}/sol_load_proc.tcl    → sol_load_proc.tcl
L2651: source ${metapath}/directb.tcl    → directb.tcl
L2657: source ${metapath}/surface.tcl    → surface.tcl
L2658: source ${metapath}/surfac2.tcl    → surfac2.tcl
L2664: source ${metapath}/cutplane.tcl    → cutplane.tcl
L2665: source ${metapath}/isosurf.tcl    → isosurf.tcl
L2666: source ${metapath}/partplane.tcl    → partplane.tcl
L2672: source ${metapath}/mc_animate.tcl    → mc_animate.tcl
L2676: source ${metapath}/dispobj.tcl    → dispobj.tcl
L2677: source ${metapath}/output.tcl    → output.tcl
L2678: source ${metapath}/mc_choosefont.tcl    → mc_choosefont.tcl
L2682: source ${metapath}/sol_prop.tcl    → sol_prop.tcl
L2695: source ${metapath}/univtool.tcl    → univtool.tcl
L2701: source ${metapath}/gridtools.tcl    → gridtools.tcl
L2705: source ${metapath}/colormap.tcl    → colormap.tcl
L2710: source ${metapath}/point_select.tcl    → point_select.tcl
L2715: source ${metapath}/partrac_gui2.tcl    → partrac_gui2.tcl
L2716: source ${metapath}/partrac.tcl    → partrac.tcl
L2721: source ${metapath}/convtool.tcl    → convtool.tcl
L2727: source ${metapath}/run_cmd.tcl    → run_cmd.tcl
```
**`mcfdtplt.tk`** (5 次 source)

```
L 102: source ${metapath}/mc_bind.tcl    → mc_bind.tcl
L 107: source ${metapath}/gui_hinit.tcl    → gui_hinit.tcl
L 112: source ${metapath}/gui_center.tcl    → gui_center.tcl
L 116: source ${metapath}/colormap.tcl    → colormap.tcl
L 118: source ${metapath}/bltGraph.tcl    → bltGraph.tcl
```

## 三、Source 依赖图

### 3.1 被引用频度排名

| 被引用次数 | 文件 |
|---:|---|
| 10 | `mc_bind.tcl` |
| 10 | `gui_hinit.tcl` |
| 10 | `gui_center.tcl` |
| 7 | `colormap.tcl` |
| 6 | `bltGraph.tcl` |
| 3 | `gui_image.tcl` |
| 3 | `run_cmd.tcl` |
| 2 | `mc_edit.tcl` |
| 2 | `lighting.tcl` |
| 2 | `directb.tcl` |
| 2 | `refer.tcl` |
| 2 | `dispobj.tcl` |
| 2 | `output.tcl` |
| 2 | `mc_choosefont.tcl` |
| 2 | `univtool.tcl` |
| 2 | `gridtools.tcl` |
| 2 | `point_select.tcl` |
| 2 | `partrac.tcl` |
| 1 | `mc_glovar1.tcl` |
| 1 | `mc_glovar2.tcl` |
| 1 | `mc_glovar3.tcl` |
| 1 | `mc_glovar4.tcl` |
| 1 | `bcsort.tcl` |
| 1 | `gui_menu.tcl` |
| 1 | `panic.tcl` |
| 1 | `run_mcfd.tcl` |
| 1 | `run_reyinf.tcl` |
| 1 | `unit_convert.tcl` |
| 1 | `ezsetup1.tcl` |
| 1 | `infotool.tcl` |
| 1 | `lmtool.tcl` |
| 1 | `lmcontrol.tcl` |
| 1 | `gui_buttons.tcl` |
| 1 | `edit_mcfd.tcl` |
| 1 | `recon_info.tcl` |
| 1 | `load_proc.tcl` |
| 1 | `init_dom.tcl` |
| 1 | `eqset.tcl` |
| 1 | `trange.tcl` |
| 1 | `probe.tcl` |
| 1 | `inoutfil.tcl` |
| 1 | `syscmd.tcl` |
| 1 | `cosim.tcl` |
| 1 | `species.tcl` |
| 1 | `turbname.tcl` |
| 1 | `reaction.tcl` |
| 1 | `volsour.tcl` |
| 1 | `volsoug.tcl` |
| 1 | `volsouc.tcl` |
| 1 | `gasprop.tcl` |
| 1 | `disperse.tcl` |
| 1 | `ldpprop.tcl` |
| 1 | `mixprop.tcl` |
| 1 | `riemann.tcl` |
| 1 | `spacdis.tcl` |
| 1 | `levelset.tcl` |
| 1 | `radmodp1.tcl` |
| 1 | `overlay.tcl` |
| 1 | `radmoddo.tcl` |
| 1 | `oxygenate.tcl` |
| 1 | `ps10_volsour.tcl` |
| 1 | `ps10_volsoug.tcl` |
| 1 | `vofmethod.tcl` |
| 1 | `special_mode.tcl` |
| 1 | `bcstuff.tcl` |
| 1 | `viewinf.tcl` |
| 1 | `infoset.tcl` |
| 1 | `timeint.tcl` |
| 1 | `timemark.tcl` |
| 1 | `topology.tcl` |
| 1 | `rotatec.tcl` |
| 1 | `sumo.tcl` |
| 1 | `gridvel.tcl` |
| 1 | `gridblnk.tcl` |
| 1 | `saving.tcl` |
| 1 | `rclickh.tcl` |
| 1 | `interview.tcl` |
| 1 | `wizards.tcl` |
| 1 | `coking_wizard.tcl` |
| 1 | `sdgui.tcl` |
| 1 | `conjheat.tcl` |
| 1 | `porosity.tcl` |
| 1 | `physour.tcl` |
| 1 | `gui_reset.tcl` |
| 1 | `frpl3d.tcl` |
| 1 | `topl3d.tcl` |
| 1 | `fp3dcg.tcl` |
| 1 | `fp3dss.tcl` |
| 1 | `fp3dzc.tcl` |
| 1 | `convert10.tcl` |
| 1 | `totec.tcl` |
| 1 | `hexdec.tcl` |
| 1 | `tometis.tcl` |
| 1 | `turbinit.tcl` |
| 1 | `plasma.tcl` |
| 1 | `prtout.tcl` |
| 1 | `dimension.tcl` |
| 1 | `mactool.tcl` |
| 1 | `infocopy.tcl` |
| 1 | `proftool.tcl` |
| 1 | `forcemom.tcl` |
| 1 | `interffm.tcl` |
| 1 | `ffm_ntout29.tcl` |
| 1 | `soltools.tcl` |
| 1 | `npfcuts.tcl` |
| 1 | `caa++.tcl` |
| 1 | `sixdof.tcl` |
| 1 | `miscsetup.tcl` |
| 1 | `gridcheck.tcl` |
| 1 | `cfdinfo.tcl` |
| 1 | `cellblnk.tcl` |
| 1 | `cfdbyte.tcl` |
| 1 | `commands.tcl` |
| 1 | `convert.tcl` |
| 1 | `pltdata.tcl` |
| 1 | `mc_draw.tcl` |
| 1 | `bltGraph.mcfd1dp.tcl` |
| 1 | `open_file.tcl` |
| 1 | `onedp_menu.tcl` |
| 1 | `onedp_buttons.tcl` |
| 1 | `sol_menu.tcl` |
| 1 | `sol_buttons.tcl` |
| 1 | `sol_load_proc.tcl` |
| 1 | `surface.tcl` |
| 1 | `surfac2.tcl` |
| 1 | `cutplane.tcl` |
| 1 | `isosurf.tcl` |
| 1 | `partplane.tcl` |
| 1 | `mc_animate.tcl` |
| 1 | `sol_prop.tcl` |
| 1 | `partrac_gui2.tcl` |
| 1 | `convtool.tcl` |

**说明**:

- `mc_bind.tcl` / `gui_hinit.tcl` / `gui_center.tcl` 被 8 个 .tk 共享,是 GUI 基础
- `bltGraph.tcl` / `colormap.tcl` 被 5 个绘图类 .tk 共享
- `run_cmd.tcl` 被 2 个 .tk 共享(异步任务)
- 其余 25+ 个文件只被 1 个 .tk 引用(专属后处理)

### 3.2 完整依赖树(`cfd++.tk` 视角)

```
cfd++.tk (主入口, 116 个 source)
│
├── [1] mc_glovar1.tcl         ← 全局变量 (求解器/流场)
├── [2] mc_glovar2.tcl         ← 全局变量 (网格/边界/渲染)
├── [3] mc_glovar3.tcl         ← 全局变量 (togl/求解)
├── [4] mc_glovar4.tcl         ← 全局变量 (GUI 状态)
│
├── gui_image.tcl              ← 图标/位图
├── mc_bind.tcl                ← 键盘/鼠标绑定 (8 个 .tk 共享)
├── mc_edit.tcl                ← 复制/剪切/粘贴
├── bcsort.tcl                 ← BC 排序
├── gui_menu.tcl               ← 菜单栏
├── gui_buttons.tcl            ← 工具栏
├── panic.tcl                  ← 紧急停止
│
├── run_mcfd.tcl ★             ← 求解器调用 (eval exec mcfd/mpiexec)
├── run_reyinf.tcl             ← 后处理运行
├── run_cmd.tcl ★              ← 异步任务 (blt::bgexec)
├── ezsetup1.tcl               ← 向导安装
├── syscmd.tcl                 ← 系统命令
├── infotool.tcl ★             ← blt::bgexec infotool
├── lmtool.tcl ★               ← blt::bgexec lmtool
├── lmcontrol.tcl              ← 限制控制
├── edit_mcfd.tcl              ← 编辑
│
├── 物理/边界/源 (15+ 模块)
│   ├── bcstuff.tcl, bcsort.tcl
│   ├── species.tcl, reaction.tcl
│   ├── turbname.tcl, turbinit.tcl
│   ├── gasprop.tcl, mixprop.tcl, ldpprop.tcl
│   ├── refer.tcl, riemann.tcl, spacdis.tcl
│   ├── volsour.tcl, volsoug.tcl, volsouc.tcl, ps10_volsour.tcl
│   ├── disperse.tcl, partrac.tcl
│   ├── physour.tcl, radmodp1.tcl, radmoddo.tcl
│   ├── plasma.tcl, oxygenate.tcl
│   └── porosity.tcl, conjheat.tcl, sixdof.tcl, levelset.tcl, vofmethod.tcl
│
├── Case 配置/信息集 (5 模块)
│   ├── load_proc.tcl, init_dom.tcl, eqset.tcl
│   ├── infoset.tcl (信息集编辑器, 33 procs)
│   └── viewinf.tcl (信息集查看器, 71 procs)
│
├── 网格/时间/拓扑 (8 模块)
│   ├── gridvel.tcl (36 procs), gridtools.tcl (60 procs), gridblnk.tcl, gridcheck.tcl
│   ├── timeint.tcl, timemark.tcl, trange.tcl
│   └── topology.tcl, rotatec.tcl
│
├── 输出/保存/探测 (8 模块)
│   ├── inoutfil.tcl, saving.tcl, probe.tcl (20 procs)
│   ├── totec.tcl, soltools.tcl, interffm.tcl, ffm_ntout29.tcl
│   └── forcemom.tcl, proftool.tcl, dimension.tcl
│
├── 后处理/可视化 (15+ 模块)
│   ├── directb.tcl, lighting.tcl, recon_info.tcl
│   ├── surface.tcl (33 procs), cutplane.tcl, isosurf.tcl
│   ├── partplane.tcl, partrac.tcl, partrac_gui.tcl, partrac_gui2.tcl
│   ├── output.tcl, dispobj.tcl, overlay.tcl, surfac2.tcl
│   ├── mc_animate.tcl, cellblnk.tcl, colormap.tcl, bltGraph.tcl
│   └── point_select.tcl, mc_draw.tcl, pltdata.tcl, graphs.tcl
│
└── 专用工具 (15+ 模块)
    ├── frpl3d.tcl, topl3d.tcl, fp3dcg.tcl, fp3dss.tcl, fp3dzc.tcl
    ├── tometis.tcl, convert.tcl, convert10.tcl, hexdec.tcl
    ├── wizards.tcl, wizard.tcl, coking_wizard.tcl, sdgui.tcl
    ├── cfdinfo.tcl, cfdbyte.tcl, interview.tcl, rclickh.tcl
    ├── commands.tcl, univtool.tcl, mactool.tcl, infocopy.tcl
    ├── cosim.tcl, special_mode.tcl, sum o.tcl, caa++.tcl
    ├── prtout.tcl, npfcuts.tcl, miscsetup.tcl
    ├── gui_hinit.tcl, gui_center.tcl, gui_reset.tcl
    └── onedp_buttons.tcl, onedp_menu.tcl (1DP 专用)
```

## 四、Proc 导出表

### 4.1 Proc 数最多的 30 个模块

| 排名 | 文件 | proc 数 | 累计行数(body) |
|---:|---|---:|---:|
| 1 | `viewinf.tcl` | 71 | 15245 |
| 2 | `bcstuff.tcl` | 63 | 34164 |
| 3 | `gridtools.tcl` | 60 | 14586 |
| 4 | `bltGraph.mcfd1dp.tcl` | 41 | 540 |
| 5 | `soltools.tcl` | 40 | 6978 |
| 6 | `gridvel.tcl` | 36 | 10099 |
| 7 | `bltGraph.tcl` | 35 | 543 |
| 8 | `topology.tcl` | 35 | 6353 |
| 9 | `init_dom.tcl` | 33 | 10721 |
| 10 | `surface.tcl` | 33 | 4373 |
| 11 | `run_mcfd.tcl` | 31 | 3544 |
| 12 | `mcfdsol.tk` | 28 | 2192 |
| 13 | `totec.tcl` | 27 | 8375 |
| 14 | `cutplane.tcl` | 25 | 1037 |
| 15 | `convert.tcl` | 24 | 2494 |
| 16 | `species.tcl` | 22 | 5539 |
| 17 | `turbname.tcl` | 22 | 5041 |
| 18 | `cosim.tcl` | 21 | 4279 |
| 19 | `disperse.tcl` | 21 | 5110 |
| 20 | `caa++.tcl` | 20 | 4755 |
| 21 | `gasprop.tcl` | 20 | 3963 |
| 22 | `mc_bind.tcl` | 20 | 377 |
| 23 | `probe.tcl` | 20 | 12608 |
| 24 | `reaction.tcl` | 19 | 5103 |
| 25 | `pltdata.tcl` | 18 | 780 |
| 26 | `cfdinfo.tcl` | 16 | 1484 |
| 27 | `rclickh.tcl` | 16 | 818 |
| 28 | `partrac_gui2.tcl` | 15 | 410 |
| 29 | `sol_menu.tcl` | 15 | 902 |
| 30 | `physour.tcl` | 14 | 4307 |

**前 6 大模块占据 39% 的 proc 定义**:

- `viewinf.tcl` (~15245 行): 信息集编辑器
- `bcstuff.tcl` (~34164 行): 网格工具(合并/分割/变换/区域映射)
- `gridtools.tcl` (~14586 行): 信息集查看器
- `bltGraph.mcfd1dp.tcl` (~540 行): 网格运动(平移/旋转/振荡/6DOF/网格变形)
- `soltools.tcl` (~6978 行): 探测点与残差输出文件配置
- `gridvel.tcl` (~10099 行): 物种/化学反应

### 4.2 各文件 proc 列表(主要模块)

> 完整列表太长,这里只列出 proc 数 ≥ 10 的文件。

#### `bcsort.tcl` — 5 procs

- `clean_bc_array()` L6-16
- `bc_name_compare(a b)` L18-21
- `clean_fam(alist)` L24-33
- `get_alpha_sorted_bclist()` L35-37
- `get_numeric_sorted_bclist()` L39-47

#### `bcstuff.tcl` — 63 procs

- `show_ordvarlist()` L6-193
- `bclbresize(bclisthandle)` L202-214
- `sp_add(pnlstr slen)` L217-229
- `bcmapp2(numb)` L232-1260
- `getbcinfo(title number)` L1262-1279
- `bctitle(title dumm1)` L1282-1790
- `getbctype2(title)` L1793-1795
- `change_bc(bct numbc {callwind {.}})` L1797-2193
- `bc_button(stat)` L2195-2205
- `bcframe_inout()` L2207-2400
- `bcframe_wall()` L2402-2787
- `bcframe_symm()` L2789-2802
- `bcframe_zone()` L2804-2817
- `bcframe_zone2()` L2819-3334
- `bcframe()` L3337-4127
- `getprofmes(proftyp var1 var2 var3 var4 var5)` L4129-4263
- `getbcmes(number)` L4266-6281
- `bound_flx_opt({callwind {.}})` L6283-6347
- `boundary_con({callwind {.}})` L6349-24385
- `modifiers_bc(wbc_num)` L24388-26438
- `3dnorm_hit(bnb)` L26441-26521
- `zonal2groups(bnb {callwind {.}})` L26525-26734
- `aux_vel(bnb)` L26737-26888
- `rbd152_hit(bnb)` L26890-27046
- `atmbl35_hit(bnb)` L27049-27169
- `atmbl36_hit(bnb)` L27172-27291
- `roughw_hit(bnb)` L27294-27657
- `roughw_b_hit(bnb)` L27659-28008
- `slipw_hit(bnb)` L28011-28154
- `wallact_hit(bnb)` L28156-28306
- `catw_hit(bnb)` L28308-28708
- `catw_info(bnb)` L28710-28719
- `mbelt_hit(bnb)` L28722-28863
- `wbleed_hit(bnb)` L28866-29242
- `vel_hit(bnb)` L29247-29374
- `radiat_bc(bnb)` L29377-29526
- `walltemp_hit(bnb)` L29529-29650
- `buffer_bc(bnb)` L29652-29801
- `pres2_hit(bnb)` L29804-29934
- `pres3_hit(bnb)` L29937-30068
- `xyzloc_hit(bnb)` L30071-30202
- `xyzloc2_hit(bnb)` L30205-30336
- `radeqi_hit(bnb)` L30340-30494
- `ptswirl_hit(bnb)` L30497-30620
- `dir_hit(bnb)` L30623-30703
- `swr_hit(bnb)` L30706-30785
- `masson_hit(bnb)` L30787-30837
- `deltap_bc(bnb res)` L30839-31094
- `3d_deltap_bc(bnb res)` L31097-31225
- `fanprop_bc(bnb res1 res2)` L31228-31887
- `losskl_bc(bnb res)` L31889-32124
- `deltap_fan_bc(bnb res)` L32126-32264
- `alt_bc(bnb)` L32266-32508
- `specific_bc(bnb)` L32511-32784
- `cycle4_bc(bnb)` L32786-33029
- `cycle5_bc(bnb)` L33032-33273
- `oscil_vel(bnb)` L33275-33466
- `spec_dep(bnb)` L33468-33652
- `bcmod_reset(numb)` L33655-33663
- `arb_rot(bnb)` L33665-33848
- `bleed_fix_vals()` L33853-34036
- `cycle5_bc_cath(bnb)` L34039-34280
- `plane_cath(bnb)` L34282-34341

#### `bltGraph.mcfd1dp.tcl` — 41 procs

- `Blt_ActiveLegend(graph)` L2-9
- `Blt_Crosshairs(graph)` L11-13
- `Blt_ZoomStack(graph)` L15-17
- `Blt_ZoomStackReset(graph)` L19-21
- `Blt_PrintKey(graph)` L23-25
- `Blt_ClosestPoint(graph)` L27-29
- `Blt_FindElement(graph x y)` L31-34
- `Blt_FindAxis(graph x y)` L36-39
- `Blt_PostScriptDialog(graph)` L41-43
- `blt::ActivateLegend(graph)` L51-64
- `blt::DeactivateLegend(graph)` L65-68
- `blt::HighlightLegend(graph)` L70-85
- `blt::ClickLegend(graph)` L87-90
- `blt::LegendMotion(graph x y)` L92-96
- `blt::ReleaseLegend(graph)` L98-101
- `turn_offon(graph elem on_off)` L103-114
- `FormatTickLabels(graph value)` L116-118
- `new_col(graph clr elem)` L120-122
- `blt::ChangeColor(graph  winam mx my)` L124-140
- `blt::Crosshairs(graph)` L143-150
- `blt::ZoomStackReset(graph)` L152-183
- `display_pos(x y)` L185-193
- `blt::ZoomStack(graph)` L195-223
- `blt::PrintKey(graph)` L225-228
- `blt::ClosestPoint(graph)` L230-236
- `blt::AddBindTag(graph name)` L238-243
- `blt::FindElement(graph x y)` L245-278
- `blt::FlashPoint(graph name index count)` L280-293
- `blt::GetCoords(graph x y index)` L295-352
- `blt::MarkPoint(graph index)` L354-369
- `blt::DestroyZoomTitle(graph)` L371-377
- `blt::PopZoom(graph)` L379-404
- `blt::PushZoom(graph)` L408-458
- `blt::ResetZoom(graph)` L460-472
- `blt::ZoomTitleNext(graph)` L479-489
- `blt::ZoomTitleLast(graph)` L491-497
- `blt::SetZoomPoint(graph x y)` L499-528
- `blt::ChangeDashes(graph  offset)` L535-543
- `blt::Box(graph)` L545-568
- `Blt_PostScriptDialog(graph)` L570-625
- `blt::ResetPostScript(graph)` L627-640

#### `bltGraph.tcl` — 35 procs

- `Blt_ActiveLegend(graph)` L2-9
- `Blt_Crosshairs(graph)` L11-13
- `Blt_ZoomStack(graph)` L15-17
- `Blt_PrintKey(graph)` L19-21
- `Blt_ClosestPoint(graph)` L23-25
- `blt::ActivateLegend(graph)` L32-35
- `blt::DeactivateLegend(graph)` L36-39
- `blt::HighlightLegend(graph)` L41-56
- `turn_offon(graph elem on_off)` L58-69
- `FormatTickLabels(graph value)` L71-73
- `new_col(graph clr elem)` L76-78
- `new_label(graph lbl elem)` L81-83
- `blt::ChangeColor(graph  winam mx my)` L85-101
- `apply_bltprop(graph elem)` L103-109
- `blt::ChangeProperties(graph  winam mx my)` L111-226
- `blt::Crosshairs(graph)` L228-235
- `blt::ZoomStack(graph)` L237-256
- `blt::PrintKey(graph)` L258-261
- `blt::ClosestPoint(graph)` L263-269
- `blt::AddBindTag(graph name)` L271-276
- `blt::FindElement(graph x y)` L278-311
- `blt::FlashPoint(graph name index count)` L313-326
- `blt::GetCoords(graph x y index)` L328-362
- `blt::MarkPoint(graph index)` L364-379
- `blt::DestroyZoomTitle(graph)` L381-387
- `blt::PopZoom(graph)` L389-412
- `blt::PushZoom(graph)` L416-455
- `blt::ResetZoom(graph)` L457-468
- `blt::ZoomTitleNext(graph)` L475-485
- `blt::ZoomTitleLast(graph)` L487-493
- `blt::SetZoomPoint(graph x y)` L495-518
- `blt::ChangeDashes(graph  offset)` L525-533
- `blt::Box(graph)` L535-558
- `Blt_PostScriptDialog(graph)` L560-616
- `blt::ResetPostScript(graph)` L618-631

#### `caa++.tcl` — 20 procs

- `waveprop()` L1-454
- `read_waveprop()` L456-586
- `waveprop2()` L588-884
- `read_waveprop2()` L886-974
- `waveprop_probe({callwind {.}})` L976-1098
- `wavepathi()` L1105-1335
- `read_wavepathi()` L1337-1403
- `wavepropf()` L1409-1946
- `read_wavepropf()` L1948-2143
- `wavepropf_probe()` L2145-2263
- `cylsurf()` L2266-2803
- `read_cylsurf()` L2805-2947
- `read_boxsurf()` L2948-3084
- `read_spheresurf()` L3085-3197
- `axis_sym_reintaxa()` L3201-3353
- `reintsoa()` L3356-3572
- `surface_data_maps()` L3576-3884
- `read_mcaainfo27()` L3886-3956
- `wavepropd()` L3963-4579
- `read_wavepropd()` L4582-4813

#### `cfdinfo.tcl` — 16 procs

- `cellsinf()` L5-97
- `nodesinf()` L102-194
- `exbcsinf()` L197-289
- `cdepsinf({callwind {.}})` L291-383
- `cdepsinf_sp(in_infotool)` L385-560
- `pltosinf()` L562-654
- `npfgetn()` L656-862
- `resettim()` L864-928
- `resetnt()` L930-994
- `cellvols(in_infotool {callwind {.}})` L996-1107
- `cellnors(in_infotool {callwind {.}})` L1110-1204
- `edit_mcfdbc()` L1206-1279
- `grdqual1()` L1282-1373
- `help_grdqual1()` L1376-1403
- `grdqual2()` L1407-1503
- `help_grdqual2()` L1506-1529

#### `convert.tcl` — 24 procs

- `gui_fromCGNS()` L5-54
- `gui_toCGNS()` L57-118
- `run_nastran()` L121-214
- `run_nstsurf()` L217-321
- `convert11({callwind {.}})` L324-423
- `convert12({callwind {.}})` L426-524
- `convert15()` L527-627
- `convert16()` L629-731
- `convert17()` L734-829
- `unftobin()` L832-927
- `ascii_to_nativtxt()` L929-1030
- `run_unsfast()` L1032-1149
- `run_fidap()` L1151-1247
- `run_gambit()` L1250-1327
- `run_tgrid()` L1329-1421
- `run_tgrid_binary()` L1424-1516
- `run_frflu4()` L1518-1615
- `run_starcd()` L1618-1744
- `exbcstl()` L1746-1876
- `convert6()` L1879-1999
- `convert4()` L2002-2111
- `convert4_3d()` L2114-2336
- `convert5()` L2339-2448
- `convert7()` L2451-2561

#### `cosim.tcl` — 21 procs

- `cos_fluid()` L4-68
- `floinf1_bc()` L70-192
- `cos_flux()` L195-259
- `flxinf1_bc()` L261-383
- `cos_dynam()` L386-451
- `dyninf1_bc()` L453-580
- `cosim1_bc_int()` L583-594
- `cosim1_region(set_num)` L596-972
- `cosim1_rbd_int()` L975-1005
- `cosim1_region2(set_num)` L1007-1388
- `cosim1_rbd_int2()` L1390-1422
- `cosim1_region5(set_num)` L1424-1750
- `cosim1_flux_int()` L1753-1784
- `cosim1_region3(set_num)` L1786-2171
- `cosim1_flux_int2()` L2173-2206
- `cosim1_region4(set_num)` L2208-2537
- `cosim_erosion()` L2540-2679
- `erosion_bc()` L2681-2790
- `cosim_bbblcol()` L2793-2896
- `cosim_eventindicat()` L2899-3055
- `icemain({callwind {.}})` L3064-4338

#### `cutplane.tcl` — 25 procs

- `cutting_planes({callwind {.}})` L4-217
- `cut_plane_draw()` L219-222
- `do_cut_plane()` L224-304
- `erase_cut_plane()` L306-309
- `arb_cutting_planes({callwind {.}})` L312-458
- `do_arbcut_plane()` L460-526
- `get_retval()` L533-537
- `show_acp_opengl()` L539-547
- `hide_acp_opengl()` L549-557
- `acp_select_point(x y)` L559-606
- `acp_start_pick_point(pnt)` L608-632
- `arbcut_display_cutplane_handler()` L634-665
- `arbcut_displaying_plane_p()` L667-675
- `arbcut_start_displaying_plane_p()` L677-690
- `arbcut_stop_displaying_plane_p()` L692-706
- `acp_point_button_handler(pnt)` L709-725
- `acp_picking_point_p(pnt)` L727-741
- `acp_stop_pick_point(pnt)` L743-769
- `acp_picking_multiple_p()` L771-779
- `acp_picking_single_p()` L781-793
- `acp_pick_all_points_button_handler()` L795-810
- `acp_stop_picking()` L812-829
- `acp_stop_pick_all_points()` L831-838
- `acp_start_pick_all_points()` L840-866
- `display_acp()` L868-1096

#### `directb.tcl` — 6 procs

- `read_dir(dirlist filelist filter)` L5-43
- `browse(filn {callwind {.}})` L45-226
- `browse_multiple(dir filemask {callwind {.}})` L237-666
- `browse_subdir({callwind {.}})` L669-820
- `browse_dir({callwind {.}})` L823-974
- `new_project_dir()` L977-1052

#### `disperse.tcl` — 21 procs

- `disperse_prop({callwind {.}})` L5-14
- `disperse_prop_col1({callwind {.}})` L16-175
- `disperse_info_reinterp(num nQ disable_vel reintrp_ind {callwind {.}})` L179-548
- `disperse_info(num nQ disable_vel {callwind {.}})` L552-866
- `disperse_info_sp(num nQ disable_vel {callwind {.}})` L868-1200
- `disp_calc(nn ii jj kk)` L1203-1331
- `reset_ref_disp(nn ii jj kk)` L1333-1350
- `disp_cp_comp(d_type nn)` L1353-1430
- `disperse_prop2()` L1435-1545
- `disperse_prop_gen({callwind {.}})` L1548-2055
- `hit_conden({callwind {.}})` L2058-2779
- `disp_species_win(il il2 {callwind {.}})` L2781-4479
- `set_evapspec(num)` L4481-4572
- `read_disp_species()` L4574-4925
- `write_disp_species()` L4927-5033
- `getndpsinp()` L5036-5054
- `getedpnmbtotrim(ndps_old)` L5057-5074
- `getedpinfsttotrim(numblist)` L5077-5106
- `edp_expunge(dellist)` L5109-5130
- `trim_edpinf()` L5133-5167
- `cfdpp_disp_species()` L5170-5172

#### `dispobj.tcl` — 9 procs

- `read_acap_file(filename)` L5-117
- `select_deselect_all_points(data)` L119-132
- `read_pnts_file(data)` L134-224
- `read_points_files()` L227-335
- `read_user_pnts_file(data)` L338-438
- `read_points_files()` L440-563
- `show_points({callwind {.}})` L566-1057
- `cell_data()` L1061-1281
- `manypntshandle(filename)` L1284-1560

#### `edit_mcfd.tcl` — 5 procs

- `read_file()` L5-16
- `write_file(data)` L18-32
- `save_text(textwidget)` L34-42
- `cancel_text(textwidget)` L44-52
- `edit_file()` L54-64

#### `forcemom.tcl` — 5 procs

- `force_manage({callwind {.}})` L4-703
- `write_infout1()` L706-795
- `read_infout1()` L798-1060
- `copy_entities(num)` L1062-1145
- `read_infout1_b({callwind {.}})` L1147-1308

#### `gasprop.tcl` — 20 procs

- `gas_prop({callwind {.}})` L5-890
- `nonnewt_param({callwind {.}})` L892-1253
- `udp_panel(callwd)` L1256-2329
- `anchor_pres()` L2332-2451
- `neg_pres()` L2453-2527
- `anchor_pres2()` L2531-2698
- `advdif_prop({callwind {.}})` L2702-2763
- `edflow_prop({callwind {.}})` L2767-2901
- `disp_gas_list()` L2905-3076
- `disp_liquid_list()` L3078-3335
- `liquid_mes(data)` L3338-3364
- `disp_solid_list(snum typ {callwind {.}})` L3367-3551
- `solid_mes(data)` L3553-3567
- `read_gas_data()` L3570-3583
- `read_liquid_data()` L3586-3617
- `read_solid_data()` L3620-3632
- `bulk_dens()` L3635-3842
- `set_bulktm_info()` L3845-3863
- `disp_liquid_list2({callwind {.}})` L3866-3954
- `set_liquid_data(data)` L3957-4025

#### `gridcheck.tcl` — 5 procs

- `grdqual1_discon()` L5-75
- `grdqual2_angcon()` L78-137
- `grdqual3_discon()` L140-209
- `grdqual6_discon()` L212-333
- `ifnwds_discon()` L335-411

#### `gridtools.tcl` — 60 procs

- `toaxigr()` L6-326
- `toxax_pie_360(chc)` L329-610
- `tohelixgr()` L612-897
- `celretyp()` L899-1065
- `inbtoexb()` L1067-1246
- `run_inbcalin({callwind {.}})` L1248-1324
- `inbcsep2()` L1326-1466
- `scalegr()` L1468-1802
- `ltrangr()` L1804-2067
- `rotatgr()` L2069-2332
- `rotgro()` L2335-2643
- `exbcsepa()` L2645-2857
- `exb2exin()` L2859-3008
- `exbgeom34({callwind {.}})` L3010-3196
- `exbgeom1()` L3198-3329
- `exbcsren()` L3332-3487
- `exbcorph()` L3490-3581
- `exbcsund()` L3584-3728
- `exbcmod()` L3730-4051
- `grid_set({callwind {.}})` L4053-4911
- `edit_mcfdgrps(mgrp {callwind {.}})` L4913-4980
- `group_name_info_set()` L4982-5015
- `write_mcfdgrp_new(mgrp)` L5017-5037
- `concat_tool()` L5039-5318
- `concat1_tool()` L5321-5856
- `scan_dir_for_mult_cgrps(dir)` L5858-5883
- `get_znumber(fn)` L5885-5894
- `scan_dir_for_cgrps(dir)` L5896-5917
- `test_for_mult_cgrps(sub_dir)` L5919-5926
- `find_first_cgrps_file(sub_dir)` L5928-5934
- `write_mcfdbc({callwind {.}})` L5936-5964
- `meshcat1_tool()` L5968-6381
- `write_mcfdbc_new({callwind {.}})` L6384-6412
- `nodeseli()` L6416-6553
- `nodesmap()` L6555-6787
- `zobmerge()` L6789-7056
- `exbmerge()` L7058-7312
- `exbcutp1()` L7314-7680
- `exbcutp2()` L7682-8161
- `exbcroco()` L8163-8234
- `exbcsmap()` L8237-8547
- `pick_bcs()` L8550-8650
- `mirrmsh()` L8654-9110
- `mirrcgr1_gui()` L9112-9236
- `exbstat1({callwind {.}})` L9238-9365
- `fix_cellfix1({callwind {.}})` L9367-9537
- `gui_celreord({callwind {.}})` L9540-10041
- `cellgrup1()` L10044-10403
- `cellgrup2()` L10405-10906
- `subsets5()` L10909-11282
- `run_sub_hint(sub cmd)` L11285-11331
- `cgrpsmap()` L11334-11663
- `subsets7()` L11665-12547
- `toponew1()` L12550-12761
- `subsets8()` L12764-12979
- `rollback()` L12981-14187
- `inbcskeep()` L14190-14424
- `mpf3d_gennew(typ)` L14427-14512
- `dfcelmax()` L14515-14613
- `cgrpnod()` L14616-14736

#### `gridvel.tcl` — 36 procs

- `grid_speeds()` L5-697
- `submen_gridvel()` L701-799
- `grid_speeds_1()` L802-814
- `gvel_region_1(set_num)` L818-1204
- `grid_speeds_7()` L1207-1219
- `gvel_region_7(set_num)` L1222-1657
- `grid_speeds_9()` L1662-1674
- `gvel_region_9(set_num)` L1677-2132
- `grid_speeds_13()` L2135-2147
- `gvel_region_13(set_num)` L2150-2584
- `grid_speeds_14()` L2587-2599
- `gvel_region_14(set_num)` L2602-3063
- `grid_speeds_10()` L3066-3078
- `gvel_region_10(set_num)` L3081-3402
- `grid_speeds_18()` L3406-3418
- `gvel_region_18(set_num)` L3421-3748
- `grid_speeds_19()` L3751-3763
- `gvel_region_19(set_num)` L3765-4089
- `grid_speeds_20()` L4092-4104
- `gvel_region_20(set_num)` L4106-4431
- `grid_speeds_21()` L4434-4446
- `gvel_region_21(set_num)` L4448-4773
- `grid_speeds_22()` L4777-4789
- `gvel_region_22(set_num)` L4791-5119
- `grid_speeds_23()` L5122-5134
- `gvel_region_23(set_num)` L5136-5466
- `grid_speeds_30()` L5468-5480
- `gvel_region_30(set_num)` L5482-6312
- `grid_speeds_31()` L6315-6327
- `gvel_region_31(set_num)` L6329-6843
- `grid_speeds_27()` L6846-6858
- `gvel_region_27(set_num)` L6861-7273
- `grid_speeds_29()` L7276-7288
- `hit_gvel29_gui(mode ind infnmb)` L7291-7311
- `disable_inf(ind infnmb)` L7314-7343
- `gvel_region_29(set_num)` L7346-10207

#### `gui_hinit.tcl` — 7 procs

- `gen_help(fil)` L7-30
- `cur_help(fil)` L32-79
- `cur_help_old(fil)` L83-107
- `help_reset()` L109-114
- `help_about()` L116-139
- `help_roughwall()` L142-179
- `help_wall_motion()` L182-204

#### `gui_menu.tcl` — 6 procs

- `help_genreset()` L739-744
- `add_frame_bc()` L1908-1961
- `bc_turnon()` L1964-1974
- `norm_turnon(j)` L1976-1986
- `bc_turnon2()` L1990-2001
- `boundary_manage({callwind {.}})` L2004-2170

#### `infotool.tcl` — 9 procs

- `cellvols_w()` L2-17
- `cellnors_w()` L19-34
- `cdepsinf_sp_w()` L36-51
- `browse_files_w()` L53-69
- `browse_files()` L71-219
- `it_cellvols()` L222-329
- `it_cellnors()` L331-418
- `it_cdepsinf_sp()` L420-586
- `cmd_tools()` L588-827

#### `init_dom.tcl` — 33 procs

- `updateusedstat(refinf)` L8-16
- `init_domain({callwind {.}})` L18-363
- `cellr_t()` L365-926
- `groupr_t()` L928-1487
- `groupsbr_t()` L1489-2092
- `xyzbr_t()` L2094-2665
- `cylin_t(cyltyp)` L2667-3263
- `init_con()` L3266-3893
- `init_coni()` L3895-4553
- `init_dep({callwind {.}})` L4555-5139
- `init_region(set_num)` L5142-5545
- `init_infset({callwind {.}})` L5547-5565
- `init_con_reg({callwind {.}})` L5567-5807
- `init_coni_reg({callwind {.}})` L5809-6082
- `getmes_init()` L6084-6211
- `getmes_init2()` L6214-6341
- `getmes_init3()` L6343-6468
- `getmes_init4()` L6470-6595
- `getmes_init9()` L6597-6681
- `init_xyzbox(set_num)` L6683-7371
- `init_infset2()` L7373-7391
- `init_con_box()` L7393-7635
- `init_coni_box()` L7637-7911
- `init_group(set_num)` L7915-8401
- `init_infset3()` L8403-8421
- `init_con_grp()` L8423-8667
- `init_coni_grp()` L8669-8933
- `init_xyzcyl(set_num cyltyp)` L8937-9398
- `init_infset4()` L9400-9418
- `init_con_cyl()` L9420-9669
- `init_coni_cyl()` L9671-9952
- `init_groupsbr(set_num)` L9954-10523
- `init_coni_grpsbr()` L10525-10800

#### `interffm.tcl` — 10 procs

- `max(x y)` L4-4
- `max3(x y z)` L6-6
- `initialize_new_workarray(box_no)` L8-60
- `update_workarray(box_no infonum)` L62-137
- `initialize_infoset(box_no infonum)` L139-175
- `update_infoset(box_no infonum)` L178-279
- `save_info_for_cancel(infonum)` L281-318
- `put_info_for_cancel(infonum)` L321-358
- `interior_ffm(set_num {callwind {.}})` L362-2783
- `rstrtcellgrp({callwind {.}} pln {pntr {1}})` L2786-3000

#### `ldpprop.tcl` — 13 procs

- `ldp_prop({callwind {.}})` L6-214
- `ldp_species_win(il il2 {callwind {.}})` L217-917
- `ldp_injprop(num)` L919-1234
- `ldp_extraprop(num)` L1236-1436
- `set_evapspec_ldp(num)` L1440-1531
- `read_ldp_species()` L1533-1535
- `write_ldp_species()` L1537-1540
- `getnldpsinp()` L1543-1560
- `getldpnmbtotrim(nldps_old)` L1563-1580
- `getldpinfsttotrim(numblist)` L1583-1612
- `ldp_expunge(dellist)` L1615-1636
- `trim_ldpinf()` L1639-1672
- `cfdpp_ldp_species()` L1674-1676

#### `levelset.tcl` — 7 procs

- `level_sets()` L4-254
- `level_set_init()` L256-419
- `ls_init_coni()` L421-609
- `ls_init_plane_t()` L612-780
- `ls_init_region(set_num)` L782-1031
- `level_set_bc()` L1033-1130
- `ls_numerics({callwind {.}})` L1133-1542

#### `load_proc.tcl` — 5 procs

- `load_proc()` L5-3554
- `bcmapper(title numb)` L3556-5171
- `bcfam_set(bct num)` L5173-5232
- `set_rieflx_info(num)` L5235-5727
- `set_riejac_info(num rief)` L5729-5835

#### `mc_bind.tcl` — 20 procs

- `platform_is_windows()` L10-13
- `Is_Window_Packed(window)` L42-50
- `dialog_wait(wind)` L52-64
- `dialog_wait2(wind)` L71-82
- `exit3()` L128-149
- `exit2()` L151-157
- `tk_dialog2(w title text bitmap default args)` L162-288
- `isnumb(numb)` L314-316
- `verify_numb(val)` L319-321
- `verify_real(val)` L323-329
- `verify_int(val)` L331-337
- `output_1(tit tx tt)` L340-356
- `output_1a(tit tx tt {callwind {.}})` L359-379
- `output_2(tit tx sz)` L382-397
- `output_2a(tit tx sz {callwind {.}})` L400-415
- `slash_change(str)` L418-437
- `configure_subwindow(win)` L439-441
- `set_win_min_size(win)` L446-449
- `check_v_state(infnum ind {callwind {.}})` L451-488
- `tk_hint1(w title text args {callwind {.}})` L490-537

#### `mcfd1dp.tk` (入口) — 11 procs

- `create_f0()` L2096-2267
- `ify1_hit()` L2269-2283
- `ify2_hit()` L2285-2299
- `display_varbox(oldName newName op)` L2301-2404
- `display_varbox2(oldName newName op)` L2406-2511
- `file_zone()` L2513-2536
- `get_elem_name()` L2538-2602
- `get_axis_name()` L2604-2650
- `graph2()` L2651-3236
- `set_axis_mnmx({callwind {.}})` L3238-3553
- `axis_limits()` L3556-3616

#### `mcfdfft.tk` (入口) — 11 procs

- `set_intervals(lmin lmax)` L76-86
- `graph_res()` L176-644
- `axis_change()` L646-869
- `array_max(ydataname)` L871-880
- `array_min(ydataname)` L882-891
- `read_files()` L894-1116
- `typdef(data)` L1118-1126
- `dwncnvrtfil(data)` L1128-1145
- `read_data(data)` L1147-1410
- `set_axis_mnmx2(xorydata xorymax xorymin xoryint vxmin vxmax)` L1413-1452
- `axis_limits()` L1455-1502

#### `mcfdfplt.tk` (入口) — 9 procs

- `graph_res()` L124-451
- `axis_change()` L453-810
- `rev_val(resi)` L813-841
- `mx_res(resi)` L843-873
- `mn_res(resi)` L875-905
- `read_files()` L907-974
- `read_data(data)` L977-2205
- `set_axis_mnmx(var_name)` L2207-2300
- `axis_limits()` L2302-2339

#### `mcfdplt2.tk` (入口) — 8 procs

- `graph_res()` L134-746
- `axis_change()` L748-1086
- `mx_res(resi)` L1089-1095
- `mn_res(resi)` L1097-1103
- `res_max_p()` L1106-1123
- `res_ulim()` L1126-1137
- `res_refresh()` L1139-1243
- `axis_limits()` L1246-1280

#### `mcfdpplt.tk` (入口) — 11 procs

- `graph_res()` L124-387
- `axis_change()` L389-739
- `mx_res(resi)` L741-748
- `mn_res(resi)` L750-757
- `read_files()` L759-864
- `typdef(data)` L866-874
- `dwncnvrtfil(data)` L876-893
- `getntout(nmb)` L895-909
- `read_data(data)` L911-1114
- `set_axis_mnmx(var_name1 var_name2)` L1116-1198
- `axis_limits()` L1200-1238

#### `mcfdsol.tk` (入口) — 28 procs

- `lremove(listVariable value)` L854-858
- `mcfd_lsort(un_list)` L860-884
- `init_ptrk()` L886-907
- `check_mcfdinp()` L1014-1039
- `PlaceMove(fract)` L1091-1104
- `Place(fract)` L1106-1127
- `print_f_proc()` L1359-1402
- `write_this_xyz(x y z jkl)` L1545-1555
- `save_browse({callwind {.}})` L1743-1908
- `viewpoint_load_tcl(load_mode {callwind {.}})` L1911-1948
- `viewpoint_save_tcl(save_mode {callwind {.}})` L1950-1964
- `view_grid_boun({callwind {.}})` L1966-2205
- `convert_tcl_to_gl_font(font_prop)` L2207-2215
- `save_surface_and_contour_manager_state()` L2217-2229
- `refresh_bound()` L2231-2340
- `refresh_noread({callwind {.}})` L2342-2428
- `set_gl_control()` L2431-2580
- `lock_current_view()` L2584-2605
- `npf0geom()` L2729-2787
- `mpf3dav()` L2790-2886
- `mpf3dget1()` L2889-2989
- `npfgetn()` L2993-3197
- `toactran(callwind)` L3199-3459
- `load_file_cmd()` L3461-3694
- `prep_for_load()` L3700-3779
- `anim_spin_control()` L3781-3881
- `arbitrary_rotate()` L3883-3942
- `init_mcfdsol_c()` L3947-3949

#### `mcfdtplt.tk` (入口) — 8 procs

- `graph_res()` L129-730
- `axis_change()` L732-1077
- `mx_res(resi)` L1080-1148
- `mn_res(resi)` L1150-1218
- `res_max_p()` L1221-1238
- `res_ulim()` L1241-1252
- `res_refresh()` L1254-1346
- `axis_limits()` L1349-1361

#### `mixprop.tcl` — 13 procs

- `mixture_prop({callwind {.}})` L4-194
- `mix_species_win(il il2 {callwind {.}})` L197-630
- `read_mix_species()` L632-634
- `write_mix_species()` L636-638
- `getnmixsinp()` L641-658
- `getmixnmbtotrim(nmixs_old)` L661-678
- `getmixinfsttotrim(numblist)` L681-710
- `mix_expunge(dellist)` L713-734
- `trim_mixinf()` L737-770
- `cfdpp_mix_species()` L772-774
- `mix_info(num nQ {callwind {.}})` L777-870
- `hit_cavitat({callwind {.}})` L873-1450
- `hit_evapcond({callwind {.}})` L1452-1848

#### `onedp_menu.tcl` — 5 procs

- `save_onedp(save_mode)` L81-93
- `reload_onedp()` L128-175
- `load_onedp()` L177-263
- `autoload_onedp()` L266-344
- `find_common_vartit()` L346-385

#### `oxygenate.tcl` — 6 procs

- `oxygenate({callwind {.}})` L4-435
- `oxygenate_bc()` L439-556
- `bctitle_rad10(title dumm1)` L560-575
- `getbcinfo_rad10(title numb)` L577-594
- `getbctype_rad10(title)` L597-599
- `cp_boun10(name_widget)` L601-875

#### `panic.tcl` — 12 procs

- `panic_button()` L1-109
- `panic_stop1()` L112-193
- `panic_stop2()` L196-271
- `panic_stop3()` L274-363
- `panic_acap_axis()` L366-428
- `panic_acap_ffbound()` L431-500
- `panic_acap_highspeed()` L503-590
- `panic_acap_wall()` L592-663
- `panic_acap_general()` L666-737
- `panic_stop5()` L739-808
- `panic_stop10()` L810-866
- `check_input_file()` L868-1047

#### `partrac_gui2.tcl` — 15 procs

- `change_ts_per_frame_handler(speed)` L1-8
- `change_fps_handler(speed)` L10-24
- `change_disp_mode_handler(mode)` L26-33
- `play_all_sets_handler()` L35-38
- `stop_all_sets_handler()` L40-43
- `ptrk_particle_load_button_handler()` L45-67
- `change_color_mode_handler(set mode)` L69-78
- `change_display_handler(set mode)` L80-92
- `synch_color_mode(mode)` L94-106
- `synch_particle_sets_loaded()` L108-183
- `change_line_thickness_handler(set speed)` L185-192
- `show_ptr_disp_options(set)` L195-311
- `choose_track_color_helper(set)` L313-324
- `choose_set_color(set)` L326-357
- `partrack_gui({callwind {.}})` L363-444

#### `physour.tcl` — 14 procs

- `udprhs({callwind {.}})` L5-163
- `synjet({callwind {.}})` L166-1081
- `axi_swirl()` L1083-1238
- `blck_source()` L1241-1368
- `absorb_layer({callwind {.}})` L1371-1721
- `abs_infinity_set()` L1724-1891
- `rotmod1_data({callwind {.}})` L1894-1905
- `rotmod1_region(set_num {callwind {.}})` L1907-2751
- `rotmod1_data2()` L2754-3035
- `rotmod1_trim_data()` L3037-3048
- `rotmod1_trim_region(set_num)` L3050-3501
- `sinusoid_bodyf()` L3504-3673
- `vort_sour2d({callwind {.}})` L3676-3990
- `vort_sour3d({callwind {.}})` L3993-4347

#### `plasma.tcl` — 5 procs

- `plasma_act({callwind {.}} plasma_model)` L4-739
- `plasma_MHD_source({callwind {.}})` L746-850
- `plasma_LEC_source({callwind {.}})` L857-1001
- `plasma_LEC_tool({callwind {.}})` L1003-1582
- `plasma_LEC_device_solver({callwind {.}})` L1589-1977

#### `pltdata.tcl` — 18 procs

- `pltdata(graph labx laby)` L4-41
- `pltdat2(graph labx laby)` L43-65
- `valv_plt(graph flow time1 time2 time3 new_old)` L68-92
- `valp_plt(graph flow1 flow2 press1 press2 new_old)` L94-119
- `pltvis(graph labx laby)` L121-158
- `pltvis2(graph labx laby)` L160-182
- `visc_plt(graph isp mult new_old)` L184-255
- `pltcpr(graph labx laby)` L259-296
- `pltcpr2(graph labx laby)` L298-320
- `cpr_plt(graph isp new_old)` L322-381
- `plthrt(graph labx laby)` L383-420
- `plthrt2(graph labx laby)` L422-444
- `hrt_plt(graph isp new_old)` L446-552
- `pltcon(graph labx laby)` L554-591
- `pltcon2(graph labx laby)` L593-615
- `cond_plt(graph isp mult new_old)` L617-688
- `gen_lab(loc_arg1 loc_arg2)` L690-693
- `hrt_gas_ret(temperature disp_num)` L696-822

#### `point_select.tcl` — 5 procs

- `clear_point_select_display()` L31-49
- `clear_point_select_points()` L52-56
- `leave_point_select()` L58-75
- `enter_point_select()` L77-95
- `display_point_select()` L97-267

#### `probe.tcl` — 20 procs

- `probe_res({callwind {.}})` L5-8111
- `remove_probe(num)` L8114-8128
- `prob_stat(num)` L8130-8827
- `cel_centroid({callwind {.}})` L8829-8928
- `xyz_celno({callwind {.}})` L8930-9079
- `xyz_nodno({callwind {.}})` L9081-9141
- `cinfout2()` L9143-9234
- `cinfout3()` L9236-9327
- `read_file_main(file_type {callwind {.}})` L9329-9396
- `probe_buttons()` L9398-9619
- `probe_all()` L9621-9674
- `probe_srf()` L9676-9712
- `probe_ffm()` L9715-9741
- `probe_bp()` L9743-9774
- `probe_cn()` L9776-9805
- `probe_other()` L9807-9853
- `bcsptrb_hit()` L9855-9946
- `hit_ran2()` L9948-10048
- `bcptrb_hit2()` L10051-10244
- `primitive_plansurf(set_num {callwind {.}})` L10252-12660

#### `proftool.tcl` — 14 procs

- `profile_tool()` L4-188
- `prof_copy_var()` L190-299
- `prof_hit_nvar()` L301-405
- `read_profile()` L407-477
- `write_profile()` L479-533
- `1dto3dprof()` L538-771
- `check_consistency()` L773-872
- `run_check_consistency(widget)` L873-997
- `check_no()` L1000-1050
- `read_inp_file()` L1052-1075
- `conv_1dto3dprof(widget)` L1080-1120
- `check_dv_consistent()` L1124-1135
- `creat3dprof()` L1137-1219
- `conv_bin()` L1221-1227

#### `radmoddo.tcl` — 8 procs

- `radmod_do()` L4-271
- `radmod_do_bc()` L274-457
- `bctitle_rad9(title dumm1)` L460-485
- `getbcinfo_rad9(title numb)` L487-504
- `getbctype_rad9(title)` L507-509
- `cp_boun9(name_widget)` L511-786
- `ps9_update_bc(numb)` L789-814
- `ps9_bcval(numb)` L817-2014

#### `radmodp1.tcl` — 9 procs

- `radmod_p1()` L4-191
- `ps_numerics({callwind {.}})` L193-650
- `radmod_p1_bc()` L652-803
- `bctitle_rad5(title dumm1)` L806-823
- `getbcinfo_rad5(title numb)` L825-842
- `getbctype_rad5(title)` L845-847
- `cp_boun5(name_widget)` L849-1124
- `ps5_update_bc(numb)` L1127-1144
- `ps5_bcval(numb)` L1147-1742

#### `rclickh.tcl` — 16 procs

- `help_eqset({callwind {.}})` L5-24
- `help_sysb({callwind {.}})` L27-37
- `help_syse({callwind {.}})` L39-49
- `help_ifile({callwind {.}})` L51-124
- `help_ofile({callwind {.}})` L126-199
- `help_probe({callwind {.}})` L201-267
- `help_reac({callwind {.}})` L269-333
- `help_species({callwind {.}})` L338-401
- `help_gasp({callwind {.}})` L403-437
- `help_turb({callwind {.}})` L439-476
- `help_refer({callwind {.}})` L478-540
- `help_trange({callwind {.}})` L542-553
- `help_riem({callwind {.}})` L555-619
- `help_space({callwind {.}})` L621-739
- `help_time({callwind {.}})` L741-823
- `help(window message_in mx my {callwind {.}})` L827-859

#### `reaction.tcl` — 19 procs

- `read_reactions()` L5-314
- `read2_reactions(br_off filn)` L316-668
- `write_reactions()` L671-739
- `write2_reactions()` L741-809
- `write2_reactions_v3()` L811-931
- `avail_react()` L933-1107
- `reaction({callwind {.}})` L1110-2581
- `set_presrate(num)` L2583-2863
- `set_3rdbody(num)` L2865-2946
- `ignite_box({callwind {.}})` L2949-3352
- `ignit_off_box()` L3355-3366
- `ignit_off_region(set_num)` L3369-3872
- `massinj_box({callwind {.}})` L3875-4383
- `massinj_values(num {callwind {.}})` L4386-4475
- `reaction_infoset()` L4477-4639
- `tflame_param()` L4642-4755
- `srcsoug_group({callwind {.}})` L4765-4980
- `srcsoug_values(num)` L4983-5050
- `srcsoug_groups(num)` L5052-5161

#### `recon_info.tcl` — 6 procs

- `recon_info(num {callwind {.}})` L6-4092
- `adjcut(infdel)` L4095-4126
- `zerousedstat(infno)` L4129-4139
- `drefcutinf()` L4143-4158
- `onernkrestatrnkinf(infrow)` L4161-4173
- `onernkrestatcutinf(startrow nocuts)` L4176-4205

#### `riemann.tcl` — 5 procs

- `riemann({callwind {.}})` L5-987
- `rieman_stat()` L989-1097
- `precon_message()` L1100-1144
- `hit_carbuncle()` L1147-1211
- `diff_modify()` L1214-1506

#### `run_cmd.tcl` — 5 procs

- `get_directory_global()` L4-7
- `run_cmd(clt_cmd detach)` L9-296
- `get_proc_mem(pid)` L304-325
- `watch_proc_mem(job_name pid)` L327-353
- `run_cmd_DEPRECATED(clt_cmd detach)` L368-513

#### `run_mcfd.tcl` — 31 procs

- `get_win32_path(r4r8)` L6-16
- `which_mcfdrun({callwind {.}})` L18-119
- `mcfd_stop()` L121-126
- `run_mcfd()` L129-154
- `run_mcfd_back()` L156-178
- `view_log2()` L180-185
- `kill_mcfd()` L187-192
- `run_mcfdplt()` L194-200
- `run_mcfdplt_ps()` L202-208
- `run_mcfdtplt()` L210-216
- `run_mcfdrhsgi()` L218-224
- `run_mcfd1dp()` L226-232
- `run_mcfdsol()` L234-244
- `run_mcfdfplt()` L246-252
- `run_mcfdfft()` L254-260
- `run_mcfdpplt()` L262-268
- `view_log()` L271-277
- `run_dfcells()` L279-285
- `run_multicpu()` L287-1339
- `read_button_display(name1 name2 op)` L1341-1353
- `root_process_display(name1 name2 op)` L1355-1375
- `mpi_queue_val(name1 name2 op)` L1377-1390
- `read_file_mcpu()` L1392-1443
- `which_cfluse({callwind {.}})` L1445-1513
- `run_multicpu_tool(tooln toolargs {callwind {.}})` L1520-2623
- `tometis_frame()` L2625-2804
- `xyzmetis_frame()` L2806-2904
- `xyzdec_frame()` L2906-3057
- `read_button_display(name1 name2 op)` L3059-3071
- `multicpu_buff_size()` L3121-3648
- `multicpu_org_io()` L3650-3665

#### `saving.tcl` — 6 procs

- `save_as()` L5-7
- `save({callwind {.}})` L9-33
- `save_do()` L36-4652
- `what_to_save()` L4654-4915
- `save_browse()` L4917-5082
- `view_save_browse({callwind {.}})` L5084-5249

#### `sixdof.tcl` — 10 procs

- `hit_rbdcouple({callwind {.}})` L5-125
- `sixdof_bodies({callwind {.}})` L129-1902
- `body_prop(bnum)` L1905-2207
- `body_bcsel(numb)` L2210-2277
- `body_extforce(numb)` L2280-2386
- `body_bfm(numb)` L2389-2604
- `body_scale_fac(numb)` L2606-2831
- `write_bodies()` L2833-3140
- `exbcgrav()` L3143-3287
- `body_speed_info(bnum)` L3290-3449

#### `sol_load_proc.tcl` — 5 procs

- `sol_load_proc({callwind {.}})` L5-25
- `bcmapper(title numb)` L28-570
- `bcfam_set(bct num)` L572-606
- `set_rieflx_info(num)` L609-821
- `set_riejac_info(num rief)` L823-869

#### `sol_menu.tcl` — 15 procs

- `get_btns(btn_set)` L399-467
- `load_npfparam()` L470-529
- `show_param_lbox(param_type callwind)` L532-554
- `init_expr()` L557-566
- `expr_keyattrib(nkey key expr_keyset)` L569-594
- `expr_help(gui_type)` L597-607
- `expr_gen(btn_set param_gui no_btns no_rows no_col equals_ac...)` L610-1186
- `run_mcfdplt()` L1189-1195
- `deadbtn()` L1198-1201
- `undercrn()` L1203-1206
- `expwellposed()` L1209-1257
- `chkasgnop(linedta)` L1260-1268
- `chknewvar(linedta)` L1271-1281
- `getnewexpr(fixtyp linedta varnmb)` L1284-1306
- `add_frame_bc()` L1352-1385

#### `sol_prop.tcl` — 5 procs

- `set_qmm()` L5-141
- `set_colormap({callwind {.}})` L144-744
- `color_button_set()` L746-883
- `getXLFD(curr_fon)` L887-912
- `change_text_color(var1 var2 var3 var4)` L915-1079

#### `soltools.tcl` — 40 procs

- `reintsol()` L5-401
- `reint_extra_vals()` L403-677
- `dataint()` L680-1036
- `cdepsmod()` L1038-1224
- `cdepsmog()` L1226-1423
- `solmodfb()` L1425-1941
- `solmodfc()` L1943-2465
- `solmodfs()` L2467-2975
- `average_npf()` L2977-3073
- `subtract_npf()` L3075-3156
- `pltrenod_npf()` L3158-3331
- `exbc2do1()` L3335-3421
- `ebnpnas1()` L3423-3602
- `rotatso()` L3605-3689
- `rotatso()` L3692-3900
- `cdepscat2()` L3902-4038
- `steady_unsteady({callwind {.}})` L4040-4280
- `mpf3dav()` L4284-4564
- `mpf3dget1()` L4566-4668
- `npftocdeps()` L4672-4938
- `npf0geom()` L4940-4997
- `mirrnpf1()` L5001-5324
- `mpf1d_extract_cols()` L5326-5555
- `npf_probes(type)` L5558-5838
- `toactran(callwind)` L5840-6100
- `misc_tools_list(callwind)` L6102-6112
- `read_tool_list()` L6114-6179
- `clean_tool_array_tdisp()` L6181-6190
- `clean_tool_array_catg()` L6192-6201
- `clean_tool_array_skey(str_key)` L6203-6217
- `tname_compare(a b)` L6219-6222
- `clean_fam(alist)` L6224-6233
- `get_tdisp_sorted_tlist()` L6235-6237
- `get_category_sorted_tlist()` L6238-6240
- `get_seach_key_tlist(str_key)` L6241-6243
- `tool_list({callwind {.}})` L6245-6395
- `tool_cmd(tin)` L6397-6565
- `show_file(inpfilename)` L6568-6646
- `reintaxr()` L6650-6801
- `boundlay_npf2lin1()` L6804-7075

#### `special_mode.tcl` — 8 procs

- `spm3_params()` L4-154
- `spm3_bc()` L157-268
- `bctitle_spm3(title dumm1)` L271-282
- `getbcinfo_spm3(title numb)` L284-301
- `getbctype_spm3(title)` L304-306
- `cp_spm3(name_widget)` L308-575
- `spm3_bcval(numb)` L578-784
- `spm3_ic()` L786-985

#### `species.tcl` — 22 procs

- `gas_prop2({callwind {.}})` L5-789
- `prop_ifkndf()` L792-1109
- `gas_prop4({callwind {.}})` L1115-1222
- `gas_prop3({callwind {.}})` L1227-1648
- `hit_ifsrtn()` L1650-1708
- `species_enter()` L1711-1838
- `species_liquid_enter()` L1840-1944
- `species_win(il il2)` L1946-2682
- `species_win_liq(il il2)` L2685-3153
- `read_species()` L3155-3449
- `write_species()` L3451-3521
- `cfdpp_species()` L3524-4055
- `cfdpp_species_direct(spec_sym)` L4057-4396
- `cfdpp_species_liq()` L4398-4565
- `species_reactions_direct()` L4568-4740
- `species_infosets()` L4742-4873
- `remove_species_info()` L4875-5001
- `spec_info(num nQ {callwind {.}})` L5004-5133
- `spec_info_old(num nQ)` L5138-5267
- `vof_info(num nQ {callwind {.}})` L5270-5363
- `spec_mole_to_mass(num nQ)` L5366-5493
- `cat_eff_info(num imode)` L5495-5604

#### `sumo.tcl` — 6 procs

- `sumo()` L1-63
- `sumo_defn()` L66-378
- `cp_from_globals()` L380-399
- `cp_2_globals()` L401-420
- `set_defaults()` L422-447
- `sumodn_create_file()` L449-486

#### `surface.tcl` — 33 procs

- `surface_manage({callwind {.}})` L11-22
- `bc_turnon()` L24-38
- `all_grid_on()` L40-58
- `bc_turnon2()` L60-75
- `sol2d_turnon()` L77-89
- `surface_manage_new({callwind {.}})` L91-286
- `fill_right_entity(entity)` L289-1274
- `part_var_color()` L1276-1347
- `redo_cutpln(cut_num {callwind {.}})` L1349-1368
- `dup_cutpln(cut_num)` L1370-1407
- `all_grid_on_new()` L1410-1440
- `bc_turnon_new()` L1442-1447
- `bc_turnon_new_vec()` L1449-1455
- `cutpl_turnon_new()` L1457-1467
- `part_turnon_new()` L1469-1474
- `sl2d_turnon_new()` L1477-1482
- `display_contour_manager({callwind {.}})` L1484-1916
- `refresh_selections()` L1919-2027
- `vec2d_control({callwind {.}})` L2029-2262
- `vecbc_control(num {callwind {.}})` L2265-2476
- `vecbc3d_control(num {callwind {.}})` L2480-2691
- `vcut_control(num {callwind {.}})` L2694-2906
- `vcut3d_control(num {callwind {.}})` L2907-3119
- `gridbc_control(num)` L3121-3273
- `grid2d_control()` L3275-3360
- `gridcut_control(num)` L3362-3512
- `contbc_control(num {callwind {.}})` L3515-3628
- `cont2d_control()` L3630-3743
- `contcut_control(num)` L3745-3857
- `cont_type_control(cv)` L3859-4017
- `cont_prop_bc_control(num)` L4019-4198
- `cont_prop_cut_control(num)` L4200-4372
- `cont_prop_2d_control()` L4374-4456

#### `timeint.tcl` — 14 procs

- `time_int({callwind {.}})` L4-503
- `time_int2()` L506-945
- `time_int3()` L947-1797
- `time_int4()` L1801-2719
- `time_int5()` L2722-3087
- `mbl_opt()` L3093-3161
- `multigrid_t({callwind {.}})` L3163-3754
- `help_set_CFL({callwind {.}})` L3757-5159
- `read_cflloc({callwind {.}})` L5162-5179
- `time_edgui({callwind {.}})` L5182-5336
- `formom_conv()` L5338-5421
- `formom_conv1()` L5424-5569
- `formom_conv2()` L5572-6024
- `color_update()` L6027-6119

#### `timemark.tcl` — 7 procs

- `time_marker({callwind {.}})` L4-160
- `tcyc_gb({callwind {.}})` L164-350
- `time_mark_calc()` L352-531
- `tcyc_react()` L533-652
- `tcyc_rsource()` L655-776
- `tcyc_rmassi()` L779-898
- `tcyc_bc0098(numb)` L901-997

#### `topology.tcl` — 35 procs

- `flag_non_osetpatch()` L5-42
- `resurv_screfinf()` L44-90
- `surveyaltbc()` L93-116
- `surveyaltbcunused(altbc_used)` L119-149
- `renum_seqcutinf(altbc_unused nrnks ncuts)` L152-183
- `renum_regcutinf(altbc_unused)` L186-206
- `altbc_expunge(altbc_unused)` L209-230
- `altbc_clnup()` L233-247
- `overset_type()` L250-1318
- `sc_hint_orphan()` L1320-1352
- `chk_scinf_used2(infon)` L1354-1371
- `sc_oset4_t({callwind {.}} {liveinf {1}})` L1373-1575
- `oset5_t()` L1577-1790
- `sc_oset5_t({callwind {.}} {liveinf {1}})` L1793-2005
- `oset6_t()` L2008-2220
- `sc_oset6_t({callwind {.}} {liveinf {1}})` L2223-2434
- `chk_scinf_used(infon)` L2436-2454
- `sc_oset_t({callwind {.}} {cutinfset {1}})` L2457-2661
- `sc_oset2_t({callwind {.}} {grpinfset {1}})` L2664-2857
- `purge_seqcut()` L2860-2916
- `beg_seq({callwind {.}})` L2919-3128
- `beg_seqcutdef()` L3131-3325
- `sc_mbcons({callwind {.}})` L3330-3412
- `clear_cutbcs()` L3414-3473
- `oset3_t()` L3476-3788
- `celltype({callwind {.}})` L3793-4403
- `bcoffset()` L4405-4575
- `inter_conc({callwind {.}})` L4578-5557
- `view_pic(picname xx yy mes1)` L5560-5580
- `group_cell({callwind {.}})` L5583-5684
- `zonal_pairs({callwind {.}})` L5689-5843
- `advanced_sewzon({callwind {.}})` L5846-6009
- `zonal_area_con({callwind {.}})` L6015-6156
- `iregrd_mod1_proc(pwin)` L6159-6269
- `cutcgr_groups()` L6272-6461

#### `totec.tcl` — 27 procs

- `totec()` L5-1444
- `totec2({callwind {.}})` L1447-2643
- `totec4({callwind {.}})` L2645-3421
- `init_plotvar()` L3423-3520
- `run_quat3({callwind {.}})` L3522-4421
- `surftec()` L4424-4654
- `genplif()` L4656-4938
- `plotting_warning()` L4941-4964
- `plot_turb()` L4967-5226
- `plot_primderiv()` L5228-5453
- `pref_quan({callwind {.}})` L5455-5528
- `ptot_limiting({callwind {.}})` L5530-5596
- `plot_other()` L5598-6301
- `plot_surface()` L6303-6638
- `htc_quan(do_nu {callwind {.}})` L6640-6705
- `plot_molemass()` L6708-6881
- `plot_rhscolor()` L6883-6963
- `plot_EDP()` L6965-7320
- `edp_quan(ed_num {callwind {.}})` L7323-7408
- `plot_back_prim()` L7411-7511
- `plot_back()` L7513-7636
- `plot_grnd()` L7638-7762
- `plot_exct()` L7764-7916
- `plot_erosion()` L7919-8010
- `mpf3dfv()` L8013-8128
- `mpf3dtecp()` L8131-8234
- `exbcelfv()` L8237-8443

#### `turbinit.tcl` — 7 procs

- `turb_init({callwind {.}})` L7-1794
- `set_new_vals()` L1797-1829
- `run_turbi()` L1831-2336
- `do_floor()` L2338-2482
- `run_turbi2()` L2487-2638
- `init_all_info_turb()` L2640-2844
- `info_prim({callwind {.}})` L2853-3189

#### `turbname.tcl` — 22 procs

- `geturbmod2(mtur mtyp)` L5-49
- `geturbmod(mtur mtyp)` L51-95
- `get_turb_type(mdtu mdty)` L97-139
- `turb_mod({callwind {.}})` L141-1602
- `spm2_params({callwind {.}})` L1605-1690
- `toff_box_control()` L1693-1950
- `toff_group_control()` L1953-2130
- `pope_sarkar_other()` L2135-2566
- `alt_mod_coef()` L2569-2838
- `atm_blayer_control({callwind {.}})` L2841-3253
- `free_ke()` L3257-3500
- `fill_infsets({callwind {.}})` L3503-3624
- `flow_invoke({callwind {.}})` L3626-3734
- `kill_turb(number nn)` L3736-3751
- `kill_turb2(number nn)` L3753-3766
- `set_name(name  i)` L3768-3907
- `set_name2(i)` L3911-4050
- `set_name3(i)` L4052-4192
- `nlas_control()` L4194-4407
- `trans_trip()` L4409-4580
- `lns_off_box()` L4583-4594
- `lns_off_region(set_num)` L4597-5103

#### `viewinf.tcl` — 71 procs

- `general_infoset_edit(typ bcnum_or_title infn {callwind {.}})` L5-723
- `get_turb_lbl(loc_nam)` L726-771
- `get_turb_lbl2(loc_nam)` L774-819
- `get_turb_lbl3(loc_nam)` L823-868
- `get_turb_lbl4(loc_nam)` L871-916
- `getinfo(inft infn)` L919-3742
- `sc_buttons(i)` L3744-3766
- `edit_seq(i)` L3769-3969
- `scanrefinf(colpos infno refinfno lplmt)` L3972-4005
- `resurv_scinf()` L4008-4025
- `seq_win_coords(windname)` L4028-4046
- `addrank()` L4049-4135
- `get_no_cuts(j)` L4138-4154
- `show_cut_info(i)` L4156-4594
- `show_cell_grps(i)` L4597-4811
- `show_ret_info(i)` L4814-4845
- `show_live_reg(j)` L4848-5085
- `delrnk_last(i)` L5088-5138
- `delrnk(i)` L5141-5232
- `lose_cutbcs()` L5235-5257
- `view_turb_units(name i)` L5260-5306
- `view_cgrain(number reset {callwind {.}})` L5309-5785
- `view_pdein(number reset {callwind {.}} pdeintyp)` L5788-6107
- `view_inf(number reset {callwind {.}})` L6113-6348
- `view_disturb(number reset {callwind {.}})` L6350-6643
- `view_five_sp(number  reset inft inftt {callwind {.}})` L6645-6939
- `view_inf2(number reset {callwind {.}})` L6941-7261
- `view_four_sp(number reset {callwind {.}})` L7264-7455
- `v1_lbls(inftt)` L7458-7470
- `view_one(number reset inft inftt lab1 {callwind {.}})` L7473-7561
- `view_two(number reset inft inftt lab1 lab2 {callwind {.}})` L7563-7644
- `view_file3(number reset inft inftt lab1 lab2 lab3 {callwind {...)` L7646-7726
- `view_file4(number reset inft inftt lab1 lab2 {callwind {.}})` L7728-7803
- `vfsp2_lbl(inftt)` L7806-7830
- `view_file_sp2(number reset inft inftt lab1 lab2 lab3 lab4 lab5 {...)` L7833-7948
- `view_file_sp(number reset inft inftt lab1 lab2 {callwind {.}})` L7952-8197
- `v2_lbls(inftt)` L8200-8228
- `view_two_sp(number reset inft inftt lab1 lab2 {callwind {.}})` L8231-8543
- `view_two_sp2(number reset inft inftt lab1 lab2 {callwind {.}})` L8545-8640
- `v3_lbls(inftt)` L8643-8693
- `view_three_sp2(number reset inft inftt lab1 lab2 lab3 {callwind {...)` L8696-8997
- `view_radop(number reset inft inftt {callwind {.}})` L9000-9377
- `view_three(number reset inft inftt lab1 lab2 lab3 {callwind {...)` L9380-9491
- `view_three_sp(number reset inft inftt lab1 lab2 lab3 {callwind {...)` L9493-9723
- `v4_lbls(inftt)` L9726-9762
- `view_four(number reset inft inftt lab1 lab2 lab3 lab4 {callw...)` L9765-9886
- `view_five(number reset inft inftt lab1 lab2 lab3 lab4 lab5 {...)` L9889-9997
- `v6_lbls(inftt)` L9999-10027
- `view_six(number reset inft inftt lab1 lab2 lab3 lab4 lab5 l...)` L10030-10168
- `view_eqdef(number {callwind {.}})` L10170-11815
- `view_six_nine_sp(number reset inft inftt {callwind {.}})` L11817-12051
- `view_seven_sp(number reset inft inftt versi {callwind {.}})` L12054-12219
- `view_boup_new(number inft inftt {callwind {.}})` L12222-12427
- `view_boup(number inft inftt lab1 lab2 {callwind {.}})` L12430-12634
- `view_depend(number inft inftt lab1 {callwind {.}})` L12636-12751
- `view_mixpl(number {callwind {.}})` L12754-12989
- `view_livecell(number inft inftt lab1 lab2 {callwind {.}})` L12991-13156
- `view_pxyzal(number inft inftt {callwind {.}})` L13159-13322
- `view_pgen(number inft inftt {callwind {.}})` L13325-13651
- `view_pgen2(number inft inftt {callwind {.}})` L13653-13961
- `view_none({callwind {.}})` L13964-13988
- `view_none2({callwind {.}})` L13990-14015
- `view_musk(number reset inft inftt {callwind {.}})` L14017-14466
- `view_grav(number reset inft inftt {callwind {.}})` L14469-14718
- `view_anode(number inft inftt {callwind {.}})` L14721-14843
- `view_anode_file(number inft inftt {callwind {.}})` L14845-14940
- `view_cathode(number inft inftt {callwind {.}})` L14943-15138
- `v7_lbls(inftt)` L15141-15164
- `view_seven_sp2(number reset inft inftt lab1 lab2 lab3 lab4 lab5 l...)` L15167-15288
- `v8_lbls(inftt)` L15290-15315
- `view_eight(number reset inft inftt lab1 lab2 lab3 lab4 lab5 l...)` L15318-15445

#### `wizard.tcl` — 5 procs

- `proc_wizard()` L4-58
- `auto_wizard()` L61-225
- `auto_wiz_set()` L227-490
- `aero_wizard()` L494-861
- `aero_wiz_set()` L864-1245

#### `wizards.tcl` — 12 procs

- `proc_wizard()` L4-64
- `auto_wizard({callwind {.}})` L67-267
- `auto_wiz_set()` L269-736
- `aero_wizard({callwind {.}})` L740-1296
- `aero_wiz_set()` L1299-1880
- `cont_pde_cycle()` L1883-1970
- `incomp_wizard()` L1973-2164
- `incomp_wiz_set()` L2167-2408
- `cl_driver_wiz()` L2411-2812
- `low_speed_react({callwind {.}})` L2815-3094
- `sel_spec(spec_typ loc_num)` L3097-3174
- `pde_pp_wiz({callwind {.}})` L3177-3316

## 五、Proc 调用矩阵

### 5.1 被调用次数最多的 proc(Top 30)

| 排名 | 目标 proc | 总调用次数 | 定义于 | 调用方数 |
|---:|---|---:|---|---:|
| 1 | `center_this` | 1087 | `gui_center.tcl` | 718 |
| 2 | `output_1a` | 656 | `mc_bind.tcl` | 229 |
| 3 | `reaction` | 626 | `reaction.tcl` | 18 |
| 4 | `cur_help` | 574 | `gui_hinit.tcl` | 524 |
| 5 | `npfgetn` | 448 | `cfdinfo.tcl`, `mcfdsol.tk` | 3 |
| 6 | `dialog_wait` | 447 | `mc_bind.tcl` | 209 |
| 7 | `max` | 407 | `interffm.tcl` | 80 |
| 8 | `save` | 354 | `saving.tcl` | 12 |
| 9 | `run_cmd` | 290 | `run_cmd.tcl` | 171 |
| 10 | `tk_dialog2` | 285 | `mc_bind.tcl` | 116 |
| 11 | `mpf3dav` | 241 | `mcfdsol.tk`, `soltools.tcl` | 2 |
| 12 | `configure_subwindow` | 220 | `mc_bind.tcl` | 137 |
| 13 | `browse` | 194 | `directb.tcl`, `open_file.tcl` | 119 |
| 14 | `wavepropd` | 169 | `caa++.tcl` | 2 |
| 15 | `synjet` | 165 | `physour.tcl` | 1 |
| 16 | `subsets7` | 148 | `gridtools.tcl` | 1 |
| 17 | `wavepropf` | 146 | `caa++.tcl` | 3 |
| 18 | `partrack_gui` | 140 | `partrac_gui.tcl`, `partrac_gui2.tcl` | 7 |
| 19 | `recon_info` | 127 | `recon_info.tcl` | 79 |
| 20 | `set_name3` | 120 | `turbname.tcl` | 24 |
| 21 | `info_sets` | 119 | `infoset.tcl` | 40 |
| 22 | `sp_add` | 108 | `bcstuff.tcl` | 3 |
| 23 | `help` | 104 | `rclickh.tcl` | 25 |
| 24 | `exbcelfv` | 104 | `totec.tcl` | 1 |
| 25 | `reference` | 103 | `refer.tcl` | 34 |
| 26 | `output_1` | 95 | `mc_bind.tcl` | 45 |
| 27 | `conv18` | 90 | `convtool.tcl` | 1 |
| 28 | `conv19` | 90 | `convtool.tcl` | 1 |
| 29 | `temp_range` | 83 | `trange.tcl` | 14 |
| 30 | `xyzdec` | 82 | `tometis.tcl` | 4 |

**Top 10 高频 proc 的角色**:

- `center_this` (1087 次,定义于 `gui_center.tcl`)
- `output_1a` (656 次,定义于 `mc_bind.tcl`)
- `reaction` (626 次,定义于 `reaction.tcl`)
- `cur_help` (574 次,定义于 `gui_hinit.tcl`)
- `npfgetn` (448 次,定义于 `cfdinfo.tcl`)
- `dialog_wait` (447 次,定义于 `mc_bind.tcl`)
- `max` (407 次,定义于 `interffm.tcl`)
- `save` (354 次,定义于 `saving.tcl`)
- `run_cmd` (290 次,定义于 `run_cmd.tcl`)
- `tk_dialog2` (285 次,定义于 `mc_bind.tcl`)

### 5.2 跨文件调用边(Top 50,按调用次数)

| 调用方 | 调用目标 | 目标所在文件 | 次数 |
|---|---|---|---:|
| `soltools.tcl::mpf3dav` | `mpf3dav` | `mcfdsol.tk` | 182 |
| `soltools.tcl::npf_probes` | `npfgetn` | `cfdinfo.tcl` | 164 |
| `soltools.tcl::npf_probes` | `npfgetn` | `mcfdsol.tk` | 164 |
| `cfdinfo.tcl::npfgetn` | `npfgetn` | `mcfdsol.tk` | 145 |
| `mcfdsol.tk::npfgetn` | `npfgetn` | `cfdinfo.tcl` | 139 |
| `mcfdsol.tk::save_browse` | `save` | `saving.tcl` | 114 |
| `infoset.tcl::info_sets` | `tk_dialog2` | `mc_bind.tcl` | 87 |
| `probe.tcl::prob_stat` | `output_1a` | `mc_bind.tcl` | 84 |
| `load_proc.tcl::load_proc` | `reaction` | `reaction.tcl` | 76 |
| `partrac_gui.tcl::partrack_gui` | `partrack_gui` | `partrac_gui2.tcl` | 69 |
| `mcfdtplt.tk::mx_res` | `max` | `interffm.tcl` | 60 |
| `mcfdsol.tk::mpf3dav` | `mpf3dav` | `soltools.tcl` | 59 |
| `bcstuff.tcl::boundary_con` | `center_this` | `gui_center.tcl` | 57 |
| `infoset.tcl::info_sets` | `dialog_wait` | `mc_bind.tcl` | 56 |
| `bcstuff.tcl::boundary_con` | `configure_subwindow` | `mc_bind.tcl` | 54 |
| `bcstuff.tcl::boundary_con` | `set_name3` | `turbname.tcl` | 54 |
| `bcstuff.tcl::boundary_con` | `info_sets` | `infoset.tcl` | 47 |
| `mcfdfplt.tk::read_data` | `set_axis_mnmx` | `mcfd1dp.tk` | 46 |
| `mcfdfplt.tk::read_data` | `set_axis_mnmx` | `mcfdpplt.tk` | 46 |
| `partrac_gui2.tcl::partrack_gui` | `partrack_gui` | `partrac_gui.tcl` | 39 |
| `bcstuff.tcl::boundary_con` | `get_turb_lbl` | `viewinf.tcl` | 33 |
| `partrac_gui2.tcl::synch_particle_sets_loaded` | `partrack_gui` | `partrac_gui.tcl` | 27 |
| `interffm.tcl::interior_ffm` | `isnumb` | `mc_bind.tcl` | 24 |
| `probe.tcl::probe_res` | `center_this` | `gui_center.tcl` | 24 |
| `probe.tcl::primitive_plansurf` | `isnumb` | `mc_bind.tcl` | 24 |
| `probe.tcl::prob_stat` | `dialog_wait` | `mc_bind.tcl` | 22 |
| `probe.tcl::probe_res` | `info_sets` | `infoset.tcl` | 21 |
| `saving.tcl::save_do` | `celltype` | `topology.tcl` | 21 |
| `infoset.tcl::info_sets` | `center_this` | `gui_center.tcl` | 19 |
| `interview.tcl::inter_start` | `dialog_wait` | `mc_bind.tcl` | 19 |
| `bcstuff.tcl::getbcmes` | `set_name3` | `turbname.tcl` | 18 |
| `bcstuff.tcl::boundary_con` | `get_turb_lbl2` | `viewinf.tcl` | 18 |
| `gridvel.tcl::gvel_region_29` | `center_this` | `gui_center.tcl` | 18 |
| `infoset.tcl::info_sets` | `set_name` | `turbname.tcl` | 18 |
| `probe.tcl::prob_stat` | `view_boup` | `viewinf.tcl` | 17 |
| `turbinit.tcl::turb_init` | `output_1a` | `mc_bind.tcl` | 17 |
| `eqset.tcl::set_eqns_all` | `dialog_wait` | `mc_bind.tcl` | 16 |
| `infoset.tcl::info_sets` | `turb_init` | `turbinit.tcl` | 16 |
| `interview.tcl::inter_start` | `center_this` | `gui_center.tcl` | 16 |
| `viewinf.tcl::getinfo` | `set_name3` | `turbname.tcl` | 16 |
| `graphs.tcl::graph_res` | `max` | `interffm.tcl` | 14 |
| `gridvel.tcl::gvel_region_29` | `output_1a` | `mc_bind.tcl` | 14 |
| `infoset.tcl::info_sets` | `spec_info` | `species.tcl` | 14 |
| `mcfdplt.tk::graph_res` | `max` | `interffm.tcl` | 14 |
| `bcstuff.tcl::getbcmes` | `get_turb_lbl` | `viewinf.tcl` | 13 |
| `eqset.tcl::set_eqns_all` | `reference` | `refer.tcl` | 13 |
| `infoset.tcl::info_sets` | `cur_help` | `gui_hinit.tcl` | 13 |
| `infoset.tcl::info_sets` | `disperse_info` | `disperse.tcl` | 13 |
| `bltGraph.mcfd1dp.tcl::blt::PushZoom` | `max` | `interffm.tcl` | 12 |
| `infoset.tcl::info_sets` | `output_1a` | `mc_bind.tcl` | 12 |

### 5.3 跨文件调用最多的源文件(Top 15)

| 文件 | 跨文件调用次数 |
|---|---:|
| `soltools.tcl` | 772 |
| `gridtools.tcl` | 523 |
| `bcstuff.tcl` | 506 |
| `mcfdsol.tk` | 409 |
| `infoset.tcl` | 376 |
| `viewinf.tcl` | 283 |
| `probe.tcl` | 262 |
| `cfdinfo.tcl` | 204 |
| `mcfdtplt.tk` | 175 |
| `init_dom.tcl` | 168 |
| `mcfdfplt.tk` | 167 |
| `convert.tcl` | 163 |
| `gridvel.tcl` | 162 |
| `pltdata.tcl` | 159 |
| `topology.tcl` | 155 |

## 六、全局变量依赖

### 6.1 声明频度最高的 30 个 global 变量

| 变量 | 声明次数 | 涉及文件数 | 涉及文件(前 5) |
|---|---:|---:|---|
| `infset` | 1195 | 68 | `coking_wizard.tcl`, `ps10_volsoug.tcl`, `saving.tcl`, `panic.tcl`, `spacdis.tcl` 等 68 |
| `infsets` | 904 | 60 | `coking_wizard.tcl`, `ps10_volsoug.tcl`, `saving.tcl`, `panic.tcl`, `spacdis.tcl` 等 60 |
| `metapath3` | 575 | 113 | `coking_wizard.tcl`, `convert10.tcl`, `ps10_volsoug.tcl`, `spacdis.tcl`, `colormap.tcl` 等 113 |
| `gui_units` | 431 | 48 | `coking_wizard.tcl`, `npfcuts.tcl`, `caa++.tcl`, `timemark.tcl`, `refer.tcl` 等 48 |
| `uspec` | 420 | 48 | `coking_wizard.tcl`, `npfcuts.tcl`, `caa++.tcl`, `timemark.tcl`, `refer.tcl` 等 48 |
| `mbcon` | 284 | 34 | `saving.tcl`, `panic.tcl`, `load_proc.tcl`, `radmoddo.tcl`, `bcsort.tcl` 等 34 |
| `mbcons` | 282 | 38 | `saving.tcl`, `mcfdsol.tk`, `npfcuts.tcl`, `panic.tcl`, `load_proc.tcl` 等 38 |
| `directory_global` | 268 | 58 | `convert10.tcl`, `open_file.tcl`, `saving.tcl`, `mcfdsol.tk`, `npfcuts.tcl` 等 58 |
| `fixed_font` | 262 | 58 | `coking_wizard.tcl`, `mcfdsol.tk`, `npfcuts.tcl`, `panic.tcl`, `spacdis.tcl` 等 58 |
| `neqg` | 256 | 41 | `coking_wizard.tcl`, `ps10_volsoug.tcl`, `panic.tcl`, `volsoug.tcl`, `load_proc.tcl` 等 41 |
| `who_called` | 249 | 19 | `radmoddo.tcl`, `special_mode.tcl`, `levelset.tcl`, `init_dom.tcl`, `interffm.tcl` 等 19 |
| `neqc` | 180 | 29 | `coking_wizard.tcl`, `load_proc.tcl`, `radmoddo.tcl`, `special_mode.tcl`, `levelset.tcl` 等 29 |
| `eqset` | 169 | 36 | `coking_wizard.tcl`, `saving.tcl`, `panic.tcl`, `spacdis.tcl`, `refer.tcl` 等 36 |
| `neqt` | 155 | 27 | `coking_wizard.tcl`, `load_proc.tcl`, `radmoddo.tcl`, `special_mode.tcl`, `levelset.tcl` 等 27 |
| `modtur` | 143 | 26 | `coking_wizard.tcl`, `saving.tcl`, `spacdis.tcl`, `load_proc.tcl`, `init_dom.tcl` 等 26 |
| `species` | 137 | 27 | `coking_wizard.tcl`, `ps10_volsoug.tcl`, `mcfdsol.tk`, `panic.tcl`, `volsoug.tcl` 等 27 |
| `mcfd_dnd_text` | 137 | 17 | `gasprop.tcl`, `soltools.tcl`, `totec.tcl`, `plasma.tcl`, `mactool.tcl` 等 17 |
| `inftyp` | 136 | 20 | `radmoddo.tcl`, `special_mode.tcl`, `levelset.tcl`, `init_dom.tcl`, `infocopy.tcl` 等 20 |
| `bcnumber` | 127 | 2 | `viewinf.tcl`, `bcstuff.tcl` |
| `askinf` | 127 | 17 | `radmodp1.tcl`, `interffm.tcl`, `levelset.tcl`, `gridvel.tcl`, `topology.tcl` 等 17 |
| `infstat` | 124 | 16 | `radmodp1.tcl`, `interffm.tcl`, `levelset.tcl`, `gridvel.tcl`, `topology.tcl` 等 16 |
| `iglob` | 124 | 22 | `topl3d.tcl`, `levelset.tcl`, `init_dom.tcl`, `disperse.tcl`, `interffm.tcl` 等 22 |
| `file_chosen` | 117 | 21 | `open_file.tcl`, `mcfdsol.tk`, `caa++.tcl`, `disperse.tcl`, `proftool.tcl` 等 21 |
| `vof_numeqns` | 104 | 18 | `saving.tcl`, `gasprop.tcl`, `spacdis.tcl`, `totec.tcl`, `plasma.tcl` 等 18 |
| `bcnew` | 103 | 2 | `gui_reset.tcl`, `bcstuff.tcl` |
| `mix_numeqns` | 92 | 13 | `saving.tcl`, `gasprop.tcl`, `totec.tcl`, `turbinit.tcl`, `turbname.tcl` 等 13 |
| `infset([expr` | 84 | 18 | `radmodp1.tcl`, `interffm.tcl`, `levelset.tcl`, `wizards.tcl`, `gridvel.tcl` 等 18 |
| `$i+1],title)` | 82 | 17 | `radmodp1.tcl`, `levelset.tcl`, `wizards.tcl`, `gridvel.tcl`, `topology.tcl` 等 17 |
| `prog_name` | 76 | 30 | `mc_animate.tcl`, `saving.tcl`, `mcfdsol.tk`, `spacdis.tcl`, `gui_hinit.tcl` 等 30 |
| `work_infoset_gvel` | 76 | 4 | `totec.tcl`, `mc_draw.tcl`, `infoset.tcl`, `gridvel.tcl` |

### 6.2 全局变量耦合度最高的 20 个文件

| 文件 | global 声明总数 | 主要变量(Top 3) |
|---|---:|---|
| `bcstuff.tcl` | 2198 | `infset`, `infsets`, `mbcon` |
| `totec.tcl` | 1758 | `metapath3`, `totec_grdonly`, `gui_units` |
| `infoset.tcl` | 1389 | `infsets`, `infset`, `who_called` |
| `gui_reset.tcl` | 1323 | `env`, `fileout`, `mix_yesno` |
| `gridtools.tcl` | 1307 | `directory_global`, `metapath3`, `nodesin_fn` |
| `saving.tcl` | 1295 | `fileout`, `directory_global`, `save_directory` |
| `probe.tcl` | 1193 | `infset`, `infsets`, `infset([expr` |
| `viewinf.tcl` | 995 | `infset`, `infsets`, `inftyp` |
| `gridvel.tcl` | 854 | `infset`, `work_infoset_gvel`, `current_gvel_reg` |
| `timeint.tcl` | 820 | `dtauin`, `infset`, `eqset` |
| `topology.tcl` | 755 | `infset`, `infsets`, `ordrnk` |
| `init_dom.tcl` | 734 | `infset`, `infsets`, `working_infoset` |
| `soltools.tcl` | 610 | `metapath3`, `file_chosen`, `directory_global` |
| `mcfdfplt.tk` | 529 | `ntsv`, `timv`, `enfv$i` |
| `surface.tcl` | 496 | `names_variables`, `neqa`, `iglob` |
| `turbname.tcl` | 490 | `modtur`, `modtyp`, `infset` |
| `wizards.tcl` | 480 | `infset`, `infsets`, `prog_name` |
| `physour.tcl` | 438 | `infset`, `infsets`, `metapath3` |
| `gasprop.tcl` | 412 | `infset`, `gui_units`, `uspec` |
| `species.tcl` | 409 | `infset`, `infsets`, `neqg` |

**洞察**:

- `mc_glovar1.tcl` 等 4 个文件**不定义 proc**(只设置 global),承载了所有 GUI 状态
- 业务模块如 `run_mcfd.tcl` 声明 ~50 个 global,反映其与 GUI 状态的深度耦合
- **建议**:在翻译后的语言中,用命名空间/类成员替换 global 变量

## 七、Exe 调用接口

### 7.1 调用类型分布

| 调用类型 | 次数 | 说明 |
|---|---|---|
| `exec` | 1 | 同步执行外部命令(罕见) |
| `eval exec` | 58 | 同步执行,命令由变量构建(主要模式) |
| `blt::bgexec` | 6 | 异步后台执行,带 stdout 回显 |

### 7.2 exec 调用点(按文件)

| 文件 | proc | body 内行 | 类型 | 首参数/说明 |
|---|---|---:|---|---|---|
| `case01.tcl` | `case01` | L120 | eval_exec | `<var>` |
| `case01.tcl` | `case01` | L125 | eval_exec | `<var>` |
| `ezsetup1.tcl` | `ezsetup1` | L130 | exec | `xterm` |
| `forcemom.tcl` | `force_manage` | L685 | bgexec | `infout1f$i` |
| `graphs.tcl` | `graph_res` | L62 | eval_exec | `<var>` |
| `gui_hinit.tcl` | `gen_help` | L7 | eval_exec | `<var>` |
| `gui_hinit.tcl` | `gen_help` | L21 | eval_exec | `<var>` |
| `gui_hinit.tcl` | `cur_help` | L31 | eval_exec | `<var>` |
| `gui_hinit.tcl` | `cur_help` | L45 | eval_exec | `<var>` |
| `gui_hinit.tcl` | `cur_help_old` | L8 | eval_exec | `<var>` |
| `gui_hinit.tcl` | `cur_help_old` | L22 | eval_exec | `<var>` |
| `infotool.tcl` | `cmd_tools` | L186 | bgexec | `infotool_bgexec_status` |
| `lmtool.tcl` | `lm_tools` | L160 | bgexec | `lmtool_bgexec_status` |
| `mc_animate.tcl` | `refresh_solstate` | L28 | eval_exec | `<var>` |
| `mc_bind.tcl` | `exit3` | L4 | eval_exec | `<var>` |
| `mc_bind.tcl` | `exit3` | L14 | eval_exec | `<var>` |
| `mcfdfplt.tk` | `graph_res` | L109 | eval_exec | `<var>` |
| `mcfdfplt.tk` | `graph_res` | L116 | eval_exec | `<var>` |
| `mcfdfplt.tk` | `graph_res` | L123 | eval_exec | `<var>` |
| `mcfdfplt.tk` | `graph_res` | L130 | eval_exec | `<var>` |
| `mcfdpplt.tk` | `graph_res` | L75 | eval_exec | `<var>` |
| `probe.tcl` | `cinfout2` | L89 | eval_exec | `<var>` |
| `probe.tcl` | `cinfout3` | L89 | eval_exec | `<var>` |
| `run_cmd.tcl` | `run_cmd` | L155 | bgexec | `run_status_$job_name` |
| `run_cmd.tcl` | `run_cmd` | L202 | bgexec | `run_status_$job_name` |
| `run_cmd.tcl` | `run_cmd_DEPRECATED` | L125 | bgexec | `run_status_$job_name` |
| `run_mcfd.tcl` | `mcfd_stop` | L5 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_mcfd_back` | L18 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `view_log2` | L5 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `kill_mcfd` | L5 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_mcfdplt` | L5 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_mcfdplt_ps` | L5 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_mcfdtplt` | L5 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_mcfdrhsgi` | L5 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_mcfd1dp` | L5 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_mcfdsol` | L9 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_mcfdfplt` | L5 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_mcfdfft` | L5 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_mcfdpplt` | L5 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `view_log` | L5 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_multicpu` | L551 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_multicpu` | L601 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_multicpu` | L670 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_multicpu` | L710 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_multicpu` | L743 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_multicpu` | L781 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_multicpu` | L866 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_multicpu` | L898 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_multicpu` | L964 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_multicpu` | L985 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `read_file_mcpu` | L5 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_multicpu_tool` | L639 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_multicpu_tool` | L674 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_multicpu_tool` | L747 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_multicpu_tool` | L772 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_multicpu_tool` | L814 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_multicpu_tool` | L899 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_multicpu_tool` | L932 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_multicpu_tool` | L986 | eval_exec | `<var>` |
| `run_mcfd.tcl` | `run_multicpu_tool` | L1009 | eval_exec | `<var>` |
| `sol_menu.tcl` | `run_mcfdplt` | L5 | eval_exec | `<var>` |
| `soltools.tcl` | `steady_unsteady` | L159 | eval_exec | `<var>` |
| `soltools.tcl` | `steady_unsteady` | L165 | eval_exec | `<var>` |
| `soltools.tcl` | `steady_unsteady` | L191 | eval_exec | `<var>` |
| `surface.tcl` | `redo_cutpln` | L4 | eval_exec | `<var>` |

### 7.3 关键 exec 调用源码模式

GUI 不直接调 exe,所有调用都通过字符串构建后 `eval exec`,典型模式:

```tcl
# ========== run_mcfd.tcl ==========
# 单精度串行求解
set command "r4_mcfd | mc_stdoutee mcfd.log"        ;# 管道重定向 stdout
eval exec $command

# 后台运行(立即返回)
set command "mcfd_background4"                      ;# 后台进程
eval exec $command &

# MPI 并行(MSMPI 后端)
set command "mpiexec -n $nproc [r4_]msmpimcfd"      ;# 变量拼接
eval exec $command

# MPI 并行(MPICH 后端)
set command "mpiexec -n $nproc [r4_]mpimcfd"
eval exec $command

# ========== run_cmd.tcl ==========
# 异步任务(blt 扩展),带实时 stdout 回显
blt::bgexec run_status_$job_name \
    -onoutput update_display_$job_name \
    -onerror   show_error_$job_name \
    $clt_cmd                                       ;# clt_cmd 由 run_mcfd 构建

# ========== infotool.tcl / lmtool.tcl ==========
blt::bgexec infotool_bgexec_status \
    -onoutput it_getinfo \
    -onerror   GetInfo \
    $clt_cmd                                       ;# 通常 infotool/lmtool 系列 exe

# ========== forcemom.tcl ==========
blt::bgexec infout1f$i infout1f $i                ;# 力和力矩计算

# ========== gui_hinit.tcl (帮助系统) ==========
# Linux/Unix: 浏览器打开 HTML
$net1_run $fil $netscape_c &                        ;# netscape/firefox

# Windows: 微软资源管理器
mexplore $html_file                                ;# Windows 98/NT 遗留

# ========== ezsetup1.tcl ==========
exec xterm -e ez1_sc1.sh                           ;# 向导安装
```

### 7.4 涉及的外部 exe 清单(从 exec 调用推断)

| exe 名称 | 用途 | 调用源 |
|---|---|---|
| `xterm` | other | `ezsetup1.tcl::ezsetup1` |
| `infout1f$i` | other | `forcemom.tcl::force_manage` |
| `infotool_bgexec_status` | other | `infotool.tcl::cmd_tools` |
| `lmtool_bgexec_status` | other | `lmtool.tcl::lm_tools` |
| `run_status_$job_name` | other | `run_cmd.tcl::run_cmd_DEPRECATED` |
| `run_status_$job_name` | other | `run_cmd.tcl::run_cmd` |
| `run_status_$job_name` | other | `run_cmd.tcl::run_cmd` |

## 八、Proc 入口归类

每个 proc 被哪个 .tk 入口加载(基于 source 传递闭包)。

### 8.1 多入口共享 proc(Top 30)

| Proc | 入口数 | 涉及入口 |
|---|---:|---|
| `center_me` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `center_this` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `center_this_seqcut` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `platform_is_windows` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `Is_Window_Packed` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `dialog_wait` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `dialog_wait2` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `exit3` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `exit2` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `tk_dialog2` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `isnumb` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `verify_numb` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `verify_real` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `verify_int` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `output_1` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `output_1a` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `output_2` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `output_2a` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `slash_change` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `configure_subwindow` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `set_win_min_size` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `check_v_state` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `tk_hint1` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `gen_help` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `cur_help` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `cur_help_old` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `help_reset` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `help_about` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `help_roughwall` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |
| `help_wall_motion` | 10 | `cfd++.tk`, `logview.tk`, `mcfd1dp.tk`, `mcfdfft.tk`, `mcfdfplt.tk`, `mcfdplt.tk`, `mcfdplt2.tk`, `mcfdpplt.tk`, `mcfdsol.tk`, `mcfdtplt.tk` |

**洞察**:

- 共享最多的 proc 是 `center_me` (10 个入口):cfd++.tk, logview.tk, mcfd1dp.tk, mcfdfft.tk, mcfdfplt.tk, mcfdplt.tk, mcfdplt2.tk, mcfdpplt.tk, mcfdsol.tk, mcfdtplt.tk
- 共享 proc 都是 GUI 基础(键盘绑定、帮助系统、窗口居中等)
- 业务专用 proc 几乎都被单一入口独占

### 8.2 各入口独占 proc 数

| 入口 | 独占 proc 数 | 示例(Top 5) |
|---|---:|---|
| `cfd++.tk` | 905 | `ps10_volsoug_group`, `ps10_volsoug_values`, `ps10_volsoug_groups`, `coking_wizard`, `fuel_list` ... (+900) |
| `mcfdsol.tk` | 101 | `mc_animate`, `refresh_solstate`, `generate_mpeg_encoder_input_file`, `surface_manage`, `all_grid_on` ... (+96) |
| `mcfd1dp.tk` | 13 | `save_onedp`, `reload_onedp`, `load_onedp`, `autoload_onedp`, `find_common_vartit` ... (+8) |
| `mcfdplt.tk` | 0 |  |
| `mcfdplt2.tk` | 0 |  |
| `mcfdtplt.tk` | 0 |  |
| `mcfdpplt.tk` | 0 |  |
| `mcfdfplt.tk` | 0 |  |
| `mcfdfft.tk` | 0 |  |
| `logview.tk` | 0 |  |

**注**: `cfd++.tk` 的独占 proc 最多(~1000),因为它 source 了几乎所有业务模块。

## 九、架构洞察

### 9.1 分层架构

```
┌──────────────────────────────────────────────────────────┐
│  入口层 (10 个 .tk,每个是一个独立 GUI 工具)             │
│  cfd++.tk / mcfdsol.tk / mcfd*.tk / logview.tk          │
└──────────────────────────────────────────────────────────┘
                         │ source 加载
                         ▼
┌──────────────────────────────────────────────────────────┐
│  全局状态层 (4 个 mc_glovar*.tcl)                         │
│  全部 GUI 状态、流场变量、求解器参数都在这里定义        │
└──────────────────────────────────────────────────────────┘
                         │ global 声明
                         ▼
┌──────────────────────────────────────────────────────────┐
│  业务模块层 (~120 个 .tcl, 1251 个 proc)                  │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐             │
│  │求解运行│ │物理/边界│ │网格/拓扑│ │输出/保存│          │
│  │ 3 模块 │ │ 30+ 模块│ │  8 模块 │ │  8 模块 │          │
│  └────────┘ └────────┘ └────────┘ └────────┘             │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐             │
│  │后处理  │ │信息查询│ │  工具  │ │  向导  │             │
│  │ 15 模块│ │  5 模块│ │ 10+ 模块│ │  5 模块│             │
│  └────────┘ └────────┘ └────────┘ └────────┘             │
└──────────────────────────────────────────────────────────┘
                         │ eval exec / blt::bgexec
                         ▼
┌──────────────────────────────────────────────────────────┐
│  外部 exe 层 (~600+ 个)                                   │
│  求解:mcfd/r4_mcfd/msmpimcfd/mpimcfd                    │
│  后处理:mcfdsol/mcfdplt/mcfdfft/mcfdpplt                │
│  网格:dfcells/tometis/toponew1                            │
│  转换:convert1-24/hextec/tritec/pltos*/infout*           │
│  信息:infotool/cellsinf/nodesinf/grdqual*                │
│  粒子:partrac/partraj/mcfd_morph1                        │
└──────────────────────────────────────────────────────────┘
```

### 9.2 数据流(以"运行一次仿真"为例)

```
用户点击"Run"
   │
   ▼
gui_menu.tcl 绑定的 menu callback
   │ 触发 proc
   ▼
run_mcfd.tcl::run_mcfd {nproc backend}
   │ 读 case 配置
   ├→ load_proc.tcl::read_xxx_proc 家族
   │ 构建 command 字符串:
   │   set command "mpiexec -n $nproc $backend $solver"
   │ 执行(2 种路径):
   ├─→ eval exec $command              [同步, 阻塞到结束]
   └─→ run_cmd.tcl::blt::bgexec ...    [异步, stdout 回显]
         │
         ▼
      mcfd.exe / mpiexec 写 .plt .log 文件
         │
         ▼
      用户打开后处理工具(独立 .tk 入口)
         │
         ▼
      mcfdsol/mcfdplt/mcfdpplt 读取结果做可视化
```

### 9.3 关键设计模式

1. **全局变量作为接口**:跨 proc 通信几乎全部通过 `global` 变量。
   - `mc_glovar1-4.tcl` 定义所有 GUI 状态(共 ~3000 行)
   - 每个业务 proc 头部 `global var1 var2 ...` 声明访问权限
   - 这种"扁平全局变量"模式简化了跨模块数据流,但不利于大型项目维护

2. **`source` 依赖图作为模块化机制**:无显式模块系统,纯靠 `source` 实现模块加载
   - 没有命名空间、没有包系统
   - 顺序敏感:mc_glovar1-4 必须按 1→2→3→4 加载

3. **`eval exec` + 字符串拼接作为命令构造**:
   - 所有外部命令都通过字符串拼接构造
   - 运行时由 `eval exec $command` 执行
   - 这种动态构造方式灵活但难以静态分析

4. **`blt::bgexec` 作为异步任务框架**:
   - 长时间运行的命令(exe 调用)用 BLT 扩展异步执行
   - 带 stdout 实时回显,适合长任务监控

5. **多入口架构**:每个 GUI 工具是独立可执行
   - 通过不同 .tk 入口启动不同的 GUI 工具
   - 工具之间通过文件系统(.plt/.log)共享数据

### 9.4 翻译/改造建议

1. **保留 `mc_glovar1-4.tcl` 结构**:这 4 个文件是核心,所有 GUI 状态集中管理
2. **替换 `global` 为命名空间/类成员**:在翻译后的语言中,建议把 `global` 改为命名空间/类成员
3. **`exec` 调用是改造的边界**:所有 exe 调用集中在以下文件,翻译时这些是主要适配点:
   - `run_mcfd.tcl` (主求解器调用)
   - `run_cmd.tcl` (异步任务框架)
   - `infotool.tcl` / `lmtool.tcl` (信息查询)
   - `forcemom.tcl` (力/力矩)
   - `gui_hinit.tcl` (帮助浏览器调用)
4. **`proc` 调用图是核心契约**:本分析中的"跨文件 proc 调用边"清单(3871 条)必须保持一致
5. **多入口共享 proc 优先翻译**:`run_mcfd`/`exit3`/`blt::bgexec` 等被多个 .tk 共享,优先处理
6. **大型模块分层翻译**:`infoset.tcl`(33 procs)/`gridtools.tcl`(60 procs)/`viewinf.tcl`(71 procs) 等需要先做内部结构梳理
7. **保持 `cfd++.tk` 作为主入口**:不要打散 116 个 source 关系,这是 GUI 加载顺序的契约

### 9.5 风险点

1. **catch 块吞掉语法**:cfd++.tk 的 `catch { ... }` 块从 L7 跨到 L38,包含整个 mcfdgui/sd_gui/ed_gui 调度,任何对此块的修改都要慎重
2. **反注释代码含 brace**:L18-22 有 `# 注释掉的 if/else 代码`,注释在 brace 字符串内仍然被算作字符,改动需保持平衡
3. **proc 名同名**:1251 个唯一名,但有些 proc 在不同文件重复定义(如各绘图工具的 `redraw`),需识别
4. **blt::bgexec 异步回调**:`-onoutput`/`-onerror` 的回调 proc 名字是动态拼接的,翻译时需保留这一模式
5. **`${metapath}` 变量**:所有 source 路径都通过 `$metapath` 解析,翻译时需保留这种环境变量配置

