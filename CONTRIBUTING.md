# Contributing

- `toolkit/core` 保存通用解密、读取、索引和导出能力。
- `toolkit/domains` 保存 Wiki 字段还原与领域规则。
- `legacy` 只用于回归核对，不继续增加功能。
- Spin/Snap 在本仓库只处理 masterdata 分类和统计，不加入资源渲染功能。
- 所有测试夹具必须人工构造或脱敏。

提交前运行：

```powershell
./scripts/verify.ps1
```

