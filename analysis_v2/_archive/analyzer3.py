"""
CFD++ GUI 调用关系分析器 v3
新策略:
1. 文件级:用基于行的扫描找 'source' 声明
2. proc 级:对每个 proc 独立解析 body,提取内部 call/global/exec
3. 跨文件:从所有 proc 中识别调用,匹配到其他文件导出的 proc
"""
import os
import re
import json
from collections import defaultdict

GUI_SRC = r"D:\software\CFD++\METACOMP\mlib\mcfd.18.5\exec\gui_src"
OUTPUT_DIR = r"E:\ProgrammingData\python\cfd++changer\analysis_v2"

# 已知 Tcl 内置命令,用于过滤
BUILTIN_CMDS = set("""
after append array bgerror binary break catch cd clock close concat continue
dde eof error eval exec exit expr fblocked fconfigure fcopy file
fileevent flush for foreach format gets glob global history if incr info
interp join lappend lindex linsert list llength load lower lrange
lreplace lsearch lsort mathfunc mathop memory msgcat namespace open
package pid pkg_mkcreate pkg_mkIndex proc puts pwd re_syntax read regexp
registry regsub rename resource return scan search seek set socket
source split string subst switch tclLog tack tell time trace unknown
unset update uplevel upvar variable vwait while tk tk_chooseColor tk_getOpenFile
wm winfo bind focus grab image bell clipboard
""".split())


def collect_files():
    files = []
    for entry in sorted(os.listdir(GUI_SRC)):
        full = os.path.join(GUI_SRC, entry)
        if not os.path.isfile(full):
            continue
        if entry.endswith('.tcl') or entry.endswith('.tk'):
            files.append(entry)
    return files


def find_source_lines(text):
    """找所有 'source filename' 调用,返回 [(line, target)]"""
    results = []
    # 匹配: source FILE  (FILE 是非空白非注释的 word)
    # 简化:在每行找 'source' 关键字
    lines = text.split('\n')
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('#'):
            continue
        # 匹配 'source FILENAME'
        m = re.match(r'^source\s+(\S+)', stripped)
        if m:
            results.append((i, m.group(1)))
    return results


def find_procs_in_text(text):
    """扫描文件找所有 proc 定义,返回 [{name, args, body_start_line, body_end_line, body_text, define_line}]"""
    procs = []
    lines = text.split('\n')
    n = len(lines)
    i = 0  # line index (0-based)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith('#'):
            i += 1
            continue
        # 匹配: proc NAME { ARGS } { BODY
        # 由于 proc body 可能跨多行,且包含 { 和 },我们需要 brace 匹配
        # 简化为: 找 'proc' 后跟 name 后跟 {args} 后跟 {body}
        m = re.match(r'^proc\s+(\S+)\s*\{', stripped)
        if m:
            proc_name = m.group(1)
            define_line = i + 1
            # 找 args 的结束 (下一个匹配的 })
            # 我们扫描字符,跟踪 brace 深度
            # 找 name 后的 {
            idx = stripped.index('{', stripped.index('proc'))
            depth = 1
            j = idx + 1
            while j < len(stripped) and depth > 0:
                if stripped[j] == '{':
                    depth += 1
                elif stripped[j] == '}':
                    depth -= 1
                j += 1
            # args 结束,j 指向 args 后第一个字符
            # 跳过空白
            while j < len(stripped) and stripped[j] in ' \t':
                j += 1
            # 应该遇到 {
            if j < len(stripped) and stripped[j] == '{':
                body_start_line = i + 1
                # 找 body 结束 (跨行 brace 匹配)
                body_text_start_char = j + 1  # 在 stripped 中的位置
                # 收集跨行内容
                full_text = text
                # 找 proc body 的实际字符位置
                line_starts = [0]
                for k, ln in enumerate(lines):
                    line_starts.append(line_starts[-1] + len(ln) + 1)  # +1 for \n
                proc_def_pos = line_starts[i]
                # 在 full_text 中,proc NAME 的开始位置
                proc_name_pos = full_text.find(proc_name, proc_def_pos)
                # args 的开始 (在 proc_name 之后)
                args_start = full_text.find('{', proc_name_pos)
                # 现在 brace 深度匹配 args
                depth = 1
                p = args_start + 1
                while p < len(full_text) and depth > 0:
                    if full_text[p] == '{':
                        depth += 1
                    elif full_text[p] == '}':
                        depth -= 1
                    p += 1
                # p 指向 args 后的字符
                # 跳过空白
                while p < len(full_text) and full_text[p] in ' \t':
                    p += 1
                # 跳过 \n
                while p < len(full_text) and full_text[p] in '\r\n':
                    p += 1
                # 跳过空白
                while p < len(full_text) and full_text[p] in ' \t':
                    p += 1
                if p < len(full_text) and full_text[p] == '{':
                    body_start = p + 1
                    # brace 深度匹配 body
                    depth = 1
                    p += 1
                    body_end = p
                    while p < len(full_text) and depth > 0:
                        if full_text[p] == '{':
                            depth += 1
                        elif full_text[p] == '}':
                            depth -= 1
                            if depth == 0:
                                body_end = p
                                break
                        p += 1
                    # 计算 body 的行号
                    body_end_line = full_text[:body_end].count('\n') + 1
                    body_text = full_text[body_start:body_end]
                    # 提取 args
                    args_text = full_text[args_start+1:p-1]  # body 前的所有
                    # 实际上 args 在 body 前,需要重新定位
                    # 简化: args 是 body 前的 brace 内容
                    # 找 args: 在 body_start 之前最近的两个 { } 块
                    # 重新从 proc_name 之后开始扫描
                    p2 = proc_name_pos + len(proc_name)
                    while p2 < len(full_text) and full_text[p2] in ' \t\n\r':
                        p2 += 1
                    if p2 < len(full_text) and full_text[p2] == '{':
                        args_start = p2
                        d = 1
                        p2 += 1
                        while p2 < len(full_text) and d > 0:
                            if full_text[p2] == '{':
                                d += 1
                            elif full_text[p2] == '}':
                                d -= 1
                            p2 += 1
                        args_text = full_text[args_start+1:p2-1]
                    else:
                        args_text = ''

                    procs.append({
                        'name': proc_name,
                        'args': args_text.strip(),
                        'body_start_line': body_start_line,
                        'body_end_line': body_end_line,
                        'body': body_text,
                    })
                    # 跳到 body 结束之后
                    # 转换 body_end 为行号
                    new_i = full_text[:p+1].count('\n')
                    i = new_i
                    continue
        i += 1
    return procs


def find_globals_in_body(body):
    """在 proc body 中找 'global VAR' 声明,返回变量名列表"""
    globals_list = []
    # 简化: 按行扫描找 'global' 关键字
    for line in body.split('\n'):
        stripped = line.strip()
        if stripped.startswith('#'):
            continue
        m = re.match(r'^global\s+(.+?)(?:;|$)', stripped)
        if m:
            # 解析变量名(可能是多个,用空白分隔)
            var_part = m.group(1)
            for v in var_part.split():
                if not v.startswith('#'):
                    globals_list.append(v)
    return globals_list


def find_exec_in_body(body):
    """在 proc body 中找 'exec' 和 'blt::bgexec' 调用,返回 [(line_in_body, type, first_arg)]"""
    results = []
    for i, line in enumerate(body.split('\n'), 1):
        stripped = line.strip()
        if stripped.startswith('#'):
            continue
        # 匹配 'exec' 关键字
        if re.match(r'^\s*exec\s+', line):
            m = re.match(r'^\s*exec\s+(\S+)', line)
            if m:
                results.append((i, 'exec', m.group(1)))
        # 匹配 'blt::bgexec' 关键字
        if 'blt::bgexec' in line:
            m = re.search(r'blt::bgexec\s+(\S+)', line)
            if m:
                results.append((i, 'bgexec', m.group(1)))
        # 匹配 'eval exec'
        if 'eval exec' in line:
            results.append((i, 'eval_exec', '<command_var>'))
    return results


def find_calls_in_body(body, all_known_procs):
    """
    在 proc body 中找所有 proc 调用,返回 {callee: count}
    只统计已知的 proc 名称(其他视为变量或关键字)
    """
    calls = defaultdict(int)
    # 用 brace 感知的方式扫描 body
    # 简化: 找所有 'word {' 或 'word' (单独 word) 模式
    # 实际上,我们需要识别"语句的第一个 word"
    # 这里用更宽松的方法: 找所有 word,过滤已知的 procs
    # 然后 dedup (因为 proc 可能被多次调用)
    # 先逐行扫描
    for line in body.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        # 分词 (简化)
        words = re.findall(r'[a-zA-Z_][\w:]*', stripped)
        for w in words:
            if w in all_known_procs:
                calls[w] += 1
    return dict(calls)


ENTRY_FILES = {
    'cfd++.tk': 'CFD++主GUI',
    'mcfdsol.tk': 'META Visualizer',
    'mcfdplt.tk': '残差绘图(简单)',
    'mcfdplt2.tk': '残差绘图(run_cmd)',
    'mcfdtplt.tk': '残差绘图(工具栏)',
    'mcfdpplt.tk': '探针绘图',
    'mcfdfplt.tk': '力/力矩绘图',
    'mcfdfft.tk': 'FFT分析',
    'mcfd1dp.tk': 'XY曲线绘图',
    'logview.tk': '日志查看器',
}


def main():
    files = collect_files()
    print(f"Files: {len(files)}")
    file_data = {}
    all_procs = set()
    for fn in files:
        path = os.path.join(GUI_SRC, fn)
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
        sources = find_source_lines(text)
        procs = find_procs_in_text(text)
        for p in procs:
            all_procs.add(p['name'])
        file_data[fn] = {
            'sources': sources,
            'procs': procs,
        }
        print(f"  {fn}: {len(procs)} procs, {len(sources)} sources")

    # 第二遍:解析每个 proc 的 body,找 calls/globals/execs
    print("\n--- Phase 2: parse proc bodies ---")
    for fn, fd in file_data.items():
        for p in fd['procs']:
            p['globals'] = find_globals_in_body(p['body'])
            p['execs'] = find_exec_in_body(p['body'])
            p['calls'] = find_calls_in_body(p['body'], all_procs)
        # 计算本文件的 exec/bgexec 总数
        n_execs = sum(len(p['execs']) for p in fd['procs'])

    out_json = os.path.join(OUTPUT_DIR, 'analysis_v3.json')
    with open(out_json, 'w', encoding='utf-8') as f:
        # 不能直接 dump,因为 body 太大
        out = {}
        for fn, fd in file_data.items():
            out[fn] = {
                'sources': fd['sources'],
                'procs': [
                    {
                        'name': p['name'],
                        'args': p['args'],
                        'body_start_line': p['body_start_line'],
                        'body_end_line': p['body_end_line'],
                        'globals': p['globals'],
                        'execs': p['execs'],
                        'calls': p['calls'],
                        'body_size': len(p['body']),
                    }
                    for p in fd['procs']
                ],
                'is_entry': fn in ENTRY_FILES,
                'entry_title': ENTRY_FILES.get(fn, ''),
            }
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\nSaved: {out_json}")
    print(f"Size: {os.path.getsize(out_json)/1024:.1f} KB")
    print(f"Total unique procs: {len(all_procs)}")


if __name__ == '__main__':
    main()
