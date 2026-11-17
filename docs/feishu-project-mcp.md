# 飞书项目只读 MCP

使用飞书项目页面给出的官方 `@lark-project/mcp` Stdio 配置。包版本固定在 `versions.env`，不使用个人浏览器 Cookie、不需要自建项目插件。当前个人账号的访问范围由飞书项目账号权限及 MCP 页面偏好共同决定。

## 凭据与运行

1. 用授权账号打开 <https://project.feishu.cn/b/mcp>，开启 MCP Server，只勾选“允许查看数据信息”，保持“允许创建或修改数据信息”关闭。
2. 在 Stdio 代码框点击复制，从 JSON 的 `env.MCP_USER_TOKEN` 获取真实值。页面显示的星号不是 Token。
3. 在部署机 `$STATE_DIR/.env` 中补充 `FEISHU_PROJECT_MCP_USER_TOKEN='实际值'`，文件权限 0600。不放整段 JSON，不提交真实值。
4. `bin/feishu-project-mcp` 每次启动读取统一文件，将该字段映射到官方 `MCP_USER_TOKEN`，运行固定版本的 `npx -y @lark-project/mcp@<版本> --domain https://project.feishu.cn`。首次运行需 npm 网络；不加 `--debug`。Token 轮换后重启这个 MCP 连接，已有进程不会自动读取新值。

该统一文件是共享凭据来源，单 Bot MCP 绑定控制工具挂载，不是操作系统级秘密隔离。项目 MCP 不等于飞书云文档读写能力。

## Meegle CLI 试用入口

除正式 Bot 使用的 MCP 外，提供 `bin/feishu-project-cli`，版本由 `versions.env` 的 `FEISHU_PROJECT_CLI_VERSION` 固定。启动器复用统一 `.env` 的 `FEISHU_PROJECT_MCP_USER_TOKEN`，映射到 `MEEGLE_USER_ACCESS_TOKEN`，指定 `MEEGLE_HOST=project.feishu.cn` 和 `MEEGLE_ACCESS_TOKEN_HEADER=X-Mcp-Token`。不需要新增密钥或 OAuth 登录，也不把真实 Token 写入参数或 CLI 配置文件。

```bash
# 在平台仓库目录执行；首次运行由 npx 下载固定版本，需要 npm 网络。
bash bin/feishu-project-cli --version
bash bin/feishu-project-cli auth status --format json
bash bin/feishu-project-cli workitem get \
  --project-key <空间key或简称> --work-item-id <工作项ID> \
  --fields _all --auto-paginate --envelope
bash bin/feishu-project-cli comment list \
  --project-key <空间key> --work-item-id <工作项ID> \
  --auto-paginate --envelope
```

该入口固定关闭 CLI 的失败诊断上报与自动升级提示；手动更新版本后重新验收。传入环境 Token 的模式不会自动刷新凭据，失效时更新统一 `.env`。2026-11-17 在部署机实测 1.0.28：认证、工作项全部字段和评论读取通过；`attachment +download` 仍被相同的 `MCPPersonalPreferenceDisabled` 拒绝，没有生成附件文件。此试用入口没有替换正式 Bot 的 MCP 或修改 Skill；不代表已经完成 Bot 调用 CLI 的端到端接入。官方参考：[认证和配置](https://github.com/larksuite/meegle-cli#authentication)、[附件下载](https://github.com/larksuite/meegle-cli#attachments)。

## 换机器接入

先按仓库 README 部署 MausBot、创建目标 Bot，再单独安全迁移统一环境文件，或在新机器重新填写 Token。新 Bot ID 和路径以新机器为准。以下命令在本仓目录运行；默认数据目录 `~/.openmausbot`、服务端口 8799，改过时传 `--data-dir` / `--port`。

```bash
# 先确认没有运行中的任务。停服后脚本备份私有 config.json，
# 只新增 feishu-project 配置，用 bot 字段绑定目标 Bot；保留其它配置。
bash bin/mausctl stop
python3 bin/configure-feishu-project.py --bot <目标Bot-ID> --wait-stop 20
bash bin/mausctl start

# 获取官方工具并确认返回 JSON 的 ok 为 true；不能仅看 HTTP 200。
curl -fsS -X POST http://127.0.0.1:8799/api/mcp/servers/feishu-project/test

# 上一步成功后再启用。
curl -fsS -X PATCH http://127.0.0.1:8799/api/mcp/servers/feishu-project \
  -H 'Content-Type: application/json' -d '{"enabled":true}'

# 安装本 Bot 的代码阅读与 Bug 单阅读 Skill。
python3 bin/install-bot-skills.py --url http://127.0.0.1:8799 \
  --bot <目标Bot-ID> --directory bots/code-reader/skills --replace
```

`configure-feishu-project.py` 拒绝服务端口仍在监听、目标 Bot 不存在或同名连接配置不同的情况。相同配置重复执行保持原启用状态。生成模板见 `bots/code-reader/mcp/feishu-project.json`；脚本自动代入当前仓库绝对路径及目标 Bot ID，真实 Token 不写进 MausBot 配置。

在目标 Bot 设置中保存 `bots/code-reader/SOUL.md`。通过以下只读 API 核对：目标 Bot 能看到该连接，其它 Bot 不应看到它。

```bash
curl -fsS http://127.0.0.1:8799/api/bots/<目标Bot-ID>/mcp-servers
```

用一个有权限的 Bug 链接验收详情全字段分页、评论、关联需求和附件元信息。当前官方只读偏好下，`get_download_url` 也返回 `MCPPersonalPreferenceDisabled`，因此附件内容下载尚不可用；Bot 必须报告缺口，不可宣称已经读取日志或视频。写工具在列表中出现不表示可以写入。用户明确授权的一次真实评论测试已被相同错误拒绝，随后回读确认没有生成测试评论；不要为了日常健康检查向真实工作项写测试消息。

## 问题分析规则

`bf-project-bug-reader` 负责项目数据读取，`bf-code-reader` 负责按分支的源码证据分析。单内环境、Build 和版本也应决定选哪个版本。服务端线上/测试/策划测试对应 `master` / `test` / `design`；客户端线上 `master`，测试和开发 `develop`。客户端策划测试版本需单独核对 Build。源码分支最新提交不能证明实际部署版本。

权限失效先核对原账号和 MCP 页面设置，不静默更换身份。下载链接、签名、Bug 正文、附件及调用证据只留部署机私有目录，不进入公开仓库。
