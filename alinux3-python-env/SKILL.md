---
name: alinux3-python-env
description: |
  Alibaba Cloud Linux 3 (OpenAnolis) 环境的 Python 工具链速查。
  解决:系统默认 Python 3.6 太老,pip 报"not found",
  现代包(pydantic 2.x / SQLAlchemy 2.x / fake-useragent 1.5+)装不上或不兼容。
  触发关键词(任一命中即用):
  - `Alinux3` / `OpenAnolis` / `Aliyun Linux 3` / `anolis:8`
  - `python3.6` / `Python 3.6.8` / `pip 9.0.3`
  - 错误信号:`pip: command not found`、`No module named 'pip'`、
    `TypeError: 'type' object is not subscriptable`(fake-useragent 1.5+)、
    `ModuleNotFoundError` 但 `pip list` 显示已装(装错了解释器)
  - dnf module 出现 `python38` / `python36` / `python27` 行
  不适用:Ubuntu/Debian/macOS/Windows;非 Python 工具链问题。
---

# Alinux3 Python 环境速查

## 目录

| § | 主题 | 一句话价值 |
|---|---|---|
| [环境特征](#环境特征) | 系统默认 Python / pip / dnf module 现状 | 1 分钟内判断"是不是该用本 skill" |
| [1. 升级到 Python 3.8](#1-升级到-python-38已验证可行) | `dnf module install python38:3.8/common` | 把解释器从 3.6 切到 3.8,核心动作 |
| [2. 配国内 pip 源](#2-配置国内-pip-源aliyun-镜像) | `~/.pip/pip.conf` 指向 Aliyun | `pip install` 从分钟级降到秒级 |
| [3. 升级 pip](#3-升级-pip避开-903-旧版的限制) | `python3.8 -m pip install -U pip` | 跳出 19.3.1 老版本限制 |
| [4. 已知兼容性问题](#4-已知兼容性问题python-38-特有) | fake-useragent / pydantic / SQLAlchemy | 装包前的版本锁定表 |
| [5. 路径速查](#5-路径速查) | 解释器 / 配置 / site-packages | "为什么我装到了 3.6" |
| [6. 常见踩坑](#6-常见踩坑) | 5+9 个症状速查表 | 出问题时第一查这里 |
| [§6.2 update-alternatives](#62-让-python3-默认指向-38update-alternatives) | 让 `python3` 默认走 3.8(慎用) | 改系统软链的完整步骤与回滚 |
| [§6.3 venv 隔离](#63-用-venv-隔离避免装到系统-site-packages) | 项目级 Python 隔离 | **推荐做法**,避免 PEP 668 |
| [7. 项目模板](#7-项目模板验证过) | 3.8 兼容的 `requirements.txt` | 直接复制就能用 |
| [8. 一键脚本](#8-一键脚本放到-setup-pythonsh) | `~/setup-python.sh` | 新机器一键就绪 |
| [9. 端到端示例](#9-端到端示例从干净容器到能跑现代包) | 真实会话轨迹 | 6 阶段完整跑通 |
| [何时用](#何时用这个-skill) | 触发条件 | 命中才用,避免误触发 |
| [10. 边界场景](#10-边界场景与替代方案) | pyenv / conda / 容器无 sudo / 3.6 共存 | 3.8 真的不够用时怎么办 |
| [11. 验证清单](#11-验证清单setup-完成后的必跑-gate) | 上线 / 提交前必跑 Gate | 任何红条就回头查 |
| [12. 可观测性](#12-可观测性--排障包出问题时第一时间抓的信息) | `diag-python.sh` + 观测项 | 出工单第一手素材 |
| [13. 反模式速查](#13-反模式速查常见自毁操作) | 10 条红线操作 | 详见 `references/anti-patterns.md` |
| [14. 参考资料](#14-参考资料) | 外部文档与 references/ 索引 | 深入查阅 |

> **5 秒决策树**:  `pip` 报错或卡死 → §2;  装包提示 PEP 585/604 → §4 + 锁版本;  `pip install` 找不到目标 → §6.1;  想换 3.10+ → §10.1;  出工单抓现场 → §12.1。

## 环境特征
- 系统: Alibaba Cloud Linux 3 (OpenAnolis Edition, 8.x 系列内核)
- 默认 Python: **3.6.8**(极老)
- 默认 pip: 9.0.3(报错时只显示 "No module",不显示原因)
- 包管理器: **dnf module**(不是 yum 直接装)

## 1. 升级到 Python 3.8(已验证可行)

```bash
# 查可用 Python 版本
dnf module list python*

# 输出关键行:
#   python38 3.8 [d]    ← 这是要装的目标
#   python27 2.7 [d][e]
#   python36 3.6 [d][e] ← 当前默认

# 一次性安装 3.8 + pip + setuptools + wheel
dnf module install -y python38:3.8/common

# 验证
/usr/bin/python3.8 --version
/usr/bin/python3.8 -m pip --version
# → Python 3.8.17
# → pip 19.3.1 (会随后升级)
```

**为什么 3.8 而不是 3.10/3.11?**
Alinux3 module 仓库只提供 `python27` / `python36` / `python38`,**没有更新的版本**。要 3.10+ 得换源或编译。

## 2. 配置国内 pip 源(Aliyun 镜像)

`pip install` 默认超时、无源时极慢。**必须先配源**:

```bash
mkdir -p ~/.pip
cat > ~/.pip/pip.conf << 'EOF'
[global]
index-url = https://mirrors.aliyun.com/pypi/simple/
trusted-host = mirrors.aliyun.com
timeout = 60
EOF
```

## 3. 升级 pip(避开 9.0.3 旧版的限制)

```bash
/usr/bin/python3.8 -m pip install --upgrade pip setuptools wheel
# pip 19.3.1 → 23+;后续安装会顺利得多
```

## 4. 已知兼容性问题(Python 3.8 特有)

| 包 | 问题 | 解决方案 |
|---|---|---|
| `fake-useragent>=1.5` | 用了 PEP 585 `list[Type]`,3.8 报 `TypeError: 'type' object is not subscriptable` | **锁定 `<1.5.0`**: `pip install "fake-useragent<1.5"` |
| pydantic 2.10+ | 需要 3.8+ | 3.8 兼容,直接装 |
| SQLAlchemy 2.0+ | 需要 3.7+ | 3.8 兼容 |
| `from __future__ import annotations` | 3.8 部分上下文报错 | 3.8 默认支持,真要的话放到文件最顶部第一行 |

**最关键的:`fake-useragent<1.5`**,这是新人最容易踩的坑。

## 5. 路径速查

| 用途 | 路径 |
|---|---|
| Python 3.8 解释器 | `/usr/bin/python3.8` |
| pip 配置 | `~/.pip/pip.conf` |
| site-packages | `/usr/local/lib/python3.8/site-packages/` |
| 默认 PATH 中的 `python3` | `/usr/bin/python3` → 还是 3.6 |

**注意**:系统默认 `python3` 仍指向 3.6,调用时**必须显式用 `/usr/bin/python3.8`**,否则装包会装到 3.6 错地方。

## 6. 常见踩坑

| 现象 | 原因 | 修法 |
|---|---|---|
| `pip: command not found` | pip 是 `python3.8 -m pip`,不是独立命令 | 用 `python3.8 -m pip ...` |
| `No module named 'X'` 但 pip 装了 | 装到了 3.6 而项目用 3.8 | 检查 `which python`,改用 `/usr/bin/python3.8` |
| `pip install` 卡死 | 没配源 | 先建 `~/.pip/pip.conf` |
| 安装 3.5+ 报 PEP 585 错 | 包用了新语法,3.8 不支持 | 装该包的旧版本 |
| 编译 C 扩展失败 | 缺 `python38-devel` | `dnf install python38-devel gcc` |

### 6.1 进阶故障排查(按症状查)

| 症状 | 排查命令 | 典型原因 / 修法 |
|---|---|---|
| `dnf module install` 报 "Conflicting requests" | `dnf module list --enabled python*` | 之前 enable 了别的版本(常见 `python36`)。先 `dnf module reset python* -y` 再装 |
| `No matches found for argument: python38` | `dnf repolist`;`ls /etc/yum.repos.d/` | 没启用 BaseOS/AppStream 源或源被禁用。检查 `/etc/yum.repos.d/AliBase.repo` 是否 `enabled=1` |
| `pip install` 报 `SSL: CERTIFICATE_VERIFY_FAILED` | `curl -vI https://mirrors.aliyun.com/pypi/simple/` | 镜像证书链问题或公司 MITM 代理。短期绕过:`pip install --trusted-host mirrors.aliyun.com ...`;根治:补 CA 证书到 `/etc/pki/ca-trust/source/anchors/` 并 `update-ca-trust` |
| `pip install` 报 `Read timed out` | `ping -c 3 mirrors.aliyun.com` | 限速或丢包。`pip.conf` 加 `timeout = 120` 或换源(`tencent`/`huaweicloud`/`tsinghua`) |
| 公司内网,出不去公网 | `curl -v https://pypi.org` | 用内部 Nexus/Artifactory:在 `pip.conf` 写 `index-url = http://nexus.internal/repository/pypi-proxy/` |
| 装了 3.8 后 `python3` 还是 3.6 | `ls -l /usr/bin/python3` | 见 §6.2 `update-alternatives` |
| `pip install` 报 `externally-managed-environment`(PEP 668) | dnf 安装的 python3.8 自带此约束 | 用 venv:见 §6.3;或临时绕过 `pip install --break-system-packages`(生产慎用) |
| `ImportError: libpython3.8.so.1.0: cannot open shared object file` | `ldconfig -p \| grep libpython3.8` | 多版本冲突。`dnf reinstall python38-libs -y` 或补 `export LD_LIBRARY_PATH=/usr/lib64` |
| 3.8 装某个包仍报 PEP 604 `X \| Y` 不支持 | — | 3.8 不支持 `X \| Y` 语法。装该包的旧版本,或用 `from __future__ import annotations` + `typing.Union` |

### 6.2 让 `python3` 默认指向 3.8(`update-alternatives`)

每次打 `/usr/bin/python3.8` 太烦,可让 `python3` / `pip3` 软链到 3.8(只影响当前用户 shell,不动 `/usr/bin/python3`):

```bash
# 备份原软链
sudo cp -a /usr/bin/python3 /usr/bin/python3.bak
sudo cp -a /usr/bin/pip3 /usr/bin/pip3.bak 2>/dev/null || true

# 切换
sudo rm -f /usr/bin/python3
sudo ln -s /usr/bin/python3.8 /usr/bin/python3
# pip3 需先创建:alternatives 由 /usr/bin/pip3 指向 python3.8 -m pip
sudo rm -f /usr/bin/pip3
sudo tee /usr/bin/pip3 > /dev/null << 'EOF'
#!/bin/bash
exec /usr/bin/python3.8 -m pip "$@"
EOF
sudo chmod +x /usr/bin/pip3

# 验证
python3 --version   # Python 3.8.17
pip3 --version      # pip 23.x from python3.8
```

**回滚**:`sudo ln -sf /usr/bin/python3.bak /usr/bin/python3`。**风险**:系统脚本假设 `python3 = 3.6`,改完后 `dnf` 自身依赖的 `/usr/bin/python3`(→ 3.6 软链)若被改,可能 break 包管理。**安全做法**:不动 `/usr/bin/python3`,只在自己 shell 里 `alias python3=/usr/bin/python3.8` 或写进 `~/.bashrc`。

### 6.3 用 venv 隔离(避免装到系统 site-packages)

```bash
/usr/bin/python3.8 -m venv ~/myproject-venv
source ~/myproject-venv/bin/activate
python --version   # 3.8.17
pip install pydantic sqlalchemy "fake-useragent<1.5"
deactivate         # 退出 venv
```

venv 的 pip 不会撞 dnf 装的位置,也不会触发 PEP 668,推荐做法。

## 7. 项目模板(验证过)

新建项目时,`requirements.txt` 写这些都兼容 3.8:

```
requests>=2.31.0
httpx>=0.27.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
SQLAlchemy>=2.0.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
loguru>=0.7.0
tenacity>=8.2.0
python-dotenv>=1.0.0
fake-useragent>=1.0.0,<1.5.0   # ← 关键限制
pytest>=7.4.0
pytest-asyncio>=0.21.0
```

## 8. 一键脚本(放到 ~/setup-python.sh)

```bash
#!/bin/bash
set -e

if ! command -v python3.8 &> /dev/null; then
    echo ">>> Installing Python 3.8 via dnf module..."
    dnf module install -y python38:3.8/common
fi

mkdir -p ~/.pip
cat > ~/.pip/pip.conf << 'EOF'
[global]
index-url = https://mirrors.aliyun.com/pypi/simple/
trusted-host = mirrors.aliyun.com
timeout = 60
EOF

echo ">>> Upgrading pip..."
/usr/bin/python3.8 -m pip install --upgrade pip setuptools wheel -q

PY=/usr/bin/python3.8
echo ">>> Python: $($PY --version)"
echo ">>> pip: $($PY -m pip --version)"
echo ">>> Ready. Use: $PY your_script.py"
```

## 9. 端到端示例(从干净容器到能跑现代包)

下面是一次真实会话的轨迹,演示按本 skill 操作的标准路径:

```bash
# === 阶段 1: 进入新容器,确认环境 ===
$ cat /etc/os-release | grep PRETTY
PRETTY_NAME="Alibaba Cloud Linux 3 (OpenAnolis Edition)"

$ python3 --version
Python 3.6.8                          # ← 太老
$ pip --version
bash: pip: command not found          # ← 触发信号

# === 阶段 2: 安装 Python 3.8 ===
$ dnf module list python* | grep -E 'python(27|36|38)\s'
python38 3.8 [d]
python27 2.7 [d][e]
python36 3.6 [d][e]                  # ← 当前默认

$ sudo dnf module install -y python38:3.8/common
... 30 秒后完成

$ /usr/bin/python3.8 --version
Python 3.8.17

# === 阶段 3: 配源 + 升 pip ===
$ bash ~/setup-python.sh            # ← 跑第 8 节的一键脚本
>>> Python: Python 3.8.17
>>> pip: pip 23.3.1 from .../python3.8/site-packages/pip (python 3.8)
>>> Ready. Use: /usr/bin/python3.8 your_script.py

# === 阶段 4: 装现代包,踩 fake-useragent 坑 ===
$ /usr/bin/python3.8 -m pip install pydantic sqlalchemy fake-useragent
...
$ /usr/bin/python3.8 -c "import fake_useragent; print(fake_useragent.UserAgent().random)"
TypeError: 'type' object is not subscriptable   # ← PEP 585 不兼容 3.8

# === 阶段 5: 锁定版本,验证通过 ===
$ /usr/bin/python3.8 -m pip install "fake-useragent<1.5"
Successfully installed fake-useragent-1.4.0

$ /usr/bin/python3.8 -c "import fake_useragent, pydantic, sqlalchemy; print('ok')"
ok                                       # ← 项目可启动

# === 阶段 6: 跑项目 ===
$ /usr/bin/python3.8 main.py
[2026-06-19 10:23:01] Server started on :8080
```

**关键经验**:整个流程不到 5 分钟,但跳过的任意一步(没装 3.8 / 没配源 / 没锁 fake-useragent 版本)都会导致后续调试数小时。

## 何时用这个 skill

- 第一次进入 Alinux3 机器/容器
- `python --version` 显示 3.6.x
- `pip install` 报 "not found" 或慢死
- 想装现代包但装不上/装上跑不起来
- 想确认某个包是否兼容 Python 3.8

## 10. 边界场景与替代方案

### 10.1 真的需要 Python 3.10 / 3.11(3.8 不够用)

如果项目强依赖 3.9+ 特性(structural pattern matching、`X | Y` 类型、`asyncio` 新 API、`tomllib` 等),3.8 走不通。三条路:

1. **pyenv**(推荐,无 root 编译安装):
   ```bash
   curl https://pyenv.run | bash
   export PATH="$HOME/.pyenv/bin:$PATH"
   eval "$(pyenv init -)"
   # 装编译依赖
   sudo dnf install -y gcc make zlib-devel bzip2 bzip2-devel readline-devel \
       sqlite sqlite-devel openssl-devel xz xz-devel libffi-devel findutils
   # 装 3.11
   pyenv install 3.11.9
   pyenv global 3.11.9
   python --version   # 3.11.9
   ```
   编译耗时 3–8 分钟,但不动系统。

2. **conda / mamba**:如果项目本来就用科学栈(尤其涉及 numpy/scipy C 扩展):
   ```bash
   curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
   bash Miniconda3-latest-Linux-x86_64.sh -b -p ~/miniconda3
   ~/miniconda3/bin/conda create -n myenv python=3.11 -y
   ~/miniconda3/bin/conda activate myenv
   ```
   缺点:conda 自带 Python,和系统 `python3` 隔离,新同学容易混淆。

3. **换基础镜像**(最后手段,需重新部署):
   - `python:3.11-slim` — 官方 Debian 镜像,包全、版本新
   - `rockylinux:9` — RHEL 系,`dnf` 体验接近 Alinux3,且有 python3.9 / python3.11 module
   - `anolisos/anolisos:8` 如果 Aliyun 上有,跟当前环境差异最小

### 10.2 容器内(无 dnf / 无 sudo)

```bash
# 检查你到底有没有权限装系统包
sudo -n true 2>/dev/null && echo "have sudo" || echo "no sudo"
# 如果是用户态容器(比如 K8s / 弹性容器实例),只能用:
#   1. pyenv(见 10.1)
#   2. 官方 python 镜像
#   3. conda/miniconda
```

### 10.3 系统 Python 3.6 已用着,项目硬要 3.8 怎么办(共存)

- `python3` 留 3.6 给系统/yum 用,**不要**用 `update-alternatives --set python3 /usr/bin/python3.8` 全局换(会断 `dnf`)。
- 项目里写 `#!` shebang 用 `#!/usr/bin/python3.8`。
- 入口脚本加 wrapper:
  ```bash
  #!/bin/bash
  exec /usr/bin/python3.8 "$@"
  ```
  放到 `~/bin/py`,加 `PATH=$HOME/bin:$PATH`,这样 `py my_script.py` 永远走 3.8。
- venv 是最干净方案(§6.3),激活后 `python` 直接是 3.8,系统 Python 毫发无损。

### 10.4 国内源对照(按公司网络选)

| 源 | URL | 特点 |
|---|---|---|
| Aliyun | `https://mirrors.aliyun.com/pypi/simple/` | 默认推荐,Alinux3 同生态,最快 |
| Tencent | `https://mirrors.tencent.com/pypi/simple/` | 备选 |
| Huawei | `https://repo.huaweicloud.com/repository/pypi/simple/` | 企业网友好 |
| Tsinghua | `https://pypi.tuna.tsinghua.edu.cn/simple/` | 学术网首选 |
| 豆瓣 | `https://pypi.douban.com/simple/` | 经常 502,不推荐生产 |

切换时改 `~/.pip/pip.conf` 的 `index-url` 即可,无需 `pip config` 命令。

## 11. 验证清单(Setup 完成后的必跑 Gate)

跑完 §1–§8 后,**项目上线 / 交付前**逐条过一遍。任何一条红就回头查对应章节,别带着问题上线。

### 11.1 环境就绪 Gate(每个新机器 / 新容器都跑)

```bash
# 把以下命令粘到 bash,所有行应返回 OK / 数值,任何 FAIL/空值都停下排查
check() { local name="$1"; local cmd="$2"; local expect="$3"
  local out; out="$(eval "$cmd" 2>&1)"
  if echo "$out" | grep -qE "$expect"; then echo "OK   $name: $out"
  else echo "FAIL $name: $out (期望匹配: $expect)"; FAILED=1; fi
}
FAILED=0

check "OS"              "cat /etc/os-release | grep PRETTY"            'Alibaba Cloud Linux 3'
check "python3.8"       "/usr/bin/python3.8 --version"                 '3\.8\.'
check "pip"             "/usr/bin/python3.8 -m pip --version"         'pip [2-9][0-9]\.'
check "pip 源"          "grep -m1 index-url ~/.pip/pip.conf 2>/dev/null || echo MISSING" 'mirrors\.aliyun\.com|pypi\.tuna|huaweicloud|tencent|douban'
check "pip timeout"     "grep -m1 timeout ~/.pip/pip.conf 2>/dev/null" '[1-9][0-9]'
check "PEP 668 标记"    "ls /usr/lib/python3.8/EXTERNALLY-MANAGED 2>/dev/null && echo MARKED || echo NOT_MARKED" 'MARKED|NOT_MARKED'
check "gcc"             "gcc --version 2>/dev/null | head -1"          'gcc '
check "python38-devel"  "rpm -q python38-devel"                       'python38-devel-[0-9]'
check "openssl-devel"   "rpm -q openssl-devel"                        'openssl-devel-[0-9]'
check "libffi-devel"    "rpm -q libffi-devel"                         'libffi-devel-[0-9]'
check "PATH 没污染"     "which python3"                               '/usr/bin/python3'
check "fake-useragent"  "/usr/bin/python3.8 -c 'import fake_useragent; print(fake_useragent.__version__)'" '1\.[0-4]\.'

echo "---"
[ "$FAILED" = "0" ] && echo "ALL CHECKS PASSED" || { echo "SOME CHECKS FAILED - see above"; exit 1; }
```

期望输出尾部 `ALL CHECKS PASSED`。任何 `FAIL` 行就是阻塞项,定位回对应章节(PEP 668 → §6.3;pip 源 MISSING → §2;fake-useragent 1.5+ → §4)。

### 11.2 项目依赖 Gate(每个项目 `requirements.txt` 提交前)

```bash
# 1. 在干净 venv 里复现依赖
/usr/bin/python3.8 -m venv /tmp/proj-validate-$$
source /tmp/proj-validate-$$/bin/activate
pip install -r requirements.txt
# 退出 /tmp 目录临时 venv 之后删,避免污染本机
deactivate
rm -rf /tmp/proj-validate-$$

# 2. 检查关键兼容项
python -c "import sys; assert sys.version_info[:2] == (3, 8), sys.version_info"
python -c "import fake_useragent; assert tuple(map(int, fake_useragent.__version__.split('.')[:2])) < (1, 5)"

# 3. 锁定包后再导出
pip freeze --exclude pip,setuptools,wheel > requirements.lock
```

如果第 1 步在任何一行 fail,**不要**直接换镜像/重试,先看 §6.1 的错误信号行(PEP 585 / PEP 604 / libpython / Read timed out)。

### 11.3 上线前 5 分钟冒烟

```bash
# 把这 5 行放进 CI / 部署脚本的最后一步
test -x /usr/bin/python3.8                                    || exit 1
/usr/bin/python3.8 -m pip check                               || exit 1   # 依赖冲突检查
/usr/bin/python3.8 -c "import <entry_module>"                 || exit 1   # 项目能 import
/usr/bin/python3.8 -m py_compile $(find src -name '*.py')     || exit 1   # 语法检查
curl -fsS http://127.0.0.1:8080/healthz                       || exit 1   # 服务可启动(按项目改端口)
```

`pip check` 是常被忽略的杀手锏 —— 它会把所有包之间的版本冲突一次性列出来,比运行时 `ImportError` 早很多。

## 12. 可观测性 / 排障包(出问题时第一时间抓的信息)

Alinux3 上报障时常因"本地能跑 / 线上挂"扯皮。下面这套**抓取脚本**在任何 issue 复现时第一时间跑,把输出贴进工单,够覆盖 80% 现场。

### 12.1 一键抓现场脚本(`~/diag-python.sh`)

```bash
#!/bin/bash
# 用法:bash ~/diag-python.sh > /tmp/diag-$(hostname)-$(date +%Y%m%d-%H%M%S).txt
echo "===== OS ====="
cat /etc/os-release
echo
echo "===== Python interpreters ====="
for p in /usr/bin/python3 /usr/bin/python3.6 /usr/bin/python3.8 /usr/bin/python3.10 /usr/bin/python3.11; do
  [ -x "$p" ] && echo "$p -> $($p --version 2>&1)"
done
echo "PATH=$PATH"
echo "which python3=$(which python3 2>&1)"
echo "which pip=$(which pip 2>&1)"
echo
echo "===== pip config ====="
/usr/bin/python3.8 -m pip config list 2>&1 || true
echo "--- ~/.pip/pip.conf ---"
cat ~/.pip/pip.conf 2>&1 || echo "(none)"
echo
echo "===== pip freeze (system 3.8) ====="
/usr/bin/python3.8 -m pip list 2>&1 || true
echo
echo "===== dnf module status ====="
dnf module list --enabled python* 2>&1 || true
echo
echo "===== gcc / headers ====="
gcc --version 2>&1 | head -1
rpm -q python38-devel python38-libs openssl-devel libffi-devel 2>&1
echo
echo "===== Network / mirror reachability ====="
for url in https://mirrors.aliyun.com/pypi/simple/ \
           https://pypi.org/simple/ \
           https://pypi.tuna.tsinghua.edu.cn/simple/; do
  printf "%-55s " "$url"
  curl -sS -o /dev/null -w "HTTP=%{http_code} TIME=%{time_total}s\n" \
       --max-time 5 "$url" 2>&1 || echo "FAIL"
done
echo
echo "===== Active venvs ====="
ls -la ~/ 2>/dev/null | grep -i venv || echo "(none)"
echo
echo "===== Recent pip errors ====="
tail -100 ~/.pip/pip.log 2>/dev/null || echo "(no pip.log)"
echo
echo "===== Process env (filtered) ====="
env | grep -iE '^(PATH|PYTHON|HTTP_PROXY|HTTPS_PROXY|NO_PROXY|LD_LIBRARY)' | sort
```

### 12.2 关键观测项(读这份输出的人该看哪几行)

| 关注点 | 在 diag 输出里的位置 | 红线 |
|---|---|---|
| 解释器错位 | `Python interpreters` | `python3` 不是 3.8,且代码里 `#!/usr/bin/env python3` |
| pip 源 | `pip config` / `~/.pip/pip.conf` | 没配源 / 配到 `pypi.org` / 配到 `douban` |
| 解释器缺包 | `pip freeze` 缺关键依赖 | 列出的版本是 3.6 路径(`/usr/lib/python3.6/site-packages`) |
| dnf 模块冲突 | `dnf module status` | 同时 enable 多个 python stream |
| 编译链缺 | `gcc / headers` | `python38-devel` not installed |
| 网络隔离 | `mirror reachability` | 全 FAIL = 在公司内网,需配 Nexus |
| 代理未透传 | `env` | 有 `HTTP_PROXY` 但 pip 没走(检查 `HTTPS_PROXY`) |
| 库冲突 | 运行时 `ldd` 输出 | `libpython3.8.so.1.0 => not found`,需 `dnf reinstall python38-libs` |

### 12.3 实时观测小技巧

- **离线调试**:把 `pip install` 加 `-v` 看实际走的 URL 和 SSLSocket 握手,定位是网络、证书还是版本问题:
  ```bash
  /usr/bin/python3.8 -m pip install -v pydantic 2>&1 | grep -E '(GET|SSLError|Read timed|Could not)'
  ```
- **隔离重试**:装包时如果怀疑是缓存问题,加 `--no-cache-dir`,会重新下载而不复用 `~/.cache/pip`:
  ```bash
  /usr/bin/python3.8 -m pip install --no-cache-dir pydantic
  ```
- **镜像健康度持续监控**(运维用,塞 crontab):
  ```bash
  */30 * * * * curl -fsS --max-time 5 https://mirrors.aliyun.com/pypi/simple/pydantic/ \
                 -o /dev/null || echo "aliyun pypi mirror down at $(date)" | mail -s "pypi-mirror-down" ops@company.com
  ```
- **包冲突快速定位**:`pip check` 输出形如 `pydantic 2.5.0 requires typing-extensions>=4.6.0, but you have typing-extensions 4.5.0`,按提示升 / 降单个包,别全量升级(AP-9)。

## 13. 反模式速查(常见自毁操作)

下面每一条都是真实坑过 `dnf` / 浪费时间 ≥ 2 小时的操作,执行前先看。详见 `references/anti-patterns.md`。

| 红线操作 | 为什么不行 | 改用 |
|---|---|---|
| `update-alternatives --set python3 /usr/bin/python3.8` | `dnf` 自身依赖 `python3 == 3.6`,全局换直接断包管理 | 改 `~/.bashrc` 加 `alias python3=/usr/bin/python3.8`;或用 venv(§6.3) |
| `dnf remove python36 -y` | dnf/yum/rpm 自己靠 3.6,移除后包管理器直接挂 | 3.6/3.8 共存,venv 隔离 |
| `pip install <pkg>`(不带 `python3.8 -m`) | 装到 3.6 的 site-packages,3.8 仍找不到 | `/usr/bin/python3.8 -m pip ...` 或 venv 里的 `pip` |
| 跳过配源直接 `pip install` | 默认 pypi.org,慢 + 可能超时 + 内网断 | 先建 `~/.pip/pip.conf`(§2) |
| `pip install fake-useragent`(不锁) | 1.5+ 用 PEP 585 语法,3.8 报 `'type' object is not subscriptable` | `pip install "fake-useragent<1.5"` |
| 系统 Python 上 `pip install`(不走 venv) | 污染系统 site-packages;dnf 装的 3.8 还会触发 PEP 668 | 每个项目一个 venv(§6.3) |
| `pip freeze`(用系统 Python) | 输出里夹带 pip/setuptools/wheel,给别人用报错 | venv 里 `pip freeze --exclude pip,setuptools,wheel` |
| 假设 `python`(无 3)存在 | Alinux3 没建 `/usr/bin/python` 符号 | 脚本里用 `python3` 或 `/usr/bin/python3.8` |
| 装 C 扩展失败就重试 | 缺 `python38-devel` / `gcc` / `openssl-devel` | `dnf install -y gcc python38-devel openssl-devel libffi-devel` |
| crontab / systemd 启动里 `pip install` | 网络/版本/IO 不可控 | 部署阶段装好,运行时只 `pip check` |

完整 12 条反模式 + 场景描述见 `references/anti-patterns.md`。

## 14. 参考资料

- `references/anti-patterns.md` — 12 条反模式详细描述(AP-1 ~ AP-12),含完整背景与正确做法
- `references/dnf-module-cheatsheet.md` — dnf module 概念、命令、reset/enable/install 流程图,排查 "Conflicting requests" / "No matches found" / 网络问题
- RHEL 8 Modules:https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/8/html/installing_managing_and_removing_user_space_components/
- Alinux3 用户文档:https://help.aliyun.com/document_detail/413369.html

## 15. 修订记录 / 验证状态

> 本节让后来人能判断"这份文档的信息是不是仍然可信"。

| Round | 主题 | 主要变更 |
|---|---|---|
| R1 | 触发条件 + 端到端示例 | 收紧 frontmatter 关键词,补 §9 真实容器轨迹 |
| R2 | 故障排查 + 边界 case | 新增 §6.1 症状表 + §6.2 alternatives + §6.3 venv |
| R3 | 边界场景 + 替代方案 + 反模式 | 新增 §10.1–10.4 + §13 红线表 + `references/anti-patterns.md`(12 条) |
| R4 | 验证清单 + 可观测性 | 新增 §11 上线 Gate + §12 diag 抓现场脚本 + `references/dnf-module-cheatsheet.md` |
| R5 | 导航 + 修订说明(本轮) | 新增目录 TOC + 5 秒决策树 + 本修订记录 |

### 已知时效性风险(未来可能失效的点)

- **`dnf module list python*` 的输出**:Aliyun 仓库可能新增 `python39` / `python311` module,届时 3.8 不再是唯一选择;先 `dnf module list python*` 看一眼当前有什么。
- **fake-useragent 版本上限**:项目方未来可能放弃 3.8 兼容(<1.5 锁定会失效),届时要么升 Python 到 3.9+,要么 fork。检查:`pip index versions fake-useragent`(或 `pip install fake-useragent==`)。
- **PEP 668 行为**:dnf 装的 python3.8 标记了 `EXTERNALLY-MANAGED`,若未来 RHEL/Alinux 取消该标记,§6.3 的 venv 强制建议可放松,但 venv 仍是工程最佳实践。
- **Aliyun 镜像 URL**:`mirrors.aliyun.com/pypi/simple/` 长期稳定;若迁到 `mirrors.aliyuncs.com` 或加 CDN 路径,§2 的 `pip.conf` 模板需同步更新。
- **`update-alternatives` 风险**:`/usr/bin/python3` 仍指向 3.6 是 Alinux3 当前实现;若未来 dnf 切到 3.8+,§6.2 的警告过时,删掉即可。

### 验证方式(如何 reproduce §9 的"端到端示例")

```bash
# 在任意 Alinux3 机器 / 容器 / K8s pod 内:
bash ~/setup-python.sh              # §8 一键脚本,2 分钟内就绪
/usr/bin/python3.8 -m pip install pydantic sqlalchemy "fake-useragent<1.5"
/usr/bin/python3.8 -c "import pydantic, sqlalchemy, fake_useragent; print(pydantic.VERSION, sqlalchemy.__version__, fake_useragent.__version__)"
# 期望输出形如:2.5.0 2.0.0 1.4.0

bash ~/diag-python.sh > /tmp/diag-$(hostname).txt   # §12.1 抓现场
bash -c "$(curl -fsSL https://raw.githubusercontent.com/.../setup-python.sh)"  # 不推荐,只在自己信任的源
```

如果验证过程中有任何步骤失败,**优先更新本 skill**(§11 Gate 直接返回非 0 时尤其说明现实已变),不要默默把失败步骤从文档删掉。
