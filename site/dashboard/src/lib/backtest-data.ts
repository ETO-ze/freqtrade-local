export interface BacktestPayload {
  generated_at: string
  strategy: string
  timerange: string
  latest_backtest: string
  metrics: Record<string, number | string>
  selected_pairs: string[]
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
