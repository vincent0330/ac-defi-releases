# AC DeFi Releases

本仓库用于保存由 Mitosis 外部 Agent 生成并通过验收的 AC DeFi 发布版本。

## 发布隔离规则

- 每一次复刻生成一个独立 Git 分支：`rebuild/<short-run-id>`。
- 每个分支对应一个独立 Railway 项目、服务和公开域名。
- 同一 `providerRunId` 的重试复用既有发布记录，不创建重复资源。
- 默认目标网络为 Ethereum Sepolia；Ethereum Mainnet 仅在拥有独立、经确认的主网配置时启用。
- Railway 产物不得包含 Anvil、测试水龙头、本地私钥、管理员签名密钥或本地链时间控制。
- 只有完成源码完整性校验、部署健康检查和发布清单写入的版本才能返回最终 URL。

详细流程见生成工作区中的 `docs/REPEATABLE_RAILWAY_RELEASE.md`。
