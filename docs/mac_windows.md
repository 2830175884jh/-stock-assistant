# MacBook Air 开发 + Windows NVIDIA 推理

Mac 运行 Python、行情抓取和报告生成；Windows 仅运行 Ollama。两机分别安装依赖，不复制 `.venv`，不提交 `.env`、Token 或私钥。以下是待你在两台机器执行的部署步骤，并非已连接成功。

## 1. Mac 安装项目

安装 Python 3.10+（建议 3.12，使用 python.org 的 macOS 安装包）和 Git；首次执行 git 若提示安装 Apple Command Line Tools，完成安装后重试。在“终端”执行：

```bash
git clone https://github.com/2830175884jh/-stock-assistant.git stock-assistant
cd stock-assistant
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -e .
cp .env.example .env
```

在编辑器打开 `.env`（也可 `open -e .env`），设置：

```ini
TUSHARE_TOKEN=填写你自己的Token
OLLAMA_BASE_URL=http://127.0.0.1:11435
OLLAMA_MODEL=qwen3:4b
OLLAMA_TIMEOUT=120
```

Mac 的 11435 专用于 SSH 隧道，避免误连 Mac 本机的 11434。环境变量优先于 `.env`；修改文件无效时检查 `env | grep OLLAMA`。默认仍支持原来的 localhost:11434 单机方式。Mac 无需安装 Ollama/CUDA。

## 2. Windows 准备 Ollama

安装 Windows 原生 Ollama。在托盘退出已有 Ollama，普通 PowerShell 中明确绑定回环地址后启动（此窗口保持开启）：

```powershell
$env:OLLAMA_HOST = '127.0.0.1:11434'
ollama serve
```

另开 PowerShell：

```powershell
ollama pull qwen3:4b
ollama list
Invoke-RestMethod http://127.0.0.1:11434/api/tags
Get-NetTCPConnection -State Listen -LocalPort 11434 | Select-Object LocalAddress,LocalPort
```

监听应为 `127.0.0.1`，不应为 `0.0.0.0`/`::` 或网卡 IP。若端口占用，先退出已有实例，不要再开第二个服务。如果希望继续使用托盘程序，在 Windows 用户环境变量设置 `OLLAMA_HOST=127.0.0.1:11434` 并重启托盘应用。

## 3. Windows 启用 SSH

管理员 PowerShell，仅在未安装时执行安装命令：

```powershell
Get-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
Get-NetFirewallRule -Name OpenSSH-Server-In-TCP
```

安装通常创建 SSH 防火墙规则。仅允许受信任的局域网/私有 VPN 来源访问 SSH 22；不要给 11434 创建入站放行规则，也不要在路由器映射 11434。两机不在同一网络时先建立私有 VPN，再使用 Windows 的 VPN 地址。此方案无需公网开放 Ollama。

建议专用非管理员 Windows 用户。Mac 生成密钥（已有密钥可复用，不覆盖）：

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_stock
cat ~/.ssh/id_ed25519_stock.pub
```

设置私钥口令。将上述**公钥**追加到 Windows 目标普通用户的 `%USERPROFILE%\.ssh\authorized_keys`，按微软公钥认证文档设置仅该用户/SYSTEM/Administrators 可访问的权限。管理员账户默认改用 `C:\ProgramData\ssh\administrators_authorized_keys`，其 ACL 不同，见文末官方文档。不要把私钥复制到 Windows。

在 Windows 获取 SSH 主机公钥指纹，用于 Mac 首次连接时核对：

```powershell
ssh-keygen -lf C:\ProgramData\ssh\ssh_host_ed25519_key.pub
whoami
ipconfig
```

## 4. Mac 建立隧道

把下面示例 IP、用户名换成实际 Windows 局域网/VPN 地址和账户名，添加到 Mac `~/.ssh/config`：

```sshconfig
Host stock-gpu
    HostName 192.168.1.100
    User your_windows_user
    IdentityFile ~/.ssh/id_ed25519_stock
    IdentitiesOnly yes
    LocalForward 127.0.0.1:11435 127.0.0.1:11434
    ExitOnForwardFailure yes
    ServerAliveInterval 30
    ServerAliveCountMax 3
```

```bash
chmod 700 ~/.ssh
chmod 600 ~/.ssh/config ~/.ssh/id_ed25519_stock
ssh -N stock-gpu
```

首次连接先核对主机指纹；不要关闭主机密钥校验。窗口保持开启，Ctrl+C 关闭。LocalForward 的第二个 127.0.0.1 指 Windows 回环地址。隧道只绑定 Mac 回环地址。`ExitOnForwardFailure` 可检测本地端口占用，但不能证明 Windows Ollama 正常，仍需下方自检。

## 5. 验证和日常运行

Mac 另开终端，进入仓库并激活虚拟环境：

```bash
source .venv/bin/activate
curl --fail --max-time 10 http://127.0.0.1:11435/api/tags
python -m stock_assistant --doctor
python -m pytest -q
python -m stock_assistant --steps '01,02,03'
# 已有行情缓存时可跳过抓取
python -m stock_assistant --steps '02,03'
open data/reports
```

`--doctor` 实际调用 tags 和 chat，检查精确模型名和非空正文；成功退出 0，失败退出 1。不需要 Tushare Token，不抓行情，不写报告，也不证明 GPU 在用。默认探测最多 5 秒，生成等待 OLLAMA_TIMEOUT 秒（默认 60；无效、非正数、非有限值回退 60）。冷启动超时可调高到 120/180。在模型响应期间于 Windows 执行 `ollama ps`，查看 PROCESSOR，判断 GPU/CPU 使用；`nvidia-smi` 可辅助观察。

隧道断开、连接超时、HTTP 错误、模型缺失或无效响应时，报告保留规则数据和降级原因。行情抓取失败仍是独立错误，不会伪造行情。自动测试通过 mock 覆盖上述失败场景和报告落盘，无需真实模型或 Token。CI 配置包含 macOS/Windows/Linux、Python 3.10/3.12；本地 Linux 测试通过不等于这六个远端任务已通过。

| 现象 | 检查 |
| --- | --- |
| SSH 超时/拒绝 | Windows 开机且未休眠、sshd、22 防火墙范围、IP/VPN |
| Permission denied | Windows 用户名、公钥文件位置和 ACL、Mac IdentityFile |
| Address already in use | `lsof -nP -iTCP:11435 -sTCP:LISTEN`；确认占用者，或同时修改 LocalForward 和 .env 端口 |
| channel open failed / curl 拒绝 | Windows 11434 回环服务是否启动 |
| 模型未安装 | 在 Windows `ollama list`，.env 填完整模型名，必要时 pull |
| tags 成功但 doctor 超时 | 模型冷启动、显存、OLLAMA_TIMEOUT；Windows 查看日志和 ollama ps |
| 代理干扰回环请求 | `export NO_PROXY=127.0.0.1,localhost` 后重试 |

Mac 睡眠、切换网络或 Windows 重启会断开隧道；恢复后重跑 `ssh -N stock-gpu` 和 doctor。Windows 需在接电时保持运行；不要把“已启动 SSH”视为模型已就绪。

官方参考：[Ollama 配置与 GPU 检查](https://docs.ollama.com/faq)、[Windows OpenSSH 安装](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse)、[Windows 公钥认证](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_keymanagement)。
