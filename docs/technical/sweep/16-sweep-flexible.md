# 计划:sweep 灵活化(cases / groups / CSV / 混合)

> **状态:** 进行中(2026-06-09)
> **对应版本:** v0.7.0
> **优先级:** 高(本项目用户最常要求的能力)
> **PR:** 分两阶段,本计划对应 PR #1(sweep 灵活化),PR #2 才是 i18n + wizard

---

## 1. 背景

当前 sweep 只支持**笛卡尔积展开**(`sweeps: {alpha:[...], beta:[...]}` → N 个 case)。但真实场景常有"每组参数不同"的需求,例如:

- 流场 1 的 T/p 对应 10°/20° 攻角,各攻角下又有不同侧滑角
- 不规则参数点(不是轴正交网格)
- 用 Excel 维护 case 表

本计划**新增**三种模式,**完全向后兼容**(老 YAML 零变化)。

---

## 2. 目标

| # | 目标 | 验收 |
|---|------|------|
| G1 | 支持 `cases:` 显式列表模式 | YAML 写 4 个 case dict,生成 4 个 .inp |
| G2 | 支持 `groups:` 分组继承模式 | `common` 字段注入到组内每个 case |
| G3 | 支持 CSV 文件输入 | `inp-tool sweep cases.csv` 直接跑 |
| G4 | 混合模式(sweeps + cases) | 笛卡尔 + 显式合并生成 |
| G5 | `{group}` 命名占位符 | 用 group.name 替换 |
| G6 | 向后兼容 | 现有 55+ 测试全绿,老 YAML 行为零变化 |
| G7 | 覆盖率 ≥ 80% | `pytest --cov --cov-fail-under=80` |
| G8 | 不引入新运行时依赖 | 仅 stdlib(`csv` + `dataclasses` + `typing`) |

---

## 3. 涉及文件

| 文件 | 动作 | 估行数 |
|------|------|--------|
| `inp_tool/inp_tool/sweep.py` | 加 `CartesianSpec` / `ExplicitCase`,`CaseSweep.specs` 字段,`_build_specs_from_dict`,`materialize`,`from_csv` | +180 / -30 |
| `inp_tool/inp_tool/cli.py` | 文件后缀自动路由(.csv 走 `from_csv`) | +30 |
| `inp_tool/tests/test_sweep_explicit.py` (新) | cases 模式 | +100 |
| `inp_tool/tests/test_sweep_groups.py` (新) | groups 模式 + common + {group} | +120 |
| `inp_tool/tests/test_sweep_csv.py` (新) | CSV loader | +80 |
| `inp_tool/tests/test_sweep_mixed.py` (新) | sweeps + cases 混合 | +60 |
| `inp_tool/tests/test_sweep_backward.py` (新) | 显式断言老 YAML 行为锁死 | +40 |
| `docs/technical/sweep/04-sweep-architecture.md` | 加 §1.5 CaseSpec 抽象 | +40 |
| `docs/technical/sweep/05-sweep-usage.md` | 加 §6 三种新模式 + 4 个完整示例 | +80 |
| `CHANGELOG.md` | 加 v0.7.0 段 | +10 |
| **本计划文档** | 归档 | +200 |

净代码 +560(扣测试/文档/计划)。

---

## 4. 实施阶段

### 阶段 0 — 开工前

- [x] 0.1 写本计划
- [x] 0.2 分支:`git switch -c feat/sweep-flexible-modes`
- [ ] 0.3 基线:跑现有 55+ 测试全绿

### 阶段 1 — 数据模型重构(零行为变化)

- [ ] 1.1 RED:`test_sweep_backward.py` — 现有老 YAML 行为锁死
- [ ] 1.2 GREEN:加 `CartesianSpec` / `ExplicitCase` dataclass
- [ ] 1.3 GREEN:`CaseSweep.specs: List[Union[CartesianSpec, ExplicitCase]] = []` 字段
- [ ] 1.4 GREEN:`from_dict` 把 `sweeps` 字段同步映射到 `specs`
- [ ] 1.5 GREEN:`materialize()` 摊平 specs → List[ExplicitCase]
- [ ] 1.6 GREEN:`generate()` 优先用 `specs`;空时回退到 `expand_cartesian(sweeps)`
- [ ] 1.7 所有现有 55+ 测试通过(零行为变化)

### 阶段 2 — 显式列表模式(`cases:`)

- [ ] 2.1 RED:`test_sweep_explicit.py` — `cases: [{...}]` 走显式
- [ ] 2.2 GREEN:`_build_specs_from_dict` 检测 `cases` → `ExplicitCase`
- [ ] 2.3 RED:缺 sweeps/cases/groups 任一 → 清晰错误
- [ ] 2.4 GREEN:错误信息含"必须二选一/三选一"

### 阶段 3 — 分组继承模式(`groups:`)

- [ ] 3.1 RED:`test_sweep_groups.py` — 4-case 分组例子
- [ ] 3.2 GREEN:解析 `groups: [{name, common, cases}]`
- [ ] 3.3 RED:`common` 注入 + cases 字段覆盖
- [ ] 3.4 GREEN:合并规则(common 默认,case 显式覆盖)
- [ ] 3.5 RED:`{group}` 在 naming 中展开
- [ ] 3.6 GREEN:`render_case_name` 支持 `{group}` 替换
- [ ] 3.7 RED:无名 group 兜底

### 阶段 4 — 混合模式(`sweeps` + `cases`)

- [ ] 4.1 RED:`test_sweep_mixed.py` — 笛卡尔 + 显式合并
- [ ] 4.2 GREEN:两个字段都接受,顺序展开
- [ ] 4.3 RED:同 key 出现在两处 → 报错
- [ ] 4.4 GREEN:重复 case 警告(不阻断)

### 阶段 5 — CSV loader

- [ ] 5.1 RED:`test_sweep_csv.py` — 4 行 CSV 解析
- [ ] 5.2 GREEN:`from_csv(path, template, output_dir, naming=None, manifest_path=None)`
- [ ] 5.3 RED:数值类型推断(空值 / 非数字)
- [ ] 5.4 GREEN:错误信息含行号 + 列名
- [ ] 5.5 编码处理:UTF-8 优先,GBK fallback

### 阶段 6 — CLI 集成

- [ ] 6.1 RED:`inp-tool sweep cases.csv --template template.inp`
- [ ] 6.2 GREEN:`cli.cmd_sweep` 后缀路由
- [ ] 6.3 RED:老用法仍能跑(向后兼容)
- [ ] 6.4 GREEN:全量测试

### 阶段 7 — 文档

- [ ] 7.1 `04-sweep-architecture.md` 加 §1.5
- [ ] 7.2 `05-sweep-usage.md` 加 §6 + 4 个完整示例
- [ ] 7.3 `CHANGELOG.md` v0.7.0
- [ ] 7.4 覆盖率 ≥ 80%

### 阶段 8 — 收尾

- [ ] 8.1 smoke:用户真实 4-case CSV 跑一遍
- [ ] 8.2 `simplify` + `code-review`
- [ ] 8.3 commit + push + PR
- [ ] 8.4 监控 CI + merge + 清理分支
- [ ] 8.5 **不**归档本计划(等 PR #2 一起归档)

---

## 5. 数据模型(关键)

```python
@dataclass
class CartesianSpec:
    """现有 sweeps 字段的内部表示"""
    axes: Dict[str, List[float]]


@dataclass
class ExplicitCase:
    """单个完整 case(显式 / 分组 / CSV 路径的最终归一化形式)"""
    values: Dict[str, float]
    group: Optional[str] = None  # 用于 {group} 命名占位


@dataclass
class CaseSweep:
    template: str
    output_dir: str
    sweeps: SweepSpec  # 老字段,向后兼容
    naming: str = ""
    overrides: Dict[str, Any] = field(default_factory=dict)
    freestream: Optional[FreestreamPreset] = None
    manifest_path: Optional[str] = None
    naming_ext: str = ".inp"
    # 新增:
    specs: List[Union[CartesianSpec, ExplicitCase]] = field(default_factory=list)
```

`from_dict` 同步 `sweeps`(老契约)+ `specs`(新契约):
- `sweeps` 在 → `CartesianSpec(axes=data["sweeps"])` 加入 specs
- `cases` 在 → 每个 case 转 `ExplicitCase`
- `groups` 在 → common + case 合并,转 `ExplicitCase` 带 group

`materialize()` 把 `specs` 摊平为 `List[ExplicitCase]`(笛卡尔展开在内部完成)。

`generate()` 优先用 `materialize()`(新),`specs` 为空时回退 `expand_cartesian(sweeps)`(纯老路径)。

---

## 6. 风险

| 等级 | 风险 | 缓解 |
|------|------|------|
| HIGH | 重构破坏 55+ 测试 | 阶段 1 严格"零行为变化",先跑通 |
| HIGH | `materialize()` 性能/正确性差异 | 阶段 1 跑全量测试对比 |
| MEDIUM | 老 YAML 在新解析器下微变 | 显式断言锁死 |
| MEDIUM | CSV 编码(Windows GBK) | UTF-8 优先,GBK fallback |
| MEDIUM | `{group}` 与字段名冲突 | 占位符隔离:group.name 不进 format |
| LOW | 命名冲突(cartesian+cases 同 key) | 报错 |

---

## 7. 兼容性

- **API:** `CaseSweep.sweeps: SweepSpec` 不变;`generate()` 签名不变
- **YAML:** 现有 `sweeps:` YAML 全部继续可用
- **CLI:** `inp-tool sweep sweep.yaml --alpha ...` 老调用全部继续
- **测试:** 55+ 现有 + ~30 新增 = 85+
- **覆盖率:** ≥ 80%

---

## 8. 不在本次范围

- ❌ Wizard / i18n(PR #2)
- ❌ LHS / Sobol 智能采样
- ❌ 无表头 CSV
- ❌ Jinja-like 命名(只 `{key}` 简单占位)
- ❌ Web GUI 接入

---

## 9. 验收

- [ ] 现有 55+ 测试全绿
- [ ] 新增 30+ 测试全绿
- [ ] 覆盖率 ≥ 80%
- [ ] 用户 4-case CSV 跑通
- [ ] 老 YAML `sweeps:` 行为零变化
- [ ] CHANGELOG v0.7.0 段
- [ ] PR merge 到 main
