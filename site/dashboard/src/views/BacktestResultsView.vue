<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { fetchBacktestData, type BacktestPayload } from '../lib/backtest-data'

const loading = ref(true)
const error = ref('')
const payload = ref<BacktestPayload | null>(null)

const activeMetrics = computed(() => payload.value?.active_factor?.metrics || payload.value?.metrics || {})
const candidateMetrics = computed(() => payload.value?.latest_candidate?.metrics || {})
const approvalChecks = computed(() => {
  const gate = payload.value?.latest_candidate?.approval?.gate_breakdown || payload.value?.approval?.gate_breakdown
  const standard = gate?.standard_checks || []
  const experimental = gate?.experimental_checks || []
  return [
    ...standard.map((item) => ({ ...item, group: 'standard' })),
    ...experimental.map((item) => ({ ...item, group: 'experimental' })),
  ]
})
const probeBacktest = computed(() => {
  const probe = payload.value?.latest_candidate?.approval?.probe_backtest || payload.value?.approval?.probe_backtest
  return probe && Object.keys(probe).length ? probe : null
})
const probeMetrics = computed(() => probeBacktest.value?.summary?.metrics || {})
const backtestDetail = computed(() => payload.value?.backtest_detail)
const liveTrading = computed(() => payload.value?.live_trading)
const walkForward = computed(() => {
  const data = payload.value?.walk_forward_retrain
  return data && Object.keys(data).length ? data : null
})
const walkForwardStability = computed(() => walkForward.value?.stability_summary || null)
const featureFamilyAblation = computed(() => {
  const data = payload.value?.feature_family_ablation
  return data && Object.keys(data).length ? data : null
})
const equityCurve = computed(() => backtestDetail.value?.equity_curve || [])
const drawdownCurve = computed(() => equityCurve.value.map((item) => ({ ...item, drawdown_abs_pct: Math.abs(item.drawdown_pct) })))
const pairRanking = computed(() => (backtestDetail.value?.pair_ranking || []).slice(0, 12))
const pairTradeStats = computed(() => (backtestDetail.value?.pair_trade_stats || []).slice(0, 12))
const monthlyRows = computed(() => backtestDetail.value?.monthly || [])
const roadmapItems = computed(() => payload.value?.project_roadmap?.items || [])

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

function numericValue(value: unknown) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function formatSignedPct(value: unknown) {
  const parsed = numericValue(value)
  return `${parsed >= 0 ? '+' : ''}${parsed.toFixed(2)}%`
}

function linePoints(items: Array<Record<string, unknown>>, key: string, height = 180, width = 760) {
  if (items.length < 2) return ''
  const values = items.map((item) => numericValue(item[key]))
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  return values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * width
      const y = height - ((value - min) / span) * height
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}

function barWidth(value: unknown, values: unknown[]) {
  const max = Math.max(...values.map((item) => Math.abs(numericValue(item))), 1)
  return `${Math.max(4, (Math.abs(numericValue(value)) / max) * 100)}%`
}

function monthName(month: number) {
  return ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][month - 1] || String(month)
}

function heatTone(value: unknown) {
  const parsed = numericValue(value)
  if (parsed > 5) return 'is-strong-profit'
  if (parsed > 0) return 'is-profit'
  if (parsed < -5) return 'is-strong-loss'
  if (parsed < 0) return 'is-loss'
  return 'is-flat'
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
        这里优先展示当前 active 配置对应的已批准因子，而不是最新候选回测。最新候选如果未过门槛，只作为旁路参考，不覆盖云端配置。
      </p>

      <div v-if="loading" class="info-banner">正在读取回测结果...</div>
      <div v-else-if="error" class="info-banner is-error">回测数据读取失败：{{ error }}</div>
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

    <article class="panel span-3" v-if="walkForward">
      <p class="panel-kicker">WALK-FORWARD RETRAIN</p>
      <h3>独立窗口重训状态</h3>
      <p class="panel-copy">
        该模块读取 stable 生成的 walk-forward 报告。当前为 report-only，用于观察模型是否跨验证期、测试期和最近窗口保持稳定。
      </p>
      <div class="key-grid status-grid-live">
        <div><span>结果</span><strong>{{ walkForward.passed ? 'passed' : 'report-only / not passed' }}</strong></div>
        <div><span>评分</span><strong>{{ walkForward.score ?? 'n/a' }}</strong></div>
        <div><span>窗口通过</span><strong>{{ walkForward.passed_windows ?? 'n/a' }} / {{ walkForward.window_count ?? 'n/a' }}</strong></div>
        <div><span>要求通过</span><strong>{{ walkForward.required_passed_windows ?? 'n/a' }}</strong></div>
        <div><span>共识模型</span><strong>{{ walkForward.best_model_consensus || 'n/a' }}</strong></div>
        <div><span>硬阻断</span><strong>{{ walkForward.hard_blocks?.join(', ') || 'none' }}</strong></div>
      </div>
      <div class="key-grid status-grid-live" v-if="walkForwardStability">
        <div><span>稳定等级</span><strong>{{ walkForwardStability.stability_grade || 'n/a' }}</strong></div>
        <div><span>建议模式</span><strong>{{ walkForwardStability.recommended_gate_mode || 'n/a' }}</strong></div>
        <div><span>模型共识率</span><strong>{{ walkForwardStability.model_consensus_ratio ?? 'n/a' }}</strong></div>
        <div><span>主导特征族</span><strong>{{ walkForwardStability.dominant_feature_family || 'n/a' }}</strong></div>
        <div><span>特征族占比</span><strong>{{ walkForwardStability.max_feature_family_share ?? 'n/a' }}</strong></div>
        <div><span>正交因子占比</span><strong>{{ walkForwardStability.average_orthogonal_feature_share ?? 'n/a' }}</strong></div>
        <div><span>内存失败</span><strong>{{ walkForwardStability.memory_failure_count ?? 0 }}</strong></div>
        <div><span>阻断原因</span><strong>{{ walkForwardStability.blockers?.join(', ') || 'none' }}</strong></div>
      </div>
      <div class="list-table compact-table">
        <div v-for="item in walkForward.windows || []" :key="item.name" class="list-row multi">
          <div>
            <strong>{{ item.name }} / {{ item.best_model || 'n/a' }} / weight {{ item.best_weight ?? 'n/a' }}</strong>
            <p>
              train {{ item.train_start }} - {{ item.train_end }} |
              test {{ item.test_start }} - {{ item.test_end }} |
              rows {{ item.train_samples ?? 'n/a' }} / {{ item.test_samples ?? 'n/a' }} |
              passed {{ item.passed ? 'yes' : 'no' }}
            </p>
            <p v-if="item.error">error: {{ item.error }}</p>
          </div>
          <span class="badge">{{ item.ok ? 'ok' : 'failed' }}</span>
        </div>
      </div>
    </article>

    <article class="panel" v-if="featureFamilyAblation">
      <p class="panel-kicker">FEATURE ABLATION</p>
      <h3>特征家族消融对照</h3>
      <p class="panel-copy">
        该模块用于观察排除 mark premium 等特征家族后模型是否仍有可用信号。默认只读展示，不参与自动 promotion。
      </p>
      <div class="key-grid">
        <div><span>状态</span><strong>{{ featureFamilyAblation.status || 'n/a' }}</strong></div>
        <div><span>排除家族</span><strong>{{ featureFamilyAblation.exclude || 'n/a' }}</strong></div>
        <div><span>主模型</span><strong>{{ featureFamilyAblation.main_best_model || 'n/a' }}</strong></div>
        <div><span>主权重</span><strong>{{ featureFamilyAblation.main_best_weight ?? 'n/a' }}</strong></div>
        <div><span>消融模型</span><strong>{{ featureFamilyAblation.ablation_best_model || 'n/a' }}</strong></div>
        <div><span>权重差</span><strong>{{ featureFamilyAblation.weight_delta ?? 'n/a' }}</strong></div>
        <div><span>风险</span><strong>{{ featureFamilyAblation.family_risk || 'n/a' }}</strong></div>
        <div><span>说明</span><strong>{{ featureFamilyAblation.note || 'n/a' }}</strong></div>
      </div>
    </article>

    <article class="panel span-2" v-if="roadmapItems.length">
      <p class="panel-kicker">ROADMAP</p>
      <h3>项目标记 / Walk-forward 重训</h3>
      <div class="list-table">
        <div v-for="item in roadmapItems" :key="item.id" class="list-row multi">
          <div>
            <strong>{{ item.title }} / {{ item.status_label || item.status }}</strong>
            <p>{{ item.summary || 'n/a' }}</p>
            <p>当前状态：{{ item.current_state || 'n/a' }}</p>
            <p>下一步：{{ item.next_step || 'n/a' }}</p>
          </div>
          <span class="badge">{{ item.enabled ? 'enabled' : 'planned' }}</span>
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
      <div class="list-table compact-table" v-if="approvalChecks.length">
        <div v-for="item in approvalChecks" :key="`${item.group}-${item.name}`" class="list-row">
          <div>
            <strong>{{ item.group }} / {{ item.name }}</strong>
            <p>{{ item.actual }} {{ item.op }} {{ item.threshold }}</p>
          </div>
          <strong>{{ item.passed ? 'PASS' : 'FAIL' }}</strong>
        </div>
      </div>
      <div class="key-grid" v-if="probeBacktest">
        <div><span>Probe</span><strong>{{ probeBacktest.enabled ? 'enabled' : 'disabled' }}</strong></div>
        <div><span>Probe 池</span><strong>{{ probeBacktest.allowed_dynamic_pools || 'n/a' }}</strong></div>
        <div><span>Probe 收益</span><strong>{{ formatPct(probeMetrics.total_profit_pct) }}</strong></div>
        <div><span>Probe PF</span><strong>{{ formatValue(probeMetrics.profit_factor) }}</strong></div>
        <div><span>Probe 回撤</span><strong>{{ formatPct(probeMetrics.max_drawdown_pct) }}</strong></div>
        <div><span>Probe 交易</span><strong>{{ formatValue(probeMetrics.trade_count) }}</strong></div>
      </div>
    </article>

    <article class="panel span-2" v-if="liveTrading">
      <p class="panel-kicker">LIVE TRADING</p>
      <h3>云端实盘只读状态</h3>
      <div class="key-grid">
        <div><span>Bot</span><strong>{{ liveTrading.bot_status || 'n/a' }}</strong></div>
        <div><span>API</span><strong>{{ liveTrading.api_ok ? 'healthy' : 'unknown' }} / {{ liveTrading.api_http_code || 'n/a' }}</strong></div>
        <div><span>持仓数量</span><strong>{{ liveTrading.open_trade_count ?? 'n/a' }}</strong></div>
        <div><span>持仓浮盈</span><strong>{{ liveTrading.total_open_profit_abs ?? 'n/a' }}</strong></div>
        <div><span>同步模式</span><strong>{{ liveTrading.mode || 'n/a' }}</strong></div>
        <div><span>重启保护</span><strong>{{ liveTrading.restart_action || 'n/a' }}</strong></div>
        <div><span>同步时间</span><strong>{{ liveTrading.generated_at || 'n/a' }}</strong></div>
      </div>
      <div class="pair-list">
        <div>
          <span>当前已知持仓</span>
          <p>{{ liveTrading.open_trade_pairs?.map(shortPair).join(', ') || 'none' }}</p>
        </div>
        <div>
          <span>保护说明</span>
          <p>{{ liveTrading.restart_reason || 'n/a' }}</p>
        </div>
      </div>
      <div class="list-table compact-table" v-if="liveTrading.open_trades?.length">
        <div v-for="item in liveTrading.open_trades" :key="`${item.pair}-${item.open_date}`" class="list-row multi">
          <div>
            <strong>{{ shortPair(item.pair || '') }} / {{ item.direction || 'n/a' }} / {{ item.leverage ?? 'n/a' }}x</strong>
            <p>浮盈 {{ item.profit_abs ?? 'n/a' }} / {{ item.profit_pct ?? 'n/a' }}% | 开仓 {{ item.open_date || 'n/a' }}</p>
          </div>
        </div>
      </div>
    </article>

    <article class="panel span-3" v-if="backtestDetail">
      <p class="panel-kicker">BACKTEST DETAIL</p>
      <h3>回测走势与结果</h3>
      <p class="panel-copy">
        数据来自 Freqtrade 回测结果包 {{ backtestDetail.source_zip || 'n/a' }}。曲线和统计均基于 zip 内真实 trades / daily_profit / periodic_breakdown 聚合。
      </p>
      <div class="key-grid">
        <div><span>策略</span><strong>{{ backtestDetail.strategy_name || 'n/a' }}</strong></div>
        <div><span>起始资金</span><strong>{{ backtestDetail.starting_balance ?? 'n/a' }}</strong></div>
        <div><span>结束资金</span><strong>{{ backtestDetail.final_balance ?? 'n/a' }}</strong></div>
        <div><span>回撤</span><strong>{{ formatPct(backtestDetail.max_drawdown_pct) }}</strong></div>
        <div><span>Long 交易</span><strong>{{ backtestDetail.trade_count_long ?? 'n/a' }}</strong></div>
        <div><span>Short 交易</span><strong>{{ backtestDetail.trade_count_short ?? 'n/a' }}</strong></div>
      </div>
    </article>

    <article class="panel span-3" v-if="equityCurve.length">
      <p class="panel-kicker">EQUITY / DRAWDOWN</p>
      <h3>权益曲线与回撤曲线</h3>
      <div class="chart-grid">
        <div class="chart-card">
          <span>Equity Curve</span>
          <svg viewBox="0 0 760 180" class="line-chart" preserveAspectRatio="none">
            <polyline :points="linePoints(equityCurve, 'equity')" />
          </svg>
        </div>
        <div class="chart-card">
          <span>Drawdown Curve</span>
          <svg viewBox="0 0 760 180" class="line-chart danger" preserveAspectRatio="none">
            <polyline :points="linePoints(drawdownCurve, 'drawdown_abs_pct')" />
          </svg>
        </div>
      </div>
    </article>

    <article class="panel span-2" v-if="pairRanking.length">
      <p class="panel-kicker">PAIR RANKING</p>
      <h3>币种盈利排行</h3>
      <div class="bar-list">
        <div v-for="item in pairRanking" :key="item.pair" class="bar-row">
          <div class="bar-row-head">
            <strong>{{ shortPair(item.pair) }}</strong>
            <span>{{ item.profit_total_abs }} USDT / {{ item.winrate }}%</span>
          </div>
          <div class="bar-track">
            <i
              :class="{ negative: numericValue(item.profit_total_abs) < 0 }"
              :style="{ width: barWidth(item.profit_total_abs, pairRanking.map((row) => row.profit_total_abs)) }"
            ></i>
          </div>
        </div>
      </div>
    </article>

    <article class="panel" v-if="backtestDetail?.side_stats?.length">
      <p class="panel-kicker">LONG / SHORT</p>
      <h3>多空分开统计</h3>
      <div class="list-table">
        <div v-for="item in backtestDetail.side_stats" :key="item.side" class="list-row multi">
          <div>
            <strong>{{ item.side.toUpperCase() }} / {{ item.profit_abs }} USDT</strong>
            <p>交易 {{ item.trades }} | 胜率 {{ item.winrate }}% | 平均收益 {{ item.avg_profit_pct }}% | 平均杠杆 {{ item.avg_leverage }}</p>
          </div>
        </div>
      </div>
    </article>

    <article class="panel span-2" v-if="monthlyRows.length">
      <p class="panel-kicker">MONTHLY HEATMAP</p>
      <h3>月度收益热力图</h3>
      <div class="heat-grid">
        <div v-for="item in monthlyRows" :key="`${item.year}-${item.month}`" class="heat-cell" :class="heatTone(item.profit_pct)">
          <span>{{ item.year }} {{ monthName(item.month) }}</span>
          <strong>{{ formatSignedPct(item.profit_pct) }}</strong>
          <small>{{ item.trades }} trades</small>
        </div>
      </div>
    </article>

    <article class="panel span-3" v-if="pairTradeStats.length">
      <p class="panel-kicker">PAIR TRADE STATS</p>
      <h3>单币交易数与胜率</h3>
      <div class="list-table compact-table">
        <div v-for="item in pairTradeStats" :key="item.pair" class="list-row multi">
          <div>
            <strong>{{ shortPair(item.pair) }} / {{ item.profit_abs }} USDT</strong>
            <p>
              交易 {{ item.trades }} | 胜率 {{ item.winrate }}% | Long {{ item.long_trades }} |
              Short {{ item.short_trades }} | 平均收益 {{ item.avg_profit_pct }}%
            </p>
          </div>
        </div>
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
