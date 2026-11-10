# bingo-frenzy-agent-platform

MausBot 的部署与接入仓库。MausBot 源码不放在本仓；安装时从上游拉取 `versions.env` 固定的提交，在目标机器上构建前端和服务端。

当前提供 macOS 原生部署：专用 Node/pnpm 运行环境、Caddy 入口、launchd 常驻服务、健康检查、隔离对话验证及停服备份。业务 Skills、MCP、飞书入口暂未接入。

## 在另一台 Mac 部署

需要 Git、Python 3、curl、Command Line Tools，以及已登录的 macOS 用户桌面会话。支持 Apple Silicon 和 Intel；当前已验收机型在部署记录中列出。

```bash
mkdir -p ~/Work
cd ~/Work
git clone https://github.com/joycastle/bingo-frenzy-agent-platform.git
cd bingo-frenzy-agent-platform
cp config.env.example config.env
bash bin/mausctl install
bash bin/mausctl start
bash bin/mausctl doctor
bash bin/mausctl pair
```

首次安装会按官方校验和核验 Node 和 Caddy，使用锁文件安装依赖，从源码构建，运行上游打包服务冒烟和临时假引擎的完整会话验证。安装不会自动配置模型账号；在目标机连接自己的账号或通过加密通道另行配置。

默认只监听 `127.0.0.1:18799`。要在内网直接访问，在未入 Git 的 `config.env` 配置 `WEB_BIND=0.0.0.0` 和真实 `OMB_PUBLIC_URL`，例如 `http://<内网地址>:18799`，然后重新 start。访问需通过 MausBot 配对；HTTP 内网入口不用于公网暴露。公网访问应另配域名与 HTTPS。

也可保持默认监听，通过 SSH 转发：`ssh -N -L 18799:127.0.0.1:18799 <SSH别名>`，本地访问 `http://localhost:18799`。原始 API 8799 与 Webhook 8800 始终只绑定回环，由 Caddy 转发；不要直接公开这两个端口。

## 日常操作

```bash
bash bin/mausctl status
bash bin/mausctl logs
bash bin/mausctl stop
bash bin/mausctl start
bash bin/mausctl backup
```

`start` 重载本仓的两个 LaunchAgents，检查入口健康。它们随当前用户登录启动，退出登录后不会继续运行；不宣称开机未登录即可启动。无需保持 SSH 会话。

`backup` 会短暂停服，将 `OMB_DATA_DIR` 备份为权限 0600 的压缩文件，然后恢复服务。运行中的任务应先结束。备份可能含敏感配置，不提交 Git；模型 CLI 的外部凭据目录不包含在备份内，换机器需重新授权。恢复时先停服，把备份解压到新目录，设置新的 `OMB_DATA_DIR` 后启动，保留旧数据以便撤回。

## 版本与目录

- 平台代码：当前 Git 仓库。
- MausBot 源码及产物：`~/Work/mausbot-releases/<commit>/`。
- 专用运行环境、日志及 current 链接：`~/.local/share/bingo-frenzy-agent-platform/`。
- MausBot 对话与配置：`~/.openmausbot/`。
- 模型账号：各自 CLI 的独立目录，不在本仓。

更新先修改 `versions.env` 中的上游提交及版本，在新目录构建和验证，通过后再 start。原始版本目录保留。应用版本回退可把 current 链接切回已有且验证过的版本再 start；数据格式是否兼容要另行检查，升级前先 backup。

Linux 可使用上游根目录 Dockerfile 从源码构建及部署；本仓当前安装脚本仅支持 macOS，没有验证 Linux 服务安装。

## 验证

```bash
python3 -m unittest discover -s tests -v
bash -n bin/common.sh bin/install.sh bin/run-service.sh bin/mausctl
```

安装过程额外执行上游 `scripts/smoke-packaged-server.mjs` 及 `bin/verify.py`。后者使用上游隔离 fixture，验证 doctor、创建机器人、发送、等待和预期回复，记录在状态目录的 `logs/verification.json`；不触碰正式对话。真实模型认证与浏览器页面需在部署时单独验收。
