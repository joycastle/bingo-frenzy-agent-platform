# bingo-frenzy-agent-platform

本仓维护 MausBot 的部署与业务接入；MausBot 源码由 `versions.env` 固定版本并下载到仓库外。

- 不复制 ai-workspace 的业务文档、Skills、个人记忆或运行凭据；业务能力按后续明确要求接入。
- `config.env` 只保存在部署机器；密钥、对话、记忆、日志和备份不入 Git。
- 修改部署行为时，维护 `tests/`、README 和真实隔离验证；不通过用户正在使用的数据验证写操作。
- 先完成源码构建、打包服务冒烟和隔离会话验证，再切换常驻服务；保留失败日志与旧版本。
- 当前原生服务支持 macOS LaunchAgents，登录后自动启动。Linux Docker 是上游独立部署入口，不宣称已验证。
- 本仓独立于 Bingo 业务代码，不操作业务机器、数据库或工作区。
