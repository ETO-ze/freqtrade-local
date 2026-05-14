import argparse
import json
import subprocess
from statistics import pstdev
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def atomic_write_json(path: Path, payload: Any) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    json.loads(text)
    atomic_write_text(path, text)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, "", "N/A", "n/a"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_pairs(config_path: Path, explicit_pairs: str) -> list[str]:
    if explicit_pairs.strip():
        return [item.strip() for item in explicit_pairs.split(",") if item.strip()]
    payload = json.loads(config_path.read_text(encoding="utf-8-sig"))
    return [str(item) for item in (payload.get("exchange") or {}).get("pair_whitelist") or []]


def data_stem(pair: str) -> str:
    return pair.replace("/", "_").replace(":", "_")


def discover_data_bounds(data_dir: Path, pairs: list[str], timeframe: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    starts: list[pd.Timestamp] = []
    ends: list[pd.Timestamp] = []
    for pair in pairs:
        path = data_dir / f"{data_stem(pair)}-{timeframe}-futures.feather"
        if not path.exists():
            continue
        frame = pd.read_feather(path, columns=["date"])
        if frame.empty:
            continue
        dates = pd.to_datetime(frame["date"], utc=True)
        starts.append(dates.min())
        ends.append(dates.max())
    if not ends:
        raise FileNotFoundError("No matching local data files found for walk-forward pairs.")
    return min(starts), max(ends)


def iso_date(value: pd.Timestamp) -> str:
    return value.strftime("%Y-%m-%d")


def default_windows(data_start: pd.Timestamp, data_end: pd.Timestamp, start_floor: str) -> list[dict[str, str]]:
    floor = pd.Timestamp(start_floor, tz="UTC") if start_floor else data_start
    start = max(data_start, floor)
    latest_plus_one = (data_end + timedelta(days=1)).normalize()
    fixed = [
        {
            "name": "wf_validation_2025q4_2026m01",
            "train_start": iso_date(start),
            "train_end": "2025-10-01",
            "test_start": "2025-10-01",
            "test_end": "2026-02-01",
        },
        {
            "name": "wf_test_2026m02_now",
            "train_start": iso_date(start),
            "train_end": "2026-02-01",
            "test_start": "2026-02-01",
            "test_end": iso_date(latest_plus_one),
        },
    ]
    recent_test_start = max(start + timedelta(days=90), (data_end - timedelta(days=60)).normalize())
    recent_train_start = max(start, recent_test_start - timedelta(days=300))
    fixed.append(
        {
            "name": "wf_recent_60d",
            "train_start": iso_date(recent_train_start),
            "train_end": iso_date(recent_test_start),
            "test_start": iso_date(recent_test_start),
            "test_end": iso_date(latest_plus_one),
        }
    )
    return [
        item
        for item in fixed
        if pd.Timestamp(item["train_start"], tz="UTC") < pd.Timestamp(item["train_end"], tz="UTC")
        and pd.Timestamp(item["test_start"], tz="UTC") < pd.Timestamp(item["test_end"], tz="UTC")
        and pd.Timestamp(item["test_start"], tz="UTC") <= data_end
    ]


def model_weight(result: dict[str, Any]) -> float:
    accuracy = safe_float(result.get("accuracy"))
    balanced = safe_float(result.get("balanced_accuracy"))
    long_precision = safe_float(result.get("long_precision"))
    short_precision = safe_float(result.get("short_precision"))
    top_feature_share = safe_float(result.get("top_feature_share"))
    top3_feature_share = safe_float(result.get("top3_feature_share"))
    mark_premium_family_share = safe_float(result.get("mark_premium_family_share"))
    orthogonal_feature_share = safe_float(result.get("orthogonal_feature_share"))
    max_feature_family_share = safe_float(result.get("max_feature_family_share"))
    precision_blend = (long_precision + short_precision) / 2.0
    side_balance = min(long_precision, short_precision)
    side_gap_penalty = abs(long_precision - short_precision)
    weight = (accuracy * 0.25) + (balanced * 0.35) + (precision_blend * 0.15) + (side_balance * 0.25) - (
        side_gap_penalty * 0.10
    )
    if long_precision <= 0.02 or short_precision <= 0.02:
        weight -= 0.06
    if top_feature_share > 0.35:
        weight -= min((top_feature_share - 0.35) * 0.40, 0.18)
    if top3_feature_share > 0.70:
        weight -= min((top3_feature_share - 0.70) * 0.20, 0.12)
    if mark_premium_family_share > 0.25:
        weight -= min((mark_premium_family_share - 0.25) * 0.75, 0.30)
    if mark_premium_family_share > 0.35 and orthogonal_feature_share < 0.18:
        weight -= 0.08
    if max_feature_family_share > 0.48:
        weight -= min((max_feature_family_share - 0.48) * 0.35, 0.16)
    if orthogonal_feature_share >= 0.25:
        weight += min((orthogonal_feature_share - 0.25) * 0.08, 0.04)
    return round(max(weight, 0.0), 4)


def summarize_stability(rows: list[dict[str, Any]], required_passed_windows: int) -> dict[str, Any]:
    window_count = len(rows)
    ok_rows = [row for row in rows if row.get("ok")]
    passed_rows = [row for row in ok_rows if row.get("passed")]
    failed_rows = [row for row in rows if not row.get("ok")]
    weights = [safe_float(row.get("best_weight")) for row in ok_rows]
    balanced_scores = [safe_float(row.get("balanced_accuracy")) for row in ok_rows]
    orthogonal_shares = [safe_float(row.get("orthogonal_feature_share")) for row in ok_rows]
    family_shares = [safe_float(row.get("max_feature_family_share")) for row in ok_rows]
    model_counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    for row in ok_rows:
        model = str(row.get("best_model") or "n/a")
        family = str(row.get("dominant_feature_family") or "n/a")
        model_counts[model] = model_counts.get(model, 0) + 1
        family_counts[family] = family_counts.get(family, 0) + 1

    consensus_model, consensus_count = max(model_counts.items(), key=lambda item: item[1], default=("n/a", 0))
    dominant_family, dominant_family_count = max(family_counts.items(), key=lambda item: item[1], default=("n/a", 0))
    memory_failure_count = sum(1 for row in failed_rows if "exit code 137" in str(row.get("error", "")).lower())
    passed_window_ratio = len(passed_rows) / max(window_count, 1)
    model_consensus_ratio = consensus_count / max(len(ok_rows), 1)
    dominant_family_ratio = dominant_family_count / max(len(ok_rows), 1)
    average_weight = sum(weights) / len(weights) if weights else 0.0
    min_weight = min(weights) if weights else 0.0
    weight_std = pstdev(weights) if len(weights) > 1 else 0.0
    average_balanced_accuracy = sum(balanced_scores) / len(balanced_scores) if balanced_scores else 0.0
    average_orthogonal_share = sum(orthogonal_shares) / len(orthogonal_shares) if orthogonal_shares else 0.0
    min_orthogonal_share = min(orthogonal_shares) if orthogonal_shares else 0.0
    average_max_family_share = sum(family_shares) / len(family_shares) if family_shares else 0.0
    max_family_share = max(family_shares) if family_shares else 0.0
    low_orthogonal_window_count = sum(1 for value in orthogonal_shares if value < 0.15)
    high_family_concentration_window_count = sum(1 for value in family_shares if value > 0.55)

    blockers: list[str] = []
    if failed_rows:
        blockers.append("failed_windows")
    if any(row.get("dry_run") for row in rows):
        blockers.append("dry_run_no_training")
    if memory_failure_count:
        blockers.append("docker_memory_exit_137")
    if len(passed_rows) < required_passed_windows:
        blockers.append("insufficient_passed_windows")
    if high_family_concentration_window_count:
        blockers.append("feature_family_concentration")
    if low_orthogonal_window_count:
        blockers.append("low_orthogonal_factor_share")
    if model_consensus_ratio < 0.67 and len(ok_rows) >= 2:
        blockers.append("weak_model_consensus")

    if not blockers and passed_window_ratio >= 0.67 and model_consensus_ratio >= 0.67:
        recommended_gate_mode = "semi_gate_ready"
        stability_grade = "A"
    elif memory_failure_count or failed_rows:
        recommended_gate_mode = "report_only_blocked"
        stability_grade = "D"
    elif passed_window_ratio >= 0.34 and average_weight >= 0.22:
        recommended_gate_mode = "observe_only"
        stability_grade = "C"
    else:
        recommended_gate_mode = "report_only_blocked"
        stability_grade = "D"

    return {
        "stability_grade": stability_grade,
        "recommended_gate_mode": recommended_gate_mode,
        "blockers": blockers,
        "failed_window_count": len(failed_rows),
        "failed_window_names": [str(row.get("name")) for row in failed_rows],
        "memory_failure_count": memory_failure_count,
        "passed_window_ratio": round(passed_window_ratio, 4),
        "model_consensus": consensus_model,
        "model_consensus_count": consensus_count,
        "model_consensus_ratio": round(model_consensus_ratio, 4),
        "dominant_feature_family": dominant_family,
        "dominant_feature_family_count": dominant_family_count,
        "dominant_feature_family_ratio": round(dominant_family_ratio, 4),
        "average_weight": round(average_weight, 4),
        "min_weight": round(min_weight, 4),
        "weight_std": round(weight_std, 4),
        "average_balanced_accuracy": round(average_balanced_accuracy, 4),
        "average_orthogonal_feature_share": round(average_orthogonal_share, 4),
        "min_orthogonal_feature_share": round(min_orthogonal_share, 4),
        "average_max_feature_family_share": round(average_max_family_share, 4),
        "max_feature_family_share": round(max_family_share, 4),
        "low_orthogonal_window_count": low_orthogonal_window_count,
        "high_family_concentration_window_count": high_family_concentration_window_count,
    }


def run_window(args, user_data: Path, pairs: list[str], window: dict[str, str]) -> dict[str, Any]:
    window_prefix = f"{args.output_prefix.rstrip('/')}/{window['name']}"
    if args.dry_run:
        return {
            **window,
            "ok": True,
            "passed": False,
            "dry_run": True,
            "best_model": "dry-run",
            "best_weight": 0.0,
            "balanced_accuracy": 0.0,
            "long_precision": 0.0,
            "short_precision": 0.0,
            "orthogonal_feature_share": 0.0,
            "dominant_feature_family": "",
            "max_feature_family_share": 0.0,
            "train_samples": 0,
            "test_samples": 0,
            "json_path": str(user_data / Path(str(window_prefix).replace("/freqtrade/user_data/", "")).with_suffix(".json")),
        }
    command = [
        "docker",
        "run",
        "--rm",
    ]
    if args.use_gpu:
        command.extend(["--gpus", "all"])
    command.extend(
        [
            "--entrypoint",
            "python",
            "-v",
            f"{user_data}:/freqtrade/user_data",
            args.docker_image,
            "/freqtrade/user_data/notebooks/train_alt_tree_models.py",
            "--pairs",
            ",".join(pairs),
            "--timeframe",
            args.timeframe,
            "--horizon",
            str(args.horizon),
            "--threshold",
            str(args.threshold),
            "--recent-window",
            str(args.recent_window),
            "--models",
            args.models,
            "--output-prefix",
            window_prefix,
            "--train-start",
            window["train_start"],
            "--train-end",
            window["train_end"],
            "--test-start",
            window["test_start"],
            "--test-end",
            window["test_end"],
        ]
    )
    if args.prefer_gpu:
        command.append("--prefer-gpu")
    if args.profile_json:
        command.extend(["--profile-json", args.profile_json])
    result = subprocess.run(command, cwd=args.project_root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    container_json = Path(str(window_prefix).replace("/freqtrade/user_data/", ""))
    json_path = user_data / container_json.with_suffix(".json")
    row: dict[str, Any] = {
        **window,
        "ok": result.returncode == 0,
        "json_path": str(json_path),
        "stdout": result.stdout[-2000:],
        "stderr": result.stderr[-2000:],
    }
    if result.returncode != 0:
        row["error"] = f"docker/train failed with exit code {result.returncode}"
        return row
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    results = payload.get("results") or []
    for item in results:
        item["walk_forward_weight"] = model_weight(item)
    best = max(results, key=lambda item: safe_float(item.get("walk_forward_weight")), default={})
    row["metadata"] = payload.get("metadata") or {}
    row["best_model"] = best.get("model") or "n/a"
    row["best_model_key"] = best.get("model_key") or ""
    row["best_weight"] = safe_float(best.get("walk_forward_weight"))
    row["balanced_accuracy"] = safe_float(best.get("balanced_accuracy"))
    row["long_precision"] = safe_float(best.get("long_precision"))
    row["short_precision"] = safe_float(best.get("short_precision"))
    row["orthogonal_feature_share"] = safe_float(best.get("orthogonal_feature_share"))
    row["dominant_feature_family"] = best.get("dominant_feature_family") or ""
    row["max_feature_family_share"] = safe_float(best.get("max_feature_family_share"))
    row["train_samples"] = int((payload.get("metadata") or {}).get("train_samples") or 0)
    row["test_samples"] = int((payload.get("metadata") or {}).get("test_samples") or 0)
    row["passed"] = (
        row["best_weight"] >= args.min_window_weight
        and row["balanced_accuracy"] >= args.min_balanced_accuracy
        and min(row["long_precision"], row["short_precision"]) >= args.min_side_precision
        and row["test_samples"] >= args.min_test_samples
    )
    return row


def write_report(path: Path, payload: dict[str, Any]) -> None:
    stability = payload.get("stability_summary") or {}
    lines = [
        "# OpenClaw Walk-Forward Retrain",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Passed: {payload['passed']}",
        f"- Score: {payload['score']}",
        f"- Passed windows: {payload['passed_windows']} / {payload['window_count']}",
        f"- Required passed windows: {payload['required_passed_windows']}",
        f"- Best model consensus: {payload['best_model_consensus']}",
        f"- Hard blocks: {', '.join(payload['hard_blocks']) if payload['hard_blocks'] else 'none'}",
        "",
        "## Stability Summary",
        "",
        f"- Stability grade: {stability.get('stability_grade', 'n/a')}",
        f"- Recommended gate mode: {stability.get('recommended_gate_mode', 'n/a')}",
        f"- Blockers: {', '.join(stability.get('blockers') or []) if stability.get('blockers') else 'none'}",
        f"- Passed window ratio: {stability.get('passed_window_ratio', 0)}",
        f"- Model consensus: {stability.get('model_consensus', 'n/a')} ({stability.get('model_consensus_ratio', 0)})",
        f"- Dominant feature family: {stability.get('dominant_feature_family', 'n/a')} ({stability.get('dominant_feature_family_ratio', 0)})",
        f"- Avg/min weight: {stability.get('average_weight', 0)} / {stability.get('min_weight', 0)}",
        f"- Avg orthogonal share: {stability.get('average_orthogonal_feature_share', 0)}",
        f"- Avg/max feature-family share: {stability.get('average_max_feature_family_share', 0)} / {stability.get('max_feature_family_share', 0)}",
        f"- Failed windows: {stability.get('failed_window_count', 0)}",
        f"- Docker memory failures: {stability.get('memory_failure_count', 0)}",
        "",
        "| Window | Train | Test | Best Model | Weight | Balanced Acc | Long P | Short P | Orthogonal | Family | Train Rows | Test Rows | Passed |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |",
    ]
    for row in payload["windows"]:
        lines.append(
            f"| {row.get('name')} | {row.get('train_start')} to {row.get('train_end')} | "
            f"{row.get('test_start')} to {row.get('test_end')} | {row.get('best_model', 'n/a')} | "
            f"{row.get('best_weight', 0)} | {row.get('balanced_accuracy', 0)} | "
            f"{row.get('long_precision', 0)} | {row.get('short_precision', 0)} | "
            f"{row.get('orthogonal_feature_share', 0)} | {row.get('dominant_feature_family', '')} | "
            f"{row.get('train_samples', 0)} | {row.get('test_samples', 0)} | {row.get('passed', False)} |"
        )
    atomic_write_text(path, "\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run independent walk-forward retraining windows for OpenClaw.")
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--config-path", required=True)
    parser.add_argument("--pairs", default="")
    parser.add_argument("--data-dir", default="user_data/data/okx/futures")
    parser.add_argument("--docker-image", default="freqtrade-local-ml-gpu:latest")
    parser.add_argument("--use-gpu", action="store_true")
    parser.add_argument("--prefer-gpu", action="store_true")
    parser.add_argument("--timeframe", default="5m")
    parser.add_argument("--horizon", type=int, default=12)
    parser.add_argument("--threshold", type=float, default=0.01)
    parser.add_argument("--recent-window", type=int, default=288)
    parser.add_argument("--models", default="tree,rf,hgb,xgb")
    parser.add_argument("--profile-json", default="")
    parser.add_argument("--start-floor", default="2025-01-01")
    parser.add_argument("--output-prefix", default="/freqtrade/user_data/reports/ml/walk-forward-stable")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--min-window-weight", type=float, default=0.28)
    parser.add_argument("--min-balanced-accuracy", type=float, default=0.28)
    parser.add_argument("--min-side-precision", type=float, default=0.02)
    parser.add_argument("--min-test-samples", type=int, default=500)
    parser.add_argument("--required-passed-windows", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true", help="Only resolve pairs/windows and write the report; do not run Docker.")
    args = parser.parse_args()

    project_root = Path(args.project_root)
    args.project_root = str(project_root)
    user_data = project_root / "user_data"
    config_path = Path(args.config_path)
    if not config_path.is_absolute():
        config_path = project_root / config_path
    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = project_root / data_dir
    pairs = load_pairs(config_path, args.pairs)
    data_start, data_end = discover_data_bounds(data_dir, pairs, args.timeframe)
    windows = default_windows(data_start, data_end, args.start_floor)
    rows = [run_window(args, user_data, pairs, window) for window in windows]

    ok_rows = [row for row in rows if row.get("ok")]
    passed_windows = sum(1 for row in ok_rows if row.get("passed"))
    hard_blocks = []
    if len(ok_rows) < len(windows):
        hard_blocks.append("window_training_failed")
    if args.dry_run:
        hard_blocks.append("dry_run_no_training")
    if passed_windows < args.required_passed_windows and not args.dry_run:
        hard_blocks.append("insufficient_passed_windows")
    model_counts: dict[str, int] = {}
    for row in ok_rows:
        model = str(row.get("best_model") or "n/a")
        model_counts[model] = model_counts.get(model, 0) + 1
    consensus = max(model_counts.items(), key=lambda item: item[1])[0] if model_counts else "n/a"
    average_weight = sum(safe_float(row.get("best_weight")) for row in ok_rows) / len(ok_rows) if ok_rows else 0.0
    score = round((passed_windows / max(len(windows), 1) * 60.0) + min(average_weight / 0.55, 1.0) * 40.0, 2)
    stability_summary = summarize_stability(rows, args.required_passed_windows)
    payload = {
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "passed": not hard_blocks,
        "score": score,
        "passed_windows": passed_windows,
        "window_count": len(windows),
        "required_passed_windows": args.required_passed_windows,
        "best_model_consensus": consensus,
        "hard_blocks": hard_blocks,
        "data_start": data_start.isoformat(),
        "data_end": data_end.isoformat(),
        "pairs": pairs,
        "stability_summary": stability_summary,
        "windows": rows,
    }
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    atomic_write_json(output_json, payload)
    write_report(output_md, payload)
    print(f"Wrote {output_json}")
    print(f"Wrote {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
