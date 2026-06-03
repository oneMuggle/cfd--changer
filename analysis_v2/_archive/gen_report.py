"""
生成 CFD_GUI_CallGraph_v2.md
"""
import json
import os
from collections import defaultdict, Counter

OUTPUT_DIR = r'E:\ProgrammingData\python\cfd++changer\analysis_v2'
JSON_FILE = os.path.join(OUTPUT_DIR, 'analysis_v9.json')
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

    # 1. 全局统计
    total_procs = sum(len(fd['procs']) for fd in data.values())
    total_sources = sum(len(fd['sources']) for fd in data.values())
    unique_proc_names = set()
    for fd in data.values():
        for p in fd['procs']:
            unique_proc_names.add(p['name'])
    # 跨文件 proc 调用统计
    cross_file_calls = []
    for fn, fd in data.items():
        for p in fd['procs']:
            for callee, cnt in p['calls'].items():
                # 找 callee 在哪些文件定义
                defn_files = [f for f, ffd in data.items()
                              if any(pp['name'] == callee for pp in ffd['procs'])]
                for df in defn_files:
                    if df != fn:
                        cross_file_calls.append((fn, p['name'], callee, df, cnt))

    # 2. source 依赖图 (谁 source 谁)
    source_edges = []
    for fn, fd in data.items():
        for line, target in fd['sources']:
            source_edges.append((fn, line, target))

    # 3. 入口归类:从每个 .tk 入口出发,递归 source,得到它加载的所有 .tcl
    def get_loaded_tcls(entry):
        """返回 entry 直接/间接 source 的所有 .tcl 文件(不含 entry 自身)"""
        loaded = set()
        stack = [entry]
        while stack:
            cur = stack.pop()
            if cur not in data:
                continue
            for line, target in data[cur]['sources']:
                # 解析 target (可能带路径,可能有变量)
                tname = target.split('/')[-1].split('\\')[-1]
                if tname.endswith('.tcl') and tname not in loaded and tname in data:
                    loaded.add(tname)
                    stack.append(tname)
        return loaded

    entry_loaded = {e: get_loaded_tcls(e) for e in ENTRY_FILES}

    # 每个 proc 被哪些 entry 加载
    proc_to_entries = defaultdict(set)
    for entry, loaded in entry_loaded.items():
        for tcl in loaded:
            for p in data[tcl]['procs']:
                proc_to_entries[p['name']].add(entry)

    # 每个 proc 在哪些文件中定义
    proc_to_files = defaultdict(list)
    for fn, fd in data.items():
        for p in fd['procs']:
            proc_to_files[p['name']].append(fn)

    # 4. exec/bgexec 统计
    exec_data = []
    for fn, fd in data.items():
        for p in fd['procs']:
            for line_in_body, etype, first_arg in p['execs']:
                exec_data.append((fn, p['name'], line_in_body, etype, first_arg))

    # 5. global 变量统计
    global_data = []
    for fn, fd in data.items():
        for p in fd['procs']:
            for v in p['globals']:
                global_data.append((fn, p['name'], v))

    # === 写报告 ===
    md = []
    md.append('# CFD++ Tcl/Tk GUI 调用关系深度分析 (v2)\n')
    md.append('> 基于源码静态分析(D:\\software\\CFD++\\METACOMP\\mlib\\mcfd.18.5\\exec\\gui_src\\)\n')
    md.append('> 分析覆盖全部 {} 个文件 ({} 个 .tcl + {} 个 .tk)\n'.format(
        len(files), len(tcl_files), len(tk_files)))
    md.append('> 提取了 6 个维度:source 依赖、proc 导出、调用矩阵、global 依赖、exe 接口、入口归类\n')
    md.append('')

    # === 第一章:执行摘要 ===
    md.append('## 一、执行摘要\n')
    md.append('| 指标 | 数值 |\n|---|---|\n')
    md.append('| 文件总数 | {} |\n'.format(len(files)))
    md.append('| .tcl 模块 | {} |\n'.format(len(tcl_files)))
    md.append('| .tk 入口 | {} |\n'.format(len(tk_files)))
    md.append('| source 声明总数 | {} |\n'.format(total_sources))
    md.append('| proc 定义总数 | {} |\n'.format(total_procs))
    md.append('| 唯一 proc 名称 | {} |\n'.format(len(unique_proc_names)))
    md.append('| 跨文件 proc 调用边 | {} |\n'.format(len(cross_file_calls)))
    md.append('| exec/bgexec 调用点 | {} |\n'.format(len(exec_data)))
    md.append('| global 变量声明 | {} |\n'.format(len(global_data)))
    md.append('')
    md.append('**关键发现**\n')
    md.append('- `cfd++.tk` 是核心入口,通过 116 次 `source` 加载了大部分 .tcl 模块\n')
    md.append('- 其他 9 个 .tk 入口各自只 source 少数模块(后处理/绘图工具)\n')
    md.append('- GUI 不直接调用 exe,统一通过 `run_mcfd.tcl` 的 `eval exec` 和 `run_cmd.tcl` 的 `blt::bgexec` 间接执行\n')
    md.append('- `mc_glovar1.tcl`~`mc_glovar4.tcl` 是全局变量定义文件(4 个),所有 GUI 状态都通过 global 传递\n')
    md.append('')

    # === 第二章:入口文件详解 ===
    md.append('## 二、入口文件详解 (.tk)\n')
    md.append('CFD++ GUI 有 {} 个独立入口 `.tk` 文件,每个对应一个 GUI 可执行工具。\n'.format(len(tk_files)))
    md.append('| 入口 | 窗口标题 | 加载 .tcl 数 | 关键依赖 |\n|---|---|---|---|\n')
    for tk in sorted(tk_files):
        title = ENTRY_FILES.get(tk, '-')
        sources = data[tk]['sources']
        n_procs = len(data[tk]['procs'])
        loaded_count = len(entry_loaded.get(tk, set()))
        # 关键依赖:取前几个 source
        key_deps = []
        for _, target in sources[:3]:
            t = target.split('/')[-1].split('\\')[-1]
            if t in data:
                key_deps.append(t)
        key_deps_str = ', '.join(key_deps[:3]) if key_deps else '(无 source)'
        if len(sources) > 3:
            key_deps_str += f' 等 {len(sources)} 个'
        md.append('| `{}` | {} | {} | {} |\n'.format(tk, title, loaded_count, key_deps_str))
    md.append('')
    md.append('### 2.1 cfd++.tk 主入口 source 链\n')
    if 'cfd++.tk' in data:
        sources = data['cfd++.tk']['sources']
        md.append('`cfd++.tk` 共 {} 次 `source` 调用,按顺序:\n'.format(len(sources)))
        md.append('```\n')
        for line, target in sources:
            t = target.split('/')[-1].split('\\')[-1]
            md.append(f'L{line:4d}: source {target}\n')
        md.append('```\n')
    md.append('')

    # === 第三章:Source 依赖图 ===
    md.append('## 三、Source 依赖图\n')
    md.append('### 3.1 总体依赖统计\n')
    # 统计每个文件被多少 entry/source
    incoming = defaultdict(int)
    for fn, fd in data.items():
        for _, target in fd['sources']:
            t = target.split('/')[-1].split('\\')[-1]
            if t in data:
                incoming[t] += 1
    md.append('| 被引用次数 | 文件 |\n|---|---|\n')
    for t, cnt in sorted(incoming.items(), key=lambda x: -x[1])[:30]:
        md.append('| {} | `{}` |\n'.format(cnt, t))
    md.append('')
    md.append('### 3.2 入口文件 source 链(分层)\n')
    md.append('```\n')
    md.append('cfd++.tk                    ← 主GUI入口, 116 个 source\n')
    md.append('├── 核心全局变量定义 (4 个,顺序加载)\n')
    md.append('│   ├── mc_glovar1.tcl      ← 求解器/流场变量\n')
    md.append('│   ├── mc_glovar2.tcl      ← 网格/边界/渲染\n')
    md.append('│   ├── mc_glovar3.tcl      ← togl/求解参数\n')
    md.append('│   └── mc_glovar4.tcl      ← GUI 状态/工具运行标记\n')
    md.append('│\n')
    md.append('├── GUI 基础 (5 个)\n')
    md.append('│   ├── gui_image.tcl       ← 图标/位图\n')
    md.append('│   ├── mc_bind.tcl         ← 键盘/鼠标绑定\n')
    md.append('│   ├── gui_hinit.tcl       ← 帮助系统\n')
    md.append('│   ├── gui_center.tcl      ← 窗口居中\n')
    md.append('│   └── bcsort.tcl          ← BC 排序工具\n')
    md.append('│\n')
    md.append('├── 求解运行 (3 个,核心)\n')
    md.append('│   ├── run_mcfd.tcl        ★ 求解器调用:eval exec mcfd/mpiexec\n')
    md.append('│   ├── run_reyinf.tcl      ← 后处理运行\n')
    md.append('│   └── run_cmd.tcl         ★ 异步任务:blt::bgexec\n')
    md.append('│\n')
    md.append('├── 信息集/Case 配置 (5 个)\n')
    md.append('│   ├── load_proc.tcl       ← 从文件加载\n')
    md.append('│   ├── init_dom.tcl        ← 域初始化\n')
    md.append('│   ├── eqset.tcl           ← 方程组\n')
    md.append('│   ├── infoset.tcl         ← 信息集编辑器\n')
    md.append('│   └── viewinf.tcl         ← 信息集查看器\n')
    md.append('│\n')
    md.append('├── 物理/边界/源 (10+ 个)\n')
    md.append('│   ├── bcstuff.tcl         ← 边界条件\n')
    md.append('│   ├── species.tcl/reaction.tcl  ← 组分/反应\n')
    md.append('│   ├── turbname.tcl/turbinit.tcl ← 湍流\n')
    md.append('│   ├── gasprop.tcl/mixprop.tcl/ldpprop.tcl ← 物性\n')
    md.append('│   ├── refer.tcl/riemann.tcl/spacdis.tcl ← 参考/求解器/格式\n')
    md.append('│   ├── volsour.tcl/volsoug.tcl/volsouc.tcl/ps10_volsour.tcl ← 体积源\n')
    md.append('│   ├── disperse.tcl        ← 弥散相\n')
    md.append('│   ├── physour.tcl/radmodp1.tcl/radmoddo.tcl ← 物理源/辐射\n')
    md.append('│   ├── porosity.tcl/conjheat.tcl/sixdof.tcl ← 多孔/共轭换热/6DOF\n')
    md.append('│   ├── plasma.tcl/oxygenate.tcl/coking_wizard.tcl ← 特殊\n')
    md.append('│   └── ...\n')
    md.append('│\n')
    md.append('├── 网格/时间/拓扑 (8 个)\n')
    md.append('│   ├── gridvel.tcl/gridtools.tcl/gridblnk.tcl/gridcheck.tcl ← 网格\n')
    md.append('│   ├── timeint.tcl/timemark.tcl/trange.tcl ← 时间\n')
    md.append('│   └── topology.tcl/rotatec.tcl ← 拓扑/旋转\n')
    md.append('│\n')
    md.append('├── 输出/保存/探测 (8 个)\n')
    md.append('│   ├── inoutfil.tcl/saving.tcl/probe.tcl ← I/O/探测\n')
    md.append('│   ├── totec.tcl/soltools.tcl/interffm.tcl/ffm_ntout29.tcl ← 后处理转换\n')
    md.append('│   └── forcemom.tcl/proftool.tcl/dimension.tcl ← 力/轮廓/无量纲\n')
    md.append('│\n')
    md.append('├── 后处理/可视化 (15+ 个)\n')
    md.append('│   ├── directb.tcl/lighting.tcl/recon_info.tcl ← 渲染\n')
    md.append('│   ├── surface.tcl/cutplane.tcl/isosurf.tcl/partplane.tcl/partrac.tcl\n')
    md.append('│   ├── output.tcl/dispobj.tcl/overlay.tcl/surfac2.tcl\n')
    md.append('│   ├── mc_animate.tcl/partrac_gui.tcl/partrac_gui2.tcl\n')
    md.append('│   ├── cellblnk.tcl/colormap.tcl/bltGraph.tcl\n')
    md.append('│   └── point_select.tcl/mc_draw.tcl/pltdata.tcl\n')
    md.append('│\n')
    md.append('├── 专用工具 (10+ 个)\n')
    md.append('│   ├── frpl3d.tcl/topl3d.tcl/fp3dcg.tcl/fp3dss.tcl/fp3dzc.tcl ← 网格格式\n')
    md.append('│   ├── tometis.tcl/convert.tcl/convert10.tcl/hexdec.tcl ← 转换\n')
    md.append('│   ├── wizards.tcl/wizard.tcl/coking_wizard.tcl/sdgui.tcl ← 向导\n')
    md.append('│   ├── infotool.tcl/lmtool.tcl/lmcontrol.tcl/infoset.tcl ← 信息\n')
    md.append('│   ├── syscmd.tcl/ezsetup1.tcl/panic.tcl/edit_mcfd.tcl/oldstuff.tcl\n')
    md.append('│   ├── cosim.tcl/levelset.tcl/vofmethod.tcl/special_mode.tcl\n')
    md.append('│   ├── prtout.tcl/mactool.tcl/infocopy.tcl/univtool.tcl/commands.tcl\n')
    md.append('│   ├── npfcuts.tcl/caa++.tcl/conjheat.tcl/miscsetup.tcl\n')
    md.append('│   ├── cfdinfo.tcl/cfdbyte.tcl/interview.tcl/rclickh.tcl\n')
    md.append('│   └── sumo.tcl/conjheat.tcl ← SUMO/共轭换热\n')
    md.append('│\n')
    md.append('└── GUI 菜单/按钮 (3 个)\n')
    md.append('    ├── gui_menu.tcl        ← 菜单栏\n')
    md.append('    ├── gui_buttons.tcl     ← 工具栏\n')
    md.append('    └── gui_reset.tcl       ← GUI 重置\n')
    md.append('```\n')
    md.append('')
    md.append('### 3.3 其他 9 个 .tk 入口的 source 链\n')
    for tk in sorted(tk_files):
        if tk == 'cfd++.tk':
            continue
        sources = data[tk]['sources']
        md.append('**`{}`** ({} 次 source)\n'.format(tk, len(sources)))
        md.append('```\n')
        for line, target in sources:
            t = target.split('/')[-1].split('\\')[-1]
            md.append(f'L{line:4d}: source {target}\n')
        md.append('```\n')
    md.append('')

    # === 第四章:Proc 导出表 ===
    md.append('## 四、Proc 导出表\n')
    md.append('### 4.1 总体统计\n')
    md.append('| 文件 | proc 数 | 行数范围 |\n|---|---|---|\n')
    proc_count_by_file = [(fn, len(fd['procs']),
                           min((p['body_start_line'] for p in fd['procs']), default=0),
                           max((p['body_end_line'] for p in fd['procs']), default=0))
                          for fn, fd in data.items()]
    for fn, n, lmin, lmax in sorted(proc_count_by_file, key=lambda x: -x[1])[:30]:
        if n == 0:
            continue
        md.append('| `{}` | {} | L{}-L{} |\n'.format(fn, n, lmin, lmax))
    md.append('')
    md.append('### 4.2 大型模块(proc 数 ≥ 20)\n')
    md.append('| 文件 | proc 数 | 总行数 | 说明 |\n|---|---|---|---|\n')
    big_modules = []
    for fn, fd in data.items():
        n = len(fd['procs'])
        if n >= 20:
            total_lines = sum(p['body_end_line'] - p['body_start_line'] for p in fd['procs'])
            big_modules.append((fn, n, total_lines))
    for fn, n, tl in sorted(big_modules, key=lambda x: -x[1]):
        try:
            path = os.path.join(r'D:\software\CFD++\METACOMP\mlib\mcfd.18.5\exec\gui_src', fn)
            total = sum(1 for _ in open(path, 'r', encoding='utf-8', errors='replace'))
        except:
            total = '?'
        md.append('| `{}` | {} | {} (body) / {} (file) | {} |\n'.format(fn, n, tl, total, ''))
    md.append('')
    md.append('### 4.3 各文件 proc 全量列表(主要模块)\n')
    for fn in sorted(data.keys()):
        fd = data[fn]
        if not fd['procs']:
            continue
        if fn in ENTRY_FILES:
            md.append('#### `{}` (入口) — {} procs\n'.format(fn, len(fd['procs'])))
        else:
            md.append('#### `{}` — {} procs\n'.format(fn, len(fd['procs'])))
        for p in fd['procs']:
            args_short = p['args'][:60] + ('...' if len(p['args']) > 60 else '')
            size = p['body_size']
            md.append('- `{}{}` — L{}-L{} ({} bytes)\n'.format(
                p['name'], args_short, p['body_start_line'], p['body_end_line'], size))
        md.append('\n')

    # === 第五章:Proc 调用矩阵 ===
    md.append('## 五、Proc 调用矩阵(跨文件)\n')
    md.append('### 5.1 调用频度最高的目标 proc(被多少个文件/不同位置调用)\n')
    callee_count = Counter()
    for fn, fd in data.items():
        for p in fd['procs']:
            for callee, cnt in p['calls'].items():
                callee_count[callee] += cnt
    md.append('| 目标 proc | 总调用次数 | 定义于 | 被调用方 |\n|---|---|---|---|\n')
    for callee, total in callee_count.most_common(50):
        defn = proc_to_files.get(callee, [])
        defn_str = ', '.join('`{}`'.format(d) for d in defn[:3])
        if len(defn) > 3:
            defn_str += f' 等 {len(defn)} 处'
        callers = []
        for fn2, fd2 in data.items():
            for p2 in fd2['procs']:
                if callee in p2['calls']:
                    callers.append('`{}::{}`'.format(fn2, p2['name']))
        callers_str = ', '.join(callers[:3])
        if len(callers) > 3:
            callers_str += f' 等 {len(callers)} 处'
        md.append('| `{}` | {} | {} | {} |\n'.format(callee, total, defn_str, callers_str))
    md.append('')
    md.append('### 5.2 跨文件调用边(目标 proc 不在调用方所在文件)\n')
    md.append('| 调用方 | 调用目标 | 目标所在文件 | 次数 |\n|---|---|---|---|\n')
    cf_sorted = sorted(cross_file_calls, key=lambda x: -x[4])
    for fn, caller, callee, defn, cnt in cf_sorted[:80]:
        md.append('| `{}::{}` | `{}` | `{}` | {} |\n'.format(fn, caller, callee, defn, cnt))
    md.append('')

    # === 第六章:全局变量依赖 ===
    md.append('## 六、全局变量依赖\n')
    md.append('### 6.1 global 声明频度最高的变量\n')
    var_count = Counter()
    var_files = defaultdict(set)
    for fn, proc_name, v in global_data:
        var_count[v] += 1
        var_files[v].add(fn)
    md.append('| 变量 | 声明次数 | 涉及文件数 | 涉及文件(前 5) |\n|---|---|---|---|\n')
    for v, cnt in var_count.most_common(50):
        files_set = var_files[v]
        files_str = ', '.join('`{}`'.format(f) for f in list(files_set)[:5])
        if len(files_set) > 5:
            files_str += f' 等 {len(files_set)}'
        md.append('| `{}` | {} | {} | {} |\n'.format(v, cnt, len(files_set), files_str))
    md.append('')
    md.append('### 6.2 各文件的 global 声明模式\n')
    md.append('每个文件的 `global` 声明数量(说明该文件与全局状态的耦合度):\n\n')
    md.append('| 文件 | global 声明数 | 主要变量 |\n|---|---|---|\n')
    file_global_count = []
    for fn, fd in data.items():
        cnt = sum(len(p['globals']) for p in fd['procs'])
        if cnt > 0:
            file_global_count.append((fn, cnt, fd))
    for fn, cnt, fd in sorted(file_global_count, key=lambda x: -x[1])[:30]:
        # 取前 3 个最常被引用的变量
        all_globals = []
        for p in fd['procs']:
            all_globals.extend(p['globals'])
        vcount = Counter(all_globals)
        top_vars = ', '.join('`{}`'.format(v) for v, _ in vcount.most_common(3))
        md.append('| `{}` | {} | {} |\n'.format(fn, cnt, top_vars))
    md.append('')

    # === 第七章:exe 调用接口 ===
    md.append('## 七、Exe 调用接口\n')
    md.append('### 7.1 调用类型分布\n')
    type_count = Counter(etype for _, _, _, etype, _ in exec_data)
    md.append('| 调用类型 | 次数 | 说明 |\n|---|---|---|\n')
    md.append('| `exec` | {} | 同步执行外部命令 |\n'.format(type_count.get('exec', 0)))
    md.append('| `eval exec` | {} | 同步执行,命令由变量构建 |\n'.format(type_count.get('eval_exec', 0)))
    md.append('| `blt::bgexec` | {} | 异步后台执行(带 stdout 回显) |\n'.format(type_count.get('bgexec', 0)))
    md.append('')
    md.append('### 7.2 所有 exec 调用点(按文件归类)\n')
    exec_by_file = defaultdict(list)
    for fn, proc, line, etype, first_arg in exec_data:
        exec_by_file[fn].append((proc, line, etype, first_arg))
    md.append('| 文件 | proc | 行(在 body 内) | 类型 | 首参数 |\n|---|---|---|---|---|\n')
    for fn in sorted(exec_by_file.keys()):
        for proc, line, etype, first_arg in exec_by_file[fn]:
            md.append('| `{}` | `{}` | L{} | {} | `{}` |\n'.format(fn, proc, line, etype, first_arg))
    md.append('')
    md.append('### 7.3 关键 exec/bgexec 调用的源码上下文(用于理解参数构造)\n')
    md.append('下面展示 `run_mcfd.tcl` 和 `run_cmd.tcl` 中实际的 exec 命令构建模式:\n\n')
    md.append('```tcl\n')
    md.append('# 典型模式1:run_mcfd.tcl 中构建命令\n')
    md.append('set command "$r4_mcfd | mc_stdoutee mcfd.log"   ;# 单精度管道输出\n')
    md.append('set command "mcfd_background4"                    ;# 后台运行\n')
    md.append('set command "mpiexec -n $nproc [r4_]msmpimcfd"    ;# MPI 并行\n')
    md.append('eval exec $command                               ;# 执行\n\n')
    md.append('# 典型模式2:run_cmd.tcl 中异步任务\n')
    md.append('blt::bgexec run_status_$job_name \\\n')
    md.append('    -onoutput update_display_$job_name \\\n')
    md.append('    -onerror   show_error_$job_name \\\n')
    md.append('    $clt_cmd                                    ;# clt_cmd 由 run_mcfd.tcl 构建\n\n')
    md.append('# 典型模式3:infotool.tcl 中信息查询\n')
    md.append('blt::bgexec infotool_bgexec_status \\\n')
    md.append('    -onoutput it_getinfo \\\n')
    md.append('    -onerror   GetInfo \\\n')
    md.append('    $clt_cmd\n')
    md.append('```\n')

    # === 第八章:入口归类 ===
    md.append('## 八、Proc 入口归类\n')
    md.append('每个 proc 被哪个 .tk 入口加载(基于 source 传递闭包)。\n\n')
    md.append('| Proc | 入口 (source 链) |\n|---|---|\n')
    # 只列出在多个 entry 中出现的 proc (共享)
    multi_entry = {p: e for p, e in proc_to_entries.items() if len(e) > 1}
    md.append('**多入口共享 proc ({} 个)**\n\n'.format(len(multi_entry)))
    for p, entries in sorted(multi_entry.items(), key=lambda x: -len(x[1]))[:50]:
        ent_str = ', '.join('`{}`'.format(e) for e in entries)
        md.append('| `{}` | {} |\n'.format(p, ent_str))
    md.append('\n')
    md.append('**单入口独占 proc (按入口统计)**\n\n')
    md.append('| 入口 | 独占 proc 数 | 示例 proc |\n|---|---|---|\n')
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
    md.append('')

    # === 第九章:架构洞察 ===
    md.append('## 九、架构洞察\n')
    md.append('### 9.1 分层架构\n')
    md.append('```\n')
    md.append('┌────────────────────────────────────────────────────────┐\n')
    md.append('│           .tk 入口层 (10 个独立工具入口)               │\n')
    md.append('│  cfd++.tk / mcfdsol.tk / mcfd*.tk / logview.tk        │\n')
    md.append('└────────────────────────────────────────────────────────┘\n')
    md.append('                          │ source\n')
    md.append('                          ▼\n')
    md.append('┌────────────────────────────────────────────────────────┐\n')
    md.append('│       GUI 核心 (4 个全局变量 + 5 个 GUI 基础)          │\n')
    md.append('│  mc_glovar1-4.tcl + gui_*.tcl + mc_bind.tcl            │\n')
    md.append('└────────────────────────────────────────────────────────┘\n')
    md.append('                          │ 提供 global 变量\n')
    md.append('                          ▼\n')
    md.append('┌────────────────────────────────────────────────────────┐\n')
    md.append('│            业务模块 (~120 个 .tcl)                      │\n')
    md.append('│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐            │\n')
    md.append('│  │求解运行│ │物理/边界│ │网格/拓扑│ │输出/保存│         │\n')
    md.append('│  └────────┘ └────────┘ └────────┘ └────────┘            │\n')
    md.append('└────────────────────────────────────────────────────────┘\n')
    md.append('                          │ exec / blt::bgexec\n')
    md.append('                          ▼\n')
    md.append('┌────────────────────────────────────────────────────────┐\n')
    md.append('│              外部 exe (~600+ 个)                        │\n')
    md.append('│  求解器:mcfd/r4_mcfd/msmpimcfd/mpimcfd                │\n')
    md.append('│  后处理:mcfdsol/mcfdplt/mcfdfft/mcfdpplt               │\n')
    md.append('│  网格工具:dfcells/tometis/toponew1                      │\n')
    md.append('│  转换:convert1-24/hextec/tritec/pltos*/infout*         │\n')
    md.append('└────────────────────────────────────────────────────────┘\n')
    md.append('```\n\n')
    md.append('### 9.2 数据流(以"运行仿真"为例)\n')
    md.append('```\n')
    md.append('1. 用户点击"Run"\n')
    md.append('   ↓\n')
    md.append('2. gui_menu.tcl 触发的 menu callback\n')
    md.append('   ↓ 调用\n')
    md.append('3. run_mcfd.tcl::run_mcfd { }  (顶层入口 proc)\n')
    md.append('   ├─ 读 case 配置 (调用 load_proc.tcl 中的 read_* 家族)\n')
    md.append('   ├─ 构建 command 字符串:\n')
    md.append('   │   eval exec $command    ← 同步路径\n')
    md.append('   │   或\n')
    md.append('   │   blt::bgexec ...       ← 异步路径(经 run_cmd.tcl)\n')
    md.append('   └─ 启动 mcfd/r4_mcfd/mpiexec 等\n')
    md.append('       ↓\n')
    md.append('4. mcfd.exe 写 .plt/.log 文件\n')
    md.append('   ↓\n')
    md.append('5. 用户打开后处理工具(mcfdsol/mcfdplt 等独立 .tk)\n')
    md.append('   ↓\n')
    md.append('6. 工具读取结果文件,做可视化/曲线\n')
    md.append('```\n\n')
    md.append('### 9.3 关键设计模式\n')
    md.append('1. **全局变量作为接口**:跨 proc 通信几乎全部通过 `global` 变量。\n')
    md.append('   - `mc_glovar1-4.tcl` 定义所有 GUI 状态\n')
    md.append('   - 每个 proc 头部 `global var1 var2 ...` 声明访问权限\n')
    md.append('2. **source 依赖图作为模块化机制**:无显式模块系统,纯靠 `source` 实现模块加载\n')
    md.append('3. **eval exec + 字符串拼接作为命令构造**:所有外部命令都通过字符串拼接,运行时由 eval 执行\n')
    md.append('4. **blt::bgexec 作为异步任务框架**:长时间运行的命令(exe 调用)用 BLT 扩展异步执行,带 stdout 回显\n')
    md.append('5. **entry 入口模式**:每个 GUI 工具是独立可执行,通过不同 .tk 入口启动\n')
    md.append('')
    md.append('### 9.4 翻译/改造建议\n')
    md.append('1. **不要打散模块**:保留 `mc_glovar1-4.tcl` 4 个文件结构,所有 GUI 状态集中管理\n')
    md.append('2. **替换 global 为命名空间**:在翻译后的语言中,建议把 `global` 变量改为命名空间/类成员\n')
    md.append('3. **exec 调用是边界**:所有 exe 调用集中在 `run_mcfd.tcl` + `run_cmd.tcl` + `infotool.tcl` + `lmtool.tcl` + `forcemom.tcl`,翻译时这些是主要适配点\n')
    md.append('4. **proc 调用图是核心**:本分析中的"跨文件 proc 调用边"清单是翻译时需要保持一致的接口契约\n')
    md.append('5. **多入口共享 proc 优先翻译**:`run_mcfd`/`exit3`/`blt::bgexec` 等被多个 .tk 共享,优先处理\n')

    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.writelines(md)
    print(f'Report saved: {REPORT_FILE} ({os.path.getsize(REPORT_FILE)/1024:.1f} KB)')


if __name__ == '__main__':
    main()
