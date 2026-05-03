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
SERVER_STATUS_REPORT = REPORT_ROOT / "openclaw-server-status-latest.json"
SERVER_SYNC_SETTINGS = ROOT / "server.openclaw-sync.local.json"

STABLE_APPROVAL_MD = REPORT_ROOT / "openclaw-auto-approval-stable.md"
README_EN = ROOT / "README.md"
README_ZH = ROOT / "README.zh-CN.md"
OVERVIEW_EN = ROOT / "PROJECT_OVERVIEW.md"
OVERVIEW_ZH = ROOT / "PROJECT_OVERVIEW.zh-CN.md"
GUIDE_PATH = ROOT / "OPENCLAW_FREQTRADE_GUIDE.md"
TUNING_GUIDE_PATH = ROOT / "ALTERNATIVEHUNTER_TUNING_GUIDE_CN.md"
TELEGRAM_GUIDE_PATH = ROOT / "TELEGRAM_TEMPLATE_LAB.md"
ML_REPORT_DIR = ROOT / "user_data" / "reports" / "ml"

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


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8-sig")
        return json.loads(text) if text.strip() else None
    except Exception:
        return None


def preview_pairs(pairs: list[str], limit: int = 8) -> str:
    symbols = [pair.split("/")[0] for pair in pairs if pair]
    if not symbols:
        return "无数据"
    if len(symbols) <= limit:
        return ", ".join(symbols)
    return f"{', '.join(symbols[:limit])} ... total {len(symbols)}"


def run_powershell(script_name: str, arguments: list[str] | None = None, timeout: int = 300) -> tuple[bool, str]:
    script = ROOT / script_name
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
        self.geometry("1420x900")
        self.minsize(1180, 760)
        self.configure(bg="#eef5f8", padx=18, pady=16)

        if ICON_PATH.exists():
            try:
                self.iconbitmap(default=str(ICON_PATH))
            except Exception:
                pass

        self._configure_style()
        self.status_vars = {name: tk.StringVar(value="加载中...") for name in DAEMONS}
        self.remote_vars = {
            "last_sync": tk.StringVar(value="未同步"),
            "server_host": tk.StringVar(value="未配置"),
            "bot_status": tk.StringVar(value="无数据"),
            "remote_openclaw": tk.StringVar(value="无数据"),
            "validation": tk.StringVar(value="无数据"),
            "selected_pairs": tk.StringVar(value="无数据"),
        }
        self.action_running = False
        self.current_action = ""

        self._build()
        self.refresh_status()
        self.after(5000, self.auto_refresh_status)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        bg = "#eef5f8"
        panel = "#ffffff"
        border = "#c9dce5"
        text = "#102033"
        muted = "#4d6273"
        accent = "#1f8fb8"
        accent_hover = "#176f91"

        style.configure(".", font=("Microsoft YaHei UI", 10))
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=text)
        style.configure("Header.TFrame", background="#dff4f8")
        style.configure("Title.TLabel", background="#dff4f8", foreground=text, font=("Microsoft YaHei UI", 20, "bold"))
        style.configure("Subtitle.TLabel", background="#dff4f8", foreground=muted, font=("Microsoft YaHei UI", 10))
        style.configure("TLabelframe", background=panel, bordercolor=border, relief="solid")
        style.configure("TLabelframe.Label", background=bg, foreground=text, font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Value.TLabel", background=panel, foreground=text)
        style.configure("Key.TLabel", background=panel, foreground="#2c4558", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Status.TLabel", background=panel, foreground="#12384a")
        style.configure("TButton", padding=(12, 7), borderwidth=1, relief="solid")
        style.map("TButton", background=[("active", "#e5f7fb")])
        style.configure("Accent.TButton", background=accent, foreground="white", bordercolor=accent, padding=(14, 8))
        style.map("Accent.TButton", background=[("active", accent_hover)], foreground=[("active", "white")])
        style.configure("Danger.TButton", background="#f3dddd", foreground="#8a1f1f", bordercolor="#e5b9b9")

    def _build(self) -> None:
        header = ttk.Frame(self, style="Header.TFrame")
        header.pack(fill="x", pady=(0, 14))
        ttk.Label(header, text="OpenClaw + Freqtrade 总控中心", style="Title.TLabel").pack(anchor="w", padx=16, pady=(14, 2))
        ttk.Label(
            header,
            text="本地负责训练、筛选、回测与 promotion；服务器负责 Freqtrade 执行。加速模式会重启 fast/stable 并缩短训练间隔。",
            style="Subtitle.TLabel",
        ).pack(anchor="w", padx=16, pady=(0, 14))

        self._build_daemon_status_frame()
        self._build_remote_frame()
        self._build_daemon_control_frame()
        self._build_server_frame()
        self._build_tools_frame()
        self._build_docs_frame()
        self._build_logs_frame()
        self._build_output_frame()

    def _build_daemon_status_frame(self) -> None:
        frame = ttk.LabelFrame(self, text="本地后台状态")
        frame.pack(fill="x", pady=(0, 12))
        for row, daemon_name in enumerate(("fast", "stable", "evolution", "autotune")):
            ttk.Label(frame, text=DAEMONS[daemon_name]["title"], style="Key.TLabel", width=20).grid(row=row, column=0, sticky="w", padx=12, pady=7)
            ttk.Label(frame, textvariable=self.status_vars[daemon_name], style="Status.TLabel", width=130).grid(row=row, column=1, sticky="w", padx=8, pady=7)
        ttk.Button(frame, text="刷新", style="Accent.TButton", command=self.refresh_status).grid(row=0, column=2, rowspan=4, padx=12, pady=10, sticky="ns")
        frame.columnconfigure(1, weight=1)

    def _build_remote_frame(self) -> None:
        frame = ttk.LabelFrame(self, text="服务器同步状态")
        frame.pack(fill="x", pady=(0, 12))
        rows = [
            ("最近同步/探测", "last_sync"),
            ("服务器", "server_host"),
            ("服务器 Bot", "bot_status"),
            ("服务器 OpenClaw", "remote_openclaw"),
            ("同步验证", "validation"),
            ("当前已同步币对", "selected_pairs"),
        ]
        for row, (label, key) in enumerate(rows):
            ttk.Label(frame, text=label, style="Key.TLabel", width=20).grid(row=row, column=0, sticky="w", padx=12, pady=5)
            ttk.Label(frame, textvariable=self.remote_vars[key], style="Value.TLabel", width=130).grid(row=row, column=1, sticky="w", padx=8, pady=5)
        ttk.Button(frame, text="刷新", style="Accent.TButton", command=self.refresh_status).grid(row=0, column=2, rowspan=6, padx=12, pady=10, sticky="ns")
        frame.columnconfigure(1, weight=1)

    def _build_daemon_control_frame(self) -> None:
        frame = ttk.LabelFrame(self, text="本地后台控制")
        frame.pack(fill="x", pady=(0, 12))

        buttons = [
            ("启动 Fast", "fast", "start", None),
            ("停止 Fast", "fast", "stop", "Danger.TButton"),
            ("启动 Stable", "stable", "start", None),
            ("停止 Stable", "stable", "stop", "Danger.TButton"),
            ("启动 Evolution", "evolution", "start", None),
            ("停止 Evolution", "evolution", "stop", "Danger.TButton"),
            ("启动 Autotune", "autotune", "start", None),
            ("停止 Autotune", "autotune", "stop", "Danger.TButton"),
        ]
        for index, (label, daemon_name, action, style_name) in enumerate(buttons):
            row, col = divmod(index, 4)
            script_name = DAEMONS[daemon_name][action]
            ttk.Button(
                frame,
                text=label,
                style=style_name or "TButton",
                command=lambda s=script_name, d=label: self.run_and_report(s, label=d),
            ).grid(row=row, column=col, padx=10, pady=8, sticky="w")

        ttk.Separator(frame).grid(row=2, column=0, columnspan=4, sticky="ew", padx=10, pady=(8, 4))
        ttk.Button(
            frame,
            text="开启训练加速模式（Fast 20m / Stable 90m）",
            style="Accent.TButton",
            command=lambda: self.run_and_report("set-openclaw-training-speed.ps1", ["-Mode", "boost"], label="开启训练加速模式"),
        ).grid(row=3, column=0, columnspan=2, padx=10, pady=8, sticky="w")
        ttk.Button(
            frame,
            text="恢复常规训练频率（Fast 60m / Stable 180m）",
            command=lambda: self.run_and_report("set-openclaw-training-speed.ps1", ["-Mode", "normal"], label="恢复常规训练频率"),
        ).grid(row=3, column=2, columnspan=2, padx=10, pady=8, sticky="w")

    def _build_server_frame(self) -> None:
        frame = ttk.LabelFrame(self, text="服务器联通与同步")
        frame.pack(fill="x", pady=(0, 12))
        buttons = [
            ("上传已审批因子到服务器", self.sync_to_server),
            ("打开同步报告", lambda: self.open_path(SERVER_SYNC_REPORT_MD)),
            ("打开同步 JSON", lambda: self.open_path(SERVER_SYNC_REPORT)),
            ("只读探测服务器", self.probe_server_status),
            ("打开服务器交易台", lambda: webbrowser.open("https://www.duskrain.cn/")),
            ("打开服务器 API Ping", lambda: webbrowser.open("https://www.duskrain.cn/api/v1/ping")),
            ("打开认证门户", lambda: webbrowser.open("https://duskrain.cn/authelia/")),
        ]
        for index, (label, callback) in enumerate(buttons):
            row, col = divmod(index, 4)
            ttk.Button(frame, text=label, command=callback).grid(row=row, column=col, padx=10, pady=8, sticky="w")

    def _build_tools_frame(self) -> None:
        frame = ttk.LabelFrame(self, text="面板与机器人")
        frame.pack(fill="x", pady=(0, 12))
        buttons = [
            ("启动只读看板", lambda: self.start_streamlit("factor_lab.py", 8501)),
            ("打开看板 (8501)", lambda: webbrowser.open("http://127.0.0.1:8501")),
            ("启动策略调试面板", lambda: self.start_streamlit("strategy_debug_lab.py", 8502)),
            ("打开调试面板 (8502)", lambda: webbrowser.open("http://127.0.0.1:8502")),
            ("启动 Telegram 模板面板", lambda: self.start_streamlit("telegram_template_lab.py", 8503)),
            ("打开 Telegram 模板 (8503)", lambda: webbrowser.open("http://127.0.0.1:8503")),
            ("测试山寨 Bot 启动保护", lambda: self.run_and_report("start-openclaw-auto-bot.ps1", label="测试山寨 Bot 启动保护")),
            ("打开山寨 API (8081)", lambda: webbrowser.open("http://127.0.0.1:8081")),
            ("启动主流 Bot", lambda: self.run_and_report("start-mainstream-auto-bot.ps1", label="启动主流 Bot")),
            ("打开主流 API (8082)", lambda: webbrowser.open("http://127.0.0.1:8082")),
            ("打开报告目录", lambda: subprocess.Popen(["explorer", str(REPORT_ROOT)])),
            ("打开历史 ML 报告", lambda: subprocess.Popen(["explorer", str(ML_REPORT_DIR)])),
            ("打开项目说明", lambda: self.open_path(GUIDE_PATH)),
            ("打开参数说明", lambda: self.open_path(TUNING_GUIDE_PATH)),
            ("打开 Telegram 说明", lambda: self.open_path(TELEGRAM_GUIDE_PATH)),
            ("打开 Stable 审批", lambda: self.open_path(STABLE_APPROVAL_MD)),
        ]
        for index, (label, callback) in enumerate(buttons):
            row, col = divmod(index, 4)
            ttk.Button(frame, text=label, command=callback).grid(row=row, column=col, padx=10, pady=8, sticky="w")

    def _build_docs_frame(self) -> None:
        frame = ttk.LabelFrame(self, text="公开文档")
        frame.pack(fill="x", pady=(0, 12))
        buttons = [
            ("README (EN)", lambda: self.open_path(README_EN)),
            ("README (中文)", lambda: self.open_path(README_ZH)),
            ("Overview (EN)", lambda: self.open_path(OVERVIEW_EN)),
            ("Overview (中文)", lambda: self.open_path(OVERVIEW_ZH)),
        ]
        for index, (label, callback) in enumerate(buttons):
            ttk.Button(frame, text=label, command=callback).grid(row=0, column=index, padx=10, pady=8, sticky="w")

    def _build_logs_frame(self) -> None:
        frame = ttk.LabelFrame(self, text="日志")
        frame.pack(fill="x", pady=(0, 12))
        buttons = [
            ("Fast 日志", "factor-daemon-fast.out.log"),
            ("Stable 日志", "factor-daemon-stable.out.log"),
            ("Evolution 日志", "factor-daemon-evolution.out.log"),
            ("Autotune 日志", "factor-daemon-autotune.out.log"),
            ("长历史回补日志", "data-refresh/long-history-backfill.out.log"),
        ]
        for col, (label, filename) in enumerate(buttons):
            ttk.Button(frame, text=label, command=lambda f=filename: self.open_log(f)).grid(row=0, column=col, padx=10, pady=8, sticky="w")

    def _build_output_frame(self) -> None:
        frame = ttk.LabelFrame(self, text="最近操作")
        frame.pack(fill="both", expand=True)
        self.output = tk.Text(
            frame,
            height=10,
            wrap="word",
            bg="#0f172a",
            fg="#dbeafe",
            insertbackground="#dbeafe",
            relief="flat",
            padx=12,
            pady=10,
            font=("Consolas", 10),
        )
        self.output.pack(fill="both", expand=True, padx=10, pady=10)
        self.output.insert("1.0", "已就绪。\n")
        self.output.configure(state="disabled")

    def refresh_status(self) -> None:
        for name in self.status_vars:
            self.status_vars[name].set(daemon_summary(f"factor-daemon-{name}"))
        self.refresh_remote_status()

    def refresh_remote_status(self) -> None:
        data = load_json(SERVER_SYNC_REPORT) or load_json(SERVER_STATUS_REPORT)
        if not data:
            self.remote_vars["last_sync"].set("未同步")
            self.remote_vars["server_host"].set("已配置，暂无报告" if SERVER_SYNC_SETTINGS.exists() else "未配置")
            self.remote_vars["validation"].set("无数据")
            self.remote_vars["bot_status"].set("无数据")
            self.remote_vars["remote_openclaw"].set("无数据")
            self.remote_vars["selected_pairs"].set("无数据")
            return

        generated_at = str(data.get("generated_at") or "未知")
        remote = data.get("remote") or {}
        validation = data.get("validation") or {}
        after = data.get("remote_status_after") or data.get("remote_status_before") or {}
        before = data.get("remote_status_before") or after
        source = data.get("source") or {}
        selected_pairs = source.get("selected_pairs") or []

        self.remote_vars["last_sync"].set(f"{generated_at} | mode={data.get('mode', 'n/a')}")
        self.remote_vars["server_host"].set(f"{remote.get('host', 'unknown')} | dir={remote.get('remote_dir', 'n/a')}")
        self.remote_vars["bot_status"].set(f"{after.get('bot_status', 'n/a')} | running={after.get('bot_running', 'n/a')}")
        self.remote_vars["remote_openclaw"].set(str(bool(str(before.get("openclaw_processes", "")).strip())))
        self.remote_vars["validation"].set(f"HTTP {validation.get('http_code', 'n/a')} | healthy={validation.get('ok', False)}")
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

        def worker() -> None:
            ok, output = run_powershell(script_name, arguments)

            def finish() -> None:
                self.action_running = False
                self.current_action = ""
                self.set_output(output or ("执行完成。" if ok else "执行失败。"))
                self.refresh_status()
                self.after(1500, self.refresh_status)
                if not ok:
                    messagebox.showwarning("OpenClaw 总控中心", output or "命令执行失败。")

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def start_streamlit(self, script_name: str, port: int) -> None:
        script = ROOT / script_name
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
                str(ROOT / "user_data" / "config.openclaw-auto.json"),
                "-RestartBot",
                "always",
                "-Mode",
                "manual-gui",
            ],
            label="上传已审批因子到服务器",
        )

    def probe_server_status(self) -> None:
        if self.action_running:
            self.set_output("已有操作在执行，请等待当前命令完成。")
            return

        self.action_running = True
        self.current_action = "只读探测服务器"
        self.set_output("正在只读探测服务器状态...")

        def worker() -> None:
            try:
                result = subprocess.run(
                    ["py", str(ROOT / "probe_openclaw_server_status.py")],
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
                self.current_action = ""
                self.set_output(output or ("探测完成。" if ok else "探测失败。"))
                self.refresh_status()
                if not ok:
                    messagebox.showwarning("OpenClaw 总控中心", output or "服务器探测失败。")

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

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
