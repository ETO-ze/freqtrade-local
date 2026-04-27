<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { fetchAlertsData, type AlertsPayload } from '../lib/alerts-data'

const loading = ref(true)
const error = ref('')
const payload = ref<AlertsPayload | null>(null)

const summaryCards = computed(() => {
  if (!payload.value) return []
  return [
    { label: 'Critical', value: payload.value.counts.critical, tone: 'critical' },
    { label: 'Warning', value: payload.value.counts.warning, tone: 'warning' },
    { label: 'Info', value: payload.value.counts.info, tone: 'info' },
  ]
})

async function loadAlerts() {
  loading.value = true
  error.value = ''
  try {
    payload.value = await fetchAlertsData()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'unknown error'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadAlerts()
})
</script>

<template>
  <section class="page-grid">
    <article class="panel hero-panel span-2">
      <p class="panel-kicker">ALERT CENTER</p>
      <h3>运行告警与状态提示</h3>
      <p class="panel-copy">
        这里聚合后台 daemon 状态、promotion gate 结果和服务器同步校验结果，区分正常保护拦截与真正异常。
      </p>

      <div v-if="loading" class="info-banner">正在读取告警状态...</div>
      <div v-else-if="error" class="info-banner is-error">
        告警数据读取失败：{{ error }}
      </div>
      <div v-else-if="payload" class="key-grid status-grid-live">
        <div v-for="item in summaryCards" :key="item.label" :class="`metric-tone metric-tone-${item.tone}`">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </div>
    </article>

    <article class="panel span-2" v-if="payload">
      <p class="panel-kicker">EVENTS</p>
      <h3>最近事件</h3>
      <div class="list-table">
        <div
          v-for="item in payload.alerts"
          :key="`${item.source}-${item.title}-${item.occurred_at}`"
          class="list-row alert-row"
          :data-severity="item.severity"
        >
          <div>
            <strong>{{ item.title }}</strong>
            <p>{{ item.detail }}</p>
          </div>
          <div class="alert-meta">
            <span>{{ item.source }}</span>
            <strong>{{ item.occurred_at || 'n/a' }}</strong>
          </div>
        </div>
      </div>
    </article>
  </section>
</template>
