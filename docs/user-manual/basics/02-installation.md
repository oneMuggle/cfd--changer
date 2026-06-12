# 02 — 安装

> **审计:** 2026-06-04 · 章节与 v0.4.2 同步 · 全部示例通过 · 全部链接有效
## 系统要求

| 项 | 要求 |
|---|---|
| 操作系统 | Windows 7 / Windows 10 / Linux(macOS 也行,未测) |
| Python | 3.8 ~ 3.12(**3.8 是 Win7 兼容下限**) |
| 磁盘 | 50MB(纯 Python 包,无大型依赖) |
| 网络 | 仅安装时需要(从 PyPI / conda 拉包) |

> 如果你公司用 Python 2 或更老,**先升级到 3.8+**,本工具不支持。

## 强烈推荐:用 conda 隔离环境

`inp_tool` 安装在 conda 环境里,不影响你机器上其他 Python 项目。一次性配置,长期使用。

### 第一步:创建环境(只做一次)

```bash
conda create -n cfdchanger python=3.8 -y
```

> 名字 `cfdchanger` 只是约定,你也可以叫 `myenv`。

### 第二步:激活环境

**Linux / macOS:**

```bash
conda activate cfdchanger
```

**Windows (Anaconda Prompt):**

```
activate cfdchanger
```

激活后,终端前缀会变成 `(cfdchanger) $` 或类似。

### 第三步:安装 inp-tool

**方式 A:从源码安装(推荐,跟随项目最新版)**

```bash
# 假设项目代码在 ./cfd--changer/inp_tool/
cd cfd--changer/inp_tool
pip install -e .[api,yaml]
```

- `pip install -e .` = editable install,代码改了立刻生效
- `[api,yaml]` = 同时装 Web 后端 + YAML 支持

**方式 B:只装核心(不想要 Web GUI / YAML)**

```bash
pip install -e .
```

### 第四步:验证

```bash
inp-tool --version
# 应输出: inp 0.4.0

inp-tool --help
# 应列出子命令: parse / get / set / diff / info / sweep / completion
```

如果 `inp-tool` 命令找不到,说明环境没激活。重做第二步。

## Windows 路径注意事项

`mcfd.inp` 路径里如果有反斜杠 `D:\path\to\mcfd.inp`:

- **JSON / YAML 配置里** — 用 `\\` 转义,例如 `"D:\\\\path\\\\to\\\\mcfd.inp"`
- **CLI 命令行** — 直接用 `D:\path\to\mcfd.inp`(shell 会处理)
- **Web GUI 表单** — 直接填 `D:\path\to\mcfd.inp`

## 离线安装(没网的公司机器)

```bash
# 有网的机器上:
pip download inp-tool[api,yaml] -d ./inp_tool_pkgs/

# 离线机器上:
pip install --no-index --find-links=./inp_tool_pkgs/ inp-tool[api,yaml]
```

## 可选:启动 Web GUI

```bash
python run_server.py
# 浏览器: http://127.0.0.1:8765/
```

需要 `pip install -e .[api]`(已装)。

## 卸载

```bash
pip uninstall inp-tool
conda deactivate    # 退出环境(可选)
conda env remove -n cfdchanger   # 删整个环境(可选)
```

## 升级

```bash
# 拉最新代码后,重装
cd cfd--changer
git pull
conda run -n cfdchanger pip install -e .[api,yaml] --upgrade
```

## 遇到问题?

- **`pip: command not found`** — conda 环境没激活
- **`python 3.8 not found`** — conda 装的 Python 版本不对,看 [01-介绍 §系统要求](./01-introduction.md)
- **Web GUI 起不来** — 检查 8765 端口没被占用;`netstat -ano | grep 8765`(Win) / `lsof -i:8765`(Linux)
- **其它** — 提 issue 或联系项目维护者

下一步:[03-快速开始](./03-quickstart.md) — 5 分钟跑通第一个批量生成。
