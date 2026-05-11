export interface DashboardStatusPayload {
  generated_at: string
  server: {
    hostname: string
  }
  bot: {
    name: string
    status: string
    running: boolean
    uptime: string
    started_at: string
    strategy: string
    timeframe: string
    max_open_trades: number
    dry_run: boolean
    stake_currency: string
    stake_amount: number | string | null
    listen_port: number
    pair_count: number
    tradable_pairs: string[]
    live_trading?: {
      synced_at?: string
      open_trade_count: number | null
      open_trade_pairs: string[]
      total_profit_abs?: number | null
      total_profit_ratio?: number | null
      cumulative_profit_abs?: number | null
      cumulative_profit_ratio?: number | null
      closed_profit_abs?: number | null
      closed_profit_ratio?: number | null
      closed_trade_count?: number | null
      profit_currency?: string
      profit_error?: string | null
      trades?: Array<{
        pair: string
        trade_id?: string | number
        profit_abs?: number | null
        profit_ratio?: number | null
        is_short?: boolean
        open_date?: string
        stake_amount?: number | null
        amount?: number | null
        open_rate?: number | null
        current_rate?: number | null
        leverage?: number | null
      }>
      error?: string
    }
  }
  api: {
    healthy: boolean
    response: string
    checked_at: string
  }
  sync: {
    last_sync_at: string
    mode: string
    strategy: string
    timeframe: string
    selected_pair_count: number
    selected_pairs: string[]
    validation_ok: boolean
    validation_http_code: number
  }
}

export async function fetchDashboardStatus(): Promise<DashboardStatusPayload> {
  const response = await fetch(`/dashboard-data/status.json?t=${Date.now()}`, {
    cache: 'no-store',
  })

  if (!response.ok) {
    throw new Error(`status fetch failed: ${response.status}`)
  }

  return response.json() as Promise<DashboardStatusPayload>
}
