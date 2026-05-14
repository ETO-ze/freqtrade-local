export interface ApprovalGateCheck {
  name: string
  actual: number | string
  threshold: number | string
  op: string
  passed: boolean
  bypass_profit_pct?: number
}

export interface ApprovalGateBreakdown {
  standard_passed?: boolean
  experimental_passed?: boolean
  standard_checks?: ApprovalGateCheck[]
  experimental_checks?: ApprovalGateCheck[]
}

export interface ApprovalSummary {
  decision: string
  thresholds: string
  approved_for_sync?: boolean
  approval_mode?: string
  gate_breakdown?: ApprovalGateBreakdown
  stability?: Record<string, unknown>
  probe_backtest?: {
    enabled?: boolean
    allowed_dynamic_pools?: string
    max_pairs?: number
    ready?: boolean
    note?: string
    summary?: {
      metrics?: Record<string, number | string>
      latest_backtest?: string
    }
  }
  promotion_protection?: Record<string, unknown>
}

export interface BacktestPayload {
  generated_at: string
  display_mode?: string
  strategy: string
  timerange: string
  latest_backtest: string
  metrics: Record<string, number | string>
  selected_pairs: string[]
  active_factor?: {
    generated_at?: string
    strategy?: string
    best_model?: string
    approval_mode?: string
    latest_backtest?: string
    selected_pairs?: string[]
    metrics?: Record<string, number | string>
    top_factors?: Array<{
      Feature: string
      WeightedImportance: number
    }>
    source?: string
  }
  latest_candidate?: {
    generated_at: string
    strategy: string
    timerange: string
    latest_backtest: string
    metrics: Record<string, number | string>
    approval: {
      decision: string
      thresholds: string
      approved_for_sync?: boolean
      approval_mode?: string
      gate_breakdown?: ApprovalGateBreakdown
      stability?: Record<string, unknown>
      probe_backtest?: ApprovalSummary['probe_backtest']
      promotion_protection?: Record<string, unknown>
    }
  }
  best_model: {
    model: string
    weight: number
  }
  top_factors: Array<{
    Feature: string
    WeightedImportance: number
  }>
  timings: Array<{
    step: string
    status: string
    duration_seconds: number
    attempts: number
    note: string
  }>
  feedback_leaders: Array<{
    pair: string
    feedback_score: number
    trades: number
    winrate: number
    profit_factor: number
    suggested_action: string
  }>
  approval: ApprovalSummary
  live_trading?: {
    generated_at?: string
    mode?: string
    bot_running?: boolean | string
    bot_status?: string
    api_ok?: boolean
    api_http_code?: number | string
    restart_action?: string
    restart_reason?: string
    open_trade_count?: number | null
    open_trade_pairs?: string[]
    total_open_profit_abs?: number | string | null
    open_trades?: Array<{
      pair?: string
      direction?: string
      leverage?: number | string | null
      profit_abs?: number | string | null
      profit_pct?: number | string | null
      open_date?: string
    }>
  }
  walk_forward_retrain?: {
    generated_at?: string
    passed?: boolean
    score?: number
    passed_windows?: number
    window_count?: number
    required_passed_windows?: number
    best_model_consensus?: string
    hard_blocks?: string[]
    data_start?: string
    data_end?: string
    pairs?: string[]
    stability_summary?: {
      stability_grade?: string
      recommended_gate_mode?: string
      blockers?: string[]
      failed_window_count?: number
      failed_window_names?: string[]
      memory_failure_count?: number
      passed_window_ratio?: number
      model_consensus?: string
      model_consensus_count?: number
      model_consensus_ratio?: number
      dominant_feature_family?: string
      dominant_feature_family_count?: number
      dominant_feature_family_ratio?: number
      average_weight?: number
      min_weight?: number
      weight_std?: number
      average_balanced_accuracy?: number
      average_orthogonal_feature_share?: number
      min_orthogonal_feature_share?: number
      average_max_feature_family_share?: number
      max_feature_family_share?: number
      low_orthogonal_window_count?: number
      high_family_concentration_window_count?: number
    }
    windows?: Array<{
      name?: string
      train_start?: string
      train_end?: string
      test_start?: string
      test_end?: string
      ok?: boolean
      passed?: boolean
      best_model?: string
      best_weight?: number
      balanced_accuracy?: number
      long_precision?: number
      short_precision?: number
      orthogonal_feature_share?: number
      dominant_feature_family?: string
      train_samples?: number
      test_samples?: number
      error?: string
    }>
  }
  feature_family_ablation?: {
    enabled?: boolean
    exclude?: string
    status?: string
    output_json?: string
    main_best_model?: string
    main_best_weight?: number
    ablation_best_model?: string
    ablation_best_weight?: number
    weight_delta?: number
    family_risk?: string
    mark_premium_family_share?: number
    orthogonal_feature_share?: number
    capped_dominant_feature_family?: string
    capped_max_feature_family_share?: number
    note?: string
    top_factors?: Array<{
      feature?: string
      importance?: number
    }>
  }
  backtest_detail?: {
    source_zip?: string
    strategy_name?: string
    starting_balance?: number
    final_balance?: number
    max_drawdown_pct?: number
    trade_count_long?: number
    trade_count_short?: number
    error?: string
    equity_curve?: Array<{
      date: string
      profit_abs: number
      equity: number
      drawdown_pct: number
    }>
    pair_ranking?: Array<{
      pair: string
      trades: number
      profit_total_pct: number
      profit_total_abs: number
      winrate: number
      profit_factor: number
      max_drawdown_abs: number
    }>
    side_stats?: Array<{
      side: string
      trades: number
      wins: number
      losses: number
      winrate: number
      profit_abs: number
      avg_profit_pct: number
      avg_leverage: number
    }>
    monthly?: Array<{
      date: string
      year: number
      month: number
      profit_abs: number
      profit_pct: number
      trades: number
      wins: number
      losses: number
      profit_factor: number
    }>
    pair_trade_stats?: Array<{
      pair: string
      trades: number
      wins: number
      losses: number
      winrate: number
      profit_abs: number
      avg_profit_pct: number
      avg_leverage: number
      long_trades: number
      short_trades: number
    }>
  }
  project_roadmap?: {
    generated_at?: string
    items?: Array<{
      id: string
      title: string
      title_en?: string
      status: string
      status_label?: string
      priority?: string
      enabled?: boolean
      safe_to_trade?: boolean
      summary?: string
      current_state?: string
      next_step?: string
      affected_modules?: string[]
    }>
  }
  approved_history?: Array<{
    generated_at?: string
    approval_mode?: string
    model?: string
    best_model?: string
    strategy?: string
    total_profit_pct?: number
    profit_factor?: number
    winrate?: number
    winrate_pct?: number
    max_drawdown_pct?: number
    trade_count?: number
    selected_pairs?: string[]
    execution_target?: string
  }> | {
    generated_at?: string
    approval_mode?: string
    model?: string
    best_model?: string
    strategy?: string
    total_profit_pct?: number
    profit_factor?: number
    winrate?: number
    winrate_pct?: number
    max_drawdown_pct?: number
    trade_count?: number
    selected_pairs?: string[]
    execution_target?: string
  }
}

export async function fetchBacktestData(): Promise<BacktestPayload> {
  const response = await fetch(`/dashboard-data/backtest.json?t=${Date.now()}`, {
    cache: 'no-store',
  })

  if (!response.ok) {
    throw new Error(`backtest fetch failed: ${response.status}`)
  }

  return response.json() as Promise<BacktestPayload>
}
