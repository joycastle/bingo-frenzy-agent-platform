# bingo-frenzy-agent-platform

MausBot 的部署与接入仓库。MausBot 源码不放在本仓；安装时从上游拉取 `versions.env` 固定的提交，在目标机器上构建前端和服务端。

当前提供 macOS 原生部署：专用 Node/pnpm 运行环境、Caddy 入口、launchd 常驻服务、健康检查、隔离对话验证及停服备份；另提供按 Bot 分组的代码与 Bug 单阅读 Skill、GitHub 凭据入口、分支工作树管理和飞书项目只读 MCP。业务知识资料单独放在部署机器私有目录，飞书群聊入口与云文档工具尚未接入。

当前固定上游版本为 **0.1.161**；已执行的部署与升级检查见 [部署验证记录](docs/deployment-validation.md)。

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

## Agent 的统一环境文件

业务接入使用一个文件：`~/.local/share/bingo-frenzy-agent-platform/.env`（配置了 `STATE_DIR` 时为 `$STATE_DIR/.env`）。首次可从本仓 `.env.example` 复制，已有文件只补充字段，不覆盖原值；设置权限 `chmod 600`。它在启动 server 时加载并导出给子进程，edge、install、doctor 和备份命令不加载；缺失时沿用原有启动行为。修改后等正在运行的任务结束，再运行 `bash bin/mausctl start`。

文件采用可信 Bash 赋值格式，例如 `NAME='value'`，JSON 写在单行单引号内，不需要逐项写 `export`；不在这里运行命令。该文件是整台服务共享的凭据来源，各 Bot 的可见范围仍受引擎环境策略影响，不能把它当成按 Bot 隔离的密钥库。部署端口与路径仍在 `config.env`，模型 CLI 的现有凭据保持原方式。`.env` 不入 Git，`mausctl backup` 也不包含它，迁移机器时单独安全备份。

GitHub 接入使用 `bin/agent-github`：每次从统一文件读取，`GH_TOKEN` 非空时优先，否则使用 `GIT_TOKEN`，通过 GitHub CLI 的 credential helper 处理 Git HTTPS，不把 token 写进 remote URL、Git 配置或命令参数。不会继承个人 Git credential helper 兜底。`GIT_USERNAME` 兼容字段暂不参与 GitHub CLI 认证；`GIT_SSH_KEY_FILE` 和 `GIT_KNOWN_HOSTS_FILE` 目前未接入，保持空值。其它机器的 `.env` 不会自动同步。

## 按 Bot 维护 Skill

飞书项目 MCP 的个人只读授权、统一环境变量、单 Bot 绑定和换机命令见 [接入说明](docs/feishu-project-mcp.md)。另提供 `bash bin/feishu-project-cli` 试用官方 Meegle CLI，复用同一 Token；目前正式 Bot 仍使用 MCP。真实 Token 不入 Git。

```text
bots/
└── code-reader/
    ├── README.md
    ├── SOUL.md
    └── skills/
        └── bf-code-reader/
            └── SKILL.md
```

每个 Bot 一个目录；通用辅助工具仍放 `bin/`。修改 Skill 先改仓库源码，再安装到明确 Bot，不只在网页留下无法追溯的修改。参见 [代码阅读 Bot](bots/code-reader/README.md)。

公司架构、仓库地图、业务文档放在部署机 `$STATE_DIR/knowledge/code-reader/`，入口为 `ENTRY.md`；不提交公开仓库。资料从明确选择的 ai-workspace 文档生成私有快照，记录原路径、当前 Git HEAD、各文件 SHA-256，并注明包含本地未提交版本。新机器需另行传入已审核的私有资料，克隆此公开仓库不会自动获得公司文档或凭据。

## 按需准备分支工作树

在统一 `.env` 配置 `GIT_REPOSITORIES_JSON`，结构为 `{"别名":{"url":"https://github.com/组织/仓库.git","branch":"默认分支"}}`。它是工具的仓库登记清单，不改变 token 的 GitHub 权限，也不是原生终端的权限沙箱。

```bash
bash bin/code-worktree repos
bash bin/code-worktree open <别名> --branch <分支>
bash bin/code-worktree list
# 确认无人使用且分支无需保留后：
bash bin/code-worktree remove <别名> --branch <分支>

# 额外的 GitHub / Git 操作同样使用统一凭据入口：
bash bin/agent-github gh api user --jq .login
bash bin/agent-github git ls-remote https://github.com/<组织>/<仓库>.git
```

一个仓库、一个分支固定一个目录：`$STATE_DIR/sources/worktrees/<仓库名>@<分支名>/`，不为每次提交创建新目录。分支名 `/` 转为 `-`；转换后重名时加分支标识以区分。Git 对象缓存放在 `sources/mirrors/`，人工索引为 `sources/WORKTREES.md` 和 `sources/index.html`。

`open` 每次先核对远端，按需 fetch，然后对**已登记且属于对应 Git 镜像的分析工作树**执行 `reset --hard` 到远端提交和 `clean -fdx`，远端强推/重建后也直接对齐。分析目录的本地改动和临时文件会被丢弃，不放报告、个人文件、依赖或开发修改。网络/权限失败或分支不存在时不以旧缓存冒充最新；已有但未登记、指向其它仓库的目录不会被覆盖。

准备操作有进程锁；阅读中的同分支任务仍需 Bot 排队，新查询不能在其它任务读代码时更新同一目录。查询过程中固定路径和实际 SHA，证据记录该 SHA。不同分支可并行查阅。工具不自动删除其它分支；`remove` 只处理登记的工作树，并拒绝强制删除脏目录。代码阅读 Bot 严格只读，不承担开发或远端写入任务。

基础环境需要 Git、Python 3 和 GitHub CLI（`gh`）；`agent-github` 不会自动安装工具或自行测试 push/PR。Skill 的脚本引用默认部署路径 `~/Work/bingo-frenzy-agent-platform`；换目录部署时同步修改 Skill 再安装。

`backup` 会短暂停服，将 `OMB_DATA_DIR` 备份为权限 0600 的压缩文件，然后恢复服务。运行中的任务应先结束。备份可能含敏感配置，不提交 Git；模型 CLI 的外部凭据目录不包含在备份内，换机器需重新授权。恢复时先停服，把备份解压到新目录，设置新的 `OMB_DATA_DIR` 后启动，保留旧数据以便撤回。

## 版本与目录

- 平台代码：当前 Git 仓库。
- MausBot 源码及产物：`~/Work/mausbot-releases/<commit>/`。
- 专用运行环境、日志及 current 链接：`~/.local/share/bingo-frenzy-agent-platform/`。
- Agent 共享环境：`~/.local/share/bingo-frenzy-agent-platform/.env`（私有文件，不在本仓）。
- 私有项目知识：`~/.local/share/bingo-frenzy-agent-platform/knowledge/code-reader/`。
- 代码阅读缓存与人工索引：`~/.local/share/bingo-frenzy-agent-platform/sources/`。
- MausBot 对话与配置：`~/.openmausbot/`。
- 模型账号：各自 CLI 的独立目录，不在本仓。

更新先修改 `versions.env` 中的上游提交及版本，在新目录构建和验证，通过后再 start。原始版本目录保留。应用版本回退可把 current 链接切回已有且验证过的版本再 start；数据格式是否兼容要另行检查，升级前先 backup。

Linux 可使用上游根目录 Dockerfile 从源码构建及部署；本仓当前安装脚本仅支持 macOS，没有验证 Linux 服务安装。

## 验证

```bash
python3 -m unittest discover -s tests -v
bash -n bin/common.sh bin/install.sh bin/run-service.sh bin/mausctl bin/agent-github bin/code-worktree bin/feishu-project-mcp bin/feishu-project-cli
```

安装过程额外执行上游 `scripts/smoke-packaged-server.mjs` 及 `bin/verify.py`。后者使用上游隔离 fixture，验证 doctor、创建机器人、发送、等待和预期回复，记录在状态目录的 `logs/verification.json`；不触碰正式对话。真实模型认证与浏览器页面需在部署时单独验收。
