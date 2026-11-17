# 代码阅读 Bot

`skills/bf-code-reader/SKILL.md` 是这个 Bot 的 Skill 源码，负责仓库定位、架构导航、跨仓调用链、分支工作树和源码证据。`SOUL.md` 是长期指示源码，明确何时使用 Skill 和架构入口。Bot 的显示名称及 ID 在部署机器选择，不写死到通用模板。

## 维护与安装

1. 在部署机配置统一 `.env` 的 `GIT_TOKEN`（或 `GH_TOKEN`）与 `GIT_REPOSITORIES_JSON`。仓库须明确 URL 和默认分支。
2. 将经审核的项目知识放入 `$STATE_DIR/knowledge/code-reader/`，使用 `ENTRY.md` 组织架构总览、仓库职责、代码定位方法、可访问范围和业务文档指针。业务文档、个人记忆、凭据不进入本公开仓库；不能把本机数据库/MCP/SSH 能力复制给这个 Bot。
3. 检查并提交本目录 Skill 源码。若部署目录不是 `~/Work/bingo-frenzy-agent-platform`，先修正 Skill 里的工具路径。
4. 在部署机器本地对空闲 Bot 安装：

```bash
python3 bin/install-bot-skills.py \
  --url http://127.0.0.1:8799 \
  --bot <目标Bot的ID> \
  --directory bots/code-reader/skills
```

安装器通过 MausBot 配置 API 安装、启用，并重新读取核对内容。它不修改 Bot 的模型、审批模式、工作目录、名称、对话或其它 Skill；目前支持单 SKILL.md，若发现支持文件会明确拒绝，避免静默漏装。

在 Bot 设置的 SOUL 中填写本目录 `SOUL.md`，在“资料库 → 技能”核对 `bf-code-reader` 已开启。维护时先更新仓库源文件，再通过浏览器设置保存并核对；安装器只处理 Skill，不覆盖已有 SOUL。用隔离临时工作区验证新流程；不往正式历史对话写测试消息。

## 给这个 Bot 的资料

- 入口导览：架构层次、问题到仓库的映射、当前授权范围、工作树目录、查询示例、记忆维护。
- ai-workspace 的架构总览、仓库地图、跨仓联动、Go/Lua 运行时说明。
- 业务文档索引及相关模块 overview / server-flow / client-flow / data-model / checklist，按问题读取。
- 只读场景适用的 Git 规范，以及后续明确开发请求时需查阅的代码风格与跨仓约定。历史文档里的开发命令不能替代本次用户授权。
- 私有快照来源清单：时间、源仓 HEAD、文件哈希，注明本地未提交内容；不复制个人 MEMORY。

## 工作树约定

每个仓库分支固定目录，开始查询前从远端强制同步，分析过程中固定版本。远端强推或重建时也以远端为准，丢弃受管分析目录的本地改动；其它分支和用户开发目录不受影响。人工索引由工具自动生成。完整命令与边界见仓根 README。

当前 Skill 默认读代码，不把读代码请求升级为提交、推送、PR、部署或业务数据操作。用户明确提出修改/开 PR 后，另建开发 worktree、执行相应测试，再进行获准操作；分析缓存不用于保存开发成果。
