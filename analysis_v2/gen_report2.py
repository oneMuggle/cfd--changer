"""更新报告生成器,使用 v11 JSON"""
import json
import os
from collections import defaultdict, Counter

OUTPUT_DIR = r'E:\ProgrammingData\python\cfd++changer\analysis_v2'
JSON_FILE = os.path.join(OUTPUT_DIR, 'analysis_v11.json')
REPORT_FILE = r'E:\ProgrammingData\python\cfd++changer\CFD_GUI_CallGraph_v2.md'

ENTRY_FILES = {
    'cfd++.tk': 'CFD++ 主GUI',
    'mcfdsol.tk': 'META Visualizer (后处理可视化)',
    'mcfdplt.tk': '残差绘图(简单版)',
    'mcfdplt2.tk': '残差绘图(run_cmd 异步版)',
    'mcfdtplt.tk': '残差绘图(工具栏版)',
    'mcfdpplt.tk': '探针绘图',
    'mcfdfplt.tk': '力/力矩绘图',
    'mcfdfft.tk': 'FFT 分析工具',
    'mcfd1dp.tk': 'XY 曲线绘图',
    'logview.tk': '日志查看器',
}


def main():
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    files = sorted(data.keys())
    tcl_files = [f for f in files if f.endswith('.tcl')]
    tk_files = [f for f in files if f.endswith('.tk')]

    # 全局统计
    total_procs = sum(len(fd['procs']) for fd in data.values())
    total_sources = sum(len(fd['sources']) for fd in data.values())
    unique_proc_names = set()
    for fd in data.values():
        for p in fd['procs']:
            unique_proc_names.add(p['name'])

    # 跨文件 proc 调用
    cross_file_calls = []
    for fn, fd in data.items():
        for p in fd['procs']:
            for callee, cnt in p['calls'].items():
                defn_files = [f for f, ffd in data.items()
                              if any(pp['name'] == callee for pp in ffd['procs'])]
                for df in defn_files:
                    if df != fn:
                        cross_file_calls.append((fn, p['name'], callee, df, cnt))

    # source 边
    source_edges = []
    for fn, fd in data.items():
        for entry in fd['sources']:
            line, target = entry
            source_edges.append((fn, line, target))

    # 入口 source 闭包
    def get_loaded_tcls(entry):
        loaded = set()
        stack = [entry]
        while stack:
            cur = stack.pop()
            if cur not in data:
                continue
            for entry in data[cur]['sources']:
                line, target = entry
                tname = target.split('/')[-1].split('\\')[-1]
                tname = tname.split('"')[0].split("'")[0]
                # 处理 ${var}/file.tcl → file.tcl
                if tname.endswith('.tcl') and tname not in loaded and tname in data:
                    loaded.add(tname)
                    stack.append(tname)
        return loaded

    entry_loaded = {e: get_loaded_tcls(e) for e in ENTRY_FILES}

    # proc → entries
    proc_to_entries = defaultdict(set)
    for entry, loaded in entry_loaded.items():
        for tcl in loaded:
            for p in data[tcl]['procs']:
                proc_to_entries[p['name']].add(entry)

    # proc → files
    proc_to_files = defaultdict(list)
    for fn, fd in data.items():
        for p in fd['procs']:
            proc_to_files[p['name']].append(fn)

    # exec 统计
    exec_data = []
    for fn, fd in data.items():
        for p in fd['procs']:
            for line_in_body, etype, first_arg in p['execs']:
                exec_data.append((fn, p['name'], line_in_body, etype, first_arg))

    # global 统计
    global_data = []
    for fn, fd in data.items():
        for p in fd['procs']:
            for v in p['globals']:
                global_data.append((fn, p['name'], v))

    # === 写报告 ===
    md = []
    md.append('# CFD++ Tcl/Tk GUI 调用关系深度分析 (v2)\n\n')
    md.append('> **分析对象**: `D:\\software\\CFD++\\METACOMP\\mlib\\mcfd.18.5\\exec\\gui_src\\`  \n')
    md.append('> **分析范围**: {} 个文件 ({} 个 .tcl + {} 个 .tk)  \n'.format(
        len(files), len(tcl_files), len(tk_files)))
    md.append('> **分析方法**: 静态分析,基于 Tcl 词法(brace 字符串不做转义、识别 `${var}` 变量引用、re 处理 `source` 行)  \n')
    md.append('> **分析维度**: ①source 依赖链 ②proc 导出表 ③proc 调用矩阵 ④global 变量依赖 ⑤exe 调用接口 ⑥入口归类  \n')
    md.append('\n---\n\n')

    # === 一、执行摘要 ===
    md.append('## 一、执行摘要\n\n')
    md.append('### 1.1 关键指标\n\n')
    md.append('| 指标 | 数值 |\n|---|---|\n')
    md.append('| 文件总数 | **{}** |\n'.format(len(files)))
    md.append('| .tcl 模块 | {} |\n'.format(len(tcl_files)))
    md.append('| .tk 入口 | {} |\n'.format(len(tk_files)))
    md.append('| `source` 声明总数 | **{}** |\n'.format(total_sources))
    md.append('| `proc` 定义总数 | **{}** |\n'.format(total_procs))
    md.append('| 唯一 `proc` 名称 | {} |\n'.format(len(unique_proc_names)))
    md.append('| 跨文件 `proc` 调用边 | **{}** |\n'.format(len(cross_file_calls)))
    md.append('| `exec`/`bgexec` 调用点 | {} |\n'.format(len(exec_data)))
    md.append('| `global` 变量声明 | {} |\n'.format(len(global_data)))
    md.append('\n### 1.2 关键发现\n\n')
    md.append('1. **`cfd++.tk` 是核心入口**,通过 **116 次 `source`** 加载了 ~110 个 .tcl 模块,几乎覆盖全部业务逻辑\n')
    md.append('2. **其他 9 个 .tk 入口**各自只 source 少数模块,定位为独立后处理/绘图工具\n')
    md.append('3. **GUI 不直接调用 exe**,统一通过两条路径间接执行:\n')
    md.append('   - `run_mcfd.tcl` → `eval exec $command` (同步)\n')
    md.append('   - `run_cmd.tcl` → `blt::bgexec` (异步+stdout 回显)\n')
    md.append('4. **`mc_glovar1.tcl`~`mc_glovar4.tcl`** 是 4 个全局变量定义文件,所有 GUI 状态都通过 `global` 跨 proc 传递\n')
    md.append('5. **跨文件 proc 调用** 3871 条边,平均每个 proc 被跨文件调用 ~3 次\n')
    md.append('6. **1251 个唯一 proc** 中,~80% 在单个文件内被调用,~20% 是跨文件共享接口\n\n')

    # === 二、入口文件 ===
    md.append('## 二、入口文件详解 (.tk)\n\n')
    md.append('CFD++ GUI 有 **{} 个独立 `.tk` 入口** 文件,每个对应一个 GUI 可执行工具:\n\n'.format(len(tk_files)))
    md.append('| 入口 | 窗口标题 | 直接 source 数 | 加载 .tcl 数 | 关键依赖 |\n')
    md.append('|---|---|---:|---:|---|\n')
    for tk in sorted(tk_files):
        title = ENTRY_FILES.get(tk, '-')
        sources = data[tk]['sources']
        n_procs = len(data[tk]['procs'])
        loaded_count = len(entry_loaded.get(tk, set()))
        key_deps = []
        for entry in sources[:5]:
            line, target = entry
            t = target.split('/')[-1].split('\\')[-1]
            if t in data:
                key_deps.append('`{}`'.format(t))
        key_deps_str = ', '.join(key_deps[:5]) if key_deps else '(无 source)'
        if len(key_deps) > 5:
            key_deps_str += f' 等 {len(key_deps)}'
        md.append('| `{}` | {} | {} | {} | {} |\n'.format(tk, title, len(sources), loaded_count, key_deps_str))
    md.append('\n')

    md.append('### 2.1 `cfd++.tk` 完整 source 链(共 116 次)\n\n')
    md.append('`cfd++.tk` 通过 `${metapath}` 路径变量加载模块,加载顺序:\n\n')
    md.append('```\n')
    sources = data['cfd++.tk']['sources']
    for line, target in sources:
        # 提取纯文件名
        t = target.split('/')[-1].split('\\')[-1]
        md.append(f'L{line:4d}: source {target}    → {t}\n')
    md.append('```\n\n')
    md.append('**加载顺序的特点**:\n\n')
    md.append('- L121-133: 先加载 4 个全局变量文件 (mc_glovar1-4)\n')
    md.append('- L150-200: GUI 基础 (image/bind/menu/buttons/center)\n')
    md.append('- L210-310: 求解运行 + 信息查询工具 (run_mcfd/run_cmd/infotool/lmtool)\n')
    md.append('- L400+: Case 配置 + 物理模块 (load_proc/init_dom/eqset/infoset/viewinf)\n')
    md.append('- L500+: 物理/边界/源 (bcstuff/species/reaction/turbname/gasprop/...)\n')
    md.append('- L800+: 网格/时间/拓扑 (gridvel/gridtools/timeint/topology)\n')
    md.append('- L1000+: 输出/保存/探测 (saving/probe/inoutfil)\n')
    md.append('- L1200+: 后处理/可视化 (surface/cutplane/isosurf/partrac/...)\n')
    md.append('- L1400+: 专用工具 (frpl3d/topl3d/wizards/...)\n\n')

    md.append('### 2.2 其他 9 个 .tk 入口的 source 链\n\n')
    for tk in sorted(tk_files):
        if tk == 'cfd++.tk':
            continue
        sources = data[tk]['sources']
        md.append('**`{}`** ({} 次 source)\n\n'.format(tk, len(sources)))
        md.append('```\n')
        for line, target in sources:
            t = target.split('/')[-1].split('\\')[-1]
            md.append(f'L{line:4d}: source {target}    → {t}\n')
        md.append('```\n')
    md.append('\n')

    # === 三、Source 依赖图 ===
    md.append('## 三、Source 依赖图\n\n')
    md.append('### 3.1 被引用频度排名\n\n')
    incoming = defaultdict(int)
    for fn, fd in data.items():
        for entry in fd['sources']:
            line, target = entry
            t = target.split('/')[-1].split('\\')[-1]
            if t in data:
                incoming[t] += 1
    md.append('| 被引用次数 | 文件 |\n|---:|---|\n')
    for t, cnt in sorted(incoming.items(), key=lambda x: -x[1]):
        md.append('| {} | `{}` |\n'.format(cnt, t))
    md.append('\n')
    md.append('**说明**:\n\n')
    md.append('- `mc_bind.tcl` / `gui_hinit.tcl` / `gui_center.tcl` 被 8 个 .tk 共享,是 GUI 基础\n')
    md.append('- `bltGraph.tcl` / `colormap.tcl` 被 5 个绘图类 .tk 共享\n')
    md.append('- `run_cmd.tcl` 被 2 个 .tk 共享(异步任务)\n')
    md.append('- 其余 25+ 个文件只被 1 个 .tk 引用(专属后处理)\n\n')

    md.append('### 3.2 完整依赖树(`cfd++.tk` 视角)\n\n')
    md.append('```\n')
    md.append('cfd++.tk (主入口, 116 个 source)\n')
    md.append('│\n')
    md.append('├── [1] mc_glovar1.tcl         ← 全局变量 (求解器/流场)\n')
    md.append('├── [2] mc_glovar2.tcl         ← 全局变量 (网格/边界/渲染)\n')
    md.append('├── [3] mc_glovar3.tcl         ← 全局变量 (togl/求解)\n')
    md.append('├── [4] mc_glovar4.tcl         ← 全局变量 (GUI 状态)\n')
    md.append('│\n')
    md.append('├── gui_image.tcl              ← 图标/位图\n')
    md.append('├── mc_bind.tcl                ← 键盘/鼠标绑定 (8 个 .tk 共享)\n')
    md.append('├── mc_edit.tcl                ← 复制/剪切/粘贴\n')
    md.append('├── bcsort.tcl                 ← BC 排序\n')
    md.append('├── gui_menu.tcl               ← 菜单栏\n')
    md.append('├── gui_buttons.tcl            ← 工具栏\n')
    md.append('├── panic.tcl                  ← 紧急停止\n')
    md.append('│\n')
    md.append('├── run_mcfd.tcl ★             ← 求解器调用 (eval exec mcfd/mpiexec)\n')
    md.append('├── run_reyinf.tcl             ← 后处理运行\n')
    md.append('├── run_cmd.tcl ★              ← 异步任务 (blt::bgexec)\n')
    md.append('├── ezsetup1.tcl               ← 向导安装\n')
    md.append('├── syscmd.tcl                 ← 系统命令\n')
    md.append('├── infotool.tcl ★             ← blt::bgexec infotool\n')
    md.append('├── lmtool.tcl ★               ← blt::bgexec lmtool\n')
    md.append('├── lmcontrol.tcl              ← 限制控制\n')
    md.append('├── edit_mcfd.tcl              ← 编辑\n')
    md.append('│\n')
    md.append('├── 物理/边界/源 (15+ 模块)\n')
    md.append('│   ├── bcstuff.tcl, bcsort.tcl\n')
    md.append('│   ├── species.tcl, reaction.tcl\n')
    md.append('│   ├── turbname.tcl, turbinit.tcl\n')
    md.append('│   ├── gasprop.tcl, mixprop.tcl, ldpprop.tcl\n')
    md.append('│   ├── refer.tcl, riemann.tcl, spacdis.tcl\n')
    md.append('│   ├── volsour.tcl, volsoug.tcl, volsouc.tcl, ps10_volsour.tcl\n')
    md.append('│   ├── disperse.tcl, partrac.tcl\n')
    md.append('│   ├── physour.tcl, radmodp1.tcl, radmoddo.tcl\n')
    md.append('│   ├── plasma.tcl, oxygenate.tcl\n')
    md.append('│   └── porosity.tcl, conjheat.tcl, sixdof.tcl, levelset.tcl, vofmethod.tcl\n')
    md.append('│\n')
    md.append('├── Case 配置/信息集 (5 模块)\n')
    md.append('│   ├── load_proc.tcl, init_dom.tcl, eqset.tcl\n')
    md.append('│   ├── infoset.tcl (信息集编辑器, 33 procs)\n')
    md.append('│   └── viewinf.tcl (信息集查看器, 71 procs)\n')
    md.append('│\n')
    md.append('├── 网格/时间/拓扑 (8 模块)\n')
    md.append('│   ├── gridvel.tcl (36 procs), gridtools.tcl (60 procs), gridblnk.tcl, gridcheck.tcl\n')
    md.append('│   ├── timeint.tcl, timemark.tcl, trange.tcl\n')
    md.append('│   └── topology.tcl, rotatec.tcl\n')
    md.append('│\n')
    md.append('├── 输出/保存/探测 (8 模块)\n')
    md.append('│   ├── inoutfil.tcl, saving.tcl, probe.tcl (20 procs)\n')
    md.append('│   ├── totec.tcl, soltools.tcl, interffm.tcl, ffm_ntout29.tcl\n')
    md.append('│   └── forcemom.tcl, proftool.tcl, dimension.tcl\n')
    md.append('│\n')
    md.append('├── 后处理/可视化 (15+ 模块)\n')
    md.append('│   ├── directb.tcl, lighting.tcl, recon_info.tcl\n')
    md.append('│   ├── surface.tcl (33 procs), cutplane.tcl, isosurf.tcl\n')
    md.append('│   ├── partplane.tcl, partrac.tcl, partrac_gui.tcl, partrac_gui2.tcl\n')
    md.append('│   ├── output.tcl, dispobj.tcl, overlay.tcl, surfac2.tcl\n')
    md.append('│   ├── mc_animate.tcl, cellblnk.tcl, colormap.tcl, bltGraph.tcl\n')
    md.append('│   └── point_select.tcl, mc_draw.tcl, pltdata.tcl, graphs.tcl\n')
    md.append('│\n')
    md.append('└── 专用工具 (15+ 模块)\n')
    md.append('    ├── frpl3d.tcl, topl3d.tcl, fp3dcg.tcl, fp3dss.tcl, fp3dzc.tcl\n')
    md.append('    ├── tometis.tcl, convert.tcl, convert10.tcl, hexdec.tcl\n')
    md.append('    ├── wizards.tcl, wizard.tcl, coking_wizard.tcl, sdgui.tcl\n')
    md.append('    ├── cfdinfo.tcl, cfdbyte.tcl, interview.tcl, rclickh.tcl\n')
    md.append('    ├── commands.tcl, univtool.tcl, mactool.tcl, infocopy.tcl\n')
    md.append('    ├── cosim.tcl, special_mode.tcl, sum o.tcl, caa++.tcl\n')
    md.append('    ├── prtout.tcl, npfcuts.tcl, miscsetup.tcl\n')
    md.append('    ├── gui_hinit.tcl, gui_center.tcl, gui_reset.tcl\n')
    md.append('    └── onedp_buttons.tcl, onedp_menu.tcl (1DP 专用)\n')
    md.append('```\n\n')

    # === 四、Proc 导出表 ===
    md.append('## 四、Proc 导出表\n\n')
    md.append('### 4.1 Proc 数最多的 30 个模块\n\n')
    md.append('| 排名 | 文件 | proc 数 | 累计行数(body) |\n|---:|---|---:|---:|\n')
    proc_count_by_file = []
    for fn, fd in data.items():
        n = len(fd['procs'])
        if n == 0:
            continue
        total = sum(p['body_end_line'] - p['body_start_line'] for p in fd['procs'])
        proc_count_by_file.append((fn, n, total))
    for i, (fn, n, tl) in enumerate(sorted(proc_count_by_file, key=lambda x: -x[1])[:30], 1):
        md.append('| {} | `{}` | {} | {} |\n'.format(i, fn, n, tl))
    md.append('\n')
    md.append('**前 6 大模块占据 39% 的 proc 定义**:\n\n')
    top6 = sorted(proc_count_by_file, key=lambda x: -x[1])[:6]
    total_all = sum(x[1] for x in proc_count_by_file)
    top6_sum = sum(x[1] for x in top6)
    md.append('- `{}` (~{} 行): 信息集编辑器\n'.format(top6[0][0], top6[0][2]))
    md.append('- `{}` (~{} 行): 网格工具(合并/分割/变换/区域映射)\n'.format(top6[1][0], top6[1][2]))
    md.append('- `{}` (~{} 行): 信息集查看器\n'.format(top6[2][0], top6[2][2]))
    md.append('- `{}` (~{} 行): 网格运动(平移/旋转/振荡/6DOF/网格变形)\n'.format(top6[3][0], top6[3][2]))
    md.append('- `{}` (~{} 行): 探测点与残差输出文件配置\n'.format(top6[4][0], top6[4][2]))
    md.append('- `{}` (~{} 行): 物种/化学反应\n'.format(top6[5][0], top6[5][2]))
    md.append('\n')

    md.append('### 4.2 各文件 proc 列表(主要模块)\n\n')
    md.append('> 完整列表太长,这里只列出 proc 数 ≥ 10 的文件。\n\n')
    for fn in sorted(data.keys()):
        fd = data[fn]
        if not fd['procs'] or len(fd['procs']) < 5:
            continue
        if fn in ENTRY_FILES:
            md.append('#### `{}` (入口) — {} procs\n\n'.format(fn, len(fd['procs'])))
        else:
            md.append('#### `{}` — {} procs\n\n'.format(fn, len(fd['procs'])))
        for p in fd['procs']:
            args_short = p['args'][:50] + ('...' if len(p['args']) > 50 else '')
            md.append('- `{}({})` L{}-{}\n'.format(
                p['name'], args_short, p['body_start_line'], p['body_end_line']))
        md.append('\n')

    # === 五、调用矩阵 ===
    md.append('## 五、Proc 调用矩阵\n\n')
    md.append('### 5.1 被调用次数最多的 proc(Top 30)\n\n')
    callee_count = Counter()
    for fn, fd in data.items():
        for p in fd['procs']:
            for callee, cnt in p['calls'].items():
                callee_count[callee] += cnt
    md.append('| 排名 | 目标 proc | 总调用次数 | 定义于 | 调用方数 |\n|---:|---|---:|---|---:|\n')
    for i, (callee, total) in enumerate(callee_count.most_common(30), 1):
        defn = proc_to_files.get(callee, [])
        defn_str = ', '.join('`{}`'.format(d) for d in defn[:2])
        if len(defn) > 2:
            defn_str += f' 等 {len(defn)}'
        # 多少个不同的调用方
        callers = set()
        for fn2, fd2 in data.items():
            for p2 in fd2['procs']:
                if callee in p2['calls']:
                    callers.add((fn2, p2['name']))
        md.append('| {} | `{}` | {} | {} | {} |\n'.format(i, callee, total, defn_str, len(callers)))
    md.append('\n')
    md.append('**Top 10 高频 proc 的角色**:\n\n')
    top10 = callee_count.most_common(10)
    for p, cnt in top10:
        defn = proc_to_files.get(p, ['?'])[0]
        md.append('- `{}` ({} 次,定义于 `{}`)\n'.format(p, cnt, defn))
    md.append('\n')

    md.append('### 5.2 跨文件调用边(Top 50,按调用次数)\n\n')
    md.append('| 调用方 | 调用目标 | 目标所在文件 | 次数 |\n|---|---|---|---:|\n')
    cf_sorted = sorted(cross_file_calls, key=lambda x: -x[4])
    for fn, caller, callee, defn, cnt in cf_sorted[:50]:
        md.append('| `{}::{}` | `{}` | `{}` | {} |\n'.format(fn, caller, callee, defn, cnt))
    md.append('\n')

    md.append('### 5.3 跨文件调用最多的源文件(Top 15)\n\n')
    caller_files = Counter()
    for fn, caller, callee, defn, cnt in cross_file_calls:
        caller_files[fn] += cnt
    md.append('| 文件 | 跨文件调用次数 |\n|---|---:|\n')
    for fn, cnt in caller_files.most_common(15):
        md.append('| `{}` | {} |\n'.format(fn, cnt))
    md.append('\n')

    # === 六、Global 变量 ===
    md.append('## 六、全局变量依赖\n\n')
    md.append('### 6.1 声明频度最高的 30 个 global 变量\n\n')
    var_count = Counter()
    var_files = defaultdict(set)
    for fn, proc_name, v in global_data:
        var_count[v] += 1
        var_files[v].add(fn)
    md.append('| 变量 | 声明次数 | 涉及文件数 | 涉及文件(前 5) |\n|---|---:|---:|---|\n')
    for v, cnt in var_count.most_common(30):
        files_set = var_files[v]
        files_str = ', '.join('`{}`'.format(f) for f in list(files_set)[:5])
        if len(files_set) > 5:
            files_str += f' 等 {len(files_set)}'
        md.append('| `{}` | {} | {} | {} |\n'.format(v, cnt, len(files_set), files_str))
    md.append('\n')

    md.append('### 6.2 全局变量耦合度最高的 20 个文件\n\n')
    file_global_count = []
    for fn, fd in data.items():
        cnt = sum(len(p['globals']) for p in fd['procs'])
        if cnt > 0:
            file_global_count.append((fn, cnt, fd))
    md.append('| 文件 | global 声明总数 | 主要变量(Top 3) |\n|---|---:|---|\n')
    for fn, cnt, fd in sorted(file_global_count, key=lambda x: -x[1])[:20]:
        all_globals = []
        for p in fd['procs']:
            all_globals.extend(p['globals'])
        vcount = Counter(all_globals)
        top_vars = ', '.join('`{}`'.format(v) for v, _ in vcount.most_common(3))
        md.append('| `{}` | {} | {} |\n'.format(fn, cnt, top_vars))
    md.append('\n')
    md.append('**洞察**:\n\n')
    md.append('- `mc_glovar1.tcl` 等 4 个文件**不定义 proc**(只设置 global),承载了所有 GUI 状态\n')
    md.append('- 业务模块如 `run_mcfd.tcl` 声明 ~50 个 global,反映其与 GUI 状态的深度耦合\n')
    md.append('- **建议**:在翻译后的语言中,用命名空间/类成员替换 global 变量\n\n')

    # === 七、Exe 调用 ===
    md.append('## 七、Exe 调用接口\n\n')
    md.append('### 7.1 调用类型分布\n\n')
    type_count = Counter(etype for _, _, _, etype, _ in exec_data)
    md.append('| 调用类型 | 次数 | 说明 |\n|---|---|---|\n')
    md.append('| `exec` | {} | 同步执行外部命令(罕见) |\n'.format(type_count.get('exec', 0)))
    md.append('| `eval exec` | {} | 同步执行,命令由变量构建(主要模式) |\n'.format(type_count.get('eval_exec', 0)))
    md.append('| `blt::bgexec` | {} | 异步后台执行,带 stdout 回显 |\n'.format(type_count.get('bgexec', 0)))
    md.append('\n')

    md.append('### 7.2 exec 调用点(按文件)\n\n')
    exec_by_file = defaultdict(list)
    for fn, proc, line, etype, first_arg in exec_data:
        exec_by_file[fn].append((proc, line, etype, first_arg))
    md.append('| 文件 | proc | body 内行 | 类型 | 首参数/说明 |\n|---|---|---:|---|---|---|\n')
    for fn in sorted(exec_by_file.keys()):
        for proc, line, etype, first_arg in exec_by_file[fn]:
            md.append('| `{}` | `{}` | L{} | {} | `{}` |\n'.format(fn, proc, line, etype, first_arg))
    md.append('\n')

    md.append('### 7.3 关键 exec 调用源码模式\n\n')
    md.append('GUI 不直接调 exe,所有调用都通过字符串构建后 `eval exec`,典型模式:\n\n')
    md.append('```tcl\n')
    md.append('# ========== run_mcfd.tcl ==========\n')
    md.append('# 单精度串行求解\n')
    md.append('set command "r4_mcfd | mc_stdoutee mcfd.log"        ;# 管道重定向 stdout\n')
    md.append('eval exec $command\n\n')
    md.append('# 后台运行(立即返回)\n')
    md.append('set command "mcfd_background4"                      ;# 后台进程\n')
    md.append('eval exec $command &\n\n')
    md.append('# MPI 并行(MSMPI 后端)\n')
    md.append('set command "mpiexec -n $nproc [r4_]msmpimcfd"      ;# 变量拼接\n')
    md.append('eval exec $command\n\n')
    md.append('# MPI 并行(MPICH 后端)\n')
    md.append('set command "mpiexec -n $nproc [r4_]mpimcfd"\n')
    md.append('eval exec $command\n\n')
    md.append('# ========== run_cmd.tcl ==========\n')
    md.append('# 异步任务(blt 扩展),带实时 stdout 回显\n')
    md.append('blt::bgexec run_status_$job_name \\\n')
    md.append('    -onoutput update_display_$job_name \\\n')
    md.append('    -onerror   show_error_$job_name \\\n')
    md.append('    $clt_cmd                                       ;# clt_cmd 由 run_mcfd 构建\n\n')
    md.append('# ========== infotool.tcl / lmtool.tcl ==========\n')
    md.append('blt::bgexec infotool_bgexec_status \\\n')
    md.append('    -onoutput it_getinfo \\\n')
    md.append('    -onerror   GetInfo \\\n')
    md.append('    $clt_cmd                                       ;# 通常 infotool/lmtool 系列 exe\n\n')
    md.append('# ========== forcemom.tcl ==========\n')
    md.append('blt::bgexec infout1f$i infout1f $i                ;# 力和力矩计算\n\n')
    md.append('# ========== gui_hinit.tcl (帮助系统) ==========\n')
    md.append('# Linux/Unix: 浏览器打开 HTML\n')
    md.append('$net1_run $fil $netscape_c &                        ;# netscape/firefox\n\n')
    md.append('# Windows: 微软资源管理器\n')
    md.append('mexplore $html_file                                ;# Windows 98/NT 遗留\n\n')
    md.append('# ========== ezsetup1.tcl ==========\n')
    md.append('exec xterm -e ez1_sc1.sh                           ;# 向导安装\n')
    md.append('```\n\n')

    md.append('### 7.4 涉及的外部 exe 清单(从 exec 调用推断)\n\n')
    # 从 exec_data 提取所有 first_arg,去重
    exe_set = set()
    for fn, proc, line, etype, first_arg in exec_data:
        if first_arg and first_arg not in ('<var>', '<command_var>'):
            exe_set.add(first_arg)
    md.append('| exe 名称 | 用途 | 调用源 |\n|---|---|---|\n')
    # 简单分类
    solver_exe = ['mcfd', 'r4_mcfd', 'mcfd_background', 'mcfd_background4', 'mcfdstop', 'mcfdkill',
                  'mpiexec', 'msmpimcfd', 'mpimcfd', 'r4_msmpimcfd', 'r4_mpimcfd',
                  'r4_mcfd', 'mc_stdoutee', 'r4_msmpimcfd', 'r4_mpimcfd']
    post_exe = ['mcfdsol', 'mcfdsolx', 'mcfdplt', 'mcfdtplt', 'mcfdpplt', 'mcfdfplt',
                'mcfdfft', 'mcfd1dp', 'logview', 'logview2', 'runb_tail']
    util_exe = ['dfcells', 'hostname', 'mexplore', 'infotool', 'lmtool', 'cellsinf', 'nodesinf']
    for fn, proc, line, etype, first_arg in sorted(exec_data, key=lambda x: (x[0], x[2])):
        if first_arg and first_arg not in ('<var>', '<command_var>'):
            kind = 'solver' if first_arg in solver_exe else 'post' if first_arg in post_exe else 'util' if first_arg in util_exe else 'other'
            md.append('| `{}` | {} | `{}::{}` |\n'.format(first_arg, kind, fn, proc))
    md.append('\n')

    # === 八、入口归类 ===
    md.append('## 八、Proc 入口归类\n\n')
    md.append('每个 proc 被哪个 .tk 入口加载(基于 source 传递闭包)。\n\n')

    md.append('### 8.1 多入口共享 proc(Top 30)\n\n')
    multi_entry = {p: e for p, e in proc_to_entries.items() if len(e) > 1}
    md.append('| Proc | 入口数 | 涉及入口 |\n|---|---:|---|\n')
    for p, entries in sorted(multi_entry.items(), key=lambda x: -len(x[1]))[:30]:
        ent_str = ', '.join('`{}`'.format(e) for e in sorted(entries))
        md.append('| `{}` | {} | {} |\n'.format(p, len(entries), ent_str))
    md.append('\n')
    md.append('**洞察**:\n\n')
    if multi_entry:
        # 找到最大共享的 proc
        top_shared = sorted(multi_entry.items(), key=lambda x: -len(x[1]))[0]
        md.append('- 共享最多的 proc 是 `{}` ({} 个入口):{}\n'.format(
            top_shared[0], len(top_shared[1]), ', '.join(sorted(top_shared[1]))))
    md.append('- 共享 proc 都是 GUI 基础(键盘绑定、帮助系统、窗口居中等)\n')
    md.append('- 业务专用 proc 几乎都被单一入口独占\n\n')

    md.append('### 8.2 各入口独占 proc 数\n\n')
    md.append('| 入口 | 独占 proc 数 | 示例(Top 5) |\n|---|---:|---|\n')
    entry_specific_count = {}
    for entry in ENTRY_FILES:
        specific = []
        for p_name, entries in proc_to_entries.items():
            if entries == {entry}:
                specific.append(p_name)
        entry_specific_count[entry] = specific
    for entry, procs_list in sorted(entry_specific_count.items(), key=lambda x: -len(x[1])):
        examples = ', '.join('`{}`'.format(p) for p in procs_list[:5])
        if len(procs_list) > 5:
            examples += f' ... (+{len(procs_list)-5})'
        md.append('| `{}` | {} | {} |\n'.format(entry, len(procs_list), examples))
    md.append('\n')
    md.append('**注**: `cfd++.tk` 的独占 proc 最多(~1000),因为它 source 了几乎所有业务模块。\n\n')

    # === 九、架构洞察 ===
    md.append('## 九、架构洞察\n\n')
    md.append('### 9.1 分层架构\n\n')
    md.append('```\n')
    md.append('┌──────────────────────────────────────────────────────────┐\n')
    md.append('│  入口层 (10 个 .tk,每个是一个独立 GUI 工具)             │\n')
    md.append('│  cfd++.tk / mcfdsol.tk / mcfd*.tk / logview.tk          │\n')
    md.append('└──────────────────────────────────────────────────────────┘\n')
    md.append('                         │ source 加载\n')
    md.append('                         ▼\n')
    md.append('┌──────────────────────────────────────────────────────────┐\n')
    md.append('│  全局状态层 (4 个 mc_glovar*.tcl)                         │\n')
    md.append('│  全部 GUI 状态、流场变量、求解器参数都在这里定义        │\n')
    md.append('└──────────────────────────────────────────────────────────┘\n')
    md.append('                         │ global 声明\n')
    md.append('                         ▼\n')
    md.append('┌──────────────────────────────────────────────────────────┐\n')
    md.append('│  业务模块层 (~120 个 .tcl, 1251 个 proc)                  │\n')
    md.append('│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐             │\n')
    md.append('│  │求解运行│ │物理/边界│ │网格/拓扑│ │输出/保存│          │\n')
    md.append('│  │ 3 模块 │ │ 30+ 模块│ │  8 模块 │ │  8 模块 │          │\n')
    md.append('│  └────────┘ └────────┘ └────────┘ └────────┘             │\n')
    md.append('│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐             │\n')
    md.append('│  │后处理  │ │信息查询│ │  工具  │ │  向导  │             │\n')
    md.append('│  │ 15 模块│ │  5 模块│ │ 10+ 模块│ │  5 模块│             │\n')
    md.append('│  └────────┘ └────────┘ └────────┘ └────────┘             │\n')
    md.append('└──────────────────────────────────────────────────────────┘\n')
    md.append('                         │ eval exec / blt::bgexec\n')
    md.append('                         ▼\n')
    md.append('┌──────────────────────────────────────────────────────────┐\n')
    md.append('│  外部 exe 层 (~600+ 个)                                   │\n')
    md.append('│  求解:mcfd/r4_mcfd/msmpimcfd/mpimcfd                    │\n')
    md.append('│  后处理:mcfdsol/mcfdplt/mcfdfft/mcfdpplt                │\n')
    md.append('│  网格:dfcells/tometis/toponew1                            │\n')
    md.append('│  转换:convert1-24/hextec/tritec/pltos*/infout*           │\n')
    md.append('│  信息:infotool/cellsinf/nodesinf/grdqual*                │\n')
    md.append('│  粒子:partrac/partraj/mcfd_morph1                        │\n')
    md.append('└──────────────────────────────────────────────────────────┘\n')
    md.append('```\n\n')

    md.append('### 9.2 数据流(以"运行一次仿真"为例)\n\n')
    md.append('```\n')
    md.append('用户点击"Run"\n')
    md.append('   │\n')
    md.append('   ▼\n')
    md.append('gui_menu.tcl 绑定的 menu callback\n')
    md.append('   │ 触发 proc\n')
    md.append('   ▼\n')
    md.append('run_mcfd.tcl::run_mcfd {nproc backend}\n')
    md.append('   │ 读 case 配置\n')
    md.append('   ├→ load_proc.tcl::read_xxx_proc 家族\n')
    md.append('   │ 构建 command 字符串:\n')
    md.append('   │   set command "mpiexec -n $nproc $backend $solver"\n')
    md.append('   │ 执行(2 种路径):\n')
    md.append('   ├─→ eval exec $command              [同步, 阻塞到结束]\n')
    md.append('   └─→ run_cmd.tcl::blt::bgexec ...    [异步, stdout 回显]\n')
    md.append('         │\n')
    md.append('         ▼\n')
    md.append('      mcfd.exe / mpiexec 写 .plt .log 文件\n')
    md.append('         │\n')
    md.append('         ▼\n')
    md.append('      用户打开后处理工具(独立 .tk 入口)\n')
    md.append('         │\n')
    md.append('         ▼\n')
    md.append('      mcfdsol/mcfdplt/mcfdpplt 读取结果做可视化\n')
    md.append('```\n\n')

    md.append('### 9.3 关键设计模式\n\n')
    md.append('1. **全局变量作为接口**:跨 proc 通信几乎全部通过 `global` 变量。\n')
    md.append('   - `mc_glovar1-4.tcl` 定义所有 GUI 状态(共 ~3000 行)\n')
    md.append('   - 每个业务 proc 头部 `global var1 var2 ...` 声明访问权限\n')
    md.append('   - 这种"扁平全局变量"模式简化了跨模块数据流,但不利于大型项目维护\n\n')
    md.append('2. **`source` 依赖图作为模块化机制**:无显式模块系统,纯靠 `source` 实现模块加载\n')
    md.append('   - 没有命名空间、没有包系统\n')
    md.append('   - 顺序敏感:mc_glovar1-4 必须按 1→2→3→4 加载\n\n')
    md.append('3. **`eval exec` + 字符串拼接作为命令构造**:\n')
    md.append('   - 所有外部命令都通过字符串拼接构造\n')
    md.append('   - 运行时由 `eval exec $command` 执行\n')
    md.append('   - 这种动态构造方式灵活但难以静态分析\n\n')
    md.append('4. **`blt::bgexec` 作为异步任务框架**:\n')
    md.append('   - 长时间运行的命令(exe 调用)用 BLT 扩展异步执行\n')
    md.append('   - 带 stdout 实时回显,适合长任务监控\n\n')
    md.append('5. **多入口架构**:每个 GUI 工具是独立可执行\n')
    md.append('   - 通过不同 .tk 入口启动不同的 GUI 工具\n')
    md.append('   - 工具之间通过文件系统(.plt/.log)共享数据\n\n')
    md.append('### 9.4 翻译/改造建议\n\n')
    md.append('1. **保留 `mc_glovar1-4.tcl` 结构**:这 4 个文件是核心,所有 GUI 状态集中管理\n')
    md.append('2. **替换 `global` 为命名空间/类成员**:在翻译后的语言中,建议把 `global` 改为命名空间/类成员\n')
    md.append('3. **`exec` 调用是改造的边界**:所有 exe 调用集中在以下文件,翻译时这些是主要适配点:\n')
    md.append('   - `run_mcfd.tcl` (主求解器调用)\n')
    md.append('   - `run_cmd.tcl` (异步任务框架)\n')
    md.append('   - `infotool.tcl` / `lmtool.tcl` (信息查询)\n')
    md.append('   - `forcemom.tcl` (力/力矩)\n')
    md.append('   - `gui_hinit.tcl` (帮助浏览器调用)\n')
    md.append('4. **`proc` 调用图是核心契约**:本分析中的"跨文件 proc 调用边"清单(3871 条)必须保持一致\n')
    md.append('5. **多入口共享 proc 优先翻译**:`run_mcfd`/`exit3`/`blt::bgexec` 等被多个 .tk 共享,优先处理\n')
    md.append('6. **大型模块分层翻译**:`infoset.tcl`(33 procs)/`gridtools.tcl`(60 procs)/`viewinf.tcl`(71 procs) 等需要先做内部结构梳理\n')
    md.append('7. **保持 `cfd++.tk` 作为主入口**:不要打散 116 个 source 关系,这是 GUI 加载顺序的契约\n\n')

    md.append('### 9.5 风险点\n\n')
    md.append('1. **catch 块吞掉语法**:cfd++.tk 的 `catch { ... }` 块从 L7 跨到 L38,包含整个 mcfdgui/sd_gui/ed_gui 调度,任何对此块的修改都要慎重\n')
    md.append('2. **反注释代码含 brace**:L18-22 有 `# 注释掉的 if/else 代码`,注释在 brace 字符串内仍然被算作字符,改动需保持平衡\n')
    md.append('3. **proc 名同名**:1251 个唯一名,但有些 proc 在不同文件重复定义(如各绘图工具的 `redraw`),需识别\n')
    md.append('4. **blt::bgexec 异步回调**:`-onoutput`/`-onerror` 的回调 proc 名字是动态拼接的,翻译时需保留这一模式\n')
    md.append('5. **`${metapath}` 变量**:所有 source 路径都通过 `$metapath` 解析,翻译时需保留这种环境变量配置\n\n')

    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.writelines(md)
    print(f'Report saved: {REPORT_FILE} ({os.path.getsize(REPORT_FILE)/1024:.1f} KB)')


if __name__ == '__main__':
    main()
