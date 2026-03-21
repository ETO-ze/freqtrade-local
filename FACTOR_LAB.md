# 因子实验室

本地可视化交易因子训练工具。

启动：

```powershell
cd C:\Users\Administrator\Documents\Playground\freqtrade-local
powershell -ExecutionPolicy Bypass -File .\start-factor-lab.ps1
```

打开：

- `http://127.0.0.1:8501`

功能：

- 选择币种、周期、预测窗口、阈值、模型
- 调用 Docker 容器内训练脚本
- 查看模型分数、因子重要性、单币边际、原始 JSON
- 读取已有历史报告做对比
- 运行 OpenClaw 本地模拟筛选

说明：

- OpenClaw 模拟默认只做本地筛选
- 不会自动修改实盘配置
- 不会自动推送 Telegram

依赖：

- 本机 `py`
- Docker 容器 `freqtrade`
- 本机 Python 包：`streamlit`、`plotly`、`pandas`
