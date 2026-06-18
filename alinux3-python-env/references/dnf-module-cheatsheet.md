# dnf module 速查(Alinux3 Python 场景)

`dnf module` 是 RHEL/Alinux3 上管理多版本语言运行时(如 Python、Node.js、Ruby)的方式。它和普通包不同:**一个模块名只能有一个版本处于 enabled 状态**。这就是为什么"装 3.8"要这么讲究。

## 基本概念

- **Module(M)**:一组相关包,带版本标签(如 `python38`)
- **Stream**:模块内的版本流(`3.8`、`3.11`),只能 enable 一个
- **Profile(P)**:预定义的安装组合(`common`、`devel`、`minimal`)
- **Enabled [e]**:已 enable,可以用 `dnf install @python38` 装
- **Default [d]**:安装新模块时默认激活的 stream

## 常用命令

### 查所有 Python 模块

```bash
dnf module list python*
# 典型输出:
# Name       Stream    Profiles    Summary
# python27   2.7 [d][e] common     Python 2.7 ...
# python36   3.6 [d][e] common     Python 3.6 ...
# python38   3.8 [d]    common     Python 3.8 ...
```

### 装 3.8(标准做法)

```bash
sudo dnf module install -y python38:3.8/common
# 含义:装 python38 模块的 3.8 stream 的 common profile
# 等价于:enable + install
```

### 只 enable 不装

```bash
sudo dnf module enable -y python38:3.8
# 此时 dnf install python38 就能装(但不强制带 pip/wheel)
```

### 列出已 enable 的模块

```bash
dnf module list --enabled
# 或
dnf module list --enabled python*
```

### 切换 stream(必看)

```bash
# 先 reset 全部 Python 模块,清除已 enable 状态
sudo dnf module reset -y python*

# 再 enable 目标版本
sudo dnf module enable -y python38:3.8

# 最后装
sudo dnf module install -y python38:3.8/common
```

**典型场景**:先 enable 了 `python36`(默认),想换成 `python38`:
```bash
$ sudo dnf module install python38:3.8/common
Last metadata expiration check: ...
Error: It is not possible to switch enabled streams of the "python" module...
# 提示你必须先 reset
```

正确做法:
```bash
sudo dnf module reset -y python
sudo dnf module enable -y python38:3.8
sudo dnf module install -y python38:3.8/common
```

### 移除模块(谨慎)

```bash
sudo dnf module remove -y python38:3.8
# 这会卸载 python38 stream 装的所有包,但 dnf 的 python36 默认依赖不受影响
```

## Python 模块装了之后有什么?

`python38:3.8/common` 一次性装这些包:

| 包 | 作用 |
|---|---|
| `python38` | 解释器本体 |
| `python38-pip` | pip(版本旧,如 19.3.1) |
| `python38-setuptools` | setuptools |
| `python38-wheel` | wheel |
| `python38-libs` | libpython3.8.so 等共享库 |
| `python38-devel` | `Python.h`(编译 C 扩展用,见 AP-11) |

后续用 `pip install --upgrade pip` 把 pip 升到 23+。

## 排查命令

### 找不到模块

```bash
# 看 repo 是否启用
dnf repolist | grep -i base
ls /etc/yum.repos.d/

# 检查 BaseOS / AppStream 是否 enabled=1
grep -E '^\s*enabled' /etc/yum.repos.d/AliBase*.repo
```

### 报 "Conflicting requests"

```bash
# 看当前 enabled 状态
dnf module list --enabled

# 通常是 python36 已 enable,先 reset
sudo dnf module reset -y python
```

### 报 "Cannot find a valid baseurl for repo"

```bash
# 源连不上,看 /etc/resolv.conf
cat /etc/resolv.conf
curl -vI https://mirrors.aliyun.com/centos/8/...

# 公司内网可能要走代理
export http_proxy=http://proxy.internal:8080
export https_proxy=http://proxy.internal:8080
sudo -E dnf module install -y python38:3.8/common
```

### 缓存清理

```bash
sudo dnf clean all
sudo dnf makecache
```

## 完整安装-排查流程图

```
你想装 Python 3.8
    │
    ├── dnf module list python* 有 python38 行?
    │       │
    │       ├── 否 → 检查 /etc/yum.repos.d/ 是否 enabled=1,网络通吗?
    │       │
    │       └── 是 ↓
    │
    ├── dnf module install python38:3.8/common
    │       │
    │       ├── 成功 → /usr/bin/python3.8 --version 验证
    │       │
    │       └── 失败:
    │             ├── "Conflicting requests" → module reset → 再装
    │             ├── "No matches found" → repo 问题,看上面排查
    │             └── 网络错 → 配 proxy / 换源
    │
    └── 装好之后:
            ├── 配 pip 源(§2)
            ├── 升级 pip(§3)
            └── venv 隔离(§6.3)
```

## 参考

- RHEL 8 Modules 文档:https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/8/html/installing_managing_and_removing_user-space_components/assembly_managing-software-packages-with-dnf-module-command_installing-managing-and-removing-user-space-components
- Alinux3 dnf 文档:https://help.aliyun.com/document_detail/413369.html