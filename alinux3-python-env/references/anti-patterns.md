# Alinux3 Python 环境 — 反模式(Anti-patterns)

每条都是真实踩过的坑,执行前先看一遍,能省下数小时调试。

## AP-1. 不要用 `update-alternatives --set python3 /usr/bin/python3.8`

```bash
# ❌ 千万别这么干
sudo update-alternatives --set python3 /usr/bin/python3.8
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.8 10
```

**为什么**:`dnf` / `yum` / `rpm` 自身的 Python 脚本硬编码假设 `python3 == 3.6`(实际上 Alinux3 把 `/usr/bin/dnf*` 都指向 3.6)。一旦全局换,下次 `dnf install ...` 直接:
- `SyntaxError: invalid syntax`(3.6 不认识 3.8 写的语法)
- 或者 `ModuleNotFoundError: No module named 'dnf'`(3.8 没 dnf 的 site-packages)
- 直接 `dnf` 命令断掉,系统包管理不可用,**装包修复都很难**(得手动恢复 `/usr/bin/python3` 软链)。

**对的做法**:见 SKILL.md §6.2,用 `alias` / `~/.bashrc` 改 user shell 默认,**不动 `/usr/bin/python3`**。或者直接用 venv(§6.3)。

## AP-2. 不要 `dnf remove python36`

```bash
# ❌ 高危:dnf 自己依赖 3.6
sudo dnf remove python36 -y
```

**为什么**:`dnf` / `rpm` / `yum` 都依赖 `/usr/bin/python3`(→ 3.6 软链)。移除 3.6 会触发 dnf 自身依赖解决错误,半数情况下包管理器直接断掉。

**对的做法**:3.6 留着,3.8 并行装,venv 隔离。

## AP-3. 不要用 `pip install <pkg>`(不带 `python3.8 -m`)

```bash
# ❌ 默认 python3 = 3.6,装到错的 site-packages
pip install pydantic
# or
python3 -m pip install pydantic
```

**症状**:`pip list` 显示装好了,但 `python3.8 -c "import pydantic"` 报 `ModuleNotFoundError` —— 因为装到了 `/usr/lib/python3.6/site-packages/`,而项目用的是 3.8。

**对的做法**:永远用 `/usr/bin/python3.8 -m pip ...` 或激活 venv 后的 `pip ...`(见 §6.3)。也可以建个 wrapper:
```bash
sudo tee /usr/local/bin/py38pip << 'EOF'
#!/bin/bash
exec /usr/bin/python3.8 -m pip "$@"
EOF
sudo chmod +x /usr/local/bin/py38pip
# 用法:py38pip install pydantic
```

## AP-4. 不要跳过配源直接 `pip install`

```bash
# ❌ 默认走 pypi.org,慢 + 可能 timeout + 公司网络直接断
pip install pydantic
```

**为什么**:Alinux3 在阿里云上,pypi.org 默认出口慢且常超时;公司内网可能根本不可达。

**对的做法**:先建 `~/.pip/pip.conf`(§2)。Aliyun 镜像同机房,**必须**配。

## AP-5. 不要 `pip install fake-useragent`(不锁版本)

```bash
# ❌ 装最新版直接跑 1.5+,3.8 报 PEP 585 错
pip install fake-useragent
python3.8 -c "import fake_useragent; ua = fake_useragent.UserAgent(); print(ua.random)"
# TypeError: 'type' object is not subscriptable
```

**对的做法**:
```bash
pip install "fake-useragent<1.5"   # 锁定到 1.4.x
# 或在 requirements.txt:
#   fake-useragent>=1.0.0,<1.5.0
```

## AP-6. 不要在系统 Python 上直接装包(用 venv)

```bash
# ❌ 装到 /usr/local/lib/python3.8/site-packages
# 触发 PEP 668 externally-managed-environment
# 多项目之间互相污染,卸载一个包可能断另一个项目
sudo /usr/bin/python3.8 -m pip install requests
```

**对的做法**:每个项目一个 venv(§6.3):
```bash
/usr/bin/python3.8 -m venv ./venv
source ./venv/bin/activate
pip install requests   # 安全,不污染系统
```

**例外**:CI / 一次性脚本 / 个人玩具项目可以 `--break-system-packages` 临时绕过,但生产项目不许。

## AP-7. 不要把 Python 包写进 `/usr/bin/python3 -m pip freeze` 输出

```bash
# ❌ 拿到一份依赖列表,直接拿去给别人用
/usr/bin/python3.8 -m pip freeze > requirements.txt
# 里面会有 pip / setuptools / wheel 这种系统级东西,别人装了也没用
```

**对的做法**:venv 里 `pip freeze`,干净。或者用 `pip freeze --exclude pip,setuptools,wheel`。

## AP-8. 不要假设 `python` 命令存在

```bash
# ❌ 在某些 Alinux3 镜像里 /usr/bin/python 不存在(只有 python3)
python --version
# bash: python: command not found
```

**对的做法**:脚本里永远用 `python3` 或 `/usr/bin/python3.8`。`python` 是 PEP 394 的"可选"符号,Alinux3 没建。

## AP-9. 不要用 `pip install -U` 全量升级

```bash
# ❌ 把所有包升到最新版,可能撞 PEP 585 / PEP 604 不兼容
/usr/bin/python3.8 -m pip install -U -r requirements.txt
```

**对的做法**:用 `pip install --upgrade-strategy only-if-needed <pkg>`,或者干脆不要全量升级,把要升的包写明确。

## AP-10. 不要在 crontab / systemd unit 里写 `pip install`

```bash
# ❌ crontab / systemd 启动时偷偷装包
@reboot pip install requests
```

**为什么**:
- 网络不可用 → 启动失败
- 装错版本 → 行为漂移
- pip 升级自身的 release notes 弹窗会卡住 cron

**对的做法**:依赖装在 deploy 阶段(setup script),运行时只 `pip check` 验证,不安装。

## AP-11. 不要假设 `gcc` / `python38-devel` 已装

```bash
# ❌ 装带 C 扩展的包直接失败
pip install numpy psycopg2 lxml
# error: command 'gcc' failed: No such file or directory
# 或: Python.h: No such file or directory
```

**对的做法**:
```bash
sudo dnf install -y gcc python38-devel openssl-devel libffi-devel
```

或者优先选 wheel-only 包(纯 Python)。

## AP-12. 不要无视 PEP 668 警告硬装

```bash
# ❌ 看到 "externally-managed-environment" 就 --break-system-packages
/usr/bin/python3.8 -m pip install --break-system-packages requests
```

**为什么**:dnf module 装的 python3.8 标记了 `/usr/lib/python3.8/EXTERNALLY-MANAGED`,是 RHEL 系的设计:**系统 Python 是受控的**。硬装会污染系统,后续 dnf 升级时可能被清理。

**对的做法**:用 venv(§6.3)。只在 sandbox / Docker 一次性环境用 `--break-system-packages`。

---

## 速查对照(红黑榜)

| 场景 | 错 | 对 |
|---|---|---|
| 全局换 python 版本 | `update-alternatives --set` | 改 shell alias / 用 venv |
| 卸载旧 Python | `dnf remove python36` | 共存,venv 隔离 |
| 装包命令 | `pip install` | `/usr/bin/python3.8 -m pip install` |
| pip 源 | 默认 pypi.org | `~/.pip/pip.conf` → Aliyun |
| fake-useragent | `pip install fake-useragent` | `pip install "fake-useragent<1.5"` |
| 系统 vs 项目 | `python3.8 -m pip install` 到系统 | venv 里 `pip install` |
| 编译扩展失败 | 重试 N 次 | `dnf install python38-devel gcc` |
| 启动时装依赖 | crontab 装包 | 部署阶段装,运行时只 verify |