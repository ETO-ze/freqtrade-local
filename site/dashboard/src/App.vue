<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { useSystemStore } from './stores/system'

const route = useRoute()
const system = useSystemStore()

const pageTitle = computed(() => {
  return (route.meta.title as string | undefined) ?? '总览'
})

const navItems = [
  { to: '/', label: '总览' },
  { to: '/freqtrade', label: 'Freqtrade 状态' },
  { to: '/backtest', label: '回测结果' },
  { to: '/alerts', label: '告警中心' },
]
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand-block">
        <p class="brand-kicker">DUSKRAIN / DASHBOARD</p>
        <h1>Control Dashboard</h1>
        <p class="brand-copy">
          独立 Vue3 子应用。承接 OpenClaw、Freqtrade、回测结果和监控面板，只做只读聚合展示。
        </p>
      </div>

      <nav class="side-nav" aria-label="Primary">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-link"
          active-class="is-active"
        >
          {{ item.label }}
        </RouterLink>
      </nav>

      <section class="status-box">
        <p class="status-label">系统边界</p>
        <div class="status-grid">
          <div>
            <span>站点模式</span>
            <strong>{{ system.publicSiteMode }}</strong>
          </div>
          <div>
            <span>交易入口</span>
            <strong>{{ system.tradeAccess }}</strong>
          </div>
          <div>
            <span>数据链路</span>
            <strong>{{ system.apiMode }}</strong>
          </div>
        </div>
      </section>
    </aside>

    <div class="main-shell">
      <header class="topbar">
        <div>
          <p class="topbar-kicker">SUB APP / VUE3</p>
          <h2>{{ pageTitle }}</h2>
        </div>
        <div class="topbar-actions">
          <a href="https://duskrain.cn/" target="_blank" rel="noreferrer">返回首页</a>
          <a href="https://duskrain.cn/dashboard/" target="_blank" rel="noreferrer">当前看板</a>
          <a href="https://www.duskrain.cn/" target="_blank" rel="noreferrer">进入交易台</a>
        </div>
      </header>

      <main class="content-area">
        <RouterView />
      </main>
    </div>
  </div>
</template>
