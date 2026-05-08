<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { fetchBacktestData, type BacktestPayload } from '../lib/backtest-data'

const loading = ref(true)
const error = ref('')
const payload = ref<BacktestPayload | null>(null)

const activeMetrics = computed(() => payload.value?.active_factor?.metrics || payload.value?.metrics || {})
const candidateMetrics = computed(() => payload.value?.latest_candidate?.metrics || {})

const headlineMetrics = computed(() => {
  const metrics = activeMetrics.value
  return [
    { label: '总收益', value: formatPct(metrics.total_profit_pct) },
    { label: '利润因子', value: formatValue(metrics.profit_factor) },
    { label: '胜率', value: formatPct(metrics.winrate) },
    { label: '最大回撤', value: formatPct(metrics.max_drawdown_pct) },
    { label: '交易次数', value: formatValue(metrics.trade_count) },
  ]
})

const approvedHistory = computed(() => {
  const history = payload.value?.approved_history
  if (!history) return []
  return Array.isArray(history) ? history : [history]
})

function formatValue(value: unknown) {
  return value === undefined || value === null || value === '' ? 'n/a' : String(value)
}

function formatPct(value: unknown) {
  return value === undefined || value === null || value === '' ? 'n/a' : `${value}%`
}

function shortPair(pair: string) {
  return pair.replace('/USDT:USDT', '').replace('/USDT', '')
}

function historyModel(item: { model?: string; best_model?: string }) {
  return item.model || item.best_model || 'n/a'
}

function historyWinrate(item: { winrate?: number; winrate_pct?: number }) {
  return item.winrate_pct ?? item.winrate ?? 'n/a'
}

async function loadBacktest() {
  loading.value = true
  error.value = ''
  try {
    payload.value = await fetchBacktestData()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'unknown error'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadBacktest()
})
</script>

<template>
  <section class="page-grid">
    <article class="panel hero-panel span-2">
      <p class="panel-kicker">ACTIVE BACKTEST</p>
      <h3>正在使用的回测结果</h3>
      <p class="panel-copy">
        这里优先展示当前 active 配置对应的已批准因子，而不是最新候选回测。最新候选如果未过门槛，只会作为旁路参考，不会覆盖正在交易的云端配置。
      </p>

      <div v-if="loading" class="info-banner">正在读取回测结果...</div>
      <div v-else-if="error" class="info-banner is-error">
        回测数据读取失败：{{ error }}
      </div>
      <div v-else-if="payload" class="key-grid status-grid-live">
        <div v-for="item in headlineMetrics" :key="item.label">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </div>
    </article>

    <article class="panel" v-if="payload">
      <p class="panel-kicker">ACTIVE FACTOR</p>
      <h3>当前生效因子</h3>
      <div class="key-grid">
        <div><span>策略</span><strong>{{ payload.active_factor?.strategy || payload.strategy || 'n/a' }}</strong></div>
        <div><span>模型</span><strong>{{ payload.active_factor?.best_model || payload.best_model.model || 'n/a' }}</strong></div>
        <div><span>批准时间</span><strong>{{ payload.active_factor?.generated_at || 'n/a' }}</strong></div>
        <div><span>批准模式</span><strong>{{ payload.active_factor?.approval_mode || 'n/a' }}</strong></div>
        <div><span>结果包</span><strong>{{ payload.active_factor?.latest_backtest || payload.latest_backtest || 'n/a' }}</strong></div>
        <div><span>来源</span><strong>{{ payload.active_factor?.source || payload.display_mode || 'n/a' }}</strong></div>
      </div>
    </article>

    <article class="panel span-2" v-if="payload">
      <p class="panel-kicker">ACTIVE PAIRS</p>
      <h3>当前云端交易币池</h3>
      <div class="pair-list">
        <div>
          <span>当前 active 白名单</span>
          <p>{{ payload.selected_pairs.map(shortPair).join(', ') || 'none' }}</p>
        </div>
        <div>
          <span>审批门槛</span>
          <p>{{ payload.approval.thresholds || 'n/a' }}</p>
        </div>
      </div>
    </article>

    <article class="panel" v-if="payload?.latest_candidate">
      <p class="panel-kicker">LATEST CANDIDATE</p>
      <h3>最新候选回测</h3>
      <div class="key-grid">
        <div><span>收益</span><strong>{{ formatPct(candidateMetrics.total_profit_pct) }}</strong></div>
        <div><span>利润因子</span><strong>{{ formatValue(candidateMetrics.profit_factor) }}</strong></div>
        <div><span>胜率</span><strong>{{ formatPct(candidateMetrics.winrate) }}</strong></div>
        <div><span>回撤</span><strong>{{ formatPct(candidateMetrics.max_drawdown_pct) }}</strong></div>
        <div><span>交易</span><strong>{{ formatValue(candidateMetrics.trade_count) }}</strong></div>
        <div><span>结论</span><strong>{{ payload.latest_candidate.approval.decision || 'n/a' }}</strong></div>
      </div>
    </article>

    <article class="panel span-3" v-if="approvedHistory.length">
      <p class="panel-kicker">APPROVED FACTORS</p>
      <h3>已批准因子历史</h3>
      <div class="list-table">
        <div v-for="item in approvedHistory" :key="`${item.generated_at}-${historyModel(item)}`" class="list-row multi">
          <div>
            <strong>{{ item.generated_at || 'n/a' }} / {{ historyModel(item) }}</strong>
            <p>
              模式 {{ item.approval_mode || 'standard' }} |
              收益 {{ item.total_profit_pct ?? 'n/a' }}% |
              PF {{ item.profit_factor ?? 'n/a' }} |
              胜率 {{ historyWinrate(item) }}% |
              回撤 {{ item.max_drawdown_pct ?? 'n/a' }}% |
              交易 {{ item.trade_count ?? 'n/a' }} |
              执行 {{ item.execution_target || 'cloud_only' }}
            </p>
            <p>币池：{{ item.selected_pairs?.map(shortPair).join(', ') || 'none' }}</p>
          </div>
        </div>
      </div>
    </article>

    <article class="panel">
      <p class="panel-kicker">TOP FACTORS</p>
      <h3>当前关键因子</h3>
      <div class="list-table">
        <div v-for="item in payload?.top_factors || []" :key="item.Feature" class="list-row">
          <span>{{ item.Feature }}</span>
          <strong>{{ item.WeightedImportance }}</strong>
        </div>
      </div>
    </article>

    <article class="panel">
      <p class="panel-kicker">TIMINGS</p>
      <h3>最近 stable 流程耗时</h3>
      <div class="list-table">
        <div v-for="item in payload?.timings || []" :key="item.step" class="list-row">
          <span>{{ item.step }} / {{ item.status }}</span>
          <strong>{{ item.duration_seconds }}s</strong>
        </div>
      </div>
    </article>

    <article class="panel span-2">
      <p class="panel-kicker">TRADE FEEDBACK</p>
      <h3>交易反馈领先币种</h3>
      <div class="list-table">
        <div v-for="item in payload?.feedback_leaders || []" :key="item.pair" class="list-row multi">
          <div>
            <strong>{{ item.pair }}</strong>
            <p>
              score {{ item.feedback_score }} | trades {{ item.trades }} | winrate {{ item.winrate }}% |
              pf {{ item.profit_factor }} | {{ item.suggested_action }}
            </p>
          </div>
        </div>
      </div>
    </article>
  </section>
</template>
