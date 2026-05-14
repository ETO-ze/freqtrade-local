# OpenClaw + Freqtrade 项目协作 Prompt

## 目标

把当前项目从“脚本型工作区”稳定升级为“本地量化交易控制平台”：

- 本地负责行情缓存、动态币池、因子训练、模型筛选、回测、walk-forward 观察、promotion 审批和云端同步准备。
- 云端负责 Freqtrade 实盘执行，只接收已审批 active 配置，不让未达标候选因子直接覆盖实盘。
- GUI、Streamlit 看板和 Vue 网站看板负责展示状态、报告、回测、实盘只读摘要和运维入口。
- 项目文档必须能让后续 Codex/GPT 快速理解架构、当前状态、硬约束和下一步优先级。

## 非目标

- 不把本项目做成公开交易信号服务。
- 不在 GitHub、README、公开网页或日志里提交任何 API key、secret、token、服务器密码、交易所密钥。
- 不让本地实验绕过 promotion gate 直接修改云端实盘。
- 不为了短期高收益删除风控、审批、历史因子保护、回测验证和同步保护。
- 不把行情数据、回测 zip、daemon logs、SQLite 数据库、本地缓存提交到 GitHub。

## 硬约束

- 项目根目录：`D:\Playground\freqtrade-local`。
- 当前主策略：`AlternativeHunter`。
- 当前执行模式：本地负责训练和筛选，云端负责实盘交易。
- 当前 active 因子不能被未达标候选结果覆盖。
- `walk-forward` 当前保持 `report-only`，没有进一步验证前不能作为强制 promotion gate。
- Docker/WSL 内存是训练链路的主要约束，出现 `exit code 137` 时优先按内存和并发问题排查。
- 禁止提交：`server.openclaw-sync.local.json`、交易所 API、Telegram token、本地行情、回测 zip、daemon logs、`dashboard-data/`、`reports/`、`user_data/backtest_cache/`。
- 涉及云端 Freqtrade、持仓、API 或策略切换时，必须优先考虑“有持仓时不强行破坏当前仓位”的保护逻辑。

## 当前项目框架

- `apps/desktop/`：Tkinter 本地总控 GUI。
- `apps/streamlit/`：因子实验室、策略调试面板、Telegram 模板面板。
- `scripts/windows/`：Windows 启停、同步、回补、walk-forward、GitHub 同步入口。
- `scripts/workflows/`：动态币池、dashboard 发布、服务器探测、walk-forward、云端同步等 workflow 脚本。
- `site/dashboard/`：Vue3 网站看板，展示回测、审批历史、实盘只读摘要、告警和状态。
- `site/landing/`：duskrain 首页静态站点。
- `server/`：服务端看板状态构建和辅助脚本。
- `user_data/notebooks/`：因子训练、进化算法、autotune、交易反馈分析等研究脚本。
- `user_data/strategies/`：Freqtrade 策略，当前核心是 `AlternativeHunter.py`。
- `docs/`：项目说明、操作指南、结构梳理和后续设计文档。
- `reports/`、`dashboard-data/`、`user_data/backtest_cache/`：运行产物和缓存，不作为公开源码提交。

## 当前量化方向

- 山寨币主线：动态币池 + robust screen + 多模型树模型筛选 + `AlternativeHunter` 策略执行。
- 核心特征：mark premium、funding、波动率、ATR、BTC/ETH beta、相对强弱、趋势确认、动态币池分数。
- 当前 active 因子偏高收益高风险：收益较高，但回撤较大，属于实验高风险通道。
- 当前主要问题：最新候选收益偏低，部分因子仍被 mark premium 家族主导，walk-forward 尚未成为硬门槛，autotune 和 Docker 内存仍需继续稳固。

## 交付物

- 可运行的本地后台训练链路：`fast`、`stable`、`autotune`、手动 `evolution`。
- 可读的本地总控 GUI：状态、启动/停止、云端同步、报告入口、GitHub 同步入口。
- 可读的网站看板：active 因子、回测详情、已批准历史、实盘持仓只读摘要、告警、walk-forward。
- 可审计的 promotion 结果：候选指标、审批结论、历史对比、云端同步状态。
- 可维护的协作文档：`Prompt.md`、`Plan.md`、`Implement.md`、`Documentation.md` 和 `docs/project/PROJECT_FRAMEWORK_AND_QUANT_REVIEW.md`。

## Done When

- `fast`、`stable`、`autotune` 后台状态可读，启动失败能显示明确原因。
- 当前 active 因子不会被未达标候选覆盖。
- 网站和 GUI 能展示同一套 active、回测、审批历史、云端同步和实盘只读数据。
- 至少一轮本地语法、构建、JSON 读取和服务器探测验证通过。
- Git 状态中没有误加入 secrets、缓存、报告、行情数据、回测 zip 或 daemon logs。
