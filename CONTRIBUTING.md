# 团队协作与分支规则

依据 [团队分工](docs/团队分工.md)。原文“今晚 / D1 / D2”为相对里程碑，开始日期由团队安排；“当前不是 git 仓库”为历史状态，本仓库已经启用 Git。

| 分支 | 用途 | 修改范围 |
|---|---|---|
| main | 稳定演示 / 发布 | 接收已验证的 develop |
| develop | 三页联调 | 接收个人分支 PR |
| p1-data | 数据与图谱 | app.py、requirements.txt、core/、scripts/、data/、docs/schema.md、docs/run.md、.env.example |
| p2-pages | 分析与展示 | pages/01_产业技术全景.py、pages/02_创新主体与合作网络.py、analysis/ |
| p3-qa | 问答与路径 | pages/03_智能问答与关联路径.py、qa/、docs/qa_intents.md |
| p4-docs | 文档与汇报 | docs/说明文档.md、docs/答辩稿.md、docs/ppt/ |
| p5-eval | 质量与交付 | eval/、README.md、delivery/ |

1. 每人只在自己的分支改自己的文件，PR 目标选 `develop`。开工前 `git fetch origin`，将 `origin/develop` 合并到个人分支，不强推共享分支。
2. 跨目录修改向负责人提需求，由负责人完成。公共依赖统一由 P1 更新 requirements.txt。
3. 契约变更同步团队分工与对应 docs，再通知使用者；不能私改字段。
4. `.github/`、`.gitignore`、本指南、分工与规划为协作配置，变更在 PR 中说明并经团队确认。旧版代码只读保留，兼容性修复由 P1 单独处理。
5. 不提交凭据、虚拟环境、全量原始数据、视频与压缩包。`data/processed/` 本地生成，七表样例入库。
6. P2 / P3 / P5 用 `load_table()` 取数；P2 / P3 用 `run_query()` 调用审核过的参数化查询。页面 03 只调用 `answer()`。P2 与 P3 没有共享业务模块。
7. 测试集由 P5 出题和判定，P3 只读。样例缺失值不能当作统计零值或用旧混合日期补申请年。

## 提交前验证

```powershell
python -m compileall -q app.py core scripts pages analysis qa eval legacy
python -m eval.check_contracts
python -m eval.smoke_test
```

GitHub Actions 在 main / develop 推送及指向它们的 PR 中执行这些基础检查，不依赖数据库 / API。它验证开发基线与入口，业务验收仍由负责人完成。未设置服务端分支保护或 CODEOWNERS：尚未提供五位成员 GitHub 账号，所有权由协作流程约束。

## 资料与迁移状态

- `docs/团队分工.md`：用户提供的分工原文快照。
- `docs/项目规划.md`：同目录 `项目规划(1).md` 的快照，包含三页架构、7.4.3 的 12 意图与 CQ10。原文 WP 角色仅作背景，实际所有权以分工为准。
- `docs/legacy/`：旧运行说明、六页设计与验证结果，仅对应旧 Schema。
- 本次为一次性公共骨架调整，未宣称达到 T0 全部交付或后续里程碑。后续开发按上表进行。
