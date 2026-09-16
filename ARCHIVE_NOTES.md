# 归档说明

归档日期：2026-09-16。原服务器目录：`/mnt/chengrongfeng_private/cc_dump/portraiture/`。

此私有仓库保存当前代码、项目说明、实验或业务数据。医院项目还保留原有本地 Git 历史；如历史包含真实凭据，上传前进行脱敏，原始历史由本地备份保留。

真实 `.env` 配置、访问密钥、缓存、运行日志和依赖安装目录不进入新增归档提交。项目和历史的原始压缩备份另存于本地“服务器项目备份”输出目录。大型文件通过 Git LFS 保存。

医院数据、医学记录和个人聊天资料应保持仓库私有。目录中现有论文、指南、样例和代码的原有使用边界继续适用。

## 凭据脱敏

上传版中检测到的凭据字符串替换为 `REDACTED_CREDENTIAL`；个人聊天、压缩导出和第三方数据集中的凭据样例也可能受影响。全部原始数据保留在本地原始压缩备份中，严格复现实验时可使用原始数据。

- `data/chatgpt_personal_backup_2026-06-08_full_with_projects.zip`：替换 6 处。
- `data/interim/normalized/messages.jsonl`：替换 4 处。
- `data/processed/personaconvbench/replay_examples.jsonl`：替换 1347 处。
- `data/raw/imports/chatgpt_team_backup/Linux安装Claude Code_6a13e0cb-0e34-83ec-9947-39773b21c70d_20260525_134127.html`：替换 2 处。
- `data/raw/imports/chatgpt_team_backup/Linux安装Claude Code_6a13e0cb-0e34-83ec-9947-39773b21c70d_20260525_134127.json`：替换 2 处。
- `data/raw/imports/chatgpt_team_backup/Linux安装Claude Code_6a13e0cb-0e34-83ec-9947-39773b21c70d_20260525_134127.md`：替换 2 处。
- `data/raw/personaconvbench_repo/Raw_Data_Postized.json`：替换 423 处。
- `gpu_package/data/messages.jsonl`：替换 4 处。

## 凭据脱敏

上传版中检测到的凭据字符串替换为 `REDACTED`；个人聊天、压缩导出和第三方数据集中的凭据样例也可能受影响。全部原始数据保留在本地原始压缩备份中，严格复现实验时可使用原始数据。

- `data/processed/personaconvbench/replay_examples.jsonl`：替换 34 处。
- `data/raw/personaconvbench_repo/Raw_Data_Postized.json`：替换 32 处。
