from __future__ import annotations

import json
import subprocess
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk

from runtime_state import daemon_summary


ROOT = Path(__file__).resolve().parent
REPORT_ROOT = ROOT / "reports"
DAEMON_ROOT = REPORT_ROOT / "daemon"
ICON_PATH = ROOT / "assets" / "openclaw-freqtrade-icon.ico"

SERVER_SYNC_REPORT = REPORT_ROOT / "openclaw-server-sync-latest.json"
SERVER_SYNC_REPORT_MD = REPORT_ROOT / "openclaw-server-sync-latest.md"
SERVER_SYNC_SETTINGS = ROOT / "server.openclaw-sync.local.json"

STABLE_SCREEN_JSON = REPORT_ROOT / "openclaw-daily-alt-ml-stable.json"
STABLE_APPROVAL_MD = REPORT_ROOT / "openclaw-auto-approval-stable.md"
STABLE_DYNAMIC_JSON = REPORT_ROOT / "openclaw-dynamic-alt-universe.json"
FAST_DYNAMIC_JSON = REPORT_ROOT / "openclaw-dynamic-alt-universe-fast.json"

README_EN = ROOT / "README.md"
README_ZH = ROOT / "README.zh-CN.md"
OVERVIEW_EN = ROOT / "PROJECT_OVERVIEW.md"
OVERVIEW_ZH = ROOT / "PROJECT_OVERVIEW.zh-CN.md"
GUIDE_PATH = ROOT / "OPENCLAW_FREQTRADE_GUIDE.md"
TUNING_GUIDE_PATH = ROOT / "ALTERNATIVEHUNTER_TUNING_GUIDE_CN.md"
TELEGRAM_GUIDE_PATH = ROOT / "TELEGRAM_TEMPLATE_LAB.md"

DAEMONS = {
    "fast": {
        "title": "Fast",
        "start": "start-openclaw-factor-daemon-fast.ps1",
        "stop": "stop-openclaw-factor-daemon-fast.ps1",
        "log": "factor-daemon-fast.out.log",
    },
    "stable": {
        "title": "Stable",
        "start": "start-openclaw-factor-daemon-stable.ps1",
        "stop": "stop-openclaw-factor-daemon-stable.ps1",
        "log": "factor-daemon-stable.out.log",
    },
    "evolution": {
        "title": "Evolution",
        "start": "start-openclaw-factor-daemon-evolution.ps1",
        "stop": "stop-openclaw-factor-daemon-evolution.ps1",
        "log": "factor-daemon-evolution.out.log",
    },
    "autotune": {
        "title": "Autotune",
        "start": "start-openclaw-factor-daemon-autotune.ps1",
        "stop": "stop-openclaw-factor-daemon-autotune.ps1",
        "log": "factor-daemon-autotune.out.log",
    },
}


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def preview_pairs(pairs: list[str], limit: int = 6) -> str:
    symbols = [pair.split("/")[0] for pair in pairs if pair]
    if not symbols:
        return "none"
    if len(symbols) <= limit:
        return ", ".join(symbols)
    return f"{', '.join(symbols[:limit])} ... total {len(symbols)}"


def run_powershell(script_name: str, arguments: list[str] | None = None) -> tuple[bool, str]:
    script = ROOT / script_name
    command = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)]
    if arguments:
        command.extend(arguments)
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            cwd=ROOT,
            timeout=300,
        )
        output = ((result.stdout or "") + (result.stderr or "")).strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, f"命令超时: {script_name}"
    except Exception as exc:
        return False, str(exc)


class ControlCenter(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("OpenClaw + Freqtrade 总控中心")
        self.geometry("1360x980")
        self.resizable(False, False)
        self.configure(padx=16, pady=16)

        if ICON_PATH.exists():
            try:
                self.iconbitmap(default=str(ICON_PATH))
            except Exception:
                pass

        self.status_vars = {name: tk.StringVar(value="加载中...") for name in DAEMONS}
        self.local_vars = {
            "strategy": tk.StringVar(value="无数据"),
            "best_model": tk.StringVar(value="无数据"),
            "timerange": tk.StringVar(value="无数据"),
            "freshest_data": tk.StringVar(value="无数据"),
            "stable_universe": tk.StringVar(value="无数据"),
            "fast_universe": tk.StringVar(value="无数据"),
            "tradable": tk.StringVar(value="无数据"),
            "observe": tk.StringVar(value="无数据"),
            "top_factor": tk.StringVar(value="无数据"),
        }
        self.remote_vars = {
            "last_sync": tk.StringVar(value="未同步"),
            "server_host": tk.StringVar(value="未配置"),
            "validation": tk.StringVar(value="无数据"),
            "bot_status": tk.StringVar(value="无数据"),
            "remote_openclaw": tk.StringVar(value="无数据"),
            "selected_pairs": tk.StringVar(value="无数据"),
        }
        self.action_running = False
        self.current_action = ""

        self._build()
        self.refresh_status()
        self.after(5000, self.auto_refresh_status)

    def _build(self) -> None:
        ttk.Label(self, text="OpenClaw + Freqtrade 总控中心", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            self,
            text=(
                "本地负责 OpenClaw 训练、筛选、回测与 promotion；"
                "服务器负责 Freqtrade 执行。当前 stable 使用动态币池正式筛选，"
                "fast 使用更宽的动态币池做轻筛。"
            ),
        ).pack(anchor="w", pady=(4, 12))

        local_frame = ttk.LabelFrame(self, text="当前本地模型与币池")
        local_frame.pack(fill="x", pady=(0, 12))
        local_rows = [
            ("策略", "strategy"),
            ("最佳模型", "best_model"),
            ("自动回测窗口", "timerange"),
            ("最新行情时间", "freshest_data"),
            ("Stable 动态币池", "stable_universe"),
            ("Fast 动态币池", "fast_universe"),
            ("当前可交易", "tradable"),
            ("当前观察", "observe"),
            ("主导因子", "top_factor"),
        ]
        for row, (label, key) in enumerate(local_rows):
            ttk.Label(local_frame, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=6)
            ttk.Label(local_frame, textvariable=self.local_vars[key], width=120).grid(row=row, column=1, sticky="w", padx=8, pady=6)

        status_frame = ttk.LabelFrame(self, text="本地后台状态")
        status_frame.pack(fill="x", pady=(0, 12))
        for row, daemon_name in enumerate(("fast", "stable", "evolution", "autotune")):
            ttk.Label(status_frame, text=DAEMONS[daemon_name]["title"]).grid(row=row, column=0, sticky="w", padx=8, pady=8)
            ttk.Label(status_frame, textvariable=self.status_vars[daemon_name], width=120).grid(row=row, column=1, sticky="w", padx=8, pady=8)
        ttk.Button(status_frame, text="刷新", command=self.refresh_status).grid(row=0, column=2, rowspan=4, padx=8, pady=8, sticky="ns")

        remote_frame = ttk.LabelFrame(self, text="服务器同步状态")
        remote_frame.pack(fill="x", pady=(0, 12))
        remote_rows = [
            ("最近同步", "last_sync"),
            ("服务器", "server_host"),
            ("服务器 Bot", "bot_status"),
            ("服务器 OpenClaw", "remote_openclaw"),
            ("同步验证", "validation"),
            ("当前已同步币对", "selected_pairs"),
        ]
        for row, (label, key) in enumerate(remote_rows):
            ttk.Label(remote_frame, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=6)
            ttk.Label(remote_frame, textvariable=self.remote_vars[key], width=120).grid(row=row, column=1, sticky="w", padx=8, pady=6)
        ttk.Button(remote_frame, text="刷新", command=self.refresh_status).grid(row=0, column=2, rowspan=6, padx=8, pady=8, sticky="ns")

        daemon_frame = ttk.LabelFrame(self, text="本地后台控制")
        daemon_frame.pack(fill="x", pady=(0, 12))
        daemon_layout = [
            ("启动 Fast", "fast", "start"),
            ("停止 Fast", "fast", "stop"),
            ("启动 Stable", "stable", "start"),
            ("停止 Stable", "stable", "stop"),
            ("启动 Evolution", "evolution", "start"),
            ("停止 Evolution", "evolution", "stop"),
            ("启动 Autotune", "autotune", "start"),
            ("停止 Autotune", "autotune", "stop"),
        ]
        for index, (label, daemon_name, action) in enumerate(daemon_layout):
            row, col = divmod(index, 4)
            script_name = DAEMONS[daemon_name][action]
            ttk.Button(
                daemon_frame,
                text=label,
                command=lambda s=script_name, d=label: self.run_and_report(s, label=d),
            ).grid(row=row, column=col, padx=8, pady=8)

        server_frame = ttk.LabelFrame(self, text="服务器联通与同步")
        server_frame.pack(fill="x", pady=(0, 12))
        server_buttons = [
            (
                "手动同步到服务器",
                lambda: self.run_and_report(
                    "sync-openclaw-runtime-to-server.ps1",
                    [
                        "-ProjectRoot",
                        str(ROOT),
                        "-SettingsPath",
                        str(SERVER_SYNC_SETTINGS),
                        "-SourceConfigPath",
                        str(ROOT / "user_data" / "config.openclaw-auto.json"),
                        "-RestartBot",
                        "if-running",
                        "-Mode",
                        "manual-gui",
                    ],
                    label="手动同步到服务器",
                ),
            ),
            ("打开同步报告", lambda: self.open_path(SERVER_SYNC_REPORT_MD)),
            ("打开同步 JSON", lambda: self.open_path(SERVER_SYNC_REPORT)),
            ("打开服务器交易台", lambda: webbrowser.open("https://www.duskrain.cn/")),
            ("打开服务器 API Ping", lambda: webbrowser.open("https://www.duskrain.cn/api/v1/ping")),
            ("打开认证门户", lambda: webbrowser.open("https://duskrain.cn/authelia/")),
        ]
        for index, (label, callback) in enumerate(server_buttons):
            row, col = divmod(index, 3)
            ttk.Button(server_frame, text=label, command=callback).grid(row=row, column=col, padx=8, pady=8)

        tools_frame = ttk.LabelFrame(self, text="面板与机器人")
        tools_frame.pack(fill="x", pady=(0, 12))
        buttons = [
            ("启动只读看板", lambda: self.run_detached_ps1("start-factor-lab.ps1")),
            ("打开看板 (8501)", lambda: webbrowser.open("http://127.0.0.1:8501")),
            ("启动策略调试面板", lambda: self.run_detached_cmd("Launch Strategy Debug Lab.cmd")),
            ("打开调试面板 (8502)", lambda: webbrowser.open("http://127.0.0.1:8502")),
            ("启动 Telegram 模板面板", lambda: self.run_detached_cmd("Launch Telegram Template Lab.cmd")),
            ("打开 Telegram 模板 (8503)", lambda: webbrowser.open("http://127.0.0.1:8503")),
            ("启动山寨 Bot", lambda: self.run_and_report("start-openclaw-auto-bot.ps1", label="启动山寨 Bot")),
            ("打开山寨 API (8081)", lambda: webbrowser.open("http://127.0.0.1:8081")),
            ("启动主流 Bot", lambda: self.run_and_report("start-mainstream-auto-bot.ps1", label="启动主流 Bot")),
            ("打开主流 API (8082)", lambda: webbrowser.open("http://127.0.0.1:8082")),
            ("打开报告目录", lambda: subprocess.Popen(["explorer", str(REPORT_ROOT)])),
            ("打开项目说明", lambda: self.open_path(GUIDE_PATH)),
            ("打开参数说明", lambda: self.open_path(TUNING_GUIDE_PATH)),
            ("打开 Telegram 说明", lambda: self.open_path(TELEGRAM_GUIDE_PATH)),
            ("打开 Stable 审批", lambda: self.open_path(STABLE_APPROVAL_MD)),
            ("打开项目双语介绍", lambda: self.open_path(OVERVIEW_ZH)),
        ]
        for index, (label, callback) in enumerate(buttons):
            row, col = divmod(index, 4)
            ttk.Button(tools_frame, text=label, command=callback).grid(row=row, column=col, padx=8, pady=8)

        docs_frame = ttk.LabelFrame(self, text="公开文档")
        docs_frame.pack(fill="x", pady=(0, 12))
        docs_buttons = [
            ("README (EN)", lambda: self.open_path(README_EN)),
            ("README (中文)", lambda: self.open_path(README_ZH)),
            ("Overview (EN)", lambda: self.open_path(OVERVIEW_EN)),
            ("Overview (中文)", lambda: self.open_path(OVERVIEW_ZH)),
        ]
        for index, (label, callback) in enumerate(docs_buttons):
            ttk.Button(docs_frame, text=label, command=callback).grid(row=0, column=index, padx=8, pady=8)

        logs_frame = ttk.LabelFrame(self, text="日志")
        logs_frame.pack(fill="x", pady=(0, 12))
        log_buttons = [
            ("Fast 日志", "factor-daemon-fast.out.log"),
            ("Stable 日志", "factor-daemon-stable.out.log"),
            ("Evolution 日志", "factor-daemon-evolution.out.log"),
            ("Autotune 日志", "factor-daemon-autotune.out.log"),
        ]
        for col, (label, filename) in enumerate(log_buttons):
            ttk.Button(logs_frame, text=label, command=lambda f=filename: self.open_log(f)).grid(row=0, column=col, padx=8, pady=8)

        output_frame = ttk.LabelFrame(self, text="最近操作")
        output_frame.pack(fill="both", expand=True)
        self.output = tk.Text(output_frame, height=14, wrap="word")
        self.output.pack(fill="both", expand=True, padx=8, pady=8)
        self.output.insert("1.0", "已就绪。\n")
        self.output.configure(state="disabled")

    def refresh_status(self) -> None:
        for name in self.status_vars:
            self.status_vars[name].set(daemon_summary(f"factor-daemon-{name}"))
        self.refresh_local_status()
        self.refresh_remote_status()

    def refresh_local_status(self) -> None:
        stable_data = load_json(STABLE_SCREEN_JSON) or {}
        stable_dynamic = load_json(STABLE_DYNAMIC_JSON) or {}
        fast_dynamic = load_json(FAST_DYNAMIC_JSON) or {}

        auto_backtest = stable_data.get("auto_backtest") or {}
        best_model = stable_data.get("best_model") or {}
        top_factors = stable_data.get("top_factors") or []
        tradable = [item.get("Pair", "") for item in stable_data.get("tradable") or []]
        observe = [item.get("Pair", "") for item in stable_data.get("observe") or []]

        stable_universe_pairs = stable_dynamic.get("selected_pairs") or []
        fast_universe_pairs = fast_dynamic.get("selected_pairs") or []

        stable_universe_text = "none"
        if stable_dynamic:
            stable_universe_text = (
                f"top_n={stable_dynamic.get('top_n', 'n/a')} | "
                f"{len(stable_universe_pairs)} pairs | "
                f"{preview_pairs(stable_universe_pairs, limit=5)}"
            )

        fast_universe_text = "none"
        if fast_dynamic:
            fast_universe_text = (
                f"top_n={fast_dynamic.get('top_n', 'n/a')} | "
                f"{len(fast_universe_pairs)} pairs | "
                f"{preview_pairs(fast_universe_pairs, limit=5)}"
            )

        top_factor_text = "none"
        if top_factors:
            first_factor = top_factors[0]
            top_factor_text = f"{first_factor.get('Feature', 'n/a')} | weight={first_factor.get('WeightedImportance', 'n/a')}"

        timerange = auto_backtest.get("timerange", "n/a")
        timerange_mode = auto_backtest.get("timerange_mode", "n/a")
        freshest = auto_backtest.get("freshest_market_timestamp") or stable_dynamic.get("freshest_market_timestamp") or "n/a"

        self.local_vars["strategy"].set(str(stable_data.get("strategy") or "AlternativeHunter"))
        self.local_vars["best_model"].set(f"{best_model.get('model', 'n/a')} | weight={best_model.get('weight', 'n/a')}")
        self.local_vars["timerange"].set(f"{timerange} ({timerange_mode})")
        self.local_vars["freshest_data"].set(str(freshest))
        self.local_vars["stable_universe"].set(stable_universe_text)
        self.local_vars["fast_universe"].set(fast_universe_text)
        self.local_vars["tradable"].set(preview_pairs(tradable, limit=6))
        self.local_vars["observe"].set(preview_pairs(observe, limit=6))
        self.local_vars["top_factor"].set(top_factor_text)

    def refresh_remote_status(self) -> None:
        data = load_json(SERVER_SYNC_REPORT)
        if not data:
            self.remote_vars["last_sync"].set("未同步")
            self.remote_vars["server_host"].set("未配置" if not SERVER_SYNC_SETTINGS.exists() else "已配置，暂无报告")
            self.remote_vars["validation"].set("无数据")
            self.remote_vars["bot_status"].set("无数据")
            self.remote_vars["remote_openclaw"].set("无数据")
            self.remote_vars["selected_pairs"].set("无数据")
            return

        generated_at = str(data.get("generated_at") or "未知")
        remote = data.get("remote") or {}
        validation = data.get("validation") or {}
        after = data.get("remote_status_after") or {}
        before = data.get("remote_status_before") or {}
        source = data.get("source") or {}
        selected_pairs = source.get("selected_pairs") or []

        self.remote_vars["last_sync"].set(f"{generated_at} | mode={data.get('mode', 'n/a')}")
        self.remote_vars["server_host"].set(f"{remote.get('host', 'unknown')} | dir={remote.get('remote_dir', 'n/a')}")
        self.remote_vars["validation"].set(f"HTTP {validation.get('http_code', 'n/a')} | healthy={validation.get('ok', False)}")
        self.remote_vars["bot_status"].set(f"{after.get('bot_status', 'n/a')} | running={after.get('bot_running', 'n/a')}")
        self.remote_vars["remote_openclaw"].set(str(before.get("openclaw_running", False)))
        self.remote_vars["selected_pairs"].set(preview_pairs(selected_pairs, limit=8))

    def auto_refresh_status(self) -> None:
        self.refresh_status()
        self.after(5000, self.auto_refresh_status)

    def set_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", tk.END)
        self.output.insert("1.0", text.strip() + "\n")
        self.output.configure(state="disabled")

    def run_and_report(self, script_name: str, arguments: list[str] | None = None, label: str | None = None) -> None:
        if self.action_running:
            self.set_output("已有操作在执行，请等待当前命令完成。")
            return

        display_name = label or script_name
        self.action_running = True
        self.current_action = display_name
        self.set_output(f"正在执行 {display_name} ...")
        self.after(25000, self.reset_if_stuck)

        def worker() -> None:
            ok, output = run_powershell(script_name, arguments)

            def finish() -> None:
                self.action_running = False
                self.current_action = ""
                self.set_output(output or ("执行完成。" if ok else "执行失败。"))
                self.refresh_status()
                if ok:
                    self.after(1200, self.refresh_status)
                    self.after(3000, self.refresh_status)
                else:
                    messagebox.showwarning("OpenClaw 总控中心", output or "命令执行失败。")

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def reset_if_stuck(self) -> None:
        if self.action_running:
            action = self.current_action or "当前命令"
            self.action_running = False
            self.current_action = ""
            self.set_output(f"{action} 长时间未返回，GUI 已自动解锁。请检查状态或日志。")
            self.refresh_status()

    def run_detached_ps1(self, script_name: str) -> None:
        script = ROOT / script_name
        subprocess.Popen(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)], cwd=ROOT)
        self.set_output(f"已启动 {script_name}")

    def run_detached_cmd(self, command_name: str) -> None:
        command = ROOT / command_name
        subprocess.Popen(["cmd", "/c", str(command)], cwd=ROOT)
        self.set_output(f"已启动 {command_name}")

    def open_log(self, file_name: str) -> None:
        path = DAEMON_ROOT / file_name
        if not path.exists():
            messagebox.showinfo("OpenClaw 总控中心", f"未找到日志文件：\n{path}")
            return
        subprocess.Popen(["notepad", str(path)])

    def open_path(self, path: Path) -> None:
        if not path.exists():
            messagebox.showinfo("OpenClaw 总控中心", f"未找到文件：\n{path}")
            return
        subprocess.Popen(["notepad", str(path)])


if __name__ == "__main__":
    app = ControlCenter()
    app.mainloop()
