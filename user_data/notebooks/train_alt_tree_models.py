import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report
from sklearn.tree import DecisionTreeClassifier

try:
    from lightgbm import LGBMClassifier
except ImportError:
    LGBMClassifier = None


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def compute_atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = frame["high"] - frame["low"]
    high_close = (frame["high"] - frame["close"].shift(1)).abs()
    low_close = (frame["low"] - frame["close"].shift(1)).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(period).mean()


def build_features(frame: pd.DataFrame, pair: str, horizon: int, threshold: float) -> pd.DataFrame:
    df = frame.copy()
    df["pair"] = pair
    df["ret_1"] = df["close"].pct_change(1)
    df["ret_3"] = df["close"].pct_change(3)
    df["ret_6"] = df["close"].pct_change(6)
    df["ret_12"] = df["close"].pct_change(12)
    df["ret_24"] = df["close"].pct_change(24)
    df["range_pct"] = (df["high"] - df["low"]) / df["open"].replace(0, np.nan)
    df["body_pct"] = (df["close"] - df["open"]).abs() / df["open"].replace(0, np.nan)
    df["direction"] = (df["close"] - df["open"]) / df["open"].replace(0, np.nan)
    df["upper_wick_pct"] = (df["high"] - df[["open", "close"]].max(axis=1)) / df["open"].replace(0, np.nan)
    df["lower_wick_pct"] = (df[["open", "close"]].min(axis=1) - df["low"]) / df["open"].replace(0, np.nan)
    df["volume_ratio_6"] = df["volume"] / df["volume"].rolling(6).mean()
    df["volume_ratio_24"] = df["volume"] / df["volume"].rolling(24).mean()
    df["volume_trend_24_72"] = (
        df["volume"].ewm(span=24, adjust=False).mean() / df["volume"].ewm(span=72, adjust=False).mean()
    ) - 1
    df["volume_zscore_24"] = (
        (df["volume"] - df["volume"].rolling(24).mean()) / df["volume"].rolling(24).std().replace(0, np.nan)
    )
    df["volatility_12"] = df["close"].pct_change().rolling(12).std()
    df["volatility_24"] = df["close"].pct_change().rolling(24).std()
    df["volatility_ratio_12_24"] = df["volatility_12"] / df["volatility_24"].replace(0, np.nan)
    df["ema_8"] = df["close"].ewm(span=8, adjust=False).mean()
    df["ema_21"] = df["close"].ewm(span=21, adjust=False).mean()
    df["ema_55"] = df["close"].ewm(span=55, adjust=False).mean()
    df["ema_gap"] = (df["ema_8"] - df["ema_21"]) / df["close"].replace(0, np.nan)
    df["ema_8_55_gap"] = (df["ema_8"] - df["ema_55"]) / df["close"].replace(0, np.nan)
    df["ema_gap_slope_3"] = df["ema_gap"].diff(3)
    df["rsi_14"] = compute_rsi(df["close"], 14) / 100.0
    df["atr_14_pct"] = compute_atr(df, 14) / df["close"].replace(0, np.nan)
    df["price_vs_rollmean_24"] = df["close"] / df["close"].rolling(24).mean() - 1
    df["breakout_24"] = df["close"] / df["high"].rolling(24).max() - 1
    df["breakdown_24"] = df["close"] / df["low"].rolling(24).min() - 1
    df["forward_return"] = df["close"].shift(-horizon) / df["close"] - 1
    df["target"] = 0
    df.loc[df["forward_return"] > threshold, "target"] = 1
    df.loc[df["forward_return"] < -threshold, "target"] = -1
    return df.dropna()


def load_dataset(data_dir: Path, pairs, timeframe: str, horizon: int, threshold: float) -> pd.DataFrame:
    frames = []
    for pair in pairs:
        stem = pair.replace("/", "_").replace(":", "_")
        path = data_dir / f"{stem}-{timeframe}-futures.feather"
        if not path.exists():
            continue
        frame = pd.read_feather(path)
        frames.append(build_features(frame, pair, horizon, threshold))
    if not frames:
        raise FileNotFoundError("No matching data files were found for the requested pairs.")
    dataset = pd.concat(frames, ignore_index=True)
    dataset["pair_name"] = dataset["pair"]
    dataset = pd.get_dummies(dataset, columns=["pair"], prefix="pair")
    return dataset.sort_values("date").reset_index(drop=True)


def get_feature_columns(dataset: pd.DataFrame) -> List[str]:
    return [
        column
        for column in dataset.columns
        if column
        not in {"date", "open", "high", "low", "close", "volume", "forward_return", "target", "pair_name"}
    ]


def load_profile(path: Optional[str]) -> dict:
    if not path:
        return {}
    profile_path = Path(path)
    if not profile_path.exists():
        raise FileNotFoundError(f"Profile json not found: {profile_path}")
    return json.loads(profile_path.read_text(encoding="utf-8"))


def build_feature_mapping(feature_columns: List[str], sanitized_columns: List[str]) -> Dict[str, str]:
    return dict(zip(feature_columns, sanitized_columns))


def resolve_feature_subset(
    feature_columns: List[str],
    feature_mapping: Dict[str, str],
    model_profile: dict,
    global_features: Optional[List[str]],
) -> List[str]:
    requested = model_profile.get("features") or global_features or feature_columns
    resolved = []
    for feature in requested:
        if feature in feature_mapping:
            resolved.append(feature_mapping[feature])
    return resolved or list(feature_mapping.values())


def build_models(requested_models: List[str], profile: dict):
    defaults = {
        "tree": {
            "name": "DecisionTreeClassifier",
            "params": {
                "max_depth": 6,
                "min_samples_leaf": 80,
                "class_weight": "balanced",
                "random_state": 42,
            },
        },
        "rf": {
            "name": "RandomForestClassifier",
            "params": {
                "n_estimators": 300,
                "max_depth": 8,
                "min_samples_leaf": 40,
                "class_weight": "balanced_subsample",
                "n_jobs": -1,
                "random_state": 42,
            },
        },
        "hgb": {
            "name": "HistGradientBoostingClassifier",
            "params": {
                "learning_rate": 0.05,
                "max_depth": 8,
                "max_iter": 250,
                "min_samples_leaf": 80,
                "random_state": 42,
            },
        },
    }

    if LGBMClassifier is not None:
        defaults["lgbm"] = {
            "name": "LGBMClassifier",
            "params": {
                "objective": "multiclass",
                "num_class": 3,
                "n_estimators": 350,
                "learning_rate": 0.05,
                "num_leaves": 63,
                "subsample": 0.85,
                "colsample_bytree": 0.85,
                "reg_alpha": 0.1,
                "reg_lambda": 0.2,
                "random_state": 42,
                "class_weight": "balanced",
                "verbosity": -1,
            },
        }

    profile_models = profile.get("models", {})
    models = []
    for key in requested_models:
        if key not in defaults:
            continue
        model_profile = profile_models.get(key, {})
        if model_profile.get("enabled", True) is False:
            continue
        params = defaults[key]["params"].copy()
        params.update(model_profile.get("params", {}))
        if key == "tree":
            model = DecisionTreeClassifier(**params)
        elif key == "rf":
            model = RandomForestClassifier(**params)
        elif key == "hgb":
            model = HistGradientBoostingClassifier(**params)
        elif key == "lgbm" and LGBMClassifier is not None:
            model = LGBMClassifier(**params)
        else:
            continue
        models.append((key, defaults[key]["name"], model, model_profile))
    return models


def evaluate_model(name: str, model, x_train, y_train, x_test, y_test, forward_returns):
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)

    mask_long = predictions == 1
    mask_short = predictions == -1

    report = classification_report(
        y_test,
        predictions,
        labels=[-1, 0, 1],
        output_dict=True,
        zero_division=0,
    )

    feature_names = x_train.columns.tolist()
    importances = getattr(model, "feature_importances_", np.zeros(len(feature_names)))
    top_features = sorted(
        zip(feature_names, importances),
        key=lambda item: item[1],
        reverse=True,
    )[:10]

    return {
        "model": name,
        "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_test, predictions)), 4),
        "predicted_long_count": int(mask_long.sum()),
        "predicted_short_count": int(mask_short.sum()),
        "predicted_long_avg_forward_return": round(float(forward_returns[mask_long].mean()) if mask_long.any() else 0.0, 4),
        "predicted_short_avg_forward_return": round(float((-forward_returns[mask_short]).mean()) if mask_short.any() else 0.0, 4),
        "long_precision": round(float(report["1"]["precision"]), 4),
        "short_precision": round(float(report["-1"]["precision"]), 4),
        "top_features": [{"feature": feature, "importance": round(float(score), 4)} for feature, score in top_features],
        "predictions": predictions.tolist(),
    }


def sanitize_feature_names(frame: pd.DataFrame) -> pd.DataFrame:
    renamed = {}
    used = set()
    for column in frame.columns:
        clean = re.sub(r"[^0-9A-Za-z_]+", "_", column).strip("_")
        if not clean:
            clean = "feature"
        base = clean
        suffix = 2
        while clean in used:
            clean = f"{base}_{suffix}"
            suffix += 1
        used.add(clean)
        renamed[column] = clean
    return frame.rename(columns=renamed)


def build_pair_breakdown(
    pair_series: pd.Series, predictions: np.ndarray, forward_returns: pd.Series, recent_window: int
) -> list:
    rows = []
    for pair in sorted(pair_series.unique()):
        mask = pair_series == pair
        pair_predictions = predictions[mask]
        pair_returns = forward_returns[mask]
        long_mask = pair_predictions == 1
        short_mask = pair_predictions == -1
        long_edge = float(pair_returns[long_mask].mean()) if long_mask.any() else 0.0
        short_edge = float((-pair_returns[short_mask]).mean()) if short_mask.any() else 0.0
        score = (max(long_edge, short_edge) * 1000.0) + (long_mask.sum() + short_mask.sum()) / 100.0

        recent_predictions = pair_predictions[-recent_window:] if recent_window > 0 else pair_predictions
        recent_returns = pair_returns.iloc[-recent_window:] if recent_window > 0 else pair_returns
        recent_long_mask = recent_predictions == 1
        recent_short_mask = recent_predictions == -1
        recent_long_edge = float(recent_returns[recent_long_mask].mean()) if recent_long_mask.any() else 0.0
        recent_short_edge = float((-recent_returns[recent_short_mask]).mean()) if recent_short_mask.any() else 0.0
        recent_score = (max(recent_long_edge, recent_short_edge) * 1000.0) + (
            recent_long_mask.sum() + recent_short_mask.sum()
        ) / 100.0
        rows.append(
            {
                "pair": pair,
                "signal_count": int(long_mask.sum() + short_mask.sum()),
                "long_signal_count": int(long_mask.sum()),
                "short_signal_count": int(short_mask.sum()),
                "long_avg_forward_return": round(long_edge, 4),
                "short_avg_forward_return": round(short_edge, 4),
                "score": round(score, 4),
                "recent_signal_count": int(recent_long_mask.sum() + recent_short_mask.sum()),
                "recent_long_avg_forward_return": round(recent_long_edge, 4),
                "recent_short_avg_forward_return": round(recent_short_edge, 4),
                "recent_score": round(recent_score, 4),
            }
        )
    return rows


def write_markdown(path: Path, results, metadata):
    lines = [
        "# Alt Tree Model Report",
        "",
        f"- Generated from: `{metadata['data_dir']}`",
        f"- Timeframe: `{metadata['timeframe']}`",
        f"- Horizon: `{metadata['horizon']}` candles",
        f"- Threshold: `{metadata['threshold']:.4f}`",
        f"- Pairs: {', '.join(metadata['pairs'])}",
        f"- Samples: `{metadata['samples']}`",
        "",
    ]

    for result in results:
        lines.extend(
            [
                f"## {result['model']}",
                "",
                f"- Accuracy: `{result['accuracy']}`",
                f"- Balanced accuracy: `{result['balanced_accuracy']}`",
                f"- Predicted long count: `{result['predicted_long_count']}`",
                f"- Predicted short count: `{result['predicted_short_count']}`",
                f"- Predicted long avg forward return: `{result['predicted_long_avg_forward_return']}`",
                f"- Predicted short avg forward return: `{result['predicted_short_avg_forward_return']}`",
                f"- Long precision: `{result['long_precision']}`",
                f"- Short precision: `{result['short_precision']}`",
                "",
                "| Feature | Importance |",
                "| --- | ---: |",
            ]
        )
        for item in result["top_features"]:
            lines.append(f"| {item['feature']} | {item['importance']} |")
        lines.append("")
        if result.get("pair_breakdown"):
            lines.extend(
                [
                    "### Pair Breakdown",
                    "",
                    "| Pair | Signals | Long Signals | Short Signals | Long Edge | Short Edge | Score |",
                    "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
                ]
            )
            for item in result["pair_breakdown"]:
                lines.append(
                    f"| {item['pair']} | {item['signal_count']} | {item['long_signal_count']} | "
                    f"{item['short_signal_count']} | {item['long_avg_forward_return']} | "
                    f"{item['short_avg_forward_return']} | {item['score']} |"
                )
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Train tree-based models on local OKX futures data.")
    parser.add_argument("--data-dir", default="/freqtrade/user_data/data/okx/futures")
    parser.add_argument("--pairs", required=True, help="Comma-separated list of pairs.")
    parser.add_argument("--timeframe", default="5m")
    parser.add_argument("--horizon", type=int, default=12)
    parser.add_argument("--threshold", type=float, default=0.01)
    parser.add_argument("--recent-window", type=int, default=288, help="Recent rows per pair used for recent scoring.")
    parser.add_argument(
        "--output-prefix",
        default="/freqtrade/user_data/reports/ml/alt-tree-model-latest",
    )
    parser.add_argument(
        "--models",
        default="tree,rf,hgb",
        help="Comma-separated models to train: tree, rf, lgbm, hgb.",
    )
    parser.add_argument("--profile-json", default="", help="Optional model evolution profile json.")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output_prefix = Path(args.output_prefix)
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    pairs = [pair.strip() for pair in args.pairs.split(",") if pair.strip()]
    profile = load_profile(args.profile_json)

    dataset = load_dataset(data_dir, pairs, args.timeframe, args.horizon, args.threshold)
    feature_columns = get_feature_columns(dataset)
    split_index = int(len(dataset) * 0.8)
    train = dataset.iloc[:split_index]
    test = dataset.iloc[split_index:]

    x_train = train[feature_columns]
    y_train = train["target"]
    x_test = test[feature_columns]
    y_test = test["target"]
    test_pairs = test["pair_name"]

    x_train = sanitize_feature_names(x_train)
    x_test = x_test.rename(columns=dict(zip(feature_columns, x_train.columns.tolist())))
    feature_mapping = build_feature_mapping(feature_columns, x_train.columns.tolist())
    global_features = profile.get("global_features")

    requested_models = [item.strip().lower() for item in args.models.split(",") if item.strip()]
    models = build_models(requested_models, profile)

    if not models:
        raise ValueError("No valid models were requested.")

    results = []
    for model_key, name, model, model_profile in models:
        selected_columns = resolve_feature_subset(feature_columns, feature_mapping, model_profile, global_features)
        result = evaluate_model(
            name,
            model,
            x_train[selected_columns],
            y_train,
            x_test[selected_columns],
            y_test,
            test["forward_return"],
        )
        result["feature_count"] = len(selected_columns)
        result["selected_features"] = selected_columns
        result["model_key"] = model_key
        result["pair_breakdown"] = build_pair_breakdown(
            test_pairs,
            np.array(result.pop("predictions")),
            test["forward_return"],
            args.recent_window,
        )
        results.append(result)

    metadata = {
        "data_dir": str(data_dir),
        "pairs": pairs,
        "timeframe": args.timeframe,
        "horizon": args.horizon,
        "threshold": args.threshold,
        "recent_window": args.recent_window,
        "samples": int(len(dataset)),
        "models": requested_models,
        "profile_json": args.profile_json or None,
    }

    json_path = output_prefix.with_suffix(".json")
    md_path = output_prefix.with_suffix(".md")
    json_path.write_text(
        json.dumps({"metadata": metadata, "results": results}, indent=2),
        encoding="utf-8",
    )
    write_markdown(md_path, results, metadata)

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
