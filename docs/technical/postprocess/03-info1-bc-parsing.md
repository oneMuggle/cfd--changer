# 03 — info1 + bc Parsing

> `mcfd.info1` 力/矩历程文件 + `mcfd.bc` 边界编号文件的格式定义与状态机解析。

---

## 1. `mcfd.bc` 解析(`bc.py`)

### 1.1 文件格式(实测 reference/full_case/Case)

```
#BC file created by Pointwise 2024-05-13 21:37:51   ← 跳过(文件头)
seq# type modi info                                  ← 跳过(列头)
#Body                                                ← 当前 name = "Body"
   1    0    0    0                                  ← 绑定 id 1 → "Body"
#HCW
   2    0    0    0
...
```

### 1.2 状态机规则

- 行首 `#BC...` → 跳过(文件头注释)
- 行首 `#<Name>` → `current_name = Name`(strip)
- 行首数字 + 有 `current_name` → `{int(parts[0]): current_name}`,清空 `current_name`
- 列头行(`seq# type modi info`,无 `#` 前缀)→ 自然忽略(首字符不是数字)
- 空白行 → 跳过

### 1.3 公共 API

```python
BcNameMap = Dict[int, str]

def parse_mcfd_bc(path: Union[str, Path]) -> BcNameMap: ...
def op_label(op_ibd: Iterable[int], bc_names: BcNameMap) -> str: ...
```

`op_label([1, 2], {1: "Body", 2: "HCW"})` → `"Body+HCW"`。未知 id 回退到 `str(id)`,顺序保留,不去重。

---

## 2. `mcfd.info1` 解析(`info1.py`)

### 2.1 文件格式

CFD++ 输出的 ASCII 力历程,每时间步包含若干个 selector(边界)的积分结果:

```
At the beginning of this run:                    ← 11 行 header,跳过
reflen: reference length = 1.0e+00
... (10 行)

nt 1 tau 0.0e+00 time 0.0e+00                    ← 新 step 触发器
For selector 1, # of boundary faces = 16079       ← 信息行(跳过)
nbc =    1, total inviscid viscous, nondimensional ← 段头:nondim 跳过
energy flux ... (10 行物理量)
nbc =   1, total inviscid viscous, dimensional    ← dimensional 累加!
energy flux  -4.27e-06  -4.27e-06   0.0e+00       ← skip
mass   flux  -1.90e-12  -1.90e-12   0.0e+00       ← skip
x force      5.67e+06    5.67e+06   0.0e+00       ← total[0]/inv[0]/vis[0]
y force      9.83e+06    9.83e+06   0.0e+00       ← total[1]/inv[1]/vis[1]
z force     -2.01e+07   -2.01e+07   0.0e+00       ← total[2]/inv[2]/vis[2]
x moment     3.28e+08    3.28e+08   0.0e+00       ← total[3]/inv[3]/vis[3]
y moment     1.26e+09    1.26e+09   0.0e+00       ← total[4]/inv[4]/vis[4]
z moment     7.07e+08    7.07e+08   0.0e+00       ← total[5]/inv[5]/vis[5]
areas        ...                                   ← skip
areamoments  ...                                   ← skip
[新 selector / 新 nt 段同上格式]
```

### 2.2 状态机规则

```
读到 nt 行(parts[0]=='nt' 且 len(parts) > 5,parts[1] 是 int,parts[5] 是 float):
    若 current 非空 → flush current 到 steps[]
    current = _StepAccumulator(step=parts[1], time=parts[5])

读到 nbc 行(parts[0]=='nbc' 且 parts[6]=='dimensional'):
    bc_id = int(parts[2].rstrip(','))
    if bc_id in op_ibd_set:
        skip 2 行(energy flux, mass flux)
        读 6 行 force/moment → 累加到 current.total/inv/vis
        skip 2 行(areas, areamoments)

EOF: 若 current 非空 → flush(reference bug 修复)
```

### 2.3 多边界 op 合并

`op_ibd=[1, 2]` 时,每个 step 内 nbc=1 和 nbc=2 的 dimensional 段都被累加到同一个 `Info1Step`,实现"边界合并 op"。

### 2.4 与 reference 的差异(已修 bug)

reference `read_info1_file`:
```python
if parts[0] == 'nt':
    if istep > 0:
        formom['total'] = np.row_stack((formom['total'], formomi['total']))
        # ...
    istep += 1
    formomi = {'total': np.zeros(6), ...}
# 末尾 EOF 后:
return step, time_vals, formom, isviscous   ← formomi 没 flush!
```

结果:**最后一个 step 的累积值丢失**。`force_extract_core` 用 `[n_steps-1]` 实际拿到的是倒数第二个 step 的力,而 `step[]` 列表有 n 个元素,`formom['total']` 只有 n-1 个,长度不一致。

我们的实现在循环结束后显式 `if current is not None: steps.append(current.to_info1_step())`,保证 `len(steps) == len(nt 标记数)`。

### 2.5 公共 API

```python
@dataclass(frozen=True)
class Info1Step:
    step: int
    time: float
    total: tuple[float, float, float, float, float, float]  # Fx..Mz
    inv:   tuple[float, float, float, float, float, float]
    vis:   tuple[float, float, float, float, float, float]

def read_info1(path, op_ibd: Sequence[int]) -> list[Info1Step]: ...
def is_viscous(steps: Sequence[Info1Step]) -> bool: ...
def find_total_force_file(case_dir) -> Optional[Path]:
    """找 minfo1_e1*,排除 _inviscid/_viscous 后缀。"""
```

### 2.6 错误容错

- 文件不存在 → `FileNotFoundError`
- 空文件 → 返回 `[]`
- 损坏 `nt` 行(< 6 列)→ 跳过该 nt,继续读后续
- 损坏 `nbc` 段(force 行不是 3 数浮点)→ 放弃本段,不更新 current

### 2.7 fixture

`tests/fixtures/reference/info1_mini.txt`(151 行,从 reference/full_case/Case/mcfd.info1 截取):
- step 1 完整:5 selector × (nondim + dim)
- step 2 partial:selector 1 完整(用于触发 EOF flush 测试)
