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
  approval: {
    decision: string
    thresholds: string
  }
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
