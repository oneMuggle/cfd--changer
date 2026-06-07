# 13 — 核心模块设计

> 本章拆解 `inp_tool` 的四大核心模块:数据模型 (`model`)、解析器 (`parser`)、序列化器 (`writer`)、差异比较 (`diff`)。
> 读者:想改 inp_tool 内部行为、写新 CLI/API、定位解析 bug 的开发者。
> 版本:与 `inp_tool` v0.4.2 同步(`pyproject.toml` 标记 `version = "0.4.0"`)。

---

## §1 model — 数据模型

`inp_tool/inp_tool/model.py`(233 行)定义四个 `@dataclass`:`Value` / `Stmt` / `Block` / `InpFile`,以及类型推断函数 `infer_type`。所有外部 API 都基于这四个类。

### 1.1 字段总览

| 类 | 字段 | 类型 | 用途 |
|---|---|---|---|
| `Value` | `raw` | `str` | 原始 token 字符串(未规范化) |
| `Value` | `typed` | `int / float / str` | `infer_type` 推断后的 Python 值 |
| `Stmt` | `keyword` | `str` | 语句关键字(如 `timestep`、`viscous`) |
| `Stmt` | `values` | `list[Value]` | 主行的 value 列表(单行多值) |
| `Stmt` | `children` | `list[Stmt]` | 后续多行 values(典型是 `info set` 的 `values` 续行) |
| `Stmt` | `line` | `int` | 源文件行号(1-based) |
| `Stmt` | `raw` | `str` | 源文件原始行 |
| `Stmt` | `comment_after` | `str` | 行尾注释(含前导空格) |
| `Stmt` | `raw_with_ws` | `str` | v0.4+ 整行(含前导/尾部空白) |
| `Stmt` | `leading_ws` | `str` | 行首空白(`write_preserve` 用) |
| `Stmt` | `trailing_ws` | `str` | 行尾空白(罕见) |
| `Block` | `name` | `str` | 块名(与 `begin/end` 一致,如 `chemkin`、`timesteps`) |
| `Block` | `begin_line` | `int` | `NAME begin` 行号 |
| `Block` | `end_line` | `int` | `NAME end` 行号(0 表示未闭合) |
| `Block` | `statements` | `list[Stmt]` | 块内语句(按出现顺序) |
| `Block` | `pre_comments` | `list[str]` | `begin` 行前的装饰注释 |
| `Block` | `trailing_comments` | `list[str]` | `end` 行前的注释 |
| `InpFile` | `path` | `str` | 源文件路径(可空) |
| `InpFile` | `header_comments` | `list[str]` | 文件头注释(在第一个块或语句之前) |
| `InpFile` | `block_list` | `list[Block]` | **所有块**,按出现顺序,同名多次出现都保留 |
| `InpFile` | `top_stmts` | `list[Stmt]` | 顶层非块语句 |
| `InpFile` | `top_decor` | `list[(line, str)]` | 顶层语句之间的装饰注释(行号 + 内容) |
| `InpFile` | `tail_lines` | `list[str]` | 文件末尾的 wrapper 行(无法解析的尾部) |

### 1.2 `infer_type` 推断规则

```python
def infer_type(raw: str) -> int | float | str
```

| 输入 | 推断结果 | 说明 |
|---|---|---|
| `""`(空串) | `""` | 短路返回,不走数字分支 |
| `"42"` | `int(42)` | 无小数点无指数 → int |
| `"3.14"` | `float(3.14)` | 含 `.` → float |
| `"1e-5"` | `float(1e-5)` | 含 `e` / `E` → float(指数先归一化) |
| `"1.5d-3"` | `float(1.5e-3)` | Fortran 风格的 `d` / `D` 等同 `e` / `E` |
| `"abc"` | `"abc"` | ValueError 兜底为原字符串 |
| `"-0"` | `int(0)` | 负号不影响 |

**实现要点**:
- 先 `s.replace('d', 'e').replace('D', 'E')` 归一化 Fortran 双精度
- `if '.' in s_norm or 'e' in s_norm or 'E' in s_norm` 走 float,否则走 int
- 这意味着 `"1."` → `1.0`(float),但 `"1"` → `1`(int),**精度敏感**的场景需显式比较 `raw`

### 1.3 关键方法语义

#### `Stmt` 的索引访问

| 方法 | 签名 | 行为 |
|---|---|---|
| `Stmt.get(i, default=None)` | `int, Any -> Any` | 返回 `values[i].typed`,越界返回 default |
| `Stmt.set(i, value)` | `int, Any -> None` | 改 `values[i].raw = str(value)`,并重跑 `infer_type` |
| `Stmt.values_raw` | `-> list[str]` | 全部 raw 字符串 |
| `Stmt.values_typed` | `-> list[Any]` | 全部 typed 值 |
| `Stmt.child_values()` | `-> list[list[Value]]` | 仅 `keyword == 'values'` 的 children 的 values |
| `Stmt.all_values()` | `-> list[Value]` | 主行 + 全部 children 的 values(扁平) |

> **陷阱**:`Stmt.set` 只改第一个 value。如果原 Stmt 有多个 values,改 `set(1, x)` 不会动 `set(0, x)`,这是预期行为。

#### `Block` 的关键字访问

| 方法 | 签名 | 行为 |
|---|---|---|
| `Block.get(kw, default=None)` | `str, Any -> Any` | 找第一条 `keyword == kw` 且 `values` 非空,返回 `values[0].typed` |
| `Block.get_value(kw)` | `str -> Value?` | 返回 `values[0]` 完整对象(含 raw) |
| `Block.get_stmt(kw)` | `str -> Stmt?` | 返回整条 Stmt(可读 children) |
| `Block.get_all(kw)` | `str -> list[Stmt]` | 同关键字的全部 Stmt |
| `Block.set(kw, value)` | `str, Any -> bool` | 改第一条匹配,返回是否成功 |
| `Block.set_all(kw, value)` | `str, Any -> int` | 改全部匹配,返回改动条数 |
| `Block.append(kw, *values)` | `str, *Any -> Stmt` | 追加新 Stmt(无 children) |
| `Block.remove(kw)` | `str -> int` | 删全部匹配,返回删除条数 |

#### `InpFile` 的兼容性 API

| 方法 | 签名 | 行为 |
|---|---|---|
| `InpFile.blocks` (property) | `-> dict[str, list[Block]]` | **核心兼容属性**:`{name: [Block, ...]}` |
| `InpFile.get_block(name, idx=0)` | `str, int -> Block?` | 取同名第 `idx` 个 |
| `InpFile.all_blocks(name)` | `str -> list[Block]` | 同名全部 |
| `InpFile.get(block, keyword, default=None)` | `str, str, Any -> Any` | 便捷链式: `get_block(block).get(keyword, default)` |
| `InpFile.set(block, keyword, value, idx=0)` | `str, str, Any, int -> bool` | 链式 set |

**为什么是 `list[Block]` 而不是 `dict[str, Block]`?**
mcfd.inp 允许同名块出现多次(如多个 `timesteps` 段对应不同求解器设置)。`block_list` 是顺序保留的列表,`blocks` property 在访问时按需聚合,保留所有同名实例。

### 1.4 何时使用 model

| 场景 | 推荐 |
|---|---|
| 读出某个值(如 `timestep`) | `inp.get('time', 'timestep', default=0)` |
| 改值并回写 | `inp.set('time', 'timestep', 0.001); writer.write(inp, 'out.inp')` |
| 遍历全部同名块 | `inp.all_blocks('timesteps')` |
| 检查某块是否存在 | `if 'chemkin' in inp.blocks: ...` |
| 加新语句 | `blk.append('my_keyword', 1, 2, 3)` |
| 删除某种语句 | `blk.remove('comment')` |

---

## §2 parser — 解析器

`inp_tool/inp_tool/parser.py`(215 行)。两个公开入口:

| 函数 | 签名 | 说明 |
|---|---|---|
| `parse(text, path='')` | `str, str -> InpFile` | 从字符串解析 |
| `parse_file(path)` | `str -> InpFile` | 从文件读 UTF-8(`errors='replace'` 容错) |

### 2.1 状态机

```
       ┌──────────┐
       │  header  │  头部注释累积
       └────┬─────┘
            │ 第一个 begin/语句
            ▼
       ┌──────────┐
       │   top    │  顶层非块语句
       └────┬─────┘
            │ NAME begin
            ▼
       ┌──────────────┐
       │ block:NAME   │  块内语句
       └────┬─────────┘
            │ NAME end
            ▼
       ┌──────────┐
       │   top    │  回顶层
       └──────────┘
```

**状态变量**(`parse()` 内部):

| 变量 | 含义 |
|---|---|
| `state` | `'header' / 'top' / 'block:NAME'` |
| `current_block` | 当前正在累积的 `Block`(`None` 在 header / top) |
| `pending_comments` | header 阶段累积的注释(空行记 `''`) |
| `last_composite` | 当前正在累积的复合语句(`None` 表示无) |

### 2.2 行类型分类

每行按以下顺序判定:

| 行类型 | 判定 | 落入 |
|---|---|---|
| 块标记 | `s == "NAME begin"` 或 `NAME end` | 切 state |
| 空行 | `s == ""` | header:pending;top:decor;block:trailing |
| 整行注释 | `s.startswith('#')` | header:pending;top:decor;block:trailing |
| 含行尾注释 | 任意非空 + `comment != ""` | 正常语句 + 保留 `comment_after` |
| 普通语句 | `parts[0]` 是 keyword,后续是 values | 加入 current state |

**行尾注释提取**(`_split_comment`):
- 找第一个 `<空白> + #` 的位置(i, i+1)
- 切出 `(no_comment, comment_with_leading_space)`
- 注释永远以一个空格开头(若有)

### 2.3 复合语句识别(`info set` 模式)

`info set` 块里常见的格式:

```
infoset
  info set
    seq.1
      values  1.0 2.0 3.0
      values  4.0 5.0 6.0
    seq.2
      values  7.0 8.0 9.0
```

**识别规则**(`_is_seq_header` / `_is_values_line`):

| 关键字 | 判定 | 处理 |
|---|---|---|
| `seq.*` / `seq#` / `seq` | `kw.startswith('seq')` | 新的复合头,作为父 Stmt |
| `values` | `kw == 'values'` | 若是 `last_composite` 的子行,加入 `children`;否则普通 Stmt |

**累积逻辑**:
- 遇到 `seq.#` → `flush_composite()`(清空旧的)+ `last_composite = stmt`
- 遇到 `values` 且 `last_composite is not None` → `last_composite.children.append(stmt)`
- 遇到其他 → `flush_composite()` 后按普通语句处理
- 遇到空行 → `flush_composite()`

> **注意**:`flush_composite()` 不写任何东西,只是清 `last_composite = None`。children 已经 append 进父 Stmt 了。

### 2.4 `preserve_format` 字段

v0.4+ 引入三个字段,使 `write_preserve` 能还原原文件缩进:

| 字段 | 来源 | 用途 |
|---|---|---|
| `raw_with_ws` | parser 填入(原行整行) | 标记"此 Stmt 有缩进可保留" |
| `leading_ws` | parser 填入(行首空白) | `write_preserve` 还原缩进 |
| `trailing_ws` | parser 填入(values 与 `#` 之间的空白) | 保留罕见的对齐空格 |

旧版数据(没有这些字段) → `write_preserve` 自动降级到 `_format_stmt` 行为。

### 2.5 容错处理

| 异常 | 行为 |
|---|---|
| 文件不闭合(`begin` 后无 `end`) | `end_line = len(lines)`,仍 append 进 `block_list` |
| 行解析失败 | 整行跳过(理论上不会发生) |
| 编码错误 | `parse_file` 用 `errors='replace'`,U+FFFD 替换 |
| 重复同名块 | 全部保留在 `block_list`,`blocks` 字典聚合为 list |

### 2.6 何时使用 parser

| 场景 | 推荐 |
|---|---|
| 从文件加载 | `inp = parse_file('mcfd.inp')` |
| 从字符串加载(测试) | `inp = parse(text, path='<test>')` |
| 检查结构 | `inp.blocks.keys()` / `inp.get_block('timesteps')` |

---

## §3 writer — 序列化器

`inp_tool/inp_tool/writer.py`(187 行)。四个公开函数:

| 函数 | 签名 | 说明 |
|---|---|---|
| `to_text(inp)` | `InpFile -> str` | InpFile → 文本(总是重构造,保证确定性) |
| `write(inp, path)` | `InpFile, str -> None` | 写到文件(UTF-8, LF, **不带 BOM**) |
| `write_bytes(inp, path)` | `InpFile, str -> None` | 写到文件(原始 `bytes`,不做 newline 翻译) |
| `write_preserve(inp, path)` | `InpFile, str -> None` | **v0.4+** 保留缩进/对齐/注释的写回 |

### 3.1 输出策略

`to_text` 按以下顺序拼接:

```
1. header_comments(规范化:无 '#' 前缀的加 '# ',空行保持空)
2. block_list + top_stmts  按 line 升序排序(同 line,block 优先)
3. segments 之间的 top_decor 装饰注释按原行号插入
4. tail_lines  原样追加
```

每条 Stmt 格式化为:

```
{leading_ws}{keyword} {val1} {val2} ... {valN}{trailing_ws}{comment_after}
```

注释规范化(`_format_comments`):

| 输入 | 输出 |
|---|---|
| `""` | `""`(空行保留) |
| `"# foo"` | `"# foo"`(已有 `#` 开头) |
| `"foo"` | `"# foo"`(无 `#` 前缀的补上) |

### 3.2 块输出

`_block_to_text(block)` 的格式:

```
{pre_comments 行}
{name} begin
{每条 Stmt(主行 + children 逐行)}
{trailing_comments 行}
{name} end
```

复合 Stmt 的 children **逐行**输出在主行之后(不是 inline),保持原文件的多行视觉。

### 3.3 `write_preserve`:保留缩进(2025-06 引入)

**触发条件**:`stmt.raw_with_ws != ''`(由 v0.4+ parser 填入)。

**行为**:
1. 保留 `leading_ws`(行首缩进)
2. 用 `values_raw` 重拼 body(`set()` 改值后新值会反映)
3. 保留 `trailing_ws` + `comment_after`

**降级**:`raw_with_ws == ''`(旧版数据/手工构造的 Stmt)→ 自动 fallback 到 `_format_stmt` 行为,不抛错。

**典型用例**:
- 用户编辑某个值(如 `timestep`),期望文件其他部分的缩进/注释**完全不变**
- 走 `parse_file` → `set` → `write_preserve` 三步即可

### 3.4 `write` vs `write_bytes` vs `write_preserve`

| 函数 | newline | 编码 | 缩进 | 何时用 |
|---|---|---|---|---|
| `write` | LF(`newline=''`) | UTF-8(无 BOM) | 重构造 | 默认推荐 |
| `write_bytes` | `\n` (字面) | UTF-8 bytes | 重构造 | 跨平台/遗留工具需要原始字节 |
| `write_preserve` | LF | UTF-8(无 BOM) | 保留 | 注释/对齐要原样保留 |

### 3.5 何时使用 writer

| 场景 | 推荐 |
|---|---|
| 默认写回(规范化输出) | `writer.write(inp, 'out.inp')` |
| 保留原文件格式 | `writer.write_preserve(inp, 'out.inp')` |
| 返回字符串(API 用) | `text = to_text(inp); return Response(text)` |

---

## §4 diff — 差异比较

`inp_tool/inp_tool/diff.py`(152 行)。比较两个 `InpFile`,产出 `DiffReport`。

### 4.1 数据结构

| 类 | 字段 | 用途 |
|---|---|---|
| `DiffEntry` | `kind` | `'add' / 'remove' / 'modify' / 'same'` |
| `DiffEntry` | `location` | 路径(如 `block:timesteps[0]`,`top`) |
| `DiffEntry` | `keyword` | 关键字(块级差异时为 `'<block>'`) |
| `DiffEntry` | `old` | 旧值(`None` 表示 add) |
| `DiffEntry` | `new` | 新值(`None` 表示 remove) |
| `DiffEntry` | `line_old` / `line_new` | 两侧行号(0 表示不存在) |
| `DiffReport` | `entries` | 全部 DiffEntry(包含 `same`) |
| `DiffReport` | `changes` (property) | 仅 `kind != 'same'` 的条目 |
| `DiffReport` | `__len__` / `__bool__` | 走 `changes`,空报告视为 False |

### 4.2 4 种 kind 的语义

| kind | 触发 | `old` | `new` |
|---|---|---|---|
| `add` | b 比 a 多一条语句/块 | `None` | 新值 |
| `remove` | a 比 b 多一条语句/块 | 旧值 | `None` |
| `modify` | 同一位置的 keyword 相同,值不同 | `(values, children)` | `(values, children)` |
| `same` | keyword+values+children 全等 | 值 | 值 |

> 注意:任务描述说"4 种类型 (added/removed/changed/moved)",**实际实现没有 `moved` 类型**。同一位置的内容不变 → `same`;内容变 → `modify`;行号变了但内容不变(被新行挤出)→ 仍判为 `same`。
> 这是已知的设计简化(见 [`09-sweep-risks-roadmap`](09-sweep-risks-roadmap.md) 风险登记)。

### 4.3 配对策略

**块配对**(`diff()` 顶层循环):
- 按 `block_list` 的索引对齐
- `ab.name == bb.name` → 递归比 statements
- 名称不同 → 分别记为 `remove`(a)+ `add`(b),**不递归比内容**(简化策略)
- 多余的尾部块 → `add` / `remove`

**语句配对**(`_diff_stmts`):
- 按索引对齐(0..min(len(a), len(b))-1)
- `_stmt_key = (keyword, tuple(values_raw))` 不等 或 children 数不同 → 视为 `modify`
- 同一位置 keyword 不同 → 拆为 `remove` + `add`(因为 `_stmt_key` 已经不等)
- 多余的尾部 → `add` / `remove`

### 4.4 `unified()` 风格输出

```python
report.unified('mcfd_v0.inp', 'mcfd_v1.inp')
```

输出形如:

```
--- mcfd_v0.inp
+++ mcfd_v1.inp
@@ -mcfd_v0.inp:42 @@
- block:timesteps[0] timestep = 0.001
+ block:timesteps[0] timestep = 0.0005
```

每个 `modify` 出一对 `-` / `+` 行;`add` / `remove` 各出一个 hunk。

### 4.5 何时使用 diff

| 场景 | 推荐 |
|---|---|
| 检查 sweep 输出是否变了 | `r = diff(base_inp, new_inp); if r: print(r)` |
| 生成 patch 文本 | `r.unified('base.inp', 'new.inp')` |
| 计数变更数 | `len(r)` |
| 仅关心 keyword 集合 | `set(e.keyword for e in r.changes if e.keyword != '<block>')` |

---

## §5 错误处理约定

`inp_tool` 核心模块的错误处理遵循三类明确约定。

### 5.1 解析错误 — 不抛,容错

`parser` 遇到**结构性问题**时,不抛异常,做**最大努力解析**:

| 情形 | 行为 |
|---|---|
| 块未闭合(无 `NAME end`) | 仍 append 进 `block_list`,`end_line` 设为文件总行数 |
| 编码错误 | `parse_file` 用 `errors='replace'`,U+FFFD 替换 |
| 重复同名块 | 全部保留(不抛,不合并) |
| 复合语句头/值错位 | `last_composite = None` 时遇到 `values`,按普通 Stmt 处理 |
| 空行出现在 `info set` 中 | `flush_composite()` 切断累积,空行记为 decor |

**为什么?** 真实世界的 .inp 文件经常有不规范之处(手写、版本差异、外部工具导出)。sweep 用例下,"尽量解析" 比 "一个错就 fail" 更有用。

### 5.2 类型错误 — 显式抛

`model` 和 `writer` 的**类型/值错误**显式抛异常:

| 情形 | 异常 |
|---|---|
| `infer_type` 不抛(`ValueError` 兜底为 str) | — |
| `Stmt.get(i)` 越界 → 返回 default(不抛) | — |
| `Block.get(kw)` 不存在 → 返回 default(不抛) | — |
| `InpFile.get_block(name, idx)` idx 越界 → `None` | — |
| `InpFile.set` 块不存在 → `False` | — |
| `Value.raw` 强制为 `str`(`__post_init__` 不验证内容) | — |
| 任何字段类型不匹配(`int` 写成 `str`)| `TypeError` (dataclass 隐式) |

> **约定**:模型层的 `get` 系列**永远不抛**,调用方用 `default` 或 `is None` 判断。
> 写操作(`set` / `append`)返回 `bool` 或新对象,失败不抛。

### 5.3 I/O 错误 — 包装后抛

`parser.parse_file` / `writer.write` / `writer.write_preserve` / `writer.write_bytes` 的 I/O 错误**不包装**,直接抛底层 `OSError` / `PermissionError` / `FileNotFoundError` 等。

调用方按需捕获:

```python
try:
    inp = parse_file('mcfd.inp')
except FileNotFoundError:
    ...
except OSError as e:
    logger.error("parse_file failed: %s", e)
```

**CLI / API 层**会进一步包装(见 [`inp_tool/cli.py`](../../inp_tool/inp_tool/cli.py) 与 [`05-sweep-usage`](05-sweep-usage.md) §3)。

### 5.4 错误处理速查表

| 来源 | 行为 | 调用方检查 |
|---|---|---|
| `parser` 解析失败 | 容错,继续 | 检查 `inp.block_list` 长度是否符合预期 |
| `model` 读访问(get) | 返回 default | `if value is None: ...` |
| `model` 写访问(set) | 返回 bool | `if not inp.set(...): raise ...` |
| I/O | 直接抛 | `try / except OSError` |

---

## §6 测试入口

`inp_tool/tests/` 包含 **14 个测试文件 + 1 个 conftest**(共约 1100 行)。所有测试用 `conda run -n cfdchanger pytest` 跑。

### 6.1 测试文件一览

| 文件 | 大小 | 覆盖模块 | 重点 |
|---|---|---|---|
| `test_parser.py` | ~5 KB | `parser` | 状态机、复合语句、preserve_format、容错 |
| `test_writer.py` | ~7 KB | `writer` | `to_text` / `write` / `write_preserve` / `write_bytes` |
| `test_diff.py` | ~3 KB | `diff` | add/remove/modify、块配对、unified 输出 |
| `test_api.py` | ~6 KB | `__init__` 公开 API | `load_inp` / `save_inp` / `diff_inp` 集成 |
| `test_cli.py` | ~3 KB | `cli` | `inp-tool info / set / diff` 子命令 |
| `test_completion.py` | ~1 KB | shell 补全 | bash/zsh completion 脚本生成 |
| `test_packaging.py` | ~4 KB | 打包 | `pyproject.toml` / `inp_tool` 命令入口 |
| `test_sweep.py` | ~10 KB | `sweep` 主流程 | `generate()` 整体行为 |
| `test_sweep_api.py` | ~3 KB | sweep API | `SweepConfig` / YAML 加载 |
| `test_sweep_cli.py` | ~4 KB | sweep CLI | sweep 子命令 |
| `test_sweep_generate.py` | ~10 KB | sweep generate | 单参数扫描、组合扫描 |
| `test_sweep_interactive.py` | ~4 KB | 交互式 CLI | prompt-based 配置 |
| `test_sweep_yaml.py` | ~4 KB | sweep YAML | YAML 解析/校验 |
| `conftest.py` | ~1.5 KB | fixtures | 路径注入、examples / external_inp_dir |

> **关于 "11 个文件"**:任务描述里说 "11 个文件",实际统计为 13 个 `test_*.py` + 1 个 `conftest.py` = 14 个文件;`test_*.py` 中 4 个专门覆盖核心模块(`test_parser` / `test_writer` / `test_diff` / `test_api`),其他 9 个是 sweep 相关的。详见 [`08-sweep-testing`](08-sweep-testing.md)。

### 6.2 公共 fixture(`conftest.py`)

| Fixture | scope | 说明 |
|---|---|---|
| `examples_dir` | session | `inp_tool/examples/` 目录路径 |
| `sample_inp` | session | examples/ 下的示例 .inp(优先 `mcfd_v2_modified.inp`) |
| `external_inp_dir` | session | Windows 路径 `E:\softwareData\edge\download\inp`(不存在自动 skip) |

`conftest.py` 还做一件关键事:

```python
_PKG_ROOT = Path(__file__).resolve().parent.parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))
```

把 `inp_tool/` 加到 `sys.path`,让测试可以直接 `import inp_tool`(无需 `pip install -e`)。

### 6.3 跑测试

```bash
# 全部
conda run -n cfdchanger pytest inp_tool/tests/ -v

# 单文件
conda run -n cfdchanger pytest inp_tool/tests/test_parser.py -v

# 核心模块(本章节覆盖的范围)
conda run -n cfdchanger pytest inp_tool/tests/test_parser.py \
                       inp_tool/tests/test_writer.py \
                       inp_tool/tests/test_diff.py \
                       inp_tool/tests/test_api.py -v
```

### 6.4 何时补充测试

| 改动 | 加测试位置 |
|---|---|
| 改 `model.py` 字段/方法 | `test_api.py`(高层集成) + 对应单测 |
| 改 `parser.py` 状态机 | `test_parser.py` 加新 case |
| 改 `writer.py` 输出格式 | `test_writer.py`(用 `parse → write → parse` 往返对比) |
| 改 `diff.py` 配对逻辑 | `test_diff.py` 加 expected entries |
| 新增 CLI 子命令 | `test_cli.py` 或 `test_sweep_cli.py` |

---

## §7 进一步阅读

- 整体架构(包结构图、数据流):[`12-architecture-overview`](12-architecture-overview.md)
- sweep 模块怎么用这些核心模块:[`04-sweep-architecture`](04-sweep-architecture.md) §3
- CLI / API 速查(用户视角):[`../user-manual/13-cli-api-reference`](../user-manual/13-cli-api-reference.md)
- mcfd.inp 字段参考(数据视角):[`../user-manual/12-mcfd-inp-field-reference`](../user-manual/12-mcfd-inp-field-reference.md)
