# 11 — 用打包版本(standalone)

> **审计:** 2026-06-04 · 章节与 v0.4.2 同步 · 全部示例通过 · 全部链接有效
> **适合谁:** 不想(或不能)装 Python 的同事;运维受限环境;想快速试一下的人。
>
> **vs Python 安装版:** 打包版是**完全独立的可执行文件**——不需要 Python 环境、不需要 pip install、不需要 conda。
>
> 缺点:体积大(~24MB),启动慢一点(解压 ~2 秒)。

---

## 1. 下载

| 平台 | 文件 | 大小 |
|---|---|---|
| Linux x86_64 | `inp-tool` | ~24 MB |
| Windows 7+ x86_64 | `inp-tool.exe` | ~25 MB |
| macOS x86_64/arm64 | `inp-tool` | ~30 MB |

到 GitHub Release 页面下载最新版:
<https://github.com/oneMuggle/cfd--changer/releases>

> ⚠️ 当前发布可能未自动化,需要项目维护者手动上传。请先在仓库主页或 Discussions 询问。

## 2. 用法

### 2.1 Linux / macOS

```bash
# 1) 给可执行权限(下载后第一次)
chmod +x inp-tool

# 2) 试一下
./inp-tool --version
# inp 0.4.0

./inp-tool --help
# usage: inp [-h] [--version] {parse,get,set,diff,info,sweep,completion} ...

# 3) 跑一次扫描
./inp-tool sweep /abs/path/to/mcfd.inp /abs/path/to/sweep.json --out /abs/path/to/cases
```

### 2.2 Windows

```cmd
:: 1) 双击直接跑(会有黑窗闪过;推荐用 cmd)
inp-tool.exe --version

:: 2) 跑一次扫描
inp-tool.exe sweep D:\cfd\mcfd.inp D:\cfd\sweep.json --out D:\cfd\cases
```

### 2.3 macOS 第一次运行

macOS Gatekeeper 会拦截未签名应用:
```
"inp-tool" can't be opened because it is from an unidentified developer.
```

**绕过(一次性):**
1. 系统设置 → 隐私与安全 → 滚动到底部 → 点"仍要打开"
2. 或:`xattr -d com.apple.quarantine inp-tool`(命令行)

## 3. 配置文件路径:必须用绝对路径

`inp-tool` 是单文件可执行,binary 启动时的"当前目录"可能不是你以为的。**配置文件里的所有路径建议用绝对路径**。

### ❌ 不推荐

```json
{
  "template": "examples/mcfd.inp",       // ← 相对路径
  "output_dir": "./cases"               // ← 相对路径
}
```

### ✅ 推荐

```json
{
  "template": "/home/me/cfd/mcfd.inp",          // Linux/macOS 绝对路径
  "output_dir": "/home/me/cfd/sweep_out"        // Linux/macOS 绝对路径
}
```

```json
{
  "template": "D:\\cfd\\mcfd.inp",              // Windows 绝对路径
  "output_dir": "D:\\cfd\\sweep_out"            // Windows 绝对路径
}
```

## 4. 不包含什么

| 功能 | 打包版是否支持 | 备注 |
|---|---|---|
| `inp-tool parse / get / set / diff / info` | ✅ | 核心 CLI |
| `inp-tool sweep`(批量生成) | ✅ | 含 JSON / 交互式 / 快捷参数 |
| `inp-tool sweep -i`(交互) | ✅ | 终端 prompt 序列 |
| `inp-tool completion bash/zsh/fish` | ✅ | Shell 补全 |
| `inp-tool sweep xxx.yaml` | ✅ | **内置 pyyaml**(v0.5+ 默认进 core) |
| **`inp-tool-api`**(Web GUI) | ❌ | 需要 FastAPI / Pydantic,体积大;v0.5+ 单独打包 |
| `inp_tool` 作为 Python 包 import | ❌ | 要用 Python API,装 `pip install inp-tool` |

## 5. 已知问题

### 5.1 启动慢(单文件解压)

首次启动 ~2-3 秒。后续调用也每次 ~2-3 秒(单文件每次启动都解压到临时目录)。

如果嫌慢,等 v0.5 的 `--onedir` 多文件版本(启动 < 0.5 秒)。

### 5.2 Windows SmartScreen 告警

```
Windows protected your PC
微软 Defender SmartScreen prevented an unrecognized app from starting...
```

**解决:** 点"更多信息" → "仍要运行"。这是因为 binary 未签名,任何未签名的可执行文件都会触发。

**长期解决:** 项目维护者用代码签名证书签名(需购买,不在本工具范围)。

### 5.3 杀软误报

部分 Windows 杀软会标记 `inp-tool.exe` 为可疑(PyInstaller 通用 bootloader 容易被误报)。

**解决:**
- 上报至 [VirusTotal](https://www.virustotal.com/),添加白名单
- 或项目维护者换成 Nuitka 编译(误报少)

### 5.4 macOS Gatekeeper

如 §2.3 所述,需手动"仍要打开"或 `xattr` 命令。

## 6. 卸载

直接删除文件即可:

```bash
rm /usr/local/bin/inp-tool   # Linux/macOS
del D:\tools\inp-tool.exe    # Windows
```

不污染系统(不写注册表、不装服务、不留临时文件)。

## 7. 调试

### 7.1 看版本和命令

```bash
inp-tool --version
inp-tool --help
inp-tool sweep --help
```

### 7.2 出错信息

binary 报错信息和 Python 版一样(因为代码一样),见 [10-常见问题](../sweep/07-faq.md)。

### 7.3 与 Python 版对比

如果打包版有问题,先装 Python 版对比:

```bash
conda create -n cfdchanger python=3.8 -y
conda activate cfdchanger
pip install -e .[api,yaml]
inp-tool sweep ...
```

如果 Python 版能跑、binary 版不行,说明是打包问题;两者都不行,说明是 `inp_tool` 代码问题。

## 8. 下一步

- 用法见 [03-快速开始](../basics/03-quickstart.md) / [05-配置文件](../sweep/02-config-files.md)
- 出错见 [10-FAQ](../sweep/07-faq.md)
- 想理解 binary 怎么打的见 [../technical/release/01-cli-packaging.md](../technical/release/01-cli-packaging.md)
