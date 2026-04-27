<script setup lang="ts">
import { useSystemStore } from '../stores/system'

const system = useSystemStore()

const cards = [
  {
    title: '站点结构',
    value: '静态首页 + Vue3 Dashboard',
    note: '首页负责公开展示，Dashboard 负责只读运行信息。',
  },
  {
    title: '看板路径',
    value: '/dashboard',
    note: '当前已通过 duskrain.cn 子路径正式上线。',
  },
  {
    title: '数据来源',
    value: '公开只读 JSON',
    note: '数据来自本地报告发布与服务器状态聚合，不直连交易敏感接口。',
  },
]
</script>

<template>
  <section class="page-grid">
    <article class="panel hero-panel">
      <p class="panel-kicker">LIVE OVERVIEW</p>
      <h3>当前看板定位</h3>
      <p class="panel-copy">
        当前 Dashboard 已接入服务器状态、最近同步、回测结果和运行告警。该页面展示的是当前系统信息，不提供交易控制。
      </p>
    </article>

    <article
      v-for="card in cards"
      :key="card.title"
      class="panel metric-panel"
    >
      <p class="metric-label">{{ card.title }}</p>
      <strong class="metric-value">{{ card.value }}</strong>
      <p class="metric-note">{{ card.note }}</p>
    </article>

    <article class="panel span-2">
      <p class="panel-kicker">SERVICE MAP</p>
      <h3>当前服务边界</h3>
      <div class="service-list">
        <div
          v-for="service in system.services"
          :key="service.name"
          class="service-item"
        >
          <div>
            <strong>{{ service.name }}</strong>
            <p>{{ service.note }}</p>
          </div>
          <span class="badge">{{ service.status }}</span>
        </div>
      </div>
    </article>
  </section>
</template>
