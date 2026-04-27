from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
REPORT_ROOT = ROOT / "reports"
DAEMON_ROOT = REPORT_ROOT / "daemon"

PROCESS_CACHE_TTL_SECONDS = 2.0
DOCKER_CACHE_TTL_SECONDS = 2.0

_process_cache: tuple[float, dict[int, str]] | None = None
_docker_workflow_cache: tuple[float, int] | None = None


def _now() -> float:
    return time.monotonic()


def _run_text(command: list[str], timeout: int = 5) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout or ""


def _process_snapshot() -> dict[int, str]:
    global _process_cache
    if _process_cache and (_now() - _process_cache[0]) < PROCESS_CACHE_TTL_SECONDS:
        return _process_cache[1]

    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        (
            "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
            "Get-CimInstance Win32_Process -Filter \"CommandLine LIKE '%freqtrade-factor-daemon.ps1%'\" | "
            "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress -Depth 3"
        ),
    ]
    output = _run_text(command, timeout=6).strip()
    snapshot: dict[int, str] = {}
    if output:
        try:
            payload = json.loads(output)
            rows = payload if isinstance(payload, list) else [payload]
            for row in rows:
                if not isinstance(row, dict):
                    continue
                pid = row.get("ProcessId")
                commandline = row.get("CommandLine") or ""
                try:
                    snapshot[int(pid)] = str(commandline)
                except (TypeError, ValueError):
                    continue
        except Exception:
            snapshot = {}

    _process_cache = (_now(), snapshot)
    return snapshot


def get_process_commandline(pid: object) -> str:
    try:
        return _process_snapshot().get(int(pid), "")
    except (TypeError, ValueError):
        return ""


def pid_is_alive(pid: object) -> bool:
    return bool(get_process_commandline(pid))


def daemon_pid_is_alive(pid: object, daemon_name: str) -> bool:
    commandline = get_process_commandline(pid)
    return bool(
        commandline
        and "freqtrade-factor-daemon.ps1" in commandline
        and daemon_name in commandline
    )


def workflow_container_count() -> int:
    global _docker_workflow_cache
    if _docker_workflow_cache and (_now() - _docker_workflow_cache[0]) < DOCKER_CACHE_TTL_SECONDS:
        return _docker_workflow_cache[1]

    output = _run_text(
        [
            "docker",
            "ps",
            "--no-trunc",
            "--format",
            "{{.Image}}\t{{.Names}}\t{{.Command}}",
        ],
        timeout=5,
    )
    count = 0
    for line in output.splitlines():
        parts = line.split("\t", 2)
        if len(parts) < 3:
            continue
        image, name, command = parts
        if name in {"freqtrade-openclaw-auto", "freqtrade-mainstream-auto"}:
            continue
        if image == "freqtrade-local-ml-gpu:latest" or (
            image == "freqtradeorg/freqtrade:stable" and "backtesting" in command
        ):
            count += 1

    _docker_workflow_cache = (_now(), count)
    return count


def normalize_daemon_status(name: str, status: dict[str, Any] | None) -> dict[str, Any] | None:
    if not status:
        return status

    normalized = dict(status)
    stop_path = DAEMON_ROOT / f"{name}.stop"
    pid = normalized.get("pid")
    daemon_alive = daemon_pid_is_alive(pid, name) if pid else False
    normalized["_daemon_alive"] = daemon_alive

    if stop_path.exists():
        if daemon_alive:
            normalized["status"] = "stopping"
            normalized["error"] = "Stop requested; waiting for daemon process to exit."
        else:
            normalized["status"] = "stopped"
            normalized["next_run_after"] = None
            normalized["error"] = "Stopped by user."
        return normalized

    if pid and not daemon_alive:
        if str(normalized.get("status", "")).lower() in {"running", "starting"}:
            if workflow_container_count() > 0:
                normalized["status"] = "orphaned"
                normalized["error"] = "Daemon process exited, but a workflow container is still running."
            else:
                normalized["status"] = "stopped"
                normalized["next_run_after"] = None
                normalized["error"] = "Daemon process exited; status file was stale."

    error_text = str(normalized.get("error") or "")
    if "Skipped because shared workflow lock is held by factor-daemon-stable" in error_text:
        normalized["status"] = "waiting"
        normalized["error"] = "Waiting for stable workflow lock."

    return normalized


def load_daemon_status(name: str) -> dict[str, Any] | None:
    path = DAEMON_ROOT / f"{name}-status.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return normalize_daemon_status(name, data)


def display_daemon_status(status: dict[str, Any] | None) -> str:
    status = status or {}
    raw_status = str(status.get("status", "not started"))
    daemon_alive = bool(status.get("_daemon_alive"))
    if raw_status == "running":
        task_count = workflow_container_count()
        if daemon_alive and task_count > 0:
            return f"running workflow ({task_count})"
        if daemon_alive:
            return "daemon waiting"
        return "stopped"
    if raw_status == "starting" and daemon_alive:
        return "starting daemon"
    if raw_status == "orphaned":
        task_count = workflow_container_count()
        return f"orphan workflow ({task_count})" if task_count > 0 else "stopped"
    return raw_status


def duration_label(status: dict[str, Any] | None) -> str:
    raw_status = str((status or {}).get("status", "")).lower()
    if raw_status in {"running", "starting", "stopping", "orphaned"}:
        return "Current Duration"
    if raw_status in {"stopped", "ok", "error", "skipped", "waiting"}:
        return "Last Duration"
    return "Duration"


def daemon_summary(name: str) -> str:
    status = load_daemon_status(name)
    if not status:
        return "not started"

    parts = [display_daemon_status(status)]
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


def runtime_snapshot() -> dict[str, Any]:
    names = ["factor-daemon-fast", "factor-daemon-stable", "factor-daemon-evolution", "factor-daemon-autotune"]
    return {
        "workflow_container_count": workflow_container_count(),
        "daemons": {
            name: {
                "summary": daemon_summary(name),
                "status": load_daemon_status(name),
            }
            for name in names
        },
    }


if __name__ == "__main__":
    print(json.dumps(runtime_snapshot(), ensure_ascii=False, indent=2))
