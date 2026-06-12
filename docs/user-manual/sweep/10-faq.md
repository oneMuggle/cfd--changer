# 10 — 常见问题(FAQ)

> **审计:** 2026-06-04 · 章节与 v0.4.2 同步 · 全部示例通过 · 全部链接有效
## 安装

### Q: `pip: command not found`

A: 你没激活 conda 环境。重新执行 `conda activate cfdchanger`(或 `activate cfdchanger` on Windows)。

### Q: `python: 3.8 not found`

A: `inp_tool` 需要 Python 3.8 ~ 3.12。如果 conda 装的是 3.7 或 3.13,会失败。

```bash
conda create -n cfdchanger python=3.8 -y   # 重新创建
```

### Q: 装在 Windows 7 上,`pip install` 报 `Microsoft Visual C++ 14.0 required`

A: `inp_tool` 核心是纯 Python,无 C 扩展。错误可能是 transitive 依赖(`pyyaml` 用了 C)。试试:

```bash
# 用纯 Python 替代:
pip install inp-tool --no-deps
pip install pyyaml --no-binary :all:
```

或者升级到 Windows 10(Win7 维护期已过)。

### Q: 公司代理下 `pip install` 失败

A: 设 `HTTPS_PROXY` 环境变量:

```bash
set HTTPS_PROXY=http://your-proxy:8080
pip install inp-tool
```

或 `pip install --proxy http://your-proxy:8080 inp-tool`。

---

## 运行

### Q: `inp-tool: command not found`

A: 装好但环境没激活,或安装路径不在 PATH。

```bash
# 1) 激活
conda activate cfdchanger

# 2) 重装
conda run -n cfdchanger pip install -e .[api,yaml]
```

### Q: `KeyError: 'template'`

A: 配置文件缺 `template` 字段。检查 JSON/YAML。

```yaml
template: path/to/mcfd.inp     # ← 必填
output_dir: path/to/out       # ← 必填
sweeps:                        # ← 必填
  alpha: [0, 5, 10]
```

### Q: `naming template ... is missing sweep key placeholders for multi-value axes: ['mach']`

A: 命名模板缺一个**多值** sweep 字段的占位符。

```yaml
# 错:
naming: "case_aoa{alpha:02.0f}.inp"
# sweep 含 mach 是多值,缺 {mach}

# 对:
naming: "case_aoa{alpha:02.0f}_ma{mach:.2f}.inp"
```

### Q: 跑完生成的文件 `diff` 模板,显示大量 modify,值没变

A: 已知 — `inp_tool` v0.2 限制,`to_text` 不保留原文件空白风格。

```bash
# 验证:值没变(只是空白不同)
inp-tool diff template.inp case_aoa04.inp
# 期望: 只看到 guiopts.aero_alpha/ma/u/v/w 之类被改
```

详见 `inp_tool` 全局限制(本项目不打算 v0.4 修复,留到 v0.5+ 写 `preserve_format` 选项)。

---

## 几何分解 / 来流

### Q: 跑出来 aero_u/v/w 和我 CFD++ 软件算的不一样

A: **方向假设可能不同**。`inp_tool` 默认:

```
α → 影响 W (法向 / 垂直)
β → 影响 V (侧滑)
```

如果你的 CFD++ 是:

```
α → 影响 V
β → 影响 W
```

**修法:** 关闭 preset,手动给:

```yaml
sweeps:
  alpha: [0, 5, 10]
freestream:
  enabled: false
overrides:
  guiopts:
    aero_u: 250.0
    aero_v: <your-formula>
    aero_w: <your-formula>
```

或者,先用 1 个 case 对比,确认差异后再决定方案。

### Q: `refvel` 算的不对 / aero_reynolds 没自动算

A: `inp_tool` 不自动算 Reynolds 数。Reynolds = ρ · v · L / μ,需要参考长度(翼弦、机翼参考长度),`inp_tool` 不知道。

**修法:** 在 overrides 里手动:

```yaml
overrides:
  guiopts:
    aero_re: 5000000.0   # 5e6
```

或自己用 Python 算:

```python
rho = 1.225      # kg/m³ (海平面空气)
v   = 250.0      # m/s
L   = 0.5        # m (翼弦)
mu  = 1.8e-5     # Pa·s
Re  = rho * v * L / mu
# Re = 8.5e6
```

---

## 文件 / 路径

### Q: Windows 路径里的反斜杠怎么写?

| 场景 | 写法 |
|---|---|
| **JSON 配置文件** | `"D:\\\\cfd\\\\mcfd.inp"`(每 `\`,2 个) |
| **YAML 配置文件** | `D:\cfd\mcfd.inp`(单引号包住) |
| **CLI 命令行** | `"D:\cfd\mcfd.inp"`(双引号包住) |
| **Web GUI** | `D:\cfd\mcfd.inp` |

### Q: 输出目录不存在会怎样?

A: 自动创建(用 `os.makedirs(..., exist_ok=True)`)。无错误。

### Q: 输出文件已存在,会被覆盖吗?

A: 会(无确认)。如担心,先 `--dry-run` 看会生成什么。

---

## 性能

### Q: 1000 个 case 要多久?

A: 开发机 SSD,~5 秒。瓶颈是磁盘 IO。

### Q: 想扫 10 万个 case?

A: 当前实现是串行同步,~10 分钟。联系项目维护者讨论并行化(v0.6 计划)。

### Q: 内存够吗?

A: 50KB/case × 1000 = 50MB。1 万 = 500MB。一般够。

---

## Web GUI

### Q: 启动后浏览器打不开

A: 检查端口 8765 没被占用,或换端口:

```bash
uvicorn inp_tool.api:app --port 9000
```

### Q: Web GUI 报"template not found"

A: 浏览器填的路径是**浏览器**视角,服务端找不到。**服务器**上填的路径才对。

- 本地:localhost → 路径可以是 `D:\cfd\mcfd.inp` 或 Linux 路径
- 远程:服务器视角,不能是 Windows 路径(除非服务器是 Windows)

### Q: Web GUI 怎么上传 .inp?

A: v0.4 还没做(规划 v0.5)。当前必须服务端能直接访问的本地路径。

---

## 与 CFD++ 求解器集成

### Q: 生成的 .inp CFD++ 跑报错

A: 常见原因:

1. **空白/缩进被改** — 已知限制,`to_text` 不保留原格式
2. **缺必要字段** — 模板里没 `guiopts` / `physics` 块
3. **值超界** — 比如 Mach > 5 触发超音速选项但模板是亚音速设置

**调试:** 对比模板和生成 case 的 `diff`,逐项排查。

### Q: 怎么批量跑 CFD++?

A: `inp_tool` 不负责。生成 .inp 后,自己写 shell 脚本:

```bash
# bash
for f in /tmp/sweep/*.inp; do
    mcrun -np 16 "$f" &
done
wait
```

或用 CFD++ GUI 自带的"批量提交"功能,或 HPC 调度器(SLURM/PBS)。

---

## 调试

### Q: 跑出来的值和我算的不一样

A: 用 manifest.json 反查每个 case 的 `applied` 字段:

```bash
cat /tmp/sweep/manifest.json | python -m json.tool
```

看每个 case 实际写进了什么。

### Q: 想看 `inp-tool` 的 debug 日志

A: Python 里:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

CLI 暂无 `--debug` 选项(可加)。

### Q: 想看模板被 `inp_tool` 怎么解析

A:

```bash
inp-tool info tpl.inp         # 看所有块
inp-tool parse tpl.inp -b tsteps -f   # 看 tsteps 块
inp-tool get tpl.inp cflbot -b tsteps  # 看单个值
```

---

## 我有别的需求 / 想贡献

提 issue / PR 到 GitHub 仓库: <https://github.com/oneMuggle/cfd--changer>

或在 `inp_tool/README.md` 看开发指南。

下一步:回到 [README](../../README.md) 总览。
