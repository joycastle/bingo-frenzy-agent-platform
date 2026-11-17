# 待办

## 飞书项目附件下载

- 状态：暂缓，2026-11-17 由用户明确要求先记录待办。
- 现象：现有个人 MCP Token 可以读取工作项和评论；官方 MCP 的 `get_download_url` 与 Meegle CLI 1.0.28 的 `attachment +download` 均返回 `MCPPersonalPreferenceDisabled`，未获得附件内容。
- 已排除：MCP 包未升级（当前发布最新版为 0.0.1）；CLI 使用错误请求头（已指定 `X-Mcp-Token`）；仅更换 CLI 不能解决当前 Token 的下载限制。
- 文档依据：[下载附件](https://project.feishu.cn/b/helpcenter/1ykiuvvj/19wmvt8b#1d06e38e) 标记为“允许查看数据信息”，与当前实际报错不一致。
- 后续排查：在独立 CLI profile 中使用同一账号的 OAuth 登录对比附件下载，并核对实际授权范围。社区 [Issue #4](https://github.com/larksuite/meegle-cli/issues/4) 有同样错误正文，作者反馈 OAuth 可用，但该例涉及状态流查询，不能直接视为附件问题已解决。不要在验证前切换正式 Bot 的凭据或扩大写权限。
- 验收：成功下载真实附件并核对文件完整性，确认只读授权边界后，再维护 Bot 使用方式；若仍失败，整理错误及私有请求 logid 向官方支持反馈。
- 记录位置：部署机私有状态目录 `operations/feishu-project/meegle-trial/`；业务内容、附件 URL 和凭据不入 Git。现有实测结果见 [部署验证记录](deployment-validation.md)。
