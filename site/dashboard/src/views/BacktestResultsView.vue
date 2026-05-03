<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { fetchBacktestData, type BacktestPayload } from '../lib/backtest-data'

const loading = ref(true)
const error = ref('')
const payload = ref<BacktestPayload | null>(null)

const headlineMetrics = computed(() => {
  if (!payload.value) return []
  const metrics = payload.value.metrics
  return [
    { label: '总收益', value: `${metrics.total_profit_pct ?? 'n/a'}%` },
    { label: '利润因子', value: String(metrics.profit_factor ?? 'n/a') },
    { label: '最大回撤', value: `${metrics.max_drawdown_pct ?? 'n/a'}%` },
    { label: '交易次数', value: String(metrics.trade_count ?? 'n/a') },
  ]
})

const approvedHistory = computed(() => {
  const history = payload.value?.approved_history
  if (!history) return []
  return Array.isArray(history) ? history : [history]
})

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
      <p class="panel-kicker">BACKTEST BOARD</p>
      <h3>最新稳定回测结果</h3>
      <p class="panel-copy">
        展示 stable 流程最近一次候选回测、模型选择、审批结论与云端可同步币池。该页只读，不直接操作交易。
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
      <p class="panel-kicker">SNAPSHOT</p>
      <h3>回测快照</h3>
      <div class="key-grid">
        <div><span>策略</span><strong>{{ payload.strategy }}</strong></div>
        <div><span>区间</span><strong>{{ payload.timerange }}</strong></div>
        <div><span>最佳模型</span><strong>{{ payload.best_model.model }}</strong></div>
        <div><span>模型权重</span><strong>{{ payload.best_model.weight }}</strong></div>
        <div><span>结果包</span><strong>{{ payload.latest_backtest }}</strong></div>
        <div><span>审批结果</span><strong>{{ payload.approval.decision || 'n/a' }}</strong></div>
      </div>
    </article>

    <article class="panel span-2" v-if="payload">
      <p class="panel-kicker">PAIR SET</p>
      <h3>同步候选币池</h3>
      <div class="pair-list">
        <div>
          <span>当前选择</span>
          <p>{{ payload.selected_pairs.map(shortPair).join(', ') || 'none' }}</p>
        </div>
        <div>
          <span>审批门槛</span>
          <p>{{ payload.approval.thresholds || 'n/a' }}</p>
        </div>
      </div>
    </article>

    <article class="panel span-3" v-if="approvedHistory.length">
      <p class="panel-kicker">APPROVED FACTORS</p>
      <h3>已审批因子历史</h3>
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
      <h3>关键因子</h3>
      <div class="list-table">
        <div v-for="item in payload?.top_factors || []" :key="item.Feature" class="list-row">
          <span>{{ item.Feature }}</span>
          <strong>{{ item.WeightedImportance }}</strong>
        </div>
      </div>
    </article>

    <article class="panel">
      <p class="panel-kicker">TIMINGS</p>
      <h3>流程耗时</h3>
      <div class="list-table">
        <div v-for="item in payload?.timings || []" :key="item.step" class="list-row">
          <span>{{ item.step }} / {{ item.status }}</span>
          <strong>{{ item.duration_seconds }}s</strong>
        </div>
      </div>
    </article>

    <article class="panel span-2">
      <p class="panel-kicker">TRADE FEEDBACK</p>
      <h3>反馈领先币种</h3>
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
