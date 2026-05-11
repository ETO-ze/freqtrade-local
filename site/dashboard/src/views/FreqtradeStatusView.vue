<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { fetchDashboardStatus, type DashboardStatusPayload } from '../lib/dashboard-status'

const loading = ref(true)
const error = ref('')
const status = ref<DashboardStatusPayload | null>(null)
let refreshTimer: number | undefined

const botStateLabel = computed(() => {
  if (!status.value) return 'unknown'
  return status.value.bot.running ? 'running' : status.value.bot.status || 'stopped'
})

const liveTrading = computed(() => status.value?.bot.live_trading)

function shortPair(pair: string) {
  return pair.replace('/USDT:USDT', '').replace('/USDT', '')
}

function formatPct(value: unknown) {
  if (value === undefined || value === null || value === '') return 'n/a'
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return String(value)
  return `${(numeric * 100).toFixed(2)}%`
}

function formatAmount(value: unknown, currency = '') {
  if (value === undefined || value === null || value === '') return 'n/a'
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return String(value)
  const suffix = currency ? ` ${currency}` : ''
  return `${numeric.toFixed(4)}${suffix}`
}

function formatDateTime(value: unknown) {
  if (!value) return 'n/a'
  const date = new Date(String(value))
  if (Number.isNaN(date.getTime())) return String(value)
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(date)
  const lookup = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return `${lookup.year}-${lookup.month}-${lookup.day} ${lookup.hour}:${lookup.minute}:${lookup.second}`
}

function numericTone(value: unknown) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric) || numeric === 0) return ''
  return numeric > 0 ? 'is-positive' : 'is-negative'
}

function directionLabel(isShort?: boolean) {
  return isShort ? '空头' : '多头'
}

function directionClass(isShort?: boolean) {
  return isShort ? 'is-short' : 'is-long'
}

async function loadStatus() {
  loading.value = true
  error.value = ''
  try {
    status.value = await fetchDashboardStatus()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'unknown error'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadStatus()
  refreshTimer = window.setInterval(loadStatus, 30000)
})

onBeforeUnmount(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
})
</script>

<template>
  <section class="page-grid">
    <article class="panel hero-panel span-2">
      <p class="panel-kicker">FREQTRADE STATUS</p>
      <h3>服务器只读实时状态</h3>
      <p class="panel-copy">
        该页面读取服务器公开只读聚合 JSON，用于显示 bot 运行状态、最近同步时间和 API 健康检查，不直接暴露交易控制。
      </p>

      <div v-if="loading" class="info-banner">正在读取服务器状态...</div>
      <div v-else-if="error" class="info-banner is-error">
        状态读取失败：{{ error }}
      </div>
      <div v-else-if="status" class="key-grid status-grid-live">
        <div>
          <span>Bot 状态</span>
          <strong>{{ botStateLabel }}</strong>
        </div>
        <div>
          <span>API 健康</span>
          <strong>{{ status.api.healthy ? 'healthy' : 'unhealthy' }}</strong>
        </div>
        <div>
          <span>最近同步</span>
          <strong>{{ status.sync.last_sync_at || 'n/a' }}</strong>
        </div>
        <div>
          <span>服务器主机</span>
          <strong>{{ status.server.hostname }}</strong>
        </div>
      </div>
    </article>

    <article class="panel" v-if="status">
      <p class="panel-kicker">BOT SNAPSHOT</p>
      <h3>运行快照</h3>
      <div class="key-grid">
        <div><span>策略</span><strong>{{ status.bot.strategy }}</strong></div>
        <div><span>周期</span><strong>{{ status.bot.timeframe }}</strong></div>
        <div><span>最大持仓</span><strong>{{ status.bot.max_open_trades }}</strong></div>
        <div><span>模式</span><strong>{{ status.bot.dry_run ? 'dry-run' : 'live' }}</strong></div>
        <div><span>持仓币种数</span><strong>{{ status.bot.pair_count }}</strong></div>
        <div><span>容器在线时长</span><strong>{{ status.bot.uptime || 'n/a' }}</strong></div>
      </div>
    </article>

    <article class="panel span-2" v-if="status">
      <p class="panel-kicker">SYNC INFO</p>
      <h3>最近同步记录</h3>
      <div class="key-grid">
        <div><span>同步时间</span><strong>{{ status.sync.last_sync_at || 'n/a' }}</strong></div>
        <div><span>同步模式</span><strong>{{ status.sync.mode || 'n/a' }}</strong></div>
        <div><span>同步策略</span><strong>{{ status.sync.strategy || 'n/a' }}</strong></div>
        <div><span>同步校验</span><strong>{{ status.sync.validation_ok ? 'ok' : 'failed' }}</strong></div>
      </div>
      <div class="pair-list">
        <div>
          <span>当前可交易币池</span>
          <p>{{ status.bot.tradable_pairs.join(', ') || 'none' }}</p>
        </div>
        <div>
          <span>最近同步币池</span>
          <p>{{ status.sync.selected_pairs.join(', ') || 'none' }}</p>
        </div>
      </div>
    </article>

    <article class="panel span-3" v-if="status">
      <p class="panel-kicker">LIVE POSITIONS</p>
      <h3>实盘持仓只读摘要</h3>
      <div v-if="!liveTrading" class="info-banner">当前状态 JSON 暂未包含持仓详情。</div>
      <div v-else-if="liveTrading.error" class="info-banner is-error">
        持仓读取失败：{{ liveTrading.error }}
      </div>
      <template v-else>
        <div class="position-summary-grid">
          <div class="position-metric is-primary" :class="numericTone(liveTrading.cumulative_profit_abs)">
            <span>总收益</span>
            <strong>{{ formatAmount(liveTrading.cumulative_profit_abs, liveTrading.profit_currency) }}</strong>
            <small>{{ formatPct(liveTrading.cumulative_profit_ratio) }}</small>
          </div>
          <div class="position-metric" :class="numericTone(liveTrading.closed_profit_abs)">
            <span>已平仓收益</span>
            <strong>{{ formatAmount(liveTrading.closed_profit_abs, liveTrading.profit_currency) }}</strong>
            <small>{{ liveTrading.closed_trade_count ?? 'n/a' }} 笔已平仓</small>
          </div>
          <div class="position-metric" :class="numericTone(liveTrading.total_profit_abs)">
            <span>当前浮动收益</span>
            <strong>{{ formatAmount(liveTrading.total_profit_abs, liveTrading.profit_currency) }}</strong>
            <small>{{ formatPct(liveTrading.total_profit_ratio) }}</small>
          </div>
          <div class="position-metric">
            <span>当前持仓</span>
            <strong>{{ liveTrading.open_trade_count ?? 'n/a' }}</strong>
            <small>{{ liveTrading.open_trade_pairs?.map(shortPair).join(', ') || 'none' }}</small>
          </div>
          <div class="position-metric is-wide">
            <span>持仓同步时间</span>
            <strong>{{ formatDateTime(liveTrading.synced_at) }}</strong>
          </div>
        </div>
        <div class="list-table" v-if="liveTrading.trades?.length">
          <div v-for="trade in liveTrading.trades" :key="`${trade.pair}-${trade.open_date}`" class="position-row">
            <div>
              <div class="position-row-head">
                <strong>{{ shortPair(trade.pair) }}</strong>
                <span class="direction-pill" :class="directionClass(trade.is_short)">
                  {{ directionLabel(trade.is_short) }}
                </span>
                <span class="leverage-pill">{{ trade.leverage ?? 'n/a' }}x</span>
              </div>
              <p>开仓 {{ trade.open_date || 'n/a' }}</p>
            </div>
            <div class="position-row-metrics">
              <span :class="numericTone(trade.profit_abs)">
                收益 <strong>{{ formatAmount(trade.profit_abs, liveTrading.profit_currency) }}</strong>
              </span>
              <span :class="numericTone(trade.profit_ratio)">
                收益率 <strong>{{ formatPct(trade.profit_ratio) }}</strong>
              </span>
              <span>开仓价 <strong>{{ trade.open_rate ?? 'n/a' }}</strong></span>
              <span>当前价 <strong>{{ trade.current_rate ?? 'n/a' }}</strong></span>
              <span>仓位 <strong>{{ formatAmount(trade.stake_amount, liveTrading.profit_currency) }}</strong></span>
            </div>
          </div>
        </div>
      </template>
    </article>
  </section>
</template>
