<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { fetchDashboardStatus, type DashboardStatusPayload } from '../lib/dashboard-status'

const loading = ref(true)
const error = ref('')
const status = ref<DashboardStatusPayload | null>(null)

const botStateLabel = computed(() => {
  if (!status.value) return 'unknown'
  return status.value.bot.running ? 'running' : status.value.bot.status || 'stopped'
})

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
  </section>
</template>
