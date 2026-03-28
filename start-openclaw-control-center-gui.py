from __future__ import annotations

import json
import os
import subprocess
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk


ROOT = Path(__file__).resolve().parent
REPORT_ROOT = ROOT / "reports"
DAEMON_ROOT = REPORT_ROOT / "daemon"
ICON_PATH = ROOT / "assets" / "openclaw-freqtrade-icon.ico"

DAEMONS = {
    "fast": {
        "start": "start-openclaw-factor-daemon-fast.ps1",
        "stop": "stop-openclaw-factor-daemon-fast.ps1",
        "log": "factor-daemon-fast.out.log",
    },
    "stable": {
        "start": "start-openclaw-factor-daemon-stable.ps1",
        "stop": "stop-openclaw-factor-daemon-stable.ps1",
        "log": "factor-daemon-stable.out.log",
    },
    "evolution": {
        "start": "start-openclaw-factor-daemon-evolution.ps1",
        "stop": "stop-openclaw-factor-daemon-evolution.ps1",
        "log": "factor-daemon-evolution.out.log",
    },
    "autotune": {
        "start": "start-openclaw-factor-daemon-autotune.ps1",
        "stop": "stop-openclaw-factor-daemon-autotune.ps1",
        "log": "factor-daemon-autotune.out.log",
    },
}


def pid_is_alive(pid: object) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def run_powershell(script_name: str) -> tuple[bool, str]:
    script = ROOT / script_name
    try:
        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=20,
        )
        output = ((result.stdout or "") + (result.stderr or "")).strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, f"Command timed out: {script_name}. Check daemon status or logs."
    except Exception as exc:
        return False, str(exc)


def normalize_status(name: str, status: dict | None) -> dict | None:
    if not status:
        return status

    normalized = dict(status)
    stop_path = DAEMON_ROOT / f"{name}.stop"
    if stop_path.exists():
        normalized["status"] = "stopped"
        normalized["next_run_after"] = None
        normalized["error"] = "Stopped by user."
        return normalized

    pid = normalized.get("pid")
    if pid and not pid_is_alive(pid):
        if str(normalized.get("status", "")).lower() in {"running", "starting"}:
            normalized["status"] = "stopped"
            normalized["next_run_after"] = None
            normalized["error"] = "Process exited; status file was stale."

    error_text = str(normalized.get("error") or "")
    if "Skipped because shared workflow lock is held by factor-daemon-stable" in error_text:
        normalized["status"] = "waiting"
        normalized["error"] = "Waiting for stable workflow lock."

    return normalized


def load_status(name: str) -> dict | None:
    path = DAEMON_ROOT / f"{name}-status.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return normalize_status(name, data)


def daemon_summary(name: str) -> str:
    status = load_status(name)
    if not status:
        return "not started"

    parts = [str(status.get("status", "unknown"))]
    run = status.get("run")
    if run not in (None, ""):
        parts.append(f"run={run}")
    next_run = status.get("next_run_after")
    if next_run:
        parts.append(f"next={next_run}")
    error = status.get("error")
    if error:
        parts.append(f"note={error}")
    return " | ".join(parts)


class ControlCenter(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("OpenClaw 总控中心")
        self.geometry("1180x820")
        self.resizable(False, False)
        self.configure(padx=16, pady=16)

        if ICON_PATH.exists():
            try:
                self.iconbitmap(default=str(ICON_PATH))
            except Exception:
                pass

        self.status_vars = {name: tk.StringVar(value="loading") for name in DAEMONS}
        self.action_running = False
        self.current_action = ""

        self._build()
        self.refresh_status()
        self.after(5000, self.auto_refresh_status)

    def _build(self) -> None:
        ttk.Label(self, text="OpenClaw + Freqtrade 总控中心", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            self,
            text="山寨线路当前使用 AlternativeHunter。fast 负责轻量筛选，stable 负责正式筛选与 promotion，evolution 保持手动研究，autotune 负责运行时调参。",
        ).pack(anchor="w", pady=(4, 12))

        status_frame = ttk.LabelFrame(self, text="后台状态")
        status_frame.pack(fill="x", pady=(0, 12))
        for row, name in enumerate(("fast", "stable", "evolution", "autotune")):
            label_text = {
                "fast": "Fast",
                "stable": "Stable",
                "evolution": "Evolution",
                "autotune": "Autotune",
            }[name]
            ttk.Label(status_frame, text=label_text).grid(row=row, column=0, sticky="w", padx=8, pady=8)
            ttk.Label(status_frame, textvariable=self.status_vars[name], width=120).grid(row=row, column=1, sticky="w", padx=8, pady=8)
        ttk.Button(status_frame, text="刷新", command=self.refresh_status).grid(row=0, column=2, rowspan=4, padx=8, pady=8, sticky="ns")

        daemon_frame = ttk.LabelFrame(self, text="后台控制")
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
            ttk.Button(daemon_frame, text=label, command=lambda s=script_name: self.run_and_report(s)).grid(row=row, column=col, padx=8, pady=8)

        tools_frame = ttk.LabelFrame(self, text="面板与机器人")
        tools_frame.pack(fill="x", pady=(0, 12))
        buttons = [
            ("启动只读看板", lambda: self.run_detached_ps1("start-factor-lab.ps1")),
            ("打开看板 (8501)", lambda: webbrowser.open("http://127.0.0.1:8501")),
            ("启动策略调试面板", lambda: self.run_detached_cmd("Launch Strategy Debug Lab.cmd")),
            ("打开调试面板 (8502)", lambda: webbrowser.open("http://127.0.0.1:8502")),
            ("启动山寨 Bot", lambda: self.run_and_report("start-openclaw-auto-bot.ps1")),
            ("打开山寨 API (8081)", lambda: webbrowser.open("http://127.0.0.1:8081")),
            ("启动主流 Bot", lambda: self.run_and_report("start-mainstream-auto-bot.ps1")),
            ("打开主流 API (8082)", lambda: webbrowser.open("http://127.0.0.1:8082")),
            ("打开报告目录", lambda: subprocess.Popen(["explorer", str(REPORT_ROOT)])),
            ("打开项目说明", lambda: subprocess.Popen(["notepad", str(ROOT / "OPENCLAW_FREQTRADE_GUIDE.md")])),
            ("打开参数说明", lambda: subprocess.Popen(["notepad", str(ROOT / "ALTERNATIVEHUNTER_TUNING_GUIDE_CN.md")])),
            ("打开 Stable 审批", lambda: subprocess.Popen(["notepad", str(REPORT_ROOT / "openclaw-auto-approval-stable.md")])),
        ]
        for index, (label, callback) in enumerate(buttons):
            row, col = divmod(index, 4)
            ttk.Button(tools_frame, text=label, command=callback).grid(row=row, column=col, padx=8, pady=8)

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
        self.output = tk.Text(output_frame, height=18, wrap="word")
        self.output.pack(fill="both", expand=True, padx=8, pady=8)
        self.output.insert("1.0", "已就绪。\n")
        self.output.configure(state="disabled")

    def refresh_status(self) -> None:
        for name in self.status_vars:
            self.status_vars[name].set(daemon_summary(f"factor-daemon-{name}"))

    def auto_refresh_status(self) -> None:
        self.refresh_status()
        self.after(5000, self.auto_refresh_status)

    def set_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", tk.END)
        self.output.insert("1.0", text.strip() + "\n")
        self.output.configure(state="disabled")

    def run_and_report(self, script_name: str) -> None:
        if self.action_running:
            self.set_output("已有操作在执行，请等待当前命令完成。")
            return

        self.action_running = True
        self.current_action = script_name
        self.set_output(f"正在执行 {script_name} ...")
        self.after(25000, self.reset_if_stuck)

        def worker() -> None:
            ok, output = run_powershell(script_name)

            def finish() -> None:
                self.action_running = False
                self.current_action = ""
                self.set_output(output or ("执行完成。" if ok else "执行失败。"))
                self.refresh_status()
                if ok:
                    self.after(1200, self.refresh_status)
                    self.after(3000, self.refresh_status)
                if not ok:
                    messagebox.showwarning("OpenClaw 总控中心", output or "命令执行失败。")

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def reset_if_stuck(self) -> None:
        if self.action_running:
            action = self.current_action or "Current command"
            self.action_running = False
            self.current_action = ""
            self.set_output(f"{action} 长时间未返回，GUI 已自动解锁。请查看状态或日志。")
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


if __name__ == "__main__":
    app = ControlCenter()
    app.mainloop()
