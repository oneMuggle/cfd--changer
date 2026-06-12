# 03 — 快速开始(5 分钟)

> **审计:** 2026-06-04 · 章节与 v0.4.2 同步 · 全部示例通过 · 全部链接有效
## 你需要的

1. 安装好的 `inp-tool`(见 [02-安装](./02-installation.md))
2. 一个 `mcfd.inp` 样例(本项目 `inp_tool/examples/mcfd_v2_modified.inp` 是一个 1300 行的真实样例)
3. 一个想扫描的参数(本节用 `alpha × mach`)

## 三种姿势任选

### 姿势 A:命令行快捷(最快)

```bash
# 最简单的一次:扫 3 个 alpha × 2 个 mach = 6 个 case
inp-tool sweep examples/mcfd_v2_modified.inp \
    --alpha 0,4,8 \
    --beta 0 \
    --mach 0.6,0.8 \
    --t-inf 288.15 \
    --p-inf 101325 \
    --out /tmp/my_sweep
```

输出:

```
[sweep] generated 6 cases -> /tmp/my_sweep
  - case_0.0_0.0_0.6_288.15_101325.0.inp  (alpha=0.0 beta=0.0 mach=0.6 ...)
  - case_0.0_0.0_0.8_288.15_101325.0.inp  ...
  - case_4.0_0.0_0.6_288.15_101325.0.inp  ...
  - case_4.0_0.0_0.8_288.15_101325.0.inp  ...
  - case_8.0_0.0_0.6_288.15_101325.0.inp  ...
  - case_8.0_0.0_0.8_288.15_101325.0.inp  ...
```

**注:** 默认 naming 包含所有 sweep 字段(单值字段 T_inf/p_inf/beta 也进)。如果你不想要这么长的名字,加 `--naming`:

```bash
inp-tool sweep examples/mcfd_v2_modified.inp \
    --alpha 0,4,8 --beta 0 --mach 0.6,0.8 \
    --t-inf 288.15 --p-inf 101325 \
    --naming "case_aoa{alpha:02.0f}_ma{mach:.2f}.inp" \
    --out /tmp/my_sweep
# 输出文件名: case_aoa00_ma0.60.inp / case_aoa04_ma0.60.inp / ...
```

### 姿势 B:JSON 配置文件(便于复现)

**1) 写一个 `sweep.json`:**

```json
{
  "template":   "examples/mcfd_v2_modified.inp",
  "output_dir": "/tmp/my_sweep",
  "sweeps": {
    "alpha": [0, 4, 8],
    "beta":  [0],
    "mach":  [0.6, 0.8],
    "T_inf": [288.15],
    "p_inf": [101325.0]
  },
  "naming": "case_aoa{alpha:02.0f}_ma{mach:.2f}.inp",
  "manifest": {
    "path": "/tmp/my_sweep/manifest.json"
  }
}
```

**2) 运行:**

```bash
inp-tool sweep examples/mcfd_v2_modified.inp sweep.json --out /tmp/my_sweep
```

**3) 把 `sweep.json` 存进 Git**,以后同事/审稿人都能复现。

### 姿势 C:交互式(边问边答)

```bash
inp-tool sweep -i
```

按提示一步步回答,回车接受默认。详见 [08-多入口 §3](../sweep/08-multiple-uis.md)。

## 看看生成结果

```bash
ls /tmp/my_sweep/
# case_aoa00_ma0.60.inp  case_aoa00_ma0.80.inp  case_aoa04_ma0.60.inp
# case_aoa04_ma0.80.inp  case_aoa08_ma0.60.inp  case_aoa08_ma0.80.inp
# manifest.json

# 抽查 alpha=8 的 case 关键字段
grep -E "^aero_(alpha|u|w|ma) " /tmp/my_sweep/case_aoa08_ma0.80.inp
# 期望:
#   aero_alpha 8.0
#   aero_ma    0.8
#   aero_u     269.58...   = 0.8 × 340.3 × cos(8°)
#   aero_w     37.88...    = 0.8 × 340.3 × sin(8°)
```

## 试试 dry-run(不写盘,先看会生成什么)

```bash
inp-tool sweep examples/mcfd_v2_modified.inp sweep.json --out /tmp/my_sweep --dry-run
```

输出和真跑一样,但磁盘上什么都没有。可以放心在生产环境上先 `--dry-run` 验证。

## 下一步

- 想扫更多参数,见 [04-扫描参数](../sweep/04-sweeping.md)
- 想用 YAML 写配置,见 [05-配置文件 §YAML](../sweep/05-config-files.md)
- 想改其他字段(不只是 alpha/beta/mach),见 [07-字段覆盖](../sweep/07-overrides.md)
- 出错了?看 [10-常见问题](../sweep/10-faq.md)
