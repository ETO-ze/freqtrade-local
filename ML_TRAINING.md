# Tree Model Training

This workflow trains tree-based models on local OKX futures data.

Run it inside the existing Freqtrade container:

```powershell
docker exec freqtrade python /freqtrade/user_data/notebooks/train_alt_tree_models.py `
  --pairs "PIPPIN/USDT:USDT,ANIME/USDT:USDT,FLOKI/USDT:USDT,RVN/USDT:USDT" `
  --timeframe 5m `
  --horizon 12 `
  --threshold 0.01 `
  --models "tree,rf,lgbm"
```

Reports are written to:

- `/freqtrade/user_data/reports/ml/alt-tree-model-latest.json`
- `/freqtrade/user_data/reports/ml/alt-tree-model-latest.md`

The output is useful as a ranking or regime filter. It should not directly control live leverage or order execution without additional validation.

Supported model keys:

- `tree`: `DecisionTreeClassifier`
- `rf`: `RandomForestClassifier`
- `lgbm`: `LGBMClassifier` when `lightgbm` is installed
- `hgb`: `HistGradientBoostingClassifier`
