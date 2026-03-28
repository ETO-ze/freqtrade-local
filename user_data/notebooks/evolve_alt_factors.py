import argparse
import json
import random
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd

from train_alt_tree_models import (
    build_feature_mapping,
    build_models,
    build_pair_breakdown,
    evaluate_model,
    get_feature_columns,
    load_dataset,
    sanitize_feature_names,
)


FEATURE_GROUPS = {
    "returns": ["ret_1", "ret_3", "ret_6", "ret_12", "ret_24"],
    "candle": ["range_pct", "body_pct", "direction", "upper_wick_pct", "lower_wick_pct"],
    "volume": ["volume_ratio_6", "volume_ratio_24", "volume_trend_24_72", "volume_zscore_24"],
    "volatility": ["volatility_12", "volatility_24", "volatility_ratio_12_24", "atr_14_pct"],
    "trend": ["ema_8", "ema_21", "ema_55", "ema_gap", "ema_8_55_gap", "ema_gap_slope_3", "rsi_14"],
    "structure": ["price_vs_rollmean_24", "breakout_24", "breakdown_24"],
}

MODEL_PARAM_SPACE = {
    "tree": {
        "max_depth": [4, 6, 8, 10],
        "min_samples_leaf": [40, 80, 120, 160],
    },
    "rf": {
        "n_estimators": [200, 300, 400],
        "max_depth": [6, 8, 10, 12],
        "min_samples_leaf": [20, 40, 80],
    },
    "hgb": {
        "learning_rate": [0.03, 0.05, 0.08],
        "max_depth": [6, 8, 10],
        "max_iter": [150, 250, 350],
        "min_samples_leaf": [40, 80, 120],
    },
    "xgb": {
        "n_estimators": [200, 350, 500],
        "learning_rate": [0.03, 0.05, 0.08],
        "max_depth": [6, 8, 10],
        "subsample": [0.75, 0.85, 1.0],
        "colsample_bytree": [0.75, 0.85, 1.0],
    },
}


def build_base_profile(models: list[str]) -> dict:
    profile = {"global_features": [], "models": {}}
    enabled_groups = list(FEATURE_GROUPS.keys())
    selected_features = []
    for group in enabled_groups:
        selected_features.extend(FEATURE_GROUPS[group])
    profile["global_features"] = selected_features

    for model in models:
        profile["models"][model] = {
            "enabled": True,
            "params": {key: values[0] for key, values in MODEL_PARAM_SPACE[model].items()},
        }
    return profile


def random_profile(models: list[str], rng: random.Random) -> dict:
    profile = {"global_features": [], "models": {}}
    enabled_groups = [name for name in FEATURE_GROUPS if rng.random() > 0.25]
    if not enabled_groups:
        enabled_groups = [rng.choice(list(FEATURE_GROUPS.keys()))]
    selected_features = []
    for group in enabled_groups:
        selected_features.extend(FEATURE_GROUPS[group])
    profile["global_features"] = selected_features

    for model in models:
        params = {}
        for key, values in MODEL_PARAM_SPACE[model].items():
            params[key] = rng.choice(values)
        profile["models"][model] = {"enabled": True, "params": params}
    return profile


def mutate_profile(profile: dict, models: list[str], rng: random.Random, mutation_rate: float) -> dict:
    child = deepcopy(profile)
    groups = {
        name: any(feature in child["global_features"] for feature in features)
        for name, features in FEATURE_GROUPS.items()
    }
    for group in groups:
        if rng.random() < mutation_rate:
            groups[group] = not groups[group]
    if not any(groups.values()):
        groups[rng.choice(list(groups.keys()))] = True

    child["global_features"] = []
    for group, enabled in groups.items():
        if enabled:
            child["global_features"].extend(FEATURE_GROUPS[group])

    for model in models:
        params = child["models"][model]["params"]
        for key, values in MODEL_PARAM_SPACE[model].items():
            if rng.random() < mutation_rate:
                params[key] = rng.choice(values)
    return child


def crossover_profiles(left: dict, right: dict, models: list[str], rng: random.Random) -> dict:
    child = {"global_features": [], "models": {}, "prefer_gpu": left.get("prefer_gpu", False) or right.get("prefer_gpu", False)}
    for group, features in FEATURE_GROUPS.items():
        source = left if rng.random() < 0.5 else right
        if any(feature in source["global_features"] for feature in features):
            child["global_features"].extend(features)
    if not child["global_features"]:
        child["global_features"].extend(FEATURE_GROUPS[rng.choice(list(FEATURE_GROUPS.keys()))])

    for model in models:
        child["models"][model] = {"enabled": True, "params": {}}
        for key in MODEL_PARAM_SPACE[model]:
            source = left if rng.random() < 0.5 else right
            child["models"][model]["params"][key] = source["models"][model]["params"][key]
    return child


def summarize_groups(profile: dict) -> list[str]:
    active = []
    for group, features in FEATURE_GROUPS.items():
        if any(feature in profile["global_features"] for feature in features):
            active.append(group)
    return active


def score_result(result: dict) -> float:
    precision_blend = (result["long_precision"] + result["short_precision"]) / 2.0
    edge = max(result["predicted_long_avg_forward_return"], result["predicted_short_avg_forward_return"])
    recent_edge = 0.0
    if result.get("pair_breakdown"):
        recent_edge = max((max(row["recent_long_avg_forward_return"], row["recent_short_avg_forward_return"]) for row in result["pair_breakdown"]), default=0.0)
    return (
        result["accuracy"] * 0.20
        + result["balanced_accuracy"] * 0.35
        + precision_blend * 0.20
        + edge * 20.0
        + recent_edge * 25.0
    )


def evaluate_profile(profile: dict, requested_models: list[str], x_train: pd.DataFrame, y_train: pd.Series, x_test: pd.DataFrame, y_test: pd.Series, test_pairs: pd.Series, forward_returns: pd.Series, feature_columns: list[str], feature_mapping: dict[str, str], recent_window: int) -> dict:
    models = build_models(requested_models, profile, prefer_gpu=profile.get("prefer_gpu", False))
    results = []
    for model_key, name, model, model_profile in models:
        selected_columns = []
        for feature in profile["global_features"]:
            if feature in feature_mapping:
                selected_columns.append(feature_mapping[feature])
        selected_columns.extend([value for key, value in feature_mapping.items() if key.startswith("pair_")])
        selected_columns = list(dict.fromkeys(selected_columns))
        result = evaluate_model(
            name,
            model,
            x_train[selected_columns],
            y_train,
            x_test[selected_columns],
            y_test,
            forward_returns,
        )
        result["pair_breakdown"] = build_pair_breakdown(
            test_pairs,
            np.array(result.pop("predictions")),
            forward_returns,
            recent_window,
        )
        result["fitness"] = round(score_result(result), 6)
        result["feature_count"] = len(selected_columns)
        result["model_key"] = model_key
        results.append(result)

    total_fitness = float(np.mean([item["fitness"] for item in results])) if results else -999.0
    return {
        "fitness": round(total_fitness, 6),
        "groups": summarize_groups(profile),
        "profile": profile,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Run a lightweight evolutionary search for local alt factor models.")
    parser.add_argument("--data-dir", default="/freqtrade/user_data/data/okx/futures")
    parser.add_argument("--pairs", required=True)
    parser.add_argument("--timeframe", default="5m")
    parser.add_argument("--horizon", type=int, default=12)
    parser.add_argument("--threshold", type=float, default=0.01)
    parser.add_argument("--recent-window", type=int, default=288)
    parser.add_argument("--models", default="tree,rf,hgb")
    parser.add_argument("--prefer-gpu", action="store_true")
    parser.add_argument("--population", type=int, default=8)
    parser.add_argument("--generations", type=int, default=3)
    parser.add_argument("--elite", type=int, default=2)
    parser.add_argument("--mutation-rate", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-samples", type=int, default=220000)
    parser.add_argument("--output-prefix", required=True)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    pairs = [pair.strip() for pair in args.pairs.split(",") if pair.strip()]
    requested_models = [item.strip().lower() for item in args.models.split(",") if item.strip()]
    output_prefix = Path(args.output_prefix)
    output_prefix.parent.mkdir(parents=True, exist_ok=True)

    dataset = load_dataset(Path(args.data_dir), pairs, args.timeframe, args.horizon, args.threshold)
    if len(dataset) > args.max_samples:
        dataset = dataset.tail(args.max_samples).reset_index(drop=True)

    feature_columns = get_feature_columns(dataset)
    split_index = int(len(dataset) * 0.8)
    train = dataset.iloc[:split_index]
    test = dataset.iloc[split_index:]

    x_train = sanitize_feature_names(train[feature_columns])
    x_test = test[feature_columns].rename(columns=dict(zip(feature_columns, x_train.columns.tolist())))
    y_train = train["target"]
    y_test = test["target"]
    test_pairs = test["pair_name"]
    forward_returns = test["forward_return"]
    feature_mapping = build_feature_mapping(feature_columns, x_train.columns.tolist())

    population = [build_base_profile(requested_models)]
    population[0]["prefer_gpu"] = args.prefer_gpu
    while len(population) < args.population:
        random_candidate = random_profile(requested_models, rng)
        random_candidate["prefer_gpu"] = args.prefer_gpu
        population.append(random_candidate)

    history = []
    best = None
    for generation in range(args.generations):
        scored = []
        for profile in population:
            evaluation = evaluate_profile(
                profile,
                requested_models,
                x_train,
                y_train,
                x_test,
                y_test,
                test_pairs,
                forward_returns,
                feature_columns,
                feature_mapping,
                args.recent_window,
            )
            scored.append(evaluation)
        scored.sort(key=lambda item: item["fitness"], reverse=True)
        generation_best = scored[0]
        history.append(
            {
                "generation": generation + 1,
                "best_fitness": generation_best["fitness"],
                "groups": generation_best["groups"],
                "results": generation_best["results"],
            }
        )
        if best is None or generation_best["fitness"] > best["fitness"]:
            best = deepcopy(generation_best)

        elites = scored[: max(1, min(args.elite, len(scored)))]
        next_population = [deepcopy(item["profile"]) for item in elites]
        while len(next_population) < args.population:
            left = rng.choice(elites)["profile"]
            right = rng.choice(elites)["profile"]
            child = crossover_profiles(left, right, requested_models, rng)
            child = mutate_profile(child, requested_models, rng, args.mutation_rate)
            next_population.append(child)
        population = next_population

    payload = {
        "metadata": {
            "pairs": pairs,
            "timeframe": args.timeframe,
            "horizon": args.horizon,
            "threshold": args.threshold,
            "recent_window": args.recent_window,
            "population": args.population,
            "generations": args.generations,
            "elite": args.elite,
            "mutation_rate": args.mutation_rate,
            "models": requested_models,
            "samples": int(len(dataset)),
        },
        "best": best,
        "history": history,
    }

    profile_json = output_prefix.with_suffix(".profile.json")
    result_json = output_prefix.with_suffix(".json")
    result_md = output_prefix.with_suffix(".md")
    profile_json.write_text(json.dumps(best["profile"], indent=2), encoding="utf-8")
    result_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Alt Factor Evolution Report",
        "",
        f"- Pairs: {', '.join(pairs)}",
        f"- Models: {', '.join(requested_models)}",
        f"- Samples: {len(dataset)}",
        f"- Population: {args.population}",
        f"- Generations: {args.generations}",
        "",
        "## Best Genome",
        "",
        f"- Fitness: {best['fitness']}",
        f"- Groups: {', '.join(best['groups'])}",
        "",
        "## Best Model Results",
        "",
    ]
    for result in best["results"]:
        lines.extend(
            [
                f"### {result['model']}",
                f"- Fitness: {result['fitness']}",
                f"- Accuracy: {result['accuracy']}",
                f"- Balanced accuracy: {result['balanced_accuracy']}",
                f"- Long precision: {result['long_precision']}",
                f"- Short precision: {result['short_precision']}",
                f"- Feature count: {result['feature_count']}",
                "",
            ]
        )
    lines.extend(["## History", ""])
    for item in history:
        lines.append(f"- Generation {item['generation']}: best fitness {item['best_fitness']} | groups {', '.join(item['groups'])}")
    result_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote {profile_json}")
    print(f"Wrote {result_json}")
    print(f"Wrote {result_md}")


if __name__ == "__main__":
    main()
