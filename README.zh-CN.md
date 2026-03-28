# OpenClaw + Freqtrade 本地量化工作区

![OpenClaw + Freqtrade Icon](assets/openclaw-freqtrade-icon.png)

[English](README.md) | [中文](README.zh-CN.md)

这个仓库是一套本地量化工作区，核心由 `OpenClaw` 和 `Freqtrade` 组成。

- `OpenClaw` 负责因子筛选、模型训练、审批和自动化流程。
- `Freqtrade` 负责 dry-run 执行。
- 山寨和主流两套系统已经按配置、端口、数据库、容器彻底隔离。

项目图标文件：
- PNG: [assets/openclaw-freqtrade-icon.png](assets/openclaw-freqtrade-icon.png)
- ICO: [assets/openclaw-freqtrade-icon.ico](assets/openclaw-freqtrade-icon.ico)

## 截图

### 看板总览
![Dashboard Overview](assets/dashboard-overview-20260328.png)

### 总控 GUI
![Control Center GUI](assets/control-center-gui-20260328.png)

## 当前运行结构

### 山寨线路
- 策略：`AlternativeHunter`
- 自动化：`stable`、`fast`、`autotune`
- Bot API：[http://127.0.0.1:8081](http://127.0.0.1:8081)

### 主流线路
- 策略：`MainstreamHunter`
- 交易池：`BTC/USDT:USDT`、`ETH/USDT:USDT`、`XAU/USDT:USDT`
- Bot API：[http://127.0.0.1:8082](http://127.0.0.1:8082)

### 后台服务
- `fast`：轻量筛选
- `stable`：完整候选生成、回测与 gated promotion
- `evolution`：手动研究层
- `autotune`：`AlternativeHunter` 的低频运行时调参

## Stable 审批门槛

当前 stable promotion 门槛：
- 收益 `>= 15%`
- 盈利因子 `>= 1.9`
- 最大回撤 `<= 8.5%`
- Sortino `>= 7`
- Calmar `>= 45`
- 交易数 `>= 180`

## 快速开始

### GUI 总控中心

打开：
- [OpenClaw Control Center GUI.cmd](OpenClaw%20Control%20Center%20GUI.cmd)

主要功能：
- 启动/停止 `fast`
- 启动/停止 `stable`
- 启动/停止 `evolution`
- 启动/停止 `autotune`
- 启动山寨/主流 bot
- 打开看板、日志、报告和说明文档

### 只读看板

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-factor-lab.ps1
```

打开：
- [http://127.0.0.1:8501](http://127.0.0.1:8501)

### 策略调试面板

```powershell
cmd /c "C:\Users\Administrator\Documents\Playground\freqtrade-local\Launch Strategy Debug Lab.cmd"
```

打开：
- [http://127.0.0.1:8502](http://127.0.0.1:8502)

## 主要命令

### 后台 daemon

Fast：
```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-openclaw-factor-daemon-fast.ps1
```

Stable：
```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-openclaw-factor-daemon-stable.ps1
```

Evolution：
```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-openclaw-factor-daemon-evolution.ps1
```

Autotune：
```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-openclaw-factor-daemon-autotune.ps1
```

### Bot

山寨 bot：
```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-openclaw-auto-bot.ps1
```

主流 bot：
```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-mainstream-auto-bot.ps1
```

### 开机启动

Windows 登录自启动入口：
- [Start OpenClaw On Login.cmd](Start%20OpenClaw%20On%20Login.cmd)

脚本：
```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\Documents\Playground\freqtrade-local\start-openclaw-on-login.ps1
```

## 关键文件

工作区：
- [factor_lab.py](factor_lab.py)
- [strategy_debug_lab.py](strategy_debug_lab.py)
- [start-openclaw-control-center-gui.py](start-openclaw-control-center-gui.py)
- [OPENCLAW_FREQTRADE_GUIDE.md](OPENCLAW_FREQTRADE_GUIDE.md)
- [ALTERNATIVEHUNTER_TUNING_GUIDE_CN.md](ALTERNATIVEHUNTER_TUNING_GUIDE_CN.md)

策略：
- [user_data/strategies/AlternativeHunter.py](user_data/strategies/AlternativeHunter.py)
- [user_data/strategies/MainstreamHunter.py](user_data/strategies/MainstreamHunter.py)

流程脚本：
- [../openclaw/scripts/freqtrade-daily-ml-screen.ps1](../openclaw/scripts/freqtrade-daily-ml-screen.ps1)
- [../openclaw/scripts/freqtrade-backtest-openclaw-auto.ps1](../openclaw/scripts/freqtrade-backtest-openclaw-auto.ps1)
- [../openclaw/scripts/freqtrade-sync-screen-to-config.ps1](../openclaw/scripts/freqtrade-sync-screen-to-config.ps1)

## 安全说明

不会提交到仓库的内容：
- 交易所 API 凭据
- Telegram token / chat id
- live 运行时密钥
- 本地行情数据
- 本地日志
- 本地报告输出
- 回测结果 zip
- SQLite 数据库

模板文件：
- [openclaw.notification.example.json](openclaw.notification.example.json)
- [user_data/config.example.json](user_data/config.example.json)
- [user_data/config.openclaw-auto.example.json](user_data/config.openclaw-auto.example.json)

## 文档

- [OPENCLAW_FREQTRADE_GUIDE.md](OPENCLAW_FREQTRADE_GUIDE.md)
- [STRATEGY_DEBUG_LAB.md](STRATEGY_DEBUG_LAB.md)
- [ALTERNATIVEHUNTER_TUNING_GUIDE_CN.md](ALTERNATIVEHUNTER_TUNING_GUIDE_CN.md)
- [ML_TRAINING.md](ML_TRAINING.md)
- [FACTOR_LAB.md](FACTOR_LAB.md)
