from __future__ import annotations

import json
import subprocess
import sys
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk


ROOT = Path(__file__).resolve().parent
REPORT_ROOT = ROOT / "reports"
DAEMON_ROOT = REPORT_ROOT / "daemon"
ICON_PATH = ROOT / "assets" / "openclaw-freqtrade-icon.ico"


def run_powershell(script_name: str) -> tuple[bool, str]:
    script = ROOT / script_name
    try:
        result = subprocess.run(
            [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=120,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return result.returncode == 0, output.strip()
    except Exception as exc:
        return False, str(exc)


def load_status(name: str) -> dict | None:
    path = DAEMON_ROOT / f"{name}-status.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def daemon_summary(name: str) -> str:
    status = load_status(name)
    if not status:
        return "未启动"
    text = f"{status.get('status', 'unknown')} | 下次: {status.get('next_run_after', 'N/A')}"
    if status.get("error"):
        text += f" | 错误: {status['error']}"
    return text


class ControlCenter(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("OpenClaw 总控中心")
        self.geometry("920x700")
        self.resizable(False, False)
        self.configure(padx=16, pady=16)
        if ICON_PATH.exists():
            try:
                self.iconbitmap(default=str(ICON_PATH))
            except Exception:
                pass

        self.fast_var = tk.StringVar()
        self.stable_var = tk.StringVar()
        self.evolution_var = tk.StringVar()
        self.output_var = tk.StringVar(value="就绪。")

        self._build()
        self.refresh_status()

    def _build(self) -> None:
        title = ttk.Label(self, text="OpenClaw + Freqtrade 总控中心", font=("Segoe UI", 18, "bold"))
        title.pack(anchor="w")

        subtitle = ttk.Label(
            self,
            text="Fast 负责轻量筛选，Stable 负责正式多模型、回测和自动更新，Evolution 保留为手动研究层。",
        )
        subtitle.pack(anchor="w", pady=(4, 12))

        status_frame = ttk.LabelFrame(self, text="后台状态")
        status_frame.pack(fill="x", pady=(0, 12))

        ttk.Label(status_frame, text="Fast 轻量筛选").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        ttk.Label(status_frame, textvariable=self.fast_var, width=80).grid(row=0, column=1, sticky="w", padx=8, pady=8)
        ttk.Label(status_frame, text="Stable 正式更新").grid(row=1, column=0, sticky="w", padx=8, pady=8)
        ttk.Label(status_frame, textvariable=self.stable_var, width=80).grid(row=1, column=1, sticky="w", padx=8, pady=8)
        ttk.Label(status_frame, text="Evolution 研究层").grid(row=2, column=0, sticky="w", padx=8, pady=8)
        ttk.Label(status_frame, textvariable=self.evolution_var, width=80).grid(row=2, column=1, sticky="w", padx=8, pady=8)
        ttk.Button(status_frame, text="刷新状态", command=self.refresh_status).grid(row=0, column=2, rowspan=3, padx=8, pady=8)

        daemon_frame = ttk.LabelFrame(self, text="后台控制")
        daemon_frame.pack(fill="x", pady=(0, 12))

        ttk.Button(daemon_frame, text="启动 Fast", command=lambda: self.run_and_report("start-openclaw-factor-daemon-fast.ps1")).grid(row=0, column=0, padx=8, pady=8)
        ttk.Button(daemon_frame, text="停止 Fast", command=lambda: self.run_and_report("stop-openclaw-factor-daemon-fast.ps1")).grid(row=0, column=1, padx=8, pady=8)
        ttk.Button(daemon_frame, text="启动 Stable", command=lambda: self.run_and_report("start-openclaw-factor-daemon-stable.ps1")).grid(row=0, column=2, padx=8, pady=8)
        ttk.Button(daemon_frame, text="停止 Stable", command=lambda: self.run_and_report("stop-openclaw-factor-daemon-stable.ps1")).grid(row=0, column=3, padx=8, pady=8)
        ttk.Button(daemon_frame, text="启动 Evolution", command=lambda: self.run_and_report("start-openclaw-factor-daemon-evolution.ps1")).grid(row=1, column=0, padx=8, pady=8)
        ttk.Button(daemon_frame, text="停止 Evolution", command=lambda: self.run_and_report("stop-openclaw-factor-daemon-evolution.ps1")).grid(row=1, column=1, padx=8, pady=8)

        tools_frame = ttk.LabelFrame(self, text="工具")
        tools_frame.pack(fill="x", pady=(0, 12))

        ttk.Button(tools_frame, text="打开看板", command=lambda: self.run_detached("start-factor-lab.ps1")).grid(row=0, column=0, padx=8, pady=8)
        ttk.Button(tools_frame, text="打开看板网址", command=lambda: webbrowser.open("http://127.0.0.1:8501")).grid(row=0, column=1, padx=8, pady=8)
        ttk.Button(tools_frame, text="启动交易机器人", command=lambda: self.run_and_report("start-openclaw-auto-bot.ps1")).grid(row=0, column=2, padx=8, pady=8)
        ttk.Button(tools_frame, text="打开 Bot API", command=lambda: webbrowser.open("http://127.0.0.1:8081")).grid(row=0, column=3, padx=8, pady=8)
        ttk.Button(tools_frame, text="打开报告目录", command=lambda: subprocess.Popen(["explorer", str(REPORT_ROOT)])).grid(row=1, column=0, padx=8, pady=8)
        ttk.Button(tools_frame, text="打开说明书", command=lambda: subprocess.Popen(["notepad", str(ROOT / "OPENCLAW_FREQTRADE_GUIDE.md")])).grid(row=1, column=1, padx=8, pady=8)
        ttk.Button(tools_frame, text="打开 Fast 日志", command=lambda: self.open_log("factor-daemon-fast.out.log")).grid(row=1, column=2, padx=8, pady=8)
        ttk.Button(tools_frame, text="打开 Stable 日志", command=lambda: self.open_log("factor-daemon-stable.out.log")).grid(row=1, column=3, padx=8, pady=8)
        ttk.Button(tools_frame, text="打开 Evolution 日志", command=lambda: self.open_log("factor-daemon-evolution.out.log")).grid(row=2, column=0, padx=8, pady=8)
        ttk.Button(tools_frame, text="开机自启动一次", command=lambda: self.run_and_report("start-openclaw-on-login.ps1")).grid(row=2, column=1, padx=8, pady=8)

        output_frame = ttk.LabelFrame(self, text="最近操作")
        output_frame.pack(fill="both", expand=True)
        self.output = tk.Text(output_frame, height=16, wrap="word")
        self.output.pack(fill="both", expand=True, padx=8, pady=8)
        self.output.insert("1.0", "就绪。\n")
        self.output.configure(state="disabled")

    def refresh_status(self) -> None:
        self.fast_var.set(daemon_summary("factor-daemon-fast"))
        self.stable_var.set(daemon_summary("factor-daemon-stable"))
        self.evolution_var.set(daemon_summary("factor-daemon-evolution"))

    def set_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", tk.END)
        self.output.insert("1.0", text.strip() + "\n")
        self.output.configure(state="disabled")

    def run_and_report(self, script_name: str) -> None:
        ok, output = run_powershell(script_name)
        self.set_output(output or ("已完成。" if ok else "执行失败。"))
        self.refresh_status()
        if not ok:
            messagebox.showwarning("OpenClaw 总控中心", output or "命令执行失败。")

    def run_detached(self, script_name: str) -> None:
        script = ROOT / script_name
        subprocess.Popen(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)],
            cwd=ROOT,
        )
        self.set_output(f"已启动 {script_name}")

    def open_log(self, file_name: str) -> None:
        path = DAEMON_ROOT / file_name
        if not path.exists():
            messagebox.showinfo("OpenClaw 总控中心", f"日志不存在：\n{path}")
            return
        subprocess.Popen(["notepad", str(path)])


if __name__ == "__main__":
    app = ControlCenter()
    app.mainloop()
