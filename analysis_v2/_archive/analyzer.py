"""
CFD++ GUI 源码调用关系分析器 v2
功能：
1. 解析所有 .tcl/.tk 文件
2. 提取 source 依赖、proc 定义、proc 调用、global 变量、exec 调用
3. 构建调用矩阵
4. 入口归类
5. 输出 JSON 中间数据 + Markdown 报告
"""
import os
import re
import json
from collections import defaultdict, OrderedDict
from pathlib import Path

GUI_SRC = r"D:\software\CFD++\METACOMP\mlib\mcfd.18.5\exec\gui_src"
OUTPUT_DIR = r"E:\ProgrammingData\python\cfd++changer\analysis_v2"

# === 1. 收集所有文件 ===
def collect_files():
    files = []
    for entry in os.listdir(GUI_SRC):
        full = os.path.join(GUI_SRC, entry)
        if not os.path.isfile(full):
            continue
        if entry.endswith('.tcl') or entry.endswith('.tk'):
            files.append(entry)
    return sorted(files)


# === 2. Tcl 词法分析 ===
def tokenize(text):
    """
    将 Tcl 源码 token 化。
    返回 token 列表，每项: (type, value, pos)
    type: 'word' (普通单词/字符串), 'brace_str' (大括号字符串), 'cmd_subst' (命令替换结果暂不处理)
    同时处理 # 注释
    """
    tokens = []
    i = 0
    n = len(text)
    line = 1
    line_starts = [0]  # 每行起始 pos

    def skip_ws_and_comments():
        nonlocal i, line
        while i < n:
            c = text[i]
            if c == ' ' or c == '\t' or c == '\r':
                i += 1
            elif c == '\n':
                i += 1
                line += 1
                line_starts.append(i)
            elif c == ';' and (i + 1 < n and text[i+1] != '\n'):
                # ; 是语句分隔符，不跳过
                break
            elif c == '#':
                # 注释到行末
                while i < n and text[i] != '\n':
                    i += 1
            else:
                break

    skip_ws_and_comments()
    while i < n:
        c = text[i]
        if c == ' ' or c == '\t' or c == '\r' or c == '\n':
            skip_ws_and_comments()
            continue
        if c == ';':
            i += 1
            skip_ws_and_comments()
            continue
        # 读取一个 word
        start_line = line
        start = i
        if c == '{':
            # brace string
            depth = 1
            i += 1
            while i < n and depth > 0:
                if text[i] == '{':
                    depth += 1
                elif text[i] == '}':
                    depth -= 1
                elif text[i] == '\\' and i + 1 < n:
                    i += 2
                    continue
                elif text[i] == '\n':
                    line += 1
                    line_starts.append(i + 1)
                i += 1
            tokens.append(('word', text[start:i], start_line))
        elif c == '"':
            # quoted string
            i += 1
            while i < n and text[i] != '"':
                if text[i] == '\\' and i + 1 < n:
                    i += 2
                    continue
                if text[i] == '\n':
                    line += 1
                    line_starts.append(i + 1)
                i += 1
            if i < n:
                i += 1
            tokens.append(('word', text[start:i], start_line))
        elif c == '[':
            # command substitution [cmd ...]
            depth = 1
            i += 1
            while i < n and depth > 0:
                if text[i] == '[':
                    depth += 1
                elif text[i] == ']':
                    depth -= 1
                elif text[i] == '\\' and i + 1 < n:
                    i += 2
                    continue
                elif text[i] == '\n':
                    line += 1
                    line_starts.append(i + 1)
                i += 1
            tokens.append(('word', text[start:i], start_line))
        else:
            # 普通 word，遇到空白/分号/注释/右大括号停止
            # 重要：反斜杠续行（\newline）应作为整体处理，因为反斜杠后跟换行
            while i < n:
                c2 = text[i]
                if c2 in ' \t\r\n;#':
                    break
                if c2 == '[' or c2 == '"' or c2 == '{':
                    break
                if c2 == '\\' and i + 1 < n and text[i+1] == '\n':
                    i += 2  # 跳过 \\n
                    line += 1
                    line_starts.append(i)
                    continue
                if c2 == '\\' and i + 1 < n:
                    i += 2
                    continue
                i += 1
            tokens.append(('word', text[start:i], start_line))
        skip_ws_and_comments()

    return tokens


def word_to_str(w):
    """把 token 化的 word 转为可分析字符串（去掉外层大括号/引号）"""
    if w.startswith('{') and w.endswith('}'):
        return w[1:-1]
    if w.startswith('"') and w.endswith('"'):
        return w[1:-1]
    if w.startswith('[') and w.endswith(']'):
        return w[1:-1]
    return w


# === 3. 解析文件 ===
def parse_file(path):
    """
    解析一个 .tcl/.tk 文件，提取：
    - source 列表
    - proc 定义 (name, args, body_start, body_end, line)
    - top-level statements 的命令名（用于入口触发识别）
    """
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()

    tokens = tokenize(text)
    # tokens 已经是按 word 分割的，每个 token 是一个 word（包含其原始字符）
    # 重新组织为语句：按文件原始位置分组
    # 简化：基于位置，识别 'proc' 和 'source' 关键字
    sources = []
    procs = []  # (name, args_str, body_start_line, body_end_line)
    top_level_cmds = []  # 顶层（不在任何 proc 体内）调用的命令名（用于入口触发）

    # 第一遍：找出所有 proc 的位置和 body 范围
    # 因为 proc body 在 { ... } 中，需要从 'proc' 关键字开始追踪
    # tokens 是按词法顺序的列表；用位置索引遍历
    pos_to_idx = {}
    for idx, (t, v, ln) in enumerate(tokens):
        pos_to_idx.setdefault(ln, []).append(idx)

    n = len(tokens)

    # 找 proc 定义
    i = 0
    while i < n:
        t, v, ln = tokens[i]
        if v == 'proc':
            # 形式: proc name {args} { body }
            # 跳过 name
            if i + 1 < n:
                _, name_word, name_line = tokens[i+1]
                proc_name = word_to_str(name_word)
                # 找 args (下一个 word) 和 body
                if i + 2 < n:
                    _, args_word, _ = tokens[i+2]
                    args_str = word_to_str(args_word)
                    # 找 body
                    if i + 3 < n:
                        _, body_word, body_line = tokens[i+3]
                        # body_word 应该是 { ... } 形式的 brace string
                        # 计算 body 的结束行（用字符位置反推）
                        body_text = body_word[1:-1] if body_word.startswith('{') and body_word.endswith('}') else body_word
                        # body 的起始行 = body_line
                        # body 的结束行 = body_line + body_text 中换行数
                        body_end_line = body_line + body_text.count('\n')
                        procs.append({
                            'name': proc_name,
                            'args': args_str,
                            'body_start_line': body_line,
                            'body_end_line': body_end_line,
                            'define_line': ln,
                        })
                        i += 4
                        continue
        i += 1

    # 第二遍：找 source 和顶层命令
    # 思路：tokens 中的每个 word 可能是语句的第一个 word (即"命令")。
    # 简化：source 关键字是显式的；proc 定义内部有 'proc' word，但 body 内的 word 可能是调用。
    # 我们用 brace depth 跟踪当前是否在 proc body 内
    depth = 0
    in_proc_body = False
    in_proc_body_lines = set()  # 哪些 token line 是在 proc body 内
    # 用字符位置跟踪更稳：对每个 token，检查其是否在某个 proc 的 body line 范围内
    proc_body_set = set()
    for p in procs:
        for ln in range(p['body_start_line'], p['body_end_line'] + 1):
            proc_body_set.add(ln)

    # 处理 source 和顶层命令
    # 每个 token 的 line 决定它是否在某个 proc body 内
    i = 0
    while i < n:
        t, v, ln = tokens[i]
        is_in_body = ln in proc_body_set

        # source 关键字（无论是否在 body 内）
        if v == 'source':
            # 下一个 token 是文件名
            if i + 1 < n:
                _, fn_word, fn_line = tokens[i+1]
                fn_str = word_to_str(fn_word)
                sources.append({
                    'target': fn_str,
                    'line': ln,
                })
            i += 2
            continue

        if not is_in_body:
            # 顶层语句的第一个 word
            top_level_cmds.append({'cmd': v, 'line': ln})

        i += 1

    return {
        'sources': sources,
        'procs': procs,
        'top_level_cmds': top_level_cmds,
    }


# === 4. 在 proc body 中提取调用 ===
BUILTIN_CMDS = set("""
after append array bgerror binary break catch cd clock close concat continue
dde eof error eval exec exit expr fblocked fconfigure fcopy file
fileevent flush for foreach format gets glob global history if incr info
interp join lappend lindex linsert list llength load lower lrange
lreplace lsearch lsort mathfunc mathop memory msgcat namespace open
package pid pkg::create pkg_mkIndex proc puts pwd re_syntax read regexp
registry regsub rename resource return scan search seek set socket
source split string subst switch tclLog tack tell time trace unknown
unset update uplevel upvar variable vwait while
""".split())


def find_calls_in_body(text, body_start_line, body_end_line):
    """
    在 body (行号范围) 内找所有命令调用。
    简化策略：把 body 文本当作多行 Tcl 源码，用 tokenize 解析，提取所有顶层 token（第一个 word 是命令名）。
    """
    lines = text.split('\n')
    if body_start_line < 1 or body_end_line > len(lines):
        return []
    body = '\n'.join(lines[body_start_line - 1:body_end_line])
    toks = tokenize(body)
    # 找所有 "语句"的第一个 word
    # 简化：把所有 word 列出来；Tcl 中每个 word 都可能是"命令"
    # 真正的"调用"是：word 在它后面是其他参数。但 Tk/Tcl 的语法是所有 word 都是 prefix 调用。
    # 所以：每个 word 都是一次潜在的命令调用，区别在于它是 built-in 还是 user proc。
    calls = []
    for t, v, ln in calls_visited_iter(toks):
        calls.append(v)
    return calls


def calls_visited_iter(toks):
    """在 token 列表中找到"语句起始 word"的迭代器。
    语句分隔符是：换行 或 分号。Tcl 中，语句由 1 个命令 + 0+ 参数组成，第一个 word 是命令。
    简化：所有 word 都是潜在命令，但需要识别语句边界。
    实际上 tokenize 已经处理了 ; 和 \n 作为分隔，所以这里我们直接取每个 word。
    """
    for tok in toks:
        yield tok


def extract_procs_calls(proc_info, file_text):
    """对每个 proc，在其 body 内提取命令调用（统计调用次数）"""
    result = {}
    for p in proc_info:
        body_start = p['body_start_line']
        body_end = p['body_end_line']
        lines = file_text.split('\n')
        if body_start < 1 or body_end > len(lines):
            result[p['name']] = {}
            continue
        body = '\n'.join(lines[body_start - 1:body_end])
        toks = tokenize(body)
        calls = defaultdict(int)
        for t, v, ln in toks:
            calls[v] += 1
        result[p['name']] = dict(calls)
    return result


# === 5. 提取 global 变量 ===
def extract_globals(proc_info, file_text):
    """对每个 proc，提取其 body 内的 'global VAR' 声明"""
    result = {}
    for p in proc_info:
        body_start = p['body_start_line']
        body_end = p['body_end_line']
        lines = file_text.split('\n')
        if body_start < 1 or body_end > len(lines):
            result[p['name']] = []
            continue
        body = '\n'.join(lines[body_start - 1:body_end])
        toks = tokenize(body)
        # 找 'global' 关键字后的所有 word
        globals_list = []
        for i_t, (t, v, ln) in enumerate(toks):
            if v == 'global':
                # 收集后面连续的 word，直到遇到 ';' 或换行或非 word
                # 简化：到 'global' 后面同语句的所有 word
                # 我们的 tokenize 把 ; \n 视为分隔，所以后面直到下一个 ; \n 都是同语句
                j = i_t + 1
                while j < len(toks):
                    _, v2, ln2 = toks[j]
                    # 检查是否还在同语句：ln2 应是连续的，差别 <= 1
                    if j > i_t + 1:
                        _, prev_v, prev_ln = toks[j-1]
                        if ln2 - prev_ln > 1:
                            break
                    if v2 in (';', '\n') or v2 == '':
                        break
                    globals_list.append(v2)
                    j += 1
        result[p['name']] = globals_list
    return result


# === 6. 提取 exec 调用 ===
def extract_execs(proc_info, file_text):
    """对每个 proc，提取其 body 内的 'exec' 或 'blt::bgexec' 命令及其参数。
    返回: [{'type': 'exec'|'bgexec', 'arg': str, 'line': int}]
    """
    result = defaultdict(list)
    # 同时也包括顶层
    all_procs = [{'name': '__TOP__', 'body_start_line': 1, 'body_end_line': len(file_text.split('\n'))}]
    all_procs.extend(proc_info)
    for p in all_procs:
        body_start = p['body_start_line']
        body_end = p['body_end_line']
        lines = file_text.split('\n')
        if body_start < 1 or body_end > len(lines):
            continue
        body = '\n'.join(lines[body_start - 1:body_end])
        toks = tokenize(body)
        for i_t, (t, v, ln) in enumerate(toks):
            if v == 'exec' or v == 'blt::bgexec':
                # 收集后面直到行尾或 ; 的 word 作为参数（取第一个有意义的）
                args = []
                j = i_t + 1
                while j < len(toks) and len(args) < 6:
                    _, v2, ln2 = toks[j]
                    if j > i_t + 1:
                        _, prev_v, prev_ln = toks[j-1]
                        if ln2 - prev_ln > 1:
                            break
                    args.append(v2)
                    j += 1
                result[p['name']].append({
                    'type': 'exec' if v == 'exec' else 'bgexec',
                    'args': args,
                    'line': ln,
                })
    return dict(result)


# === 主程序 ===
def main():
    files = collect_files()
    print(f"Files: {len(files)}")
    all_data = {}
    for fn in files:
        path = os.path.join(GUI_SRC, fn)
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
        parsed = parse_file(path)
        proc_calls = extract_procs_calls(parsed['procs'], text)
        proc_globals = extract_globals(parsed['procs'], text)
        proc_execs = extract_execs(parsed['procs'], text)
        all_data[fn] = {
            'sources': parsed['sources'],
            'procs': parsed['procs'],
            'top_level_cmds': parsed['top_level_cmds'],
            'proc_calls': proc_calls,
            'proc_globals': proc_globals,
            'proc_execs': proc_execs,
        }
        print(f"  {fn}: {len(parsed['procs'])} procs, {len(parsed['sources'])} sources")

    out_json = os.path.join(OUTPUT_DIR, 'analysis.json')
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=1)
    print(f"\nSaved: {out_json}")
    print(f"Size: {os.path.getsize(out_json)/1024:.1f} KB")


if __name__ == '__main__':
    main()
