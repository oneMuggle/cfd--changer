# 11 — CI/CD (GitHub Actions)

> **审计:** 2026-06-04 · 章节与 v0.4.2 同步 · 全部示例通过 · 全部链接有效
**位置:** `.github/workflows/`  ·  **工具:** GitHub Actions + conda + PyInstaller

---

## 1. 一句话

PR 触发测试(3 平台),tag 触发打包(3 平台)并自动发 GitHub Release。

## 2. 工作流概览

| 文件 | 触发 | 干啥 |
|---|---|---|
| `.github/workflows/ci.yml` | `pull_request` / `push` 到 main | 跑测试套件 (3 平台) |
| `.github/workflows/release.yml` | `push` tag `v*` / `workflow_dispatch` | 测试 + 3 平台打包 + GitHub Release |

## 3. 触发方式

### 3.1 测 PR / commit(自动)

`ci.yml` 自动跑:
- PR 开/更新 → 跑测试
- push 到 main → 跑测试
- 任何 commit → 跑测试(防 main 变红)

### 3.2 发新版(手动)

```bash
git tag v0.4.2
git push origin v0.4.2
# → release.yml 自动跑:
#    1. test 矩阵(必须全绿)
#    2. build 矩阵(3 平台各编一次)
#    3. 创建 GitHub Release (draft 模式,人工 review 后 publish)
```

或者 GitHub 网页 → Actions → "release" → Run workflow(无需 tag)。

## 4. CI 详情(`ci.yml`)

```yaml
strategy:
  matrix:
    os: [ubuntu-latest, windows-latest, macos-latest]
    python-version: ["3.8"]   # 钉死 Py3.8(Win7 兼容下限)
```

每平台跑:
1. `actions/checkout@v4` — 拉代码
2. `conda-incubator/setup-miniconda@v3` — 用 `environment.yml` 创建 cfdchanger env(Py 3.8)
3. `pip install -e ".[dev,api]"` — 装 inp_tool + FastAPI 测试依赖
4. `pytest tests/ --cov=inp_tool --cov-fail-under=80` — 跑测试,覆盖率 <80% 失败
5. (仅 ubuntu) `coverage html` + `upload-artifact` — 存 HTML 报告

并发控制:同一 ref 的旧 run 自动 cancel。

## 5. Release 详情(`release.yml`)

**3 个 job,顺序: test → build → release**

### 5.1 `test` job(预检)

3 平台跑测试。**`fail-fast: true`** — 任一失败立刻停,不浪费 CI 资源。

### 5.2 `build` job(打包)

matrix 包含 3 平台:
| OS | 产物名 | binary 内部名 |
|---|---|---|
| ubuntu-latest | `inp-tool-linux-x86_64` | `inp-tool` |
| windows-latest | `inp-tool-windows-x86_64.exe` | `inp-tool.exe` |
| macos-latest | `inp-tool-macos-universal2` | `inp-tool` |

每平台:
1. 装 conda + PyInstaller
2. 跑 PyInstaller 出 binary
3. 烟雾测试 (`./dist/inp-tool --version`)
4. 上传 artifact(`actions/upload-artifact@v4`)

`fail-fast: false` — 一个平台编失败不阻塞其它。

### 5.3 `release` job(发版)

ubuntu runner 收集所有平台 artifact,调 `softprops/action-gh-release@v2` 创建 GitHub Release:
- **`draft: true`** — 创建为草稿,人工 review 后再 publish(防误发)
- **`prerelease`** — 自动检测 `vX.Y.Z-rc.N` / `alpha` / `beta` tag,标为预发布
- **`generate_release_notes: true`** — GitHub 自动从 PR 生成 release notes
- **`fail_on_unmatched_files: true`** — 任何 artifact 漏传就 fail

## 6. 环境文件(`environment.yml`)

```yaml
name: cfdchanger
channels: [conda-forge, defaults]
dependencies:
  - python=3.8
  - pip
  - pytest>=7.0
  - pytest-cov>=4.0
  - httpx>=0.24
  - pyyaml>=6.0
  - pyinstaller=5.13.2   # 钉死,支持 Py 3.8 + Win7
```

**好处:** CI 和本地用同一份环境配置,完全可复现。

## 7. 踩坑记录

### 7.1 Windows runner + bash 脚本

GitHub Windows runner 默认 PowerShell。但我们在 `shell: bash -l {0}` 下,意思是"用 Git Bash"。

```yaml
- name: Build
  shell: bash -l {0}        # 强制用 bash
  run: |
    if [ "$RUNNER_OS" == "Windows" ]; then
        # Git Bash 不能直接跑 .bat
        python -c "import PyInstaller.__main__ as m; m.run(['inp_tool.spec','--clean','--noconfirm'])"
    else
        bash scripts/build.sh
    fi
```

### 7.2 conda 在 GitHub Actions 的坑

`setup-miniconda@v3` 的 `activate-environment` 选项**不**会自动激活,后续命令需用 `conda run -n cfdchanger ...`。

### 7.3 `working-directory` 默认

`defaults.run.working-directory` 让所有 `run:` 默认在指定目录,避免每个 step 重复 `cd`。

### 7.4 不要用 `master` 分支名

`on.push.branches: [main, master]` 兼容老仓库;新仓库只写 `main`。

## 8. 不在本 CI 范围

- **PyPI 发布** — 单独配 trusted publisher(留 v0.5)
- **代码签名** — 需证书(留 v0.5+)
- **依赖自动更新** — Dependabot 单独配
- **macOS 通用 binary** — 当前只在 macos-latest 跑,产出是 arm64;Intel Mac 需额外 `x86_64` runner

## 9. 本地模拟 CI

想本地跑 CI 等价的命令:

```bash
conda env create -f environment.yml
conda activate cfdchanger
pip install -e ".[dev,api]"
cd inp_tool
python -m pytest tests/ -v --tb=short --cov=inp_tool --cov-fail-under=80
```

## 10. 监控

- GitHub → repo → Actions tab:看每次 PR / tag 跑的结果
- 失败通知:GitHub 默认在 PR 上提示;也可在 Settings → Notifications 配邮件/Slack

## 11. 后续

- [ ] PR check required: 强制 ci.yml 跑过才允许合并(Settings → Branches → Branch protection)
- [ ] 跑 PyPI 发布 trusted publisher(配 OIDC)
- [ ] 启用 Dependabot(自动 PR 依赖更新)
- [ ] macOS 通用 binary(arm64 + x86_64 合并)
