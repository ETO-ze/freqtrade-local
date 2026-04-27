export interface AlertsPayload {
  generated_at: string
  counts: {
    critical: number
    warning: number
    info: number
  }
  alerts: Array<{
    severity: 'critical' | 'warning' | 'info'
    source: string
    title: string
    detail: string
    occurred_at: string
  }>
}

export async function fetchAlertsData(): Promise<AlertsPayload> {
  const response = await fetch(`/dashboard-data/alerts.json?t=${Date.now()}`, {
    cache: 'no-store',
  })

  if (!response.ok) {
    throw new Error(`alerts fetch failed: ${response.status}`)
  }

  return response.json() as Promise<AlertsPayload>
}
