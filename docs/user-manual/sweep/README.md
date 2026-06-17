# Sweep(扫描参数)

> sweep 是本工具的**主要用途**;本章把 sweep 从入门讲到精通,含 FAQ。

## 章节

| # | 标题 | 内容简介 | 阅读时间 |
|---|---|---|---|
| [01-sweeping](01-sweeping.md) | 扫描参数 | 可扫哪些字段 / 笛卡尔积 / 来流参数 / 几何分解 | 15 分钟 |
| [02-config-files](02-config-files.md) | 配置文件 | JSON vs YAML vs CLI 怎么选 / 字段详解 | 15 分钟 |
| [03-naming](03-naming.md) | 命名规则 | `str.format` 模板 / 格式说明符 / 校验规则 | 10 分钟 |
| [04-overrides](04-overrides.md) | 字段覆盖 | 改 alpha/ma 之外的字段(时间步、输出频率等) | 15 分钟 |
| [05-multiple-uis](05-multiple-uis.md) | 多入口使用 | CLI / Python / Web GUI / 交互式 / Shell 补全 | 15 分钟 |
| [06-examples](06-examples.md) | 完整示例 | 6 个端到端真实场景 | 20 分钟 |
| [07-faq](07-faq.md) | 常见问题 | 安装/运行/几何分解/路径/性能/调试 | 边用边查 |

## 速读路径

- **30 分钟会用** → 01 + 02
- **完整掌握** → 01-07(约 1.5 小时)

## 三视图使用(GUI 批量算例标签页)

「批量算例」标签页升级为**三视图 tab 整合**,3 个子 tab 共享同一份配置,改一个其他自动同步。

### 三个子视图

| 子 tab | 适合谁 | 主要功能 |
|---|---|---|
| **向导** | 第一次用 / 一步步带 | 4 步引导:模板与输出 → 选轴设值 → 条件依赖 → 预览运行 |
| **自由表单** | 老用户 / 快速编辑 | 单页紧凑表,每行 combo(变量) + 值 widget + 删除 |
| **YAML** | 高级用户 / 复现 / Git diff | 直接编辑 v2 YAML + 左侧变量/preset 树 + 实时 lint |

### 切换方式

- **鼠标**:点击顶部 tab 行
- **键盘**:
  - `Ctrl+1` 切到「向导」
  - `Ctrl+2` 切到「自由表单」
  - `Ctrl+3` 切到「YAML」

### 共享数据流

3 个视图**共用同一个 `ConfigStore`**(不可变配置),任一视图修改后:

1. View 调 `ConfigStore.replace(...)` 返回新实例
2. store holder emit `config_changed(new)`
3. 其他 2 个 View 自动同步(改 YAML 后切到向导,值已变;在向导选轴后切到 YAML,看到对应行)

不需要手动「保存」,切换 tab 就是同步动作。

### 第一次启动:3 个默认 preset

首次打开 GUI 时,程序会自动 `seed_default_presets()`,把 3 个内置 preset 复制到 `~/.config/cfd--changer/presets/`:

| Preset 名 | 用途 |
|---|---|
| `low-speed-baseline` | 亚音速算例基线(Ma ≤ 0.3 区间) |
| `transonic-baseline` | 跨音速算例基线(含 2 个 conditions) |
| `high-speed-baseline` | 高超声速算例基线(Ma ≥ 2.0) |

> 这些 preset 仅作为参考起点;你可以双击「我的 preset」里同名文件查看/编辑/另存为新 preset。

### 常用快捷键速查

| 键 | 行为 |
|---|---|
| `Ctrl+1/2/3` | 切子 tab(向导/表单/YAML) |
| `Ctrl+S` | 当前 spec 存为 YAML(弹保存对话框) |
| `Ctrl+R` | Dry run(预估 case 数 + 渲染预览) |
| `Ctrl+Shift+R` | 实际运行 |
| `Ctrl+Shift+P` | 打开 preset 库管理 |

## 关联

- 上级: [`../README.md`](../README.md) — 用户手册总览
- 上游: [`../basics/`](../basics/) — 入门
- 开发者视角: [`../../technical/sweep/`](../../technical/sweep/) — sweep 内部实现
- 三视图架构详解: [`../../technical/sweep/13-sweep-ui-v2.md`](../../technical/sweep/13-sweep-ui-v2.md)
