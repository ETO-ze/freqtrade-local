from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime_state import daemon_summary


WINDOWS_SCRIPT_ROOT = ROOT / "scripts" / "windows"
STREAMLIT_APP_ROOT = ROOT / "apps" / "streamlit"
WORKFLOW_SCRIPT_ROOT = ROOT / "scripts" / "workflows"
REPORT_ROOT = ROOT / "reports"
DAEMON_ROOT = REPORT_ROOT / "daemon"
ICON_PATH = ROOT / "assets" / "openclaw-freqtrade-icon.ico"
ICON_PNG_PATH = ROOT / "assets" / "openclaw-freqtrade-icon.png"

SERVER_SYNC_REPORT = REPORT_ROOT / "openclaw-server-sync-latest.json"
SERVER_STATUS_REPORT = REPORT_ROOT / "openclaw-server-status-latest.json"
SERVER_SYNC_SETTINGS = ROOT / "server.openclaw-sync.local.json"

ACTIVE_CONFIG = ROOT / "user_data" / "config.openclaw-auto.json"
RUNTIME_POLICY = ROOT / "user_data" / "model_runtime_policy.json"
APPROVED_HISTORY = REPORT_ROOT / "openclaw-approved-history.json"
LATEST_BACKTEST = REPORT_ROOT / "openclaw-auto-backtest-latest.json"
STABLE_APPROVAL_MD = REPORT_ROOT / "openclaw-auto-approval-stable.md"
MANUAL_PROMOTION_REPORT = REPORT_ROOT / "openclaw-manual-promotion-latest.md"
ML_REPORT_DIR = ROOT / "user_data" / "reports" / "ml"

GUIDE_PATH = ROOT / "docs" / "guides" / "OPENCLAW_FREQTRADE_GUIDE.md"
TUNING_GUIDE_PATH = ROOT / "docs" / "guides" / "ALTERNATIVEHUNTER_TUNING_GUIDE_CN.md"
TELEGRAM_GUIDE_PATH = ROOT / "docs" / "guides" / "TELEGRAM_TEMPLATE_LAB.md"
README_EN = ROOT / "README.md"
README_ZH = ROOT / "README.zh-CN.md"
PROJECT_INTRO_ZH = ROOT / "docs" / "project" / "PROJECT_INTRO.zh-CN.md"
PROJECT_ROADMAP = ROOT / "PROJECT_ROADMAP.json"

DAEMONS = {
    "fast": {
        "title": "Fast 轻量筛选",
        "start": "start-openclaw-factor-daemon-fast.ps1",
        "stop": "stop-openclaw-factor-daemon-fast.ps1",
        "log": "factor-daemon-fast.out.log",
    },
    "stable": {
        "title": "Stable 正式筛选",
        "start": "start-openclaw-factor-daemon-stable.ps1",
        "stop": "stop-openclaw-factor-daemon-stable.ps1",
        "log": "factor-daemon-stable.out.log",
    },
    "evolution": {
        "title": "Evolution 进化算法",
        "start": "start-openclaw-factor-daemon-evolution.ps1",
        "stop": "stop-openclaw-factor-daemon-evolution.ps1",
        "log": "factor-daemon-evolution.out.log",
    },
    "autotune": {
        "title": "Autotune 参数推演",
        "start": "start-openclaw-factor-daemon-autotune.ps1",
        "stop": "stop-openclaw-factor-daemon-autotune.ps1",
        "log": "factor-daemon-autotune.out.log",
    },
}


def load_json(path: Path, default=None):
    if not path.exists():
        return {} if default is None else default
    try:
        text = path.read_text(encoding="utf-8-sig")
        return json.loads(text) if text.strip() else ({} if default is None else default)
    except Exception:
        return {} if default is None else default


def short_pairs(pairs: list[str], limit: int = 8) -> str:
    symbols = [pair.split("/")[0] for pair in pairs if pair]
    if not symbols:
        return "none"
    if len(symbols) <= limit:
        return ", ".join(symbols)
    return f"{', '.join(symbols[:limit])} ... total {len(symbols)}"


def fmt(value, suffix: str = "") -> str:
    if value is None or value == "":
        return "n/a"
    return f"{value}{suffix}"


def history_list() -> list[dict]:
    raw = load_json(APPROVED_HISTORY, [])
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        value = raw.get("value")
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        return [raw]
    return []


def active_factor() -> dict:
    policy = load_json(RUNTIME_POLICY)
    if isinstance(policy.get("active_approved_factor"), dict):
        return policy["active_approved_factor"]
    history = history_list()
    if not history:
        return {}
    manual = MANUAL_PROMOTION_REPORT.read_text(encoding="utf-8-sig") if MANUAL_PROMOTION_REPORT.exists() else ""
    approved_at = re.search(r"- Source approved at:\s*(.+)", manual)
    backtest = re.search(r"- Backtest:\s*(.+)", manual)
    approved_at_text = approved_at.group(1).strip() if approved_at else ""
    backtest_text = backtest.group(1).strip() if backtest else ""
    if approved_at_text or backtest_text:
        for item in history:
            if approved_at_text and str(item.get("generated_at") or "") == approved_at_text:
                return item
            if backtest_text and str(item.get("latest_backtest") or "") == backtest_text:
                return item
    active_config = load_json(ACTIVE_CONFIG)
    active_pairs = set((active_config.get("exchange") or {}).get("pair_whitelist") or [])
    if active_pairs:
        ranked = []
        for item in history:
            overlap = len(active_pairs.intersection(set(item.get("selected_pairs") or [])))
            profit = float(item.get("total_profit_pct") or 0)
            ranked.append((overlap, profit, item))
        ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)
        if ranked and ranked[0][0] > 0:
            return ranked[0][2]
    return max(history, key=lambda item: float(item.get("total_profit_pct") or 0))


def manual_active_pairs() -> list[str]:
    if not MANUAL_PROMOTION_REPORT.exists():
        return []
    text = MANUAL_PROMOTION_REPORT.read_text(encoding="utf-8-sig")
    match = re.search(r"- Active pairs:\s*(.+)", text)
    if not match:
        return []
    return [item.strip() for item in match.group(1).split(",") if item.strip()]


def run_powershell(script_name: str, arguments: list[str] | None = None, timeout: int = 300) -> tuple[bool, str]:
    script = WINDOWS_SCRIPT_ROOT / script_name
    command = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)]
    if arguments:
        command.extend(str(item) for item in arguments)
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=ROOT,
            timeout=timeout,
        )
        output = ((result.stdout or "") + (result.stderr or "")).strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, f"命令超时：{script_name}"
    except Exception as exc:
        return False, str(exc)


class ControlCenter(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("OpenClaw + Freqtrade 总控中心")
        self.geometry("1480x920")
        self.minsize(1200, 780)
        self.configure(bg="#f5f7fb")
        if ICON_PATH.exists():
            try:
                self.iconbitmap(default=str(ICON_PATH))
            except Exception:
                pass
        if ICON_PNG_PATH.exists():
            try:
                self._icon_photo = tk.PhotoImage(file=str(ICON_PNG_PATH))
                self.iconphoto(True, self._icon_photo)
            except Exception:
                pass

        self.action_running = False
        self.status_vars = {name: tk.StringVar(value="加载中") for name in DAEMONS}
        self.remote_vars = {
            "last_sync": tk.StringVar(value="未同步"),
            "server": tk.StringVar(value="未配置"),
            "bot": tk.StringVar(value="无数据"),
            "validation": tk.StringVar(value="无数据"),
            "pairs": tk.StringVar(value="无数据"),
        }
        self.active_vars = {
            "strategy": tk.StringVar(value="n/a"),
            "model": tk.StringVar(value="n/a"),
            "profit": tk.StringVar(value="n/a"),
            "pf": tk.StringVar(value="n/a"),
            "winrate": tk.StringVar(value="n/a"),
            "drawdown": tk.StringVar(value="n/a"),
            "trades": tk.StringVar(value="n/a"),
            "pairs": tk.StringVar(value="n/a"),
            "latest_candidate": tk.StringVar(value="n/a"),
        }
        self.roadmap_var = tk.StringVar(value="n/a")

        self._configure_style()
        self._build()
        self.refresh_status()
        self.after(5000, self.auto_refresh_status)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        bg = "#f5f7fb"
        panel = "#ffffff"
        panel_2 = "#f8fafc"
        line = "#d7dee9"
        text = "#0f172a"
        muted = "#64748b"
        accent = "#2563eb"
        green = "#059669"
        danger = "#dc2626"

        style.configure(".", font=("Microsoft YaHei UI", 10), background=bg, foreground=text)
        style.configure("TFrame", background=bg)
        style.configure("Hero.TFrame", background=bg)
        style.configure("Card.TFrame", background=panel, relief="solid", borderwidth=1)
        style.configure("Metric.TFrame", background=panel_2, relief="solid", borderwidth=1)
        style.configure("Card.TLabelframe", background=panel, bordercolor=line, relief="solid")
        style.configure(
            "Card.TLabelframe.Label",
            background=bg,
            foreground=accent,
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        style.configure("Title.TLabel", background=bg, foreground=text, font=("Microsoft YaHei UI", 22, "bold"))
        style.configure("Sub.TLabel", background=bg, foreground=muted)
        style.configure("Kicker.TLabel", background=panel, foreground=accent, font=("Microsoft YaHei UI", 9, "bold"))
        style.configure("CardTitle.TLabel", background=panel, foreground=text, font=("Microsoft YaHei UI", 13, "bold"))
        style.configure("Value.TLabel", background=panel, foreground=text, font=("Microsoft YaHei UI", 12, "bold"))
        style.configure("MetricValue.TLabel", background=panel_2, foreground=text, font=("Microsoft YaHei UI", 13, "bold"))
        style.configure("MetricMuted.TLabel", background=panel_2, foreground=muted, font=("Microsoft YaHei UI", 9))
        style.configure("Muted.TLabel", background=panel, foreground=muted)
        style.configure("TButton", padding=(12, 7), background="#ffffff", foreground=text, bordercolor=line)
        style.map("TButton", background=[("active", "#eef2ff")], foreground=[("active", text)])
        style.configure("Accent.TButton", background="#2563eb", foreground="#ffffff", bordercolor=accent)
        style.map("Accent.TButton", background=[("active", "#1d4ed8")])
        style.configure("Danger.TButton", background="#fff1f2", foreground=danger, bordercolor="#fecdd3")
        style.map("Danger.TButton", background=[("active", "#ffe4e6")])
        style.configure("Success.TButton", background="#ecfdf5", foreground=green, bordercolor="#bbf7d0")
        style.map("Success.TButton", background=[("active", "#d1fae5")])

    def _build(self) -> None:
        outer = ttk.Frame(self)
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, bg="#f5f7fb", highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        root = ttk.Frame(canvas)
        window_id = canvas.create_window((0, 0), window=root, anchor="nw")

        def update_scroll_region(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def update_window_width(event) -> None:
            canvas.itemconfigure(window_id, width=event.width)

        def on_mousewheel(event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        root.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", update_window_width)
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        content = ttk.Frame(root)
        content.pack(fill="both", expand=True, padx=20, pady=18)

        header = ttk.Frame(content)
        header.pack(fill="x", pady=(0, 16))
        ttk.Label(header, text="OpenClaw + Freqtrade 总控中心", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="本地负责训练、筛选、回测与 promotion；云端负责交易执行。此 GUI 只控制本地后台与同步链路。",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        self._build_active_area(content)
        self._build_roadmap_area(content)
        self._build_runtime_area(content)
        self._build_controls(content)
        self._build_tools(content)
        self._build_output(content)

    def card(self, parent, title: str, kicker: str = "") -> ttk.Frame:
        label = f"{kicker} / {title}" if kicker else title
        frame = ttk.LabelFrame(parent, text=label, style="Card.TLabelframe", padding=18)
        return frame

    def metric(self, parent, label: str, variable: tk.StringVar, row: int, col: int) -> None:
        box = ttk.Frame(parent, style="Metric.TFrame", padding=12)
        box.grid(row=row, column=col, sticky="nsew", padx=7, pady=7)
        ttk.Label(box, text=label, style="MetricMuted.TLabel").pack(anchor="w")
        ttk.Label(box, textvariable=variable, style="MetricValue.TLabel").pack(anchor="w", pady=(5, 0))

    def _build_active_area(self, parent) -> None:
        area = ttk.Frame(parent)
        area.pack(fill="x", pady=(0, 14))
        area.columnconfigure(0, weight=2)
        area.columnconfigure(1, weight=1)

        active = self.card(area, "正在使用的因子与回测", "ACTIVE FACTOR")
        active.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        grid = ttk.Frame(active, style="Card.TFrame")
        grid.pack(fill="x")
        for index, (label, key) in enumerate(
            [
                ("策略", "strategy"),
                ("模型", "model"),
                ("收益", "profit"),
                ("利润因子", "pf"),
                ("胜率", "winrate"),
                ("最大回撤", "drawdown"),
                ("交易次数", "trades"),
                ("当前币池", "pairs"),
            ]
        ):
            self.metric(grid, label, self.active_vars[key], index // 4, index % 4)
        for col in range(4):
            grid.columnconfigure(col, weight=1)

        candidate = self.card(area, "最新候选回测", "LATEST CANDIDATE")
        candidate.grid(row=0, column=1, sticky="nsew")
        ttk.Label(candidate, textvariable=self.active_vars["latest_candidate"], style="Value.TLabel", wraplength=360).pack(anchor="w")

    def _build_roadmap_area(self, parent) -> None:
        frame = self.card(parent, "项目标记", "ROADMAP")
        frame.pack(fill="x", pady=(0, 14))
        ttk.Label(
            frame,
            textvariable=self.roadmap_var,
            style="Value.TLabel",
            wraplength=1320,
            justify="left",
        ).pack(anchor="w")

    def _build_runtime_area(self, parent) -> None:
        area = ttk.Frame(parent)
        area.pack(fill="x", pady=(0, 14))
        area.columnconfigure(0, weight=1)
        area.columnconfigure(1, weight=1)

        local = self.card(area, "本地后台状态", "LOCAL DAEMONS")
        local.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        for row, name in enumerate(("fast", "stable", "evolution", "autotune")):
            ttk.Label(local, text=DAEMONS[name]["title"], style="Muted.TLabel", width=18).grid(row=row, column=0, sticky="w", pady=5)
            ttk.Label(local, textvariable=self.status_vars[name], style="Value.TLabel").grid(row=row, column=1, sticky="w", pady=5)
        local.columnconfigure(1, weight=1)

        remote = self.card(area, "服务器连通状态", "SERVER")
        remote.grid(row=0, column=1, sticky="nsew")
        rows = [("最近同步", "last_sync"), ("服务器", "server"), ("云端 Bot", "bot"), ("验证", "validation"), ("已同步币对", "pairs")]
        for row, (label, key) in enumerate(rows):
            ttk.Label(remote, text=label, style="Muted.TLabel", width=14).grid(row=row, column=0, sticky="w", pady=5)
            ttk.Label(remote, textvariable=self.remote_vars[key], style="Value.TLabel").grid(row=row, column=1, sticky="w", pady=5)
        remote.columnconfigure(1, weight=1)

    def _build_controls(self, parent) -> None:
        frame = self.card(parent, "本地后台控制", "CONTROL")
        frame.pack(fill="x", pady=(0, 14))
        buttons = [
            ("启动 Fast", "fast", "start", "TButton"),
            ("停止 Fast", "fast", "stop", "Danger.TButton"),
            ("启动 Stable", "stable", "start", "TButton"),
            ("停止 Stable", "stable", "stop", "Danger.TButton"),
            ("启动 Evolution", "evolution", "start", "TButton"),
            ("停止 Evolution", "evolution", "stop", "Danger.TButton"),
            ("启动 Autotune", "autotune", "start", "TButton"),
            ("停止 Autotune", "autotune", "stop", "Danger.TButton"),
        ]
        for i, (label, daemon, action, style) in enumerate(buttons):
            ttk.Button(
                frame,
                text=label,
                style=style,
                command=lambda d=daemon, a=action, l=label: self.run_and_report(DAEMONS[d][a], label=l),
            ).grid(row=i // 4, column=i % 4, padx=6, pady=6, sticky="w")
        ttk.Button(
            frame,
            text="开启训练加速",
            style="Accent.TButton",
            command=lambda: self.run_and_report("set-openclaw-training-speed.ps1", ["-Mode", "boost"], "开启训练加速"),
        ).grid(row=2, column=0, padx=6, pady=(12, 6), sticky="w")
        ttk.Button(
            frame,
            text="恢复常规频率",
            command=lambda: self.run_and_report("set-openclaw-training-speed.ps1", ["-Mode", "normal"], "恢复常规频率"),
        ).grid(row=2, column=1, padx=6, pady=(12, 6), sticky="w")
        ttk.Button(frame, text="刷新状态", style="Accent.TButton", command=self.refresh_status).grid(row=2, column=2, padx=6, pady=(12, 6), sticky="w")
        for col in range(4):
            frame.columnconfigure(col, weight=1)

    def _build_tools(self, parent) -> None:
        frame = self.card(parent, "面板、服务器与文档", "TOOLS")
        frame.pack(fill="x", pady=(0, 14))
        buttons = [
            ("启动网页看板", lambda: self.start_streamlit("factor_lab.py", 8501)),
            ("打开网页看板", lambda: webbrowser.open("http://127.0.0.1:8501")),
            ("启动策略调试", lambda: self.start_streamlit("strategy_debug_lab.py", 8502)),
            ("打开策略调试", lambda: webbrowser.open("http://127.0.0.1:8502")),
            ("启动 Telegram 模板", lambda: self.start_streamlit("telegram_template_lab.py", 8503)),
            ("打开 Telegram 模板", lambda: webbrowser.open("http://127.0.0.1:8503")),
            ("探测服务器", self.probe_server_status),
            ("同步到服务器", self.sync_to_server),
            ("打开本地 API", lambda: webbrowser.open("http://127.0.0.1:8081")),
            ("打开云端入口", lambda: webbrowser.open("https://duskrain.cn/")),
            ("打开报告目录", lambda: subprocess.Popen(["explorer", str(REPORT_ROOT)])),
            ("打开历史 ML 报告", lambda: subprocess.Popen(["explorer", str(ML_REPORT_DIR)])),
            ("Stable 审批", lambda: self.open_path(STABLE_APPROVAL_MD)),
            ("项目说明", lambda: self.open_path(GUIDE_PATH)),
            ("参数说明", lambda: self.open_path(TUNING_GUIDE_PATH)),
            ("README 中文", lambda: self.open_path(README_ZH)),
            ("README EN", lambda: self.open_path(README_EN)),
        ]
        for i, (label, callback) in enumerate(buttons):
            ttk.Button(frame, text=label, command=callback).grid(row=i // 5, column=i % 5, padx=6, pady=6, sticky="w")
        github_index = len(buttons)
        ttk.Button(frame, text="一键同步 GitHub", style="Accent.TButton", command=self.sync_to_github).grid(
            row=github_index // 5,
            column=github_index % 5,
            padx=6,
            pady=6,
            sticky="w",
        )
        for col in range(5):
            frame.columnconfigure(col, weight=1)

    def _build_output(self, parent) -> None:
        frame = self.card(parent, "最近操作", "OUTPUT")
        frame.pack(fill="both", expand=True)
        self.output = tk.Text(
            frame,
            height=8,
            bg="#ffffff",
            fg="#0f172a",
            insertbackground="#0f172a",
            relief="flat",
            padx=12,
            pady=10,
            wrap="word",
            font=("Consolas", 10),
        )
        self.output.pack(fill="both", expand=True)
        self.set_output("就绪。")

    def refresh_status(self) -> None:
        for name in self.status_vars:
            self.status_vars[name].set(daemon_summary(f"factor-daemon-{name}"))
        self.refresh_active_factor()
        self.refresh_roadmap()
        self.refresh_remote_status()

    def refresh_active_factor(self) -> None:
        config = load_json(ACTIVE_CONFIG)
        factor = active_factor()
        latest = load_json(LATEST_BACKTEST)
        metrics = {
            "total_profit_pct": factor.get("total_profit_pct"),
            "profit_factor": factor.get("profit_factor"),
            "winrate": factor.get("winrate") or factor.get("winrate_pct"),
            "max_drawdown_pct": factor.get("max_drawdown_pct"),
            "trade_count": factor.get("trade_count"),
        }
        pairs = manual_active_pairs() or (config.get("exchange") or {}).get("pair_whitelist") or factor.get("selected_pairs") or []
        self.active_vars["strategy"].set(config.get("strategy") or factor.get("strategy") or "n/a")
        self.active_vars["model"].set(factor.get("best_model") or factor.get("model") or "n/a")
        self.active_vars["profit"].set(fmt(metrics["total_profit_pct"], "%"))
        self.active_vars["pf"].set(fmt(metrics["profit_factor"]))
        self.active_vars["winrate"].set(fmt(metrics["winrate"], "%"))
        self.active_vars["drawdown"].set(fmt(metrics["max_drawdown_pct"], "%"))
        self.active_vars["trades"].set(fmt(metrics["trade_count"]))
        self.active_vars["pairs"].set(short_pairs(pairs, 10))

        latest_metrics = latest.get("metrics") or {}
        self.active_vars["latest_candidate"].set(
            "收益 {profit}% | PF {pf} | 回撤 {dd}% | 交易 {trades}\n结果包：{zip}".format(
                profit=latest_metrics.get("total_profit_pct", "n/a"),
                pf=latest_metrics.get("profit_factor", "n/a"),
                dd=latest_metrics.get("max_drawdown_pct", "n/a"),
                trades=latest_metrics.get("trade_count", "n/a"),
                zip=latest.get("latest_backtest", "n/a"),
            )
        )

    def refresh_roadmap(self) -> None:
        roadmap = load_json(PROJECT_ROADMAP, {"items": []})
        items = roadmap.get("items") if isinstance(roadmap, dict) else []
        if not items:
            self.roadmap_var.set("暂无项目标记。")
            return
        lines = []
        for item in items:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or item.get("id") or "unknown"
            status = item.get("status_label") or item.get("status") or "unknown"
            enabled = "已启用" if item.get("enabled") else "未启用"
            summary = item.get("summary") or ""
            current = item.get("current_state") or ""
            next_step = item.get("next_step") or ""
            lines.append(f"{title}：{status}（{enabled}）")
            if summary:
                lines.append(f"说明：{summary}")
            if current:
                lines.append(f"当前：{current}")
            if next_step:
                lines.append(f"下一步：{next_step}")
        self.roadmap_var.set("\n".join(lines) if lines else "暂无项目标记。")

    def refresh_remote_status(self) -> None:
        data = load_json(SERVER_SYNC_REPORT) or load_json(SERVER_STATUS_REPORT)
        if not data:
            self.remote_vars["last_sync"].set("未同步")
            self.remote_vars["server"].set("已配置，暂无报告" if SERVER_SYNC_SETTINGS.exists() else "未配置")
            self.remote_vars["bot"].set("无数据")
            self.remote_vars["validation"].set("无数据")
            self.remote_vars["pairs"].set("无数据")
            return

        remote = data.get("remote") or {}
        validation = data.get("validation") or {}
        after = data.get("remote_status_after") or data.get("remote_status_before") or {}
        source = data.get("source") or {}
        self.remote_vars["last_sync"].set(f"{data.get('generated_at', 'n/a')} | {data.get('mode', 'n/a')}")
        self.remote_vars["server"].set(f"{remote.get('host', 'unknown')} | {remote.get('remote_dir', 'n/a')}")
        self.remote_vars["bot"].set(f"{after.get('bot_status', 'n/a')} | running={after.get('bot_running', 'n/a')}")
        self.remote_vars["validation"].set(f"HTTP {validation.get('http_code', 'n/a')} | healthy={validation.get('ok', False)}")
        self.remote_vars["pairs"].set(short_pairs(source.get("selected_pairs") or [], 8))

    def auto_refresh_status(self) -> None:
        self.refresh_status()
        self.after(5000, self.auto_refresh_status)

    def set_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", tk.END)
        self.output.insert("1.0", text.strip() + "\n")
        self.output.configure(state="disabled")

    def run_and_report(
        self,
        script_name: str,
        arguments: list[str] | None = None,
        label: str | None = None,
        timeout: int = 300,
    ) -> None:
        if self.action_running:
            self.set_output("已有操作正在执行，请等待当前命令完成。")
            return
        self.action_running = True
        self.set_output(f"正在执行：{label or script_name} ...")

        def worker() -> None:
            ok, output = run_powershell(script_name, arguments, timeout=timeout)

            def finish() -> None:
                self.action_running = False
                self.set_output(output or ("执行完成。" if ok else "执行失败。"))
                self.refresh_status()
                if not ok:
                    messagebox.showwarning("OpenClaw 总控中心", output or "命令执行失败。")

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def start_streamlit(self, script_name: str, port: int) -> None:
        script = STREAMLIT_APP_ROOT / script_name
        if not script.exists():
            messagebox.showinfo("OpenClaw 总控中心", f"未找到面板脚本：\n{script}")
            return
        subprocess.Popen(
            [
                "py",
                "-m",
                "streamlit",
                "run",
                str(script),
                "--server.address",
                "127.0.0.1",
                "--server.port",
                str(port),
                "--server.headless",
                "true",
            ],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.set_output(f"已启动 {script_name}，端口：http://127.0.0.1:{port}")

    def sync_to_server(self) -> None:
        self.run_and_report(
            "sync-openclaw-runtime-to-server.ps1",
            [
                "-ProjectRoot",
                str(ROOT),
                "-SettingsPath",
                str(SERVER_SYNC_SETTINGS),
                "-SourceConfigPath",
                str(ACTIVE_CONFIG),
                "-RestartBot",
                "always",
                "-Mode",
                "manual-gui",
            ],
            label="同步当前 active 配置到服务器",
        )

    def install_position_sync(self) -> None:
        self.run_and_report(
            "install-server-position-sync.ps1",
            ["-IntervalSeconds", "60", "-RunOnce"],
            label="安装云端持仓同步",
            timeout=180,
        )

    def sync_to_github(self) -> None:
        self.run_and_report(
            "sync-github-safe.ps1",
            [
                "-ProjectRoot",
                str(ROOT),
                "-Message",
                "chore: sync OpenClaw local updates",
            ],
            label="一键同步 GitHub",
            timeout=300,
        )

    def probe_server_status(self) -> None:
        if self.action_running:
            self.set_output("已有操作正在执行，请等待当前命令完成。")
            return
        self.action_running = True
        self.set_output("正在只读探测服务器状态...")

        def worker() -> None:
            try:
                result = subprocess.run(
                    ["py", str(WORKFLOW_SCRIPT_ROOT / "probe_openclaw_server_status.py")],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=ROOT,
                    timeout=90,
                )
                output = ((result.stdout or "") + (result.stderr or "")).strip()
                ok = result.returncode == 0
            except Exception as exc:
                output = str(exc)
                ok = False

            def finish() -> None:
                self.action_running = False
                self.set_output(output or ("探测完成。" if ok else "探测失败。"))
                self.refresh_status()
                if not ok:
                    messagebox.showwarning("OpenClaw 总控中心", output or "服务器探测失败。")

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def open_path(self, path: Path) -> None:
        if not path.exists():
            messagebox.showinfo("OpenClaw 总控中心", f"未找到文件：\n{path}")
            return
        subprocess.Popen(["notepad", str(path)])


if __name__ == "__main__":
    app = ControlCenter()
    app.mainloop()
