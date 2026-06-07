# 10 — CLI 打包(PyInstaller)

> **审计:** 2026-06-04 · 章节与 v0.4.2 同步 · 全部示例通过 · 全部链接有效
**模块:** `inp_tool` 打包分发  ·  **工具:** PyInstaller 5.13.2  ·  **状态:** 已发布

---

## 1. 一句话

把 `inp-tool` Python 包打包成 **单文件 standalone 可执行**,用户下载双击就能用,**无需 Python 环境**。

| 平台 | 产物 | 大小 |
|---|---|---|
| Linux x86_64 | `inp-tool` | ~24 MB |
| Windows 7+ x86_64 | `inp-tool.exe` | ~25 MB |
| macOS x86_64/arm64 | `inp-tool` | ~30 MB |

## 2. 为什么需要打包

| 用户类型 | 场景 |
|---|---|
| Python 熟手 | `pip install -e .[api,yaml]`,用 venv 一切正常 |
| **非 Python 同事** | **没装 Python,不愿装**,需要 standalone |
| **运维受限环境** | **不能装第三方 Python 包**,只允许可执行 |
| **分发评审/审稿人** | 给同事拷一个 binary,免去配置说明 |

## 3. 技术选型

| 工具 | 选? | 理由 |
|---|---|---|
| **PyInstaller 6.16.0** | ✅ | 6.x 仍支持 Python 3.8(直到 6.9);修了一些 5.x onedir 边缘 bug |
| PyInstaller 5.13.2 | 旧备 | 5.x 末班,仅在 6.x 有兼容性回归时回退 |
| Nuitka | 备选 | 性能更好(编译为 C),但配置复杂,Win7 兼容性未测 |
| cx_Freeze | 不选 | 老旧 |
| pyoxidizer | 不选 | 体积小但 Win7 兼容性未测 |

**为什么 6.16 而不是更新的 6.x?** 6.10+ 移除了 Python 3.8 支持,违反 `requires-python = ">=3.8"` 硬约束。6.16 是支持 Py3.8 的最后一个 6.x(2026-06 当前)。

## 4. 文件清单

| 路径 | 角色 |
|---|---|
| `inp_tool/inp_tool.spec` | PyInstaller spec(跨平台) |
| `scripts/build.sh` | Linux/macOS 构建 |
| `scripts/build.bat` | Windows 构建 |
| `inp_tool/pyproject.toml` | 新增 `[build]` extras |
| `inp_tool/tests/test_packaging.py` | 静态 + 动态测试 |

## 5. Spec 设计要点

### 5.1 入口文件

用 `inp_tool/__main__.py` 作为入口(不是 `cli.py`)。原因:
- 走 `python -m inp_tool` 标准入口
- binary 启动时 `__main__` 的 `__package__` 为空,相对导入会失败
- **`__main__.py` 必须用绝对导入**:`from inp_tool.cli import main` ✓

### 5.2 单文件模式 (onefile)

```python
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name=exe_name,
    console=True,   # CLI 工具,需要 stdout
    upx=False,      # 部分杀软误报 UPX
)
```

- **不用 COLLECT()** — 那会生成 onedir(多文件目录)模式
- **UPX 关掉** — 体积稍大(24MB vs 15MB),但避免杀软误报

### 5.3 资源打包

```python
datas=[
    ('examples', 'inp_tool/examples'),
    ('web',      'inp_tool/web'),
],
```

- 路径相对 spec 所在目录(默认 cwd = `inp_tool/`)
- 运行时通过 `sys._MEIPASS` 访问(单文件解压到临时目录)

### 5.4 hiddenimports

```python
hiddenimports=[
    'inp_tool',
    'inp_tool.sweep',
    'inp_tool.api',
    'inp_tool.cli',
    'inp_tool.parser',
    'inp_tool.writer',
    'inp_tool.diff',
    'inp_tool.model',
],
```

防止 PyInstaller 静态分析漏掉动态加载的子模块。

### 5.5 excludes(慎用)

```python
excludes=[
    'tkinter', 'unittest', 'test', 'tests', 'lib2to3', 'pdb',
],
```

**踩坑记录:**
- ❌ 不要 exclude `email` / `xml` — setuptools 的 `pkg_resources` 间接依赖
- ❌ 不要 exclude `urllib` — 留 `urllib.error` / `urllib.parse`,会被 `urllib3` 等使用
- ❌ 不要 exclude `http` — `urllib.request` / `httpx` 需要 `http.client`

最终保守 excludes,只在确定不用的(用不到的 GUI / IDE / 测试框架)才 exclude。

## 6. 构建流程

```bash
# 1) 装 build extras
conda activate cfdchanger
pip install -e .[build]

# 2) 构建
./scripts/build.sh
# 或 Windows: scripts\build.bat
```

输出:
```
==> [1/4] 检查 PyInstaller
  PyInstaller 5.13.2
==> [2/4] 清理上次构建
==> [3/4] PyInstaller 构建
... (PyInstaller 日志) ...
==> [4/4] 验证产物
  ✓ dist/inp-tool (24M)
==> 烟雾测试: --version
inp 0.4.0
==> 烟雾测试: --help
usage: inp [-h] [--version] {parse,get,set,diff,info,sweep,completion} ...
```

## 7. 跨平台编译

⚠️ **PyInstaller 不支持交叉编译。** 必须在目标平台(或其等价环境)上编:

| 目标 binary | 必须在哪编 | 备注 |
|---|---|---|
| `inp-tool` (Linux) | Linux | 用 conda 装的 PyInstaller 5.13.2 |
| `inp-tool.exe` (Win) | Windows (Anaconda Prompt) | 同样装 `[build]` 后跑 build.bat |
| `inp-tool` (macOS) | macOS | 同上 |

**生产建议:** GitHub Actions matrix
```yaml
strategy:
  matrix:
    os: [ubuntu-latest, windows-latest, macos-latest]
```

每个 runner 跑 `pyinstaller`,然后 `actions/upload-artifact` 上传 `dist/inp-tool*` 到 GitHub Release。

## 8. 验证产物

`scripts/build.sh` 末尾会自动跑烟雾测试:
- `./dist/inp-tool --version`  → 输出 `inp 0.4.x`
- `./dist/inp-tool --help`    → 列出 7 个子命令

端到端验证(手动):
```bash
mkdir /tmp/test
cat > /tmp/test/sweep.json <<'EOF'
{
  "template": "/abs/path/to/mcfd.inp",
  "output_dir": "/tmp/test/out",
  "sweeps": {
    "alpha": [8.0],
    "mach":  [0.6],
    "T_inf": [288.15],
    "p_inf": [101325.0]
  }
}
EOF
./dist/inp-tool sweep /tmp/test/sweep.json
# 期望: 1 个 case_aoa08_ma0.60.inp,几何分解正确
```

**注意:** 配置文件里的 `template` 必须用**绝对路径**。相对路径相对 binary 启动时的 cwd,行为不可预期。

## 9. 测试

`tests/test_packaging.py`:
- **静态检查**(默认跑):7 个,验证 spec / build 脚本 / pyproject extras
- **动态构建**(`ENABLE_BUILD_TEST=1` 跑):2 个,真编并跑端到端

```bash
# 静态(快,~0.1s)
pytest tests/test_packaging.py -v

# 动态(慢,~30-60s)
ENABLE_BUILD_TEST=1 pytest tests/test_packaging.py -v
```

## 10. 已知限制

| 限制 | 缓解 |
|---|---|
| 单文件启动慢(解压 ~0.5 秒) | 用户期望;`--mode onedir` 已可用(同 onefile 行为,仅分发形态不同) |
| 体积大(~24MB) | 已是去除 stdlib 大块后;UPX 不可用(杀软) |
| `inp-tool-api` (Web GUI) 不在默认 binary | 需 FastAPI+Pydantic 等重依赖;若需 Web,单独打包 `api` 版本 |
| Win SmartScreen 告警(未签名) | 待证书;当前用户点"仍要运行"即可 |
| Linux 杀软偶发误报 | 上报至 https://www.virustotal.com |

## 11. 后续工作(v0.5+)

- [ ] GitHub Actions matrix 自动编 + 发 GitHub Release
- [x] `--onedir` 模式(分发形态:EXE + 同目录,实际产物仍自包含 deps,因 PyInstaller 5.x/6.x + Python 3.8 + Linux 的 COLLECT+_MEI libpython bug 不可行,见 `inp_tool_onedir.spec` 头注释 2026-06-07)
- [ ] `inp-tool-api` 单独 binary(含 Web GUI)
- [ ] 代码签名(Win 避开 SmartScreen / macOS notarization)
- [ ] 体积进一步压缩(excludes + 资源文件分拆)
