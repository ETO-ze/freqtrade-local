from __future__ import annotations

import argparse
import json
import posixpath
from pathlib import Path
from typing import Any

import paramiko


SERVICE_NAME = "openclaw-dashboard-status-sync"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run(client: paramiko.SSHClient, command: str, timeout: int = 60) -> tuple[int, str]:
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    return code, (out + err).strip()


def mkdir_p(sftp: paramiko.SFTPClient, path: str) -> None:
    parts: list[str] = []
    current = path
    while current not in ("", "/"):
        parts.append(current)
        current = posixpath.dirname(current)
    for item in reversed(parts):
        try:
            sftp.stat(item)
        except OSError:
            sftp.mkdir(item)


def write_remote_text(sftp: paramiko.SFTPClient, path: str, text: str) -> None:
    mkdir_p(sftp, posixpath.dirname(path))
    with sftp.file(path, "w") as handle:
        handle.write(text)


def connect(settings: dict[str, Any]) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=str(settings["host"]),
        port=int(settings.get("port") or 22),
        username=str(settings.get("username") or "root"),
        password=str(settings.get("password") or ""),
        timeout=30,
        banner_timeout=30,
        auth_timeout=30,
    )
    return client


def service_text(remote_script: str) -> str:
    return f"""[Unit]
Description=OpenClaw dashboard status and live position sync
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 {remote_script}
WorkingDirectory={posixpath.dirname(remote_script)}
TimeoutStartSec=90
"""


def timer_text(interval_seconds: int) -> str:
    interval = max(int(interval_seconds), 30)
    return f"""[Unit]
Description=Run OpenClaw dashboard status sync every {interval} seconds

[Timer]
OnBootSec=45
OnUnitActiveSec={interval}
AccuracySec=5
Unit={SERVICE_NAME}.service
Persistent=true

[Install]
WantedBy=timers.target
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Install server-side OpenClaw live position status sync timer.")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--settings-path", required=True)
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--run-once", action="store_true")
    args = parser.parse_args()

    project_root = Path(args.project_root)
    settings = load_json(Path(args.settings_path))
    remote_dir = str(settings.get("remote_dir") or "/root/freqtrade-local")
    local_status_script = project_root / "server" / "build_dashboard_status.py"
    if not local_status_script.exists():
        raise FileNotFoundError(local_status_script)

    remote_server_dir = posixpath.join(remote_dir, "server")
    remote_status_script = posixpath.join(remote_server_dir, "build_dashboard_status.py")

    client = connect(settings)
    try:
        sftp = client.open_sftp()
        try:
            mkdir_p(sftp, remote_server_dir)
            sftp.put(str(local_status_script), remote_status_script)
            write_remote_text(sftp, f"/etc/systemd/system/{SERVICE_NAME}.service", service_text(remote_status_script))
            write_remote_text(sftp, f"/etc/systemd/system/{SERVICE_NAME}.timer", timer_text(args.interval_seconds))
        finally:
            sftp.close()

        commands = [
            "systemctl daemon-reload",
            f"systemctl enable --now {SERVICE_NAME}.timer",
        ]
        if args.run_once:
            commands.append(f"systemctl start {SERVICE_NAME}.service")
        commands.extend(
            [
                f"systemctl is-enabled {SERVICE_NAME}.timer || true",
                f"systemctl status {SERVICE_NAME}.timer --no-pager -l | head -40 || true",
                f"systemctl status {SERVICE_NAME}.service --no-pager -l | head -60 || true",
            ]
        )
        for command in commands:
            code, output = run(client, command, timeout=120)
            print(f"$ {command}")
            print(output if output else f"exit={code}")
            if code != 0 and "|| true" not in command:
                return code
    finally:
        client.close()

    print("Installed server-side dashboard status sync timer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

