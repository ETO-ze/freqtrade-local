import argparse
import hashlib
import json
import posixpath
import shutil
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import paramiko
except ImportError as exc:  # pragma: no cover
    raise SystemExit("paramiko is required. Install it with: py -m pip install --user paramiko") from exc


DEFAULT_TIMEOUT = 30


@dataclass
class SyncSettings:
    host: str
    port: int
    username: str
    password: str
    remote_dir: str
    bot_container_name: str
    remote_api_url: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_settings(path: Path) -> SyncSettings:
    payload = load_json(path)
    required = ["host", "username", "password"]
    missing = [key for key in required if not str(payload.get(key) or "").strip()]
    if missing:
        raise ValueError(f"Missing settings fields: {', '.join(missing)}")
    return SyncSettings(
        host=str(payload["host"]).strip(),
        port=int(payload.get("port") or 22),
        username=str(payload["username"]).strip(),
        password=str(payload["password"]),
        remote_dir=str(payload.get("remote_dir") or "/root/freqtrade-local"),
        bot_container_name=str(payload.get("bot_container_name") or "freqtrade-openclaw-auto"),
        remote_api_url=str(payload.get("remote_api_url") or "http://127.0.0.1:8081/api/v1/ping"),
    )


def quote_single(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


class RemoteHost:
    def __init__(self, settings: SyncSettings) -> None:
        self.settings = settings
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(
            settings.host,
            port=settings.port,
            username=settings.username,
            password=settings.password,
            timeout=DEFAULT_TIMEOUT,
            banner_timeout=DEFAULT_TIMEOUT,
            auth_timeout=DEFAULT_TIMEOUT,
        )
        self.sftp = self.client.open_sftp()

    def close(self) -> None:
        try:
            self.sftp.close()
        finally:
            self.client.close()

    def run(self, command: str, timeout: int = 120, check: bool = True) -> tuple[int, str, str]:
        stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
        out = stdout.read().decode("utf-8", "ignore")
        err = stderr.read().decode("utf-8", "ignore")
        code = stdout.channel.recv_exit_status()
        if check and code != 0:
            raise RuntimeError(f"Remote command failed ({code}): {command}\nSTDOUT:\n{out}\nSTDERR:\n{err}")
        return code, out, err

    def mkdir_p(self, path: str) -> None:
        self.run(f"mkdir -p {quote_single(path)}")

    def put_file(self, local_path: Path, remote_path: str) -> None:
        remote_parent = posixpath.dirname(remote_path)
        self.mkdir_p(remote_parent)
        self.sftp.put(str(local_path), remote_path)

    def put_text(self, content: str, remote_path: str) -> None:
        remote_parent = posixpath.dirname(remote_path)
        self.mkdir_p(remote_parent)
        with self.sftp.open(remote_path, "w") as handle:
            handle.write(content)


def remote_detect(host: RemoteHost) -> dict[str, Any]:
    bot_name = host.settings.bot_container_name
    commands = {
        "hostname": "hostname",
        "docker_ps": "docker ps --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}'",
        "openclaw_processes": "ps -ef | grep -Ei 'freqtrade-factor-daemon|freqtrade-daily-ml-screen|freqtrade-auto-tune-alternativehunter|freqtrade-trade-feedback-isolated|freqtrade-backtest-openclaw-auto' | grep -v grep || true",
        "bot_running": f"docker inspect -f '{{{{.State.Running}}}}' {quote_single(bot_name)} 2>/dev/null || true",
        "bot_status": f"docker inspect -f '{{{{.State.Status}}}}' {quote_single(bot_name)} 2>/dev/null || true",
        "api_ping": f"curl -s {quote_single(host.settings.remote_api_url)} || true",
    }
    result: dict[str, Any] = {}
    for key, command in commands.items():
        _, out, _ = host.run(command, check=False)
        result[key] = out.strip()
    result["openclaw_running"] = bool(result["openclaw_processes"])
    return result


def build_file_manifest(project_root: Path, source_config_path: Path, runtime_policy_path: Path, tuning_path: Path, strategy_dir: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    explicit_paths = [
        source_config_path,
        runtime_policy_path,
        tuning_path,
    ]
    for path in explicit_paths:
        if path.exists():
            relative = path.relative_to(project_root).as_posix()
            files.append(
                {
                    "local_path": path,
                    "relative_path": relative,
                    "sha256": sha256_file(path),
                    "size": path.stat().st_size,
                }
            )
    if strategy_dir.exists():
        for path in sorted(strategy_dir.glob("*.py")):
            relative = path.relative_to(project_root).as_posix()
            files.append(
                {
                    "local_path": path,
                    "relative_path": relative,
                    "sha256": sha256_file(path),
                    "size": path.stat().st_size,
                }
            )
    return files


def backup_remote_files(host: RemoteHost, manifest: list[dict[str, Any]], backup_root: str) -> None:
    host.mkdir_p(backup_root)
    for item in manifest:
        relative = str(item["relative_path"])
        remote_path = posixpath.join(host.settings.remote_dir, *relative.split("/"))
        remote_backup = posixpath.join(backup_root, relative)
        parent = posixpath.dirname(remote_backup)
        host.mkdir_p(parent)
        host.run(
            f"if [ -f {quote_single(remote_path)} ]; then cp {quote_single(remote_path)} {quote_single(remote_backup)}; fi",
            check=False,
        )


def upload_manifest(host: RemoteHost, manifest: list[dict[str, Any]]) -> list[dict[str, Any]]:
    uploaded: list[dict[str, Any]] = []
    for item in manifest:
        relative = str(item["relative_path"])
        remote_path = posixpath.join(host.settings.remote_dir, *relative.split("/"))
        host.put_file(Path(item["local_path"]), remote_path)
        uploaded.append(
            {
                "relative_path": relative,
                "remote_path": remote_path,
                "sha256": item["sha256"],
                "size": item["size"],
            }
        )
    return uploaded


def restart_remote_bot(host: RemoteHost, mode: str) -> dict[str, Any]:
    bot_name = host.settings.bot_container_name
    _, exists_out, _ = host.run(f"docker inspect {quote_single(bot_name)} >/dev/null 2>&1; echo $?", check=False)
    exists = exists_out.strip() == "0"
    if not exists:
        return {"container_exists": False, "action": "skipped", "reason": "container not found"}

    _, running_out, _ = host.run(f"docker inspect -f '{{{{.State.Running}}}}' {quote_single(bot_name)}", check=False)
    running = running_out.strip().lower() == "true"
    if mode == "never":
        return {"container_exists": True, "running_before": running, "action": "skipped", "reason": "restart disabled"}
    if mode == "if-running" and not running:
        return {"container_exists": True, "running_before": running, "action": "skipped", "reason": "container not running"}

    action = "restart" if running else "start"
    host.run(f"docker {action} {quote_single(bot_name)}", timeout=180)
    return {"container_exists": True, "running_before": running, "action": action}


def wait_for_remote_api(host: RemoteHost, attempts: int = 30, delay_seconds: int = 2) -> dict[str, Any]:
    command = f"curl -s -o /tmp/openclaw_sync_ping.out -w '%{{http_code}}' {quote_single(host.settings.remote_api_url)} || true"
    last_code = ""
    last_body = ""
    for _ in range(attempts):
        _, out, _ = host.run(command, check=False)
        last_code = out.strip()
        _, body, _ = host.run("cat /tmp/openclaw_sync_ping.out 2>/dev/null || true", check=False)
        last_body = body.strip()
        if last_code == "200":
            return {"ok": True, "http_code": 200, "body": last_body}
        time.sleep(delay_seconds)
    try:
        code_int = int(last_code) if last_code else 0
    except ValueError:
        code_int = 0
    return {"ok": False, "http_code": code_int, "body": last_body}


def generate_report(
    project_root: Path,
    payload: dict[str, Any],
    report_md_path: Path,
    report_json_path: Path,
) -> None:
    ensure_parent(report_md_path)
    ensure_parent(report_json_path)
    write_json(report_json_path, payload)

    lines = [
        "# OpenClaw Server Sync",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Mode: {payload['mode']}",
        f"- Remote host: {payload['remote']['host']}",
        f"- Remote dir: {payload['remote']['remote_dir']}",
        f"- Source config: {payload['source']['config_path']}",
        f"- Runtime policy: {payload['source']['runtime_policy_path']}",
        f"- Strategy files synced: {payload['source']['strategy_file_count']}",
        "",
        "## Remote Status Before Sync",
        "",
        f"- Hostname: {payload['remote_status_before'].get('hostname') or 'unknown'}",
        f"- OpenClaw running: {payload['remote_status_before'].get('openclaw_running')}",
        f"- Bot running: {payload['remote_status_before'].get('bot_running')}",
        f"- API ping: {payload['remote_status_before'].get('api_ping') or 'n/a'}",
        "",
        "## Upload",
        "",
        f"- Files uploaded: {len(payload['uploaded_files'])}",
    ]
    for item in payload["uploaded_files"]:
        lines.append(f"- {item['relative_path']}")
    lines.extend(
        [
            "",
            "## Restart",
            "",
            f"- Action: {payload['restart'].get('action')}",
            f"- Reason: {payload['restart'].get('reason') or 'n/a'}",
            "",
            "## Validation",
            "",
            f"- API healthy: {payload['validation'].get('ok')}",
            f"- HTTP code: {payload['validation'].get('http_code')}",
            f"- Response: {payload['validation'].get('body') or 'n/a'}",
            "",
            "## Remote Status After Sync",
            "",
            f"- Bot running: {payload['remote_status_after'].get('bot_running')}",
            f"- Bot status: {payload['remote_status_after'].get('bot_status')}",
            f"- API ping: {payload['remote_status_after'].get('api_ping') or 'n/a'}",
        ]
    )
    write_text(report_md_path, "\n".join(lines))


def build_public_sync_payload(
    generated_at: str,
    mode: str,
    local_config: dict[str, Any],
    selected_pairs: list[str],
    validation: dict[str, Any],
    settings: SyncSettings,
) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "mode": mode,
        "bot_container_name": settings.bot_container_name,
        "strategy": str(local_config.get("strategy") or ""),
        "timeframe": str(local_config.get("timeframe") or ""),
        "selected_pairs": selected_pairs,
        "selected_pair_count": len(selected_pairs),
        "validation": {
            "ok": bool(validation.get("ok")),
            "http_code": int(validation.get("http_code") or 0),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync local OpenClaw/Freqtrade runtime files to remote Freqtrade server.")
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--settings-path", default=None)
    parser.add_argument("--source-config-path", default=None)
    parser.add_argument("--runtime-policy-path", default=None)
    parser.add_argument("--runtime-tuning-path", default=None)
    parser.add_argument("--strategy-dir", default=None)
    parser.add_argument("--report-md-path", default=None)
    parser.add_argument("--report-json-path", default=None)
    parser.add_argument("--restart-bot", choices=["if-running", "always", "never"], default="if-running")
    parser.add_argument("--mode", default="manual")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    settings_path = Path(args.settings_path or (project_root / "server.openclaw-sync.local.json")).resolve()
    source_config_path = Path(args.source_config_path or (project_root / "user_data" / "config.openclaw-auto.json")).resolve()
    runtime_policy_path = Path(args.runtime_policy_path or (project_root / "user_data" / "model_runtime_policy.json")).resolve()
    runtime_tuning_path = Path(args.runtime_tuning_path or (project_root / "user_data" / "model_runtime_tuning.auto.json")).resolve()
    strategy_dir = Path(args.strategy_dir or (project_root / "user_data" / "strategies")).resolve()
    report_md_path = Path(args.report_md_path or (project_root / "reports" / "openclaw-server-sync-latest.md")).resolve()
    report_json_path = Path(args.report_json_path or (project_root / "reports" / "openclaw-server-sync-latest.json")).resolve()

    if not settings_path.exists():
        raise SystemExit(f"Settings file not found: {settings_path}")
    if not source_config_path.exists():
        raise SystemExit(f"Source config not found: {source_config_path}")
    if not runtime_policy_path.exists():
        raise SystemExit(f"Runtime policy not found: {runtime_policy_path}")
    if not strategy_dir.exists():
        raise SystemExit(f"Strategy directory not found: {strategy_dir}")

    settings = load_settings(settings_path)
    local_config = load_json(source_config_path)
    selected_pairs = list((local_config.get("exchange") or {}).get("pair_whitelist") or [])
    manifest = build_file_manifest(project_root, source_config_path, runtime_policy_path, runtime_tuning_path, strategy_dir)
    if not manifest:
        raise SystemExit("Nothing to upload.")

    generated_at = time.strftime("%Y-%m-%d %H:%M:%S")
    host = RemoteHost(settings)
    try:
        remote_before = remote_detect(host)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        backup_root = posixpath.join(settings.remote_dir, "sync_backups", timestamp)
        backup_remote_files(host, manifest, backup_root)
        uploaded_files = upload_manifest(host, manifest)
        restart_result = restart_remote_bot(host, args.restart_bot)
        validation = wait_for_remote_api(host)
        public_sync_payload = build_public_sync_payload(
            generated_at=generated_at,
            mode=args.mode,
            local_config=local_config,
            selected_pairs=selected_pairs,
            validation=validation,
            settings=settings,
        )
        host.put_text(
            json.dumps(public_sync_payload, ensure_ascii=False, indent=2),
            posixpath.join(settings.remote_dir, "dashboard-data", "last-sync.json"),
        )
        remote_after = remote_detect(host)
    finally:
        host.close()

    payload = {
        "generated_at": generated_at,
        "mode": args.mode,
        "source": {
            "config_path": str(source_config_path),
            "runtime_policy_path": str(runtime_policy_path),
            "runtime_tuning_path": str(runtime_tuning_path) if runtime_tuning_path.exists() else "",
            "selected_pairs": selected_pairs,
            "strategy_file_count": len([item for item in manifest if str(item["relative_path"]).startswith("user_data/strategies/")]),
        },
        "remote": {
            "host": settings.host,
            "port": settings.port,
            "remote_dir": settings.remote_dir,
            "bot_container_name": settings.bot_container_name,
            "remote_api_url": settings.remote_api_url,
            "backup_root": backup_root,
        },
        "remote_status_before": remote_before,
        "uploaded_files": uploaded_files,
        "restart": restart_result,
        "validation": validation,
        "remote_status_after": remote_after,
    }
    generate_report(project_root, payload, report_md_path, report_json_path)
    print(f"Remote host: {settings.host}")
    print(f"Uploaded files: {len(uploaded_files)}")
    print(f"Restart action: {restart_result.get('action')}")
    print(f"Validation: {validation.get('http_code')} {validation.get('body')}")
    print(f"Report: {report_md_path}")
    return 0 if validation.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
