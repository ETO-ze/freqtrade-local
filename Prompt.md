# OpenClaw + Freqtrade Project Prompt

## 目标

把当前项目维护成一个可持续迭代的本地量化交易控制平台：

- 本地负责行情缓存、动态币池、因子训练、回测、promotion 审批、运行时策略生成。
- 云端负责 Freqtrade 实盘执行、受保护访问、只读状态同步和看板数据发布。
- GUI 和网站看板负责把后台状态、已批准因子、回测、walk-forward、服务器连通性和实盘状态展示清楚。
- 每次改动都要优先保证现有实盘链路安全，不因实验功能破坏当前 active 配置。

## 非目标

- 不把本项目包装成公开交易信号服务。
- 不在仓库里保存或展示任何 API key、secret、token、服务器密码、Telegram token。
- 不让本地模型实验直接绕过 promotion gate 修改云端实盘。
- 不为了短期收益删除风控、审批、回测、历史因子保护逻辑。
- 不把本地缓存、回测 zip、daemon 日志、数据库文件提交到 GitHub。

## 硬约束

- 项目根目录固定为 `D:\Playground\freqtrade-local`。
- 默认策略为 `AlternativeHunter`，云端实盘由 Freqtrade 执行。
- 本地训练和筛选可以失败，但失败必须可见、可诊断、可恢复。
- `walk-forward` 当前保持 `report-only`，未确认稳定前不作为强制 promotion gate。
- Docker 训练受本机内存限制影响，必须控制样本量、模型规模和后台并发。
- 不提交 `server.openclaw-sync.local.json`、交易所 API、Telegram token、本地行情数据、回测 zip、daemon logs。
- 不随意重启云端实盘 Bot；涉及持仓、策略切换、API 修改时必须考虑保护逻辑。

## 交付物

- 可运行的本地后台因子训练链路：`fast`、`stable`、`autotune`、手动 `evolution`。
- 可读的本地 GUI 总控：启动/停止后台、查看状态、同步云端、打开报告、运行 walk-forward。
- 可读的网站看板：active 因子、回测结果、已批准历史、实盘状态、告警、walk-forward 状态。
- 可审计的 promotion 结果：候选指标、审批结论、历史因子比较、云端同步结果。
- 可维护的项目文档：README、协作文档、运行命令、已知问题和决策记录。

## Done When

- 本地 `fast` 和 `stable` 后台能启动、运行、失败可恢复。
- 本地模型训练不会因为常规动态币池触发 Docker `exit code 137`。
- 最新通过审批的因子不会被未达标候选覆盖。
- 云端 Freqtrade 实盘状态能通过只读数据同步到看板。
- 网站和 GUI 能展示当前 active 状态与 walk-forward 状态。
- Git 状态中没有误加入密钥、缓存、报告、数据、回测 zip 或 daemon logs。
