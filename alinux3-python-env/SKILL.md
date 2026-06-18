---
name: alinux3-python-env
description: |
  Alibaba Cloud Linux 3 (OpenAnolis) 环境的 Python 工具链速查。
  解决:系统默认 Python 3.6 太老,pip 报"not found",
  现代包(pydantic 2.x / SQLAlchemy 2.x / fake-useragent 1.5+)装不上或不兼容。
  触发:在 Alinux3 容器/机器上,任何 Python 项目启动前。
---

# Alinux3 Python 环境速查

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

## 何时用这个 skill

- 第一次进入 Alinux3 机器/容器
- `python --version` 显示 3.6.x
- `pip install` 报 "not found" 或慢死
- 想装现代包但装不上/装上跑不起来
- 想确认某个包是否兼容 Python 3.8
