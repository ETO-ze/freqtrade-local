# 因子实验室

本地可视化交易因子训练工具。

启动：

```powershell
cd D:\Playground\freqtrade-local
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
- 查看候选因子与当前 active/历史最优因子的对比
- 读取最新审批报告中的真实 gate、实验高收益通道和 promotion protection 规则
- 查看回测缓存命中、回测区间、最新行情时间和结果包信息
- 诊断 mark_premium 依赖、top3 因子集中度和正交因子占比
- 查看回测详情：权益曲线、回撤曲线、币种盈利排行、long/short 统计、月度收益热力图、单币交易数与胜率

说明：

- OpenClaw 模拟默认只做本地筛选
- 不会自动修改实盘配置
- 不会自动推送 Telegram

依赖：

- 本机 `py`
- Docker 容器 `freqtrade`
- 本机 Python 包：`streamlit`、`plotly`、`pandas`
