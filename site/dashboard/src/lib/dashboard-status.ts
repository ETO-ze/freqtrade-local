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
